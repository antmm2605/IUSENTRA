"""Contratti HTTP del CRM: clearance conflitto e adeguata verifica SQL-first."""

from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, g

from pct.antiriciclaggio import GestioneAntiriciclaggio
from pct.crm_intake import GestioneCrmIntake
from pct.storage import StudioDB
from web.bootstrap.crm_routes import register_crm_routes


class _User:
    username = "avv.qa"

    @staticmethod
    def ha_permesso(_permission: str) -> bool:
        return True


class _Repository:
    def tutti(self, stato=None):
        return []


class _Users:
    def tutti(self, solo_attivi=False):
        return [SimpleNamespace(username="avv.qa", nome_completo="Avv. QA", attivo=True)]


def _app(tmp_path):
    db = StudioDB.get(str(tmp_path / "studio.db"))
    crm = GestioneCrmIntake(
        db_path=str(tmp_path / "crm" / "leads.json"), studio_db=db, tenant_id="tenant-qa"
    )
    aml = GestioneAntiriciclaggio(
        db_path=str(tmp_path / "antiriciclaggio" / "verifiche.json"), studio_db=db, tenant_id="tenant-qa"
    )
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="qa")

    @app.before_request
    def _sessione_qa():
        g.utente_corrente = _User()

    register_crm_routes(
        app,
        {
            "get_crm": lambda: crm,
            "get_antiriciclaggio": lambda: aml,
            "get_clienti": lambda: _Repository(),
            "get_soggetti": lambda: _Repository(),
            "get_utenti": _Users,
            "audit": lambda *args, **kwargs: None,
        },
    )
    return app, crm, aml, db


def test_route_aml_avvia_con_cliente_e_scrive_nel_db_canonico(tmp_path):
    app, crm, aml, db = _app(tmp_path)
    lead = crm.nuovo(denominazione="Cliente QA")
    crm.verifica_conflitti(lead.id)
    crm.converti_in_cliente(lead.id, crea_cliente=lambda dati: {"id": "CL-QA"})

    client = app.test_client()
    invalid = client.post(f"/crm/lead/{lead.id}/antiriciclaggio/avvia", json={})
    assert invalid.status_code == 400
    response = client.post(
        f"/crm/lead/{lead.id}/antiriciclaggio/avvia",
        json={
            "prestazione": "gestione_denaro",
            "scopoNatura": "Gestione del corrispettivo della compravendita.",
            "titolareEffettivo": {"nome": "Cliente QA", "criterio": "coincide_con_cliente"},
        },
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    verifica = aml.per_lead(lead.id)[0]
    assert verifica.cliente_id == "CL-QA"
    assert db.conn.execute("SELECT COUNT(*) FROM aml_verifications").fetchone()[0] == 1

    payload = client.get("/api/v1/ui/crm").get_json()
    card = next(column for column in payload["columns"] if column["stato"] == "VINTO")["leads"][0]
    assert card["antiriciclaggio"]["id"] == verifica.id
    assert card["antiriciclaggio"]["actions"]["conferma"].endswith("/conferma")


def test_route_decisione_conflitto_richiede_motivazione(tmp_path):
    app, crm, _aml, _db = _app(tmp_path)
    lead = crm.nuovo(denominazione="Alfa S.r.l.", partita_iva="01234567890")
    controparte = SimpleNamespace(
        id="S1", ragione_sociale="Alfa S.r.l.", nome="", cognome="",
        codice_fiscale="", partita_iva="01234567890", tipo="CONTROPARTE",
    )
    crm.verifica_conflitti(lead.id, get_soggetti=lambda: SimpleNamespace(tutti=lambda: [controparte]))

    client = app.test_client()
    blocked = client.post(f"/crm/lead/{lead.id}/conflitti/decisione", json={"decisione": "CLEARANCE_CONCESSA"})
    assert blocked.status_code == 400
    response = client.post(
        f"/crm/lead/{lead.id}/conflitti/decisione",
        json={"decisione": "CLEARANCE_CONCESSA", "motivazione": "Verificato il perimetro del nuovo incarico."},
    )
    assert response.status_code == 200
    assert response.get_json()["esito"]["convertibile"] is True


def test_route_screening_salva_snapshot_ed_esito_nel_repository(tmp_path, monkeypatch):
    app, crm, aml, _db = _app(tmp_path)
    lead = crm.nuovo(denominazione="Cliente QA")
    crm.verifica_conflitti(lead.id)
    crm.converti_in_cliente(lead.id, crea_cliente=lambda dati: {"id": "CL-QA"})
    verifica = aml.nuova(
        cliente_id="CL-QA", lead_id=lead.id, prestazione="gestione_denaro", scopo_natura="Gestione controllata"
    )
    monkeypatch.setattr(
        "web.bootstrap.crm_routes.screen_eu_financial_sanctions",
        lambda subject, cache_dir: {
            "provider_key": "eu-consolidated-financial-sanctions",
            "source_url": "https://example.test/eu.xml",
            "source_version": "qa",
            "snapshot_hash": "sha256:qa",
            "subject_label": subject,
            "outcome": "NESSUN_RISCONTRO",
            "matches": [],
            "note": "Snapshot di test verificato.",
        },
    )

    response = app.test_client().post(f"/crm/lead/{lead.id}/antiriciclaggio/{verifica.id}/screening-ue")

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    evidence = aml.evidenze_screening(verifica.id)[0]
    assert evidence["snapshot_hash"] == "sha256:qa"
    assert evidence["outcome"] == "NESSUN_RISCONTRO"


def test_route_barriera_informativa_crea_accesso_riservato_e_payload(tmp_path):
    app, crm, _aml, db = _app(tmp_path)
    lead = crm.nuovo(denominazione="Contatto riservato")

    response = app.test_client().post(
        f"/crm/lead/{lead.id}/barriera-riservatezza",
        json={
            "motivazione": "Trattativa riservata verificata dal responsabile.",
            "utentiAutorizzati": ["avv.qa"],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert crm.accesso_lead_consentito(lead.id, operatore="avv.qa") is True
    assert crm.accesso_lead_consentito(lead.id, operatore="avv.estraneo") is False
    assert db.conn.execute("SELECT COUNT(*) FROM ethical_walls").fetchone()[0] == 1
    payload = app.test_client().get("/api/v1/ui/crm").get_json()
    card = next(column for column in payload["columns"] if column["stato"] == "NUOVO")["leads"][0]
    assert card["barrieraRiservatezza"]["attiva"] is True
    assert card["actions"]["revocaBarrieraRiservatezza"].endswith("/revoca")
