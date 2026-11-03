"""Lo script del collaudo dei motori (deploy/hetzner/collaudo_motori.py) su dati finti.

Verifica che l'inventario esca con soli conteggi, che le fasi di scrittura tocchino solo un fascicolo di prova
senza cliente, che l'aggiunta di un documento faccia leggere solo quel documento e che la pulizia lasci il
fascicolo di prova senza documenti di collaudo.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from pct.fascicoli import TipoDocumento, TipoFascicolo
from tests.test_archivio_letture_runtime import DECRETO, _app

RADICE = Path(__file__).resolve().parent.parent


def _script():
    spec = importlib.util.spec_from_file_location("collaudo_motori", RADICE / "deploy" / "hetzner" / "collaudo_motori.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _seed(app, *, titolo: str, cliente: str = "") -> str:
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo(titolo, TipoFascicolo.ALTRO, nome_cliente=cliente)
        fascicoli.aggiungi_documento(fascicolo.id, nome_file="decreto.pdf", tipo=TipoDocumento.ALTRO, contenuto=DECRETO)
        return fascicolo.id


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
    app = _app(tmp_path)
    reale = _seed(app, titolo="Bianchi / Delta S.r.l.", cliente="Anna Bianchi")
    prova = _seed(app, titolo="COLLAUDO MOTORI – non cliente")
    monkeypatch.setenv("FASCICOLO", prova)
    monkeypatch.setenv("ATTESA_S", "0")
    return app, reale, prova


def test_inventario_solo_conteggi_e_fascicolo_di_prova_riconosciuto(ambiente):
    app, _reale, prova = ambiente
    with app.app_context():
        esito = _script().esegui(app, ["INVENTARIO"])
    testo = json.dumps(esito, ensure_ascii=False, default=str)
    assert "Bianchi" not in testo and "Delta" not in testo and "decreto" not in testo
    inventario = esito["INVENTARIO"]
    studio = inventario["studi"][0]
    assert studio["studio"] == "studio_1"
    assert studio["fascicoli"] == 2
    assert studio["inventario"]["documento"]["vivi"] == 2
    assert studio["lettori"]["motore_documenti"]["oggetti"] == 2
    assert set(studio["lettori"]) >= {"ocr", "motore_pec", "presidio_economico", "scadenze_pdf"}
    assert inventario["fascicolo_di_collaudo"]["trovato"] and inventario["fascicolo_di_collaudo"]["id"] == prova


def test_fasi_di_scrittura_rifiutano_un_fascicolo_con_cliente(ambiente, monkeypatch):
    app, reale, _prova = ambiente
    monkeypatch.setenv("FASCICOLO", reale)
    with app.app_context():
        modulo = _script()
        monkeypatch.setattr(modulo, "ETICHETTA_PROVA", "titolo-che-non-esiste")
        esito = modulo.esegui(app, ["INCREMENTALE"])
        documenti = app.extensions["core_runtime"]["get_fascicoli"]().get(reale).documenti
    assert "errore" in esito["INCREMENTALE"]
    assert len(documenti) == 1


def test_incrementale_rilegge_solo_il_documento_di_prova_e_la_pulizia_lo_toglie(ambiente):
    app, _reale, prova = ambiente
    with app.app_context():
        modulo = _script()
        modulo.esegui(app, ["INCREMENTALE"])  # primo giro: legge anche il documento già presente
        esito = modulo.esegui(app, ["INCREMENTALE", "PULIZIA"])
        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().get(prova)
    passi = esito["INCREMENTALE"]["incrementale"]
    assert passi["aggiunta"]["altri_oggetti_riletti"] == 0
    assert passi["aggiunta"]["letture_del_documento"].get("motore_documenti") == "letto"
    assert passi["aggiunta"]["sintesi_aggiornata"]
    assert passi["modifica"]["impronta_cambiata"]
    assert passi["modifica"]["altri_oggetti_riletti"] == 0
    assert passi["modifica"]["letture_nuova_impronta"].get("motore_documenti") == "letto"
    assert passi["rimozione"]["nel_registro_ancora_presente"] is False
    assert passi["rimozione"]["sintesi_coerente_col_registro"]
    assert passi["rimozione"]["altri_oggetti_riletti"] == 0
    assert esito["PULIZIA"]["pulizia"]["restano_di_prova"] == 0
    assert not [d for d in fascicolo.documenti_cestino if d.nome.startswith("collaudo_motori_")]


def test_errori_il_pdf_guasto_non_blocca_il_buono_ed_e_scritto(ambiente):
    app, _reale, _prova = ambiente
    with app.app_context():
        modulo = _script()
        esito = modulo.esegui(app, ["ERRORI", "PULIZIA"])["ERRORI"]["errori"]
    assert esito["buono"]["letture"].get("motore_documenti") == "letto"
    assert esito["guasto"]["letture"].get("motore_documenti") in {"non_leggibile", "errore", "letto"}
    assert esito["guasto"]["pannello"]["oggetto_nel_pannello"]
    assert esito["dopo_la_sostituzione"]["letture"].get("motore_documenti") == "letto"
    assert esito["altri_oggetti_riletti"] == 0


def test_numeri_non_fa_uscire_testi():
    modulo = _script()
    numeri = modulo._numeri({"ok": True, "job": "x", "totals": {"letti": 3, "nome": "Rossi"}, "tenants": [{"tenant": "studio-rossi"}]})
    assert numeri == {"ok": True, "totals.letti": 3, "tenants#": 1}
