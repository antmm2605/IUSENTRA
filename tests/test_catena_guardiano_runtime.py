"""Il guardiano della catena in esercizio su uno studio temporaneo: riparazioni vere, registro, API, idempotenza."""

from __future__ import annotations

from datetime import date

import pytest

from pct.fascicoli import TipoFascicolo
from tests.test_archivio_letture_runtime import _app

OGGI = date(2026, 11, 19)
DECRETO = {"documento_id": "DEC", "documento": "Decreto di fissazione udienza.pdf", "brano": "FISSA", "data": "09/10/2026"}


def _conclusione(codice, cosa, scadenza, onerato="noi"):
    return {"codice": codice, "cosa": cosa, "stato": "da_fare", "onerato_codice": onerato, "letto": DECRETO,
            "norme": [{"norma": "art. 415, commi 4–6, c.p.c."}],
            "termine": {"scadenza_iso": scadenza, "natura": "ordinatorio", "scaduto": False}, "dubbi": []}


LETTURA = {"ragionamento": {
    "impronta": "impronta-modello",
    "fase": {"codice": "udienza_fissata"},
    "conclusioni": [
        _conclusione("notifica_ricorso_decreto_415", "Notificare alla controparte il ricorso con il decreto", "2027-01-08"),
        _conclusione("costituzione_convenuto", "Costituzione del convenuto", "2027-01-29", onerato="controparte"),
    ],
    "udienze": [{"data": "09/02/2027", "ora": "", "modalita": "sostituita da note scritte (art. 127-ter c.p.c.)",
                 "documento": "Decreto di fissazione udienza.pdf", "documento_id": "DEC"}],
}, "prossimi_passi": [{"azione": "Notificare alla controparte il ricorso con il decreto"}]}


@pytest.fixture()
def studio(tmp_path):
    app = _app(tmp_path)
    app.config["STUDIO_AVVOCATO"] = "Mario Rossi"
    with app.app_context():
        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().nuovo(
            "Gialli / Ministero", TipoFascicolo.CIVILE, nome_cliente="Anna Gialli", tribunale="Tribunale di Vicenza",
            numero_rg="1571", anno_rg=2026, controparte="Ministero dell'Istruzione e del Merito")
    return app, fascicolo.id


def test_ripara_scadenziario_e_agenda_e_registra_il_motivo(studio):
    from pct.scadenziario import StatoTermine, TipoTermine

    app, fid = studio
    with app.test_request_context("/"):
        from web.helpers import get_agenda, get_scadenziario
        from web.services.catena_guardiano_runtime import controlla_fascicolo, payload_fascicolo

        scadenziario = get_scadenziario()
        proposta = scadenziario.nuova("Costituzione del convenuto con memoria difensiva", TipoTermine.ADEMPIMENTO,
                                      "2027-01-29", id_fascicolo=fid, note="PEC_TERMINE_PROPOSTO:x:LAV_416_COSTITUZIONE")
        scadenziario.aggiorna(proposta.id, stato=StatoTermine.BOZZA)
        esito = controlla_fascicolo(fid, origine="collaudo", lettura=LETTURA, oggi=OGGI)
        codici = sorted(v["codice"] for v in esito["incoerenze"])
        assert codici == ["termine_certo_senza_scadenza", "termine_della_controparte", "udienza_non_in_agenda"], esito
        assert all(v["esito_riparazione"].startswith("riparata") for v in esito["incoerenze"]), esito

        righe = {s.titolo: s for s in get_scadenziario().tutte(id_fascicolo=fid, solo_aperte=False)}
        assert "Notificare alla controparte il ricorso con il decreto" in righe, (list(righe), esito)
        nuova = righe["Notificare alla controparte il ricorso con il decreto"]
        assert str(nuova.data_scadenza)[:10] == "2027-01-08" and nuova.stato == StatoTermine.APERTO
        assert "RAGIONAMENTO:notifica_ricorso_decreto_415" in nuova.note and "art. 415" in nuova.note
        assert righe["Costituzione del convenuto con memoria difensiva"].stato == StatoTermine.ANNULLATO
        (udienza,) = [a for a in get_agenda().tutti() if a.id_fascicolo == fid]
        assert udienza.data_ora.startswith("2027-02-09") and udienza.hearing_mode == "note_scritte"
        assert "Ora da confermare" in udienza.note

        # Secondo giro: nulla da riparare, le incoerenze riparate si chiudono; nessun doppione.
        secondo = controlla_fascicolo(fid, origine="collaudo", lettura=LETTURA, oggi=OGGI)
        assert secondo["incoerenze"] == []
        assert len([s for s in get_scadenziario().tutte(id_fascicolo=fid) if "RAGIONAMENTO:" in (s.note or "")]) == 1
        assert len([a for a in get_agenda().tutti() if a.id_fascicolo == fid]) == 1
        payload = payload_fascicolo(fid)
        assert payload["avvisi"] == [] and len(payload["giri"]) == 2


def test_la_scadenza_dell_avvocato_non_si_tocca_e_diventa_un_avviso(studio):
    from pct.scadenziario import StatoTermine, TipoTermine

    app, fid = studio
    with app.test_request_context("/"):
        from web.helpers import get_scadenziario
        from web.services.catena_guardiano_runtime import controlla_fascicolo, payload_fascicolo

        scadenziario = get_scadenziario()
        mia = scadenziario.nuova("Costituzione del convenuto", TipoTermine.ADEMPIMENTO, "2027-01-29", id_fascicolo=fid,
                                 note="la tengo io", id_utente_responsabile="avv1")
        lettura = {**LETTURA, "ragionamento": {**LETTURA["ragionamento"], "udienze": [],
                                               "conclusioni": LETTURA["ragionamento"]["conclusioni"][1:]}, "prossimi_passi": []}
        esito = controlla_fascicolo(fid, origine="collaudo", lettura=lettura, oggi=OGGI)
        assert [(v["codice"], v["riparazione"]) for v in esito["incoerenze"]] == [("termine_della_controparte", "")]
        riletta = get_scadenziario().get(mia.id)
        assert riletta.stato == StatoTermine.APERTO and riletta.note == "la tengo io"
        (avviso,) = payload_fascicolo(fid)["avvisi"]
        assert "termine della controparte" in avviso["descrizione"] and "resta com'è" in avviso["perche"]


def test_api_del_guardiano(studio):
    app, fid = studio
    client = app.test_client()
    risposta = client.get(f"/api/v1/ui/fascicoli/{fid}/guardiano-catena", headers={"X-API-Key": "react-test-key"})
    assert risposta.status_code == 200 and risposta.get_json()["stato"] == "mai_controllato"
    assert client.get("/api/v1/ui/fascicoli/NONCE/guardiano-catena", headers={"X-API-Key": "react-test-key"}).status_code == 404
    studio_intero = client.get("/api/v1/ui/guardiano-catena", headers={"X-API-Key": "react-test-key"}).get_json()
    assert studio_intero["ok"] and any(r["codice"] == "allineamento_scadenziario" for r in studio_intero["mappa"])
    assert client.get(f"/api/v1/ui/fascicoli/{fid}/guardiano-catena").status_code == 401


def test_proposta_certa_confermata_e_doppione_scartato(studio):
    """Due proposte dello stesso termine (PEC e obbligo di notifica): una diventa la scadenza, l'altra si scarta."""
    from pct.scadenziario import StatoTermine, TipoTermine

    app, fid = studio
    with app.test_request_context("/"):
        from web.helpers import get_scadenziario
        from web.services.catena_guardiano_runtime import controlla_fascicolo

        ids = []
        for nota in ("PEC_TERMINE_PROPOSTO:x:LAV_415_NOTIFICA_TRENTA_GIORNI", "Obbligo di notifica letto dal documento"):
            proposta = get_scadenziario().nuova("Notificare ricorso e decreto di fissazione dell'udienza", TipoTermine.NOTIFICA,
                                                "2027-01-08", id_fascicolo=fid, note=nota)
            get_scadenziario().aggiorna(proposta.id, stato=StatoTermine.BOZZA)
            ids.append(proposta.id)
        lettura = {**LETTURA, "ragionamento": {**LETTURA["ragionamento"], "udienze": [],
                                               "conclusioni": LETTURA["ragionamento"]["conclusioni"][:1]}}
        esito = controlla_fascicolo(fid, origine="collaudo", lettura=lettura, oggi=OGGI)
        assert [(v["codice"], v["esito_riparazione"][:8]) for v in esito["incoerenze"]] == [("termine_certo_in_bozza", "riparata")]
        stati = sorted(str(get_scadenziario().get(i).stato.value) for i in ids)
        assert stati == ["ANNULLATO", "APERTO"], stati
        assert controlla_fascicolo(fid, origine="collaudo", lettura=lettura, oggi=OGGI)["incoerenze"] == []
