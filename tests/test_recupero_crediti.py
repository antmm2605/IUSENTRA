"""Recupero crediti in serie: importazione CSV, conteggi (D.Lgs. 231/2002), percorso con i termini
(artt. 641, 644, 480, 481 c.p.c.), fascicoli e bozze in blocco dal compilatore."""

from __future__ import annotations

import io
from datetime import date

import pytest

from pct.recupero_crediti.archivio import ArchivioRecupero
from pct.recupero_crediti.conteggi import conteggio
from pct.recupero_crediti.importazione import leggi_csv
from pct.recupero_crediti.modello import DocumentoCredito, Posizione
from pct.recupero_crediti.stati import ammesso, termini_da_evento

CSV = (
    "Debitore;Partita IVA;Numero fattura;Data fattura;Scadenza;Importo;PEC\n"
    "Beta srl;01234567890;12;15/01/2026;14/02/2026;1.200,00;beta@pec.it\n"
    "Beta srl;01234567890;18;10/02/2026;12/03/2026;800,00;beta@pec.it\n"
    "Gamma snc;09876543210;3;01/03/2026;;500;\n"
    ";;4;01/03/2026;;500;\n"
    "Delta;;5;data sbagliata;;100;\n"
).encode("utf-8")


def test_importazione_raggruppa_per_debitore_e_segnala_le_righe():
    posizioni, errori = leggi_csv(CSV, creditore_id="C1", creditore="Alfa spa", lotto="Lotto 1")
    assert [p.debitore for p in posizioni] == ["Beta srl", "Gamma snc"]
    assert posizioni[0].capitale == 2000.0 and len(posizioni[0].documenti) == 2
    assert posizioni[0].debitore_pec == "beta@pec.it" and posizioni[0].commerciale
    assert errori == ["Riga 5: servono debitore, importo positivo e data valida.",
                      "Riga 6: servono debitore, importo positivo e data valida."]
    _, mancanti = leggi_csv(b"Nome;Totale\nx;1\n", creditore_id="C1", creditore="Alfa", lotto="L")
    assert "Mancano le colonne" in mancanti[0]


def test_conteggio_con_indennizzo_e_acconti():
    posizione = Posizione(debitore="Beta", commerciale=True, acconti=200.0, documenti=[
        DocumentoCredito(numero="12", data="2026-01-15", scadenza="2026-02-14", importo=1200.0),
        DocumentoCredito(numero="18", data="2026-02-10", scadenza="", importo=800.0)])
    chiamate = []

    def interessi(payload):
        chiamate.append(payload)
        return {"total_interest": 10.0}

    esito = conteggio(posizione, date(2026, 6, 30), interessi)
    assert esito["capitale"] == 1800.0  # l'acconto riduce il documento più vecchio
    assert esito["indennizzo_forfettario"] == 80.0 and esito["totale"] == 1900.0
    decorrenze = sorted(c["int_data_inizio"] for c in chiamate)
    assert {c["int_tipo"] for c in chiamate} == {"moratori"}
    assert decorrenze == ["2026-02-15", "2026-03-13"]  # dopo la scadenza; 30 giorni dalla fattura senza scadenza (art. 4 c. 2)
    civile = conteggio(Posizione(commerciale=False, documenti=[DocumentoCredito(data="2026-01-01", scadenza="2026-01-31", importo=100)]),
                       date(2026, 6, 30), lambda p: {"total_interest": 1.0})
    assert civile["indennizzo_forfettario"] == 0 and civile["tipo_interessi"].startswith("legali")


def test_percorso_e_termini_di_legge():
    assert ammesso("da_diffidare", "diffidato") and not ammesso("da_diffidare", "precetto_notificato")
    assert not ammesso("chiusa_pagata", "diffidato")
    notifica = {t["codice"]: t["data"] for t in termini_da_evento("decreto_notificato", date(2026, 3, 2))}
    assert notifica["CIV_OPPOSIZIONE_DI"] == "2026-04-13"  # 40 giorni: cade sabato 11/04, slitta a lunedì (art. 155 c.p.c.)
    precetto = {t["codice"]: t["data"] for t in termini_da_evento("precetto_notificato", date(2026, 3, 2))}
    assert set(precetto) == {"ESE_PRECETTO_ADEMPIMENTO_10GG", "ESE_PRECETTO_EFFICACIA_90GG"}


@pytest.fixture()
def studio(tmp_path):
    from pct.clienti import TipoCliente
    from tests.test_revisione_2410_sicurezza import _app
    from web.helpers import get_clienti

    app = _app(tmp_path)
    with app.test_request_context("/"):
        creditore = get_clienti().nuovo(TipoCliente.PERSONA_GIURIDICA, ragione_sociale="Alfa spa")
    return app, creditore.id


def test_flusso_completo_dalle_rotte(studio):
    from tests.test_topbar_operational_api import _login
    from web.helpers import get_fascicoli, get_scadenziario

    app, cid = studio
    intestazioni = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    with app.test_client() as client:
        _login(client)
        importa = client.post("/recupero-crediti/importa", headers=intestazioni, content_type="multipart/form-data",
                              data={"creditore_id": cid, "lotto": "Lotto 1", "file": (io.BytesIO(CSV), "debitori.csv")}).get_json()
        assert importa["ok"] and importa["importate"] == 2 and len(importa["errori"]) == 2
        ancora = client.post("/recupero-crediti/importa", headers=intestazioni, content_type="multipart/form-data",
                             data={"creditore_id": cid, "file": (io.BytesIO(CSV), "debitori.csv")}).get_json()
        assert ancora["importate"] == 0 and ancora["gia_presenti"] == 2
        dati = client.get("/api/v1/ui/recupero-crediti", headers=intestazioni).get_json()
        ids = [p["id"] for p in dati["posizioni"]]
        assert dati["riepilogo"]["capitale"] == 2500.0
        senza_fascicolo = client.post("/recupero-crediti/atti", json={"ids": ids, "tipo": "diffida"}, headers=intestazioni).get_json()
        assert senza_fascicolo["create"] == 0 and len(senza_fascicolo["saltate"]) == 2
        assert client.post("/recupero-crediti/fascicoli", json={"ids": ids}, headers=intestazioni).get_json()["aperti"] == 2
        assert client.post("/recupero-crediti/fascicoli", json={"ids": ids}, headers=intestazioni).get_json()["aperti"] == 0
        diffide = client.post("/recupero-crediti/atti", json={"ids": ids, "tipo": "diffida"}, headers=intestazioni).get_json()
        assert diffide["ok"] and diffide["create"] == 2, diffide
        rifiuto = client.post("/recupero-crediti/avanza", json={"ids": ids, "stato": "precetto_notificato", "data": "2026-03-02"},
                              headers=intestazioni).get_json()
        assert rifiuto["aggiornate"] == 0 and len(rifiuto["rifiutate"]) == 2
        for stato in ("ricorso_da_depositare", "ricorso_depositato", "decreto_emesso", "decreto_notificato"):
            esito = client.post("/recupero-crediti/avanza", json={"ids": ids[:1], "stato": stato, "data": "2026-03-02"},
                                headers=intestazioni).get_json()
            assert esito["aggiornate"] == 1, esito
        futura = client.post("/recupero-crediti/avanza", json={"ids": ids[:1], "stato": "esecutivo", "data": "2099-01-01"}, headers=intestazioni)
        assert futura.status_code == 400
        conto = client.get(f"/api/v1/ui/recupero-crediti/{ids[0]}/conteggio", headers=intestazioni).get_json()
        assert conto["ok"] and conto["capitale"] > 0
    with app.test_request_context("/"):
        posizione = ArchivioRecupero.accanto_a(app.extensions.get("config_studio_path", "") or _config_path(app)).get(ids[0])
        fascicolo = get_fascicoli().get(posizione.fascicolo_id)
        assert fascicolo is not None and fascicolo.id_cliente == cid
        assert len([d for d in fascicolo.documenti]) >= 1
        titoli = [s.titolo for s in get_scadenziario().tutte(solo_aperte=False) if s.id_fascicolo == posizione.fascicolo_id]
    assert any("644" in t for t in titoli) and any("641" in t for t in titoli)


def _config_path(app):
    from web.blueprints.impostazioni import _get_gestore

    return _get_gestore().percorso
