"""«Letture e verifiche» di un fascicolo di lavoro già notificato e deciso (dati sintetici, nessun dato reale).

A) Notifiche richieste dagli atti: una voce per atto anche con più copie, prova dell'atto, fase superata.
B) Parti lette dagli atti: enti senza codice fiscale di persona fisica, domanda dell'atto non è epigrafe,
   varianti dello stesso ente fuse.
C) Fasi, termini e norme del rito del lavoro: ogni norma ha la fonte ufficiale registrata.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from pct.archivio_letture.copie_atti import riunisci_obblighi
from pct.obblighi_notifica import (
    STATO_DA_NOTIFICARE,
    STATO_DA_VERIFICARE,
    STATO_FACOLTATIVO,
    STATO_NOTIFICATO,
    DocumentoCatalogato,
    Parte,
    obblighi_del_fascicolo,
)
from pct.obblighi_notifica_atto import fase_superata, una_voce_per_atto
from pct.registro_letture.fatti_repository import Fatto

OGGI = date(2026, 11, 2)
RICORSO = "Ricorso in materia di lavoro (art. 414 c.p.c.)"
MINISTERO = Parte("Ministero della Prova", "controparte", difensore="Avvocatura Distrettuale dello Stato di Alfa")


def _voci(documenti, contesto, parti=(MINISTERO,)):
    """Come `obblighi_fascicolo`: un calcolo per documento, poi le copie riunite e la fase."""
    voci = []
    for documento in documenti:
        voci.extend(o.to_dict() for o in obblighi_del_fascicolo([documento], list(parti), contesto=contesto, oggi=OGGI))
    return una_voce_per_atto(riunisci_obblighi(voci, {}), contesto)


def _due_copie():
    return [DocumentoCatalogato("ric", "ricorso.pdf", RICORSO, nostro=True),
            DocumentoCatalogato("ric_not", "ricorso_originale_notificato.pdf", RICORSO, nostro=True)]


# ── A) Notifiche richieste dagli atti ─────────────────────────────────────


def test_stesso_ricorso_in_due_copie_una_sola_voce():
    voci = _voci(_due_copie(), {"notifica_estero": False})
    lavoro = [v for v in voci if v["regola"] == "lavoro_415"]
    assert len(lavoro) == 1
    assert {f["documentoId"] for f in lavoro[0]["fonti_documentali"]} == {"ric", "ric_not"}


def test_due_atti_della_stessa_natura_con_date_diverse_restano_due_voci():
    decreti = [DocumentoCatalogato("d1", "di1.pdf", "Decreto ingiuntivo", data="2026-10-01", nostro=True),
               DocumentoCatalogato("d2", "di2.pdf", "Decreto ingiuntivo", data="2026-10-20", nostro=True)]
    assert len(_voci(decreti, {"notifica_estero": False, "sospensione_feriale": False}, [Parte("Alfa S.r.l.", "controparte")])) == 2


def test_relata_nella_copia_notificata_non_lascia_la_voce_da_notificare():
    prova = {"documento_id": "ric_not", "atto_documento_id": "ric_not", "relata": True, "consegna": False, "verificata": False}
    voci = _voci(_due_copie(), {"notifica_estero": False, "prove_notifica": [prova],
                                "nomi_documenti": {"ric_not": "ricorso_originale_notificato.pdf"}})
    (voce,) = voci
    assert voce["stato"] == STATO_DA_VERIFICARE
    assert "ricorso_originale_notificato.pdf" in voce["motivo"]
    assert voce["prove_documenti"] == ["ric_not"]


def test_prova_verificata_in_una_copia_chiude_la_voce():
    prova = {"documento_id": "ric_not", "atto_documento_id": "ric_not", "relata": True, "consegna": True,
             "verificata": True, "destinatari_completi": True}
    (voce,) = _voci(_due_copie(), {"notifica_estero": False, "prove_notifica": [prova]})
    assert voce["stato"] == STATO_NOTIFICATO


def test_sentenza_e_ricevute_nel_fascicolo_notifica_eseguita_e_sentenza_facoltativa():
    documenti = [*_due_copie(), DocumentoCatalogato("sent", "sentenza.pdf", "Sentenza", data="2026-09-30")]
    contesto = {
        "notifica_estero": False, "sentenze": ["sent"], "documenti_atti": ["ric", "ric_not", "sent"],
        "udienze_tenute": ["2026-06-10"],
        "nomi_documenti": {"rac": "accettazione.eml", "rdac": "consegna.eml"},
        "prove_notifica": [  # ricevute PEC in file separati, non collegate a un altro atto
            {"documento_id": "rac", "atto_documento_id": "", "relata": False, "consegna": False, "verificata": False},
            {"documento_id": "rdac", "atto_documento_id": "", "relata": False, "consegna": True, "verificata": False},
        ],
    }
    voci = {v["regola"]: v for v in _voci(documenti, contesto)}
    assert set(voci) == {"lavoro_415", "sentenza_notifica_breve"}
    ricorso = voci["lavoro_415"]
    assert ricorso["stato"] == STATO_NOTIFICATO
    assert ricorso["dati_mancanti"] == [] and ricorso["scadenza"] == ""
    assert "consegna.eml" in ricorso["motivo"] and "sentenza" in ricorso["motivo"]
    assert voci["sentenza_notifica_breve"]["stato"] == STATO_FACOLTATIVO
    assert {"art. 285 c.p.c.", "art. 325 c.p.c.", "art. 326 c.p.c."} <= set(voci["sentenza_notifica_breve"]["fonti"])


def test_fase_superata_senza_prove_la_notifica_del_ricorso_non_si_propone():
    documenti = [*_due_copie(), DocumentoCatalogato("sent", "sentenza.pdf", "Sentenza", data="2026-09-30")]
    voci = _voci(documenti, {"notifica_estero": False, "sentenze": ["sent"], "documenti_atti": ["ric", "ric_not", "sent"]})
    assert [v["regola"] for v in voci] == ["sentenza_notifica_breve"]


def test_la_prova_della_sentenza_notificata_non_prova_il_ricorso():
    documenti = [*_due_copie(), DocumentoCatalogato("sent", "sentenza_notificata.pdf", "Sentenza", data="2026-09-30")]
    prova_sentenza = {"documento_id": "sent", "atto_documento_id": "sent", "relata": True, "consegna": True, "verificata": True}
    voci = _voci(documenti, {"notifica_estero": False, "sentenze": ["sent"], "documenti_atti": ["ric", "ric_not", "sent"],
                             "prove_notifica": [prova_sentenza]})
    assert "lavoro_415" not in {v["regola"] for v in voci}


def test_motivi_della_fase_superata():
    assert "sentenza" in fase_superata({"sentenze": ["s"]})
    assert "10/06/2026" in fase_superata({"udienze_tenute": ["2026-03-01", "2026-06-10"]})
    assert "definito" in fase_superata({"fascicolo_definito": True})
    assert fase_superata({"udienze_future": ["2027-01-10"]}) == ""


def test_fase_non_superata_il_ricorso_resta_da_notificare():
    (voce,) = _voci(_due_copie(), {"notifica_estero": False, "udienze_future": ["2027-01-10"]})
    assert voce["stato"] == STATO_DA_NOTIFICARE


def test_raccolta_legge_sentenza_udienze_tenute_e_fascicolo_definito():
    from web.services.obblighi_notifica_runtime import raccogli

    fascicolo = SimpleNamespace(id="F1", controparte="", avvocato_controparte="", stato=SimpleNamespace(value="DEFINITO"),
                                documenti=[SimpleNamespace(id="ric", nome="ricorso.pdf"), SimpleNamespace(id="sent", nome="sentenza.pdf")])
    fatti = [Fatto(categoria="data", campo="udienza", valore="2026-06-10", valore_letto="2026-06-10", oggetto_id="ric", verifica="verificata")]
    _, _, contesto = raccogli(fascicolo, fatti, {"ric": RICORSO, "sent": "Sentenza"})
    assert contesto["sentenze"] == ["sent"]
    assert contesto["udienze_tenute"] == ["2026-06-10"]
    assert contesto["fascicolo_definito"] is True
    assert set(contesto["documenti_atti"]) == {"ric", "sent"}


# ── B) Parti lette dagli atti ─────────────────────────────────────────────


def _cf_persona() -> str:
    from pct.codice_fiscale import calcola

    return calcola(cognome="Neri", nome="Sandra", sesso="F", data_nascita="1978-02-23", luogo_nascita="Milano")["codice_fiscale"]


def test_ente_non_prende_il_codice_fiscale_di_una_persona_fisica():
    from pct.archivio_letture.estrazione_parti import estrai_parti

    testo = (f"TRIBUNALE DI ALFA\nPER\nGiulia Verdi, ricorrente\nCONTRO\n"
             f"Ufficio Scolastico Regionale per la Prova – Ambito Territoriale di Alfa, in persona del dirigente pro tempore, "
             f"c.f. 96007280793; la ricorrente Sandra Neri c.f. {_cf_persona()}\n\nPREMESSO CHE\nla ricorrente lavora.")
    ente = next(p for p in estrai_parti(testo) if p.nome.startswith("Ufficio Scolastico"))
    assert ente.codice_fiscale == "96007280793"


def test_ente_senza_codice_numerico_non_eredita_il_codice_vicino():
    from pct.archivio_letture.estrazione_parti import estrai_parti

    testo = (f"TRIBUNALE DI ALFA\nPER\nGiulia Verdi, ricorrente\nCONTRO\n"
             f"Ufficio Scolastico Regionale per la Prova – Ambito Territoriale di Alfa, c.f. {_cf_persona()}\n")
    ente = next(p for p in estrai_parti(testo) if p.nome.startswith("Ufficio Scolastico"))
    assert ente.codice_fiscale == ""


def test_la_domanda_dell_atto_non_rende_il_ministero_parte_ricorrente():
    from pct.archivio_letture.estrazione_parti import estrai_parti

    testo = ("TRIBUNALE DI ALFA\nPER\nGiulia Verdi, ricorrente\nCONTRO\n"
             "MINISTERO DELLA PROVA, c.f. 80000000001, in persona del Ministro pro tempore,\n"
             "nonché per sentirsi condannare il Ministero alla rifusione in favore della ricorrente delle spese\n"
             "PREMESSO CHE\nla ricorrente lavora.")
    parti = estrai_parti(testo)
    assert [p.nome for p in parti if p.nome.casefold().startswith("ministero")] == ["MINISTERO DELLA PROVA"]
    assert all(p.posizione != "ricorrente" for p in parti if p.nome.casefold().startswith("ministero"))


def _fatto_parte(nome: str, ruolo: str, codice: str = "", oggetto: str = "d1", **extra) -> Fatto:
    prove = [{"codice": "codice_fiscale", "esito": "ok", "dettaglio": f"{codice} (carattere di controllo valido)"}] if codice else []
    return Fatto(categoria="parte", campo=ruolo, valore=nome, valore_letto=codice or nome, oggetto_id=oggetto,
                 prove=prove, verifica=extra.get("verifica", "plausibile"))


def test_letture_archiviate_corrette_nell_aggregazione():
    from pct.archivio_letture.parti_fascicolo import parti_lette

    fatti = [
        _fatto_parte("Ministero", "parte"),  # dalla domanda dell'atto
        _fatto_parte("Ufficio Scolastico Regionale per la Prova – Ambito Territoriale", "parte", _cf_persona()),
        _fatto_parte("MINISTERO DELLA PROVA", "controparte", "80000000001", verifica="verificata"),
        _fatto_parte("Ministero della Prova", "controparte", oggetto="d2"),
        _fatto_parte("Ministero della  prova", "parte", oggetto="d3"),
        _fatto_parte("Ministero per la Prova e il Merito", "controparte", "80000000001", oggetto="d4"),
    ]
    voci = parti_lette(fatti)
    nomi = [(v.nome, v.ruolo, v.codice_fiscale) for v in voci]
    assert not any(v.nome == "Ministero" for v in voci)
    ministeri = [v for v in voci if v.nome.casefold().startswith("ministero")]
    assert len(ministeri) == 1, nomi
    assert ministeri[0].ruolo == "controparte" and ministeri[0].codice_fiscale == "80000000001"
    assert set(ministeri[0].oggetti) == {"d1", "d2", "d4"}
    usr = next(v for v in voci if v.nome.startswith("Ufficio Scolastico"))
    assert usr.codice_fiscale == ""


# ── C) Fasi, termini e norme del rito del lavoro ──────────────────────────


def test_ogni_norma_del_rito_del_lavoro_ha_fonte_ufficiale_registrata():
    from pct.procedura_fasi import schede_per_fascicolo
    from pct.procedura_fasi.fonti import FONTI

    schede = schede_per_fascicolo(tipo="LAVORO", tipo_procedimento="Ricorso ex art. 414 c.p.c.")
    rito = schede["rito"]
    citate = [i for fase in rito["fasi"] for a in fase["adempimenti"] for i in a["fonti"]]
    for scheda in (rito, schede["deposito"], *schede["notifiche"]):
        for fase in scheda.get("fasi", []):
            for identificativo in [*fase.get("fonti", []), *(i for a in fase.get("adempimenti", []) for i in a["fonti"])]:
                voce = FONTI.get(identificativo)
                assert voce, identificativo
                assert voce["url"].startswith("https://") and "2026" in voce["verifica"] and len(voce["estratto"]) > 60, identificativo
    assert {"cpc_414", "cpc_415", "cpc_416", "cpc_417bis", "cpc_420", "cpc_429", "cpc_430", "cpc_433", "cpc_434",
            "cpc_435", "cpc_327", "l53_art3bis", "rd1611_art11"} <= set(citate)
    assert {f["id"] for f in rito["fonti"]} >= set(citate)
    fasi = [f["codice"] for f in rito["fasi"]]
    assert fasi == ["introduttiva", "discussione", "decisoria", "appello"]


def test_appello_del_lavoro_si_propone_con_il_deposito_art_434():
    from pct.procedura_fasi.riti import SCHEDE_RITO

    termini = next(a for f in SCHEDE_RITO["lavoro"]["fasi"] for a in f["adempimenti"] if a["azione"] == "Termini per impugnare")
    assert termini["fonti"] == ["cpc_434", "cpc_327"]
    assert "deposito del ricorso" in termini["termine"] and "quaranta" in termini["termine"]


def test_le_norme_delle_notifiche_del_lavoro_corrispondono_al_registro():
    from pct.obblighi_notifica import REGOLE
    from pct.procedura_fasi.fonti import FONTI

    lavoro = next(r for r in REGOLE if r.id == "lavoro_415")
    assert lavoro.fonti == ("art. 415, commi 4, 5 e 7, c.p.c.", "art. 417-bis c.p.c.")
    assert "propri dipendenti" in lavoro.avvertenze and "propri dipendenti" in FONTI["cpc_417bis"]["estratto"]
    assert "Avvocatura dello Stato" in FONTI["rd1611_art11"]["estratto"]
