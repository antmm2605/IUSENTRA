"""Guardrail SQL e API: non attestano un deposito esterno o prove hardware."""
from types import SimpleNamespace

import pytest
from flask import Flask, g

from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.mediazione_procedimenti import MediazioneProcedimentiRepository, normalizza
from pct.storage import StudioDB
from web.bootstrap.mediazione_fascicolo_routes import register_mediazione_fascicolo_routes


@pytest.fixture
def procedure(tmp_path):
    db = StudioDB.get(str(tmp_path / "studio.db"))
    manager = GestioneFascicoli(db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"), archive_dir=str(tmp_path / "archivio"), studio_db=db)
    case = manager.nuovo(titolo="Prova mediazione", tipo=TipoFascicolo.CIVILE)
    return manager, case, MediazioneProcedimentiRepository(db)


def test_sql_version_conflict_rolls_back_without_losing_audit(procedure):
    _, case, repo = procedure
    payload = normalizza({"titolo": "Bozza riservata"}, set())
    identifier = repo.salva(case.id, "", 0, payload, "avvocato")
    repo.salva(case.id, identifier, 1, dict(payload, titolo="Revisione"), "avvocato")
    with pytest.raises(ValueError, match="aggiornato altrove"):
        repo.salva(case.id, identifier, 1, payload, "altro")
    assert repo.lista(case.id)[0]["titolo"] == "Revisione"
    assert repo.lista(case.id)[0]["versione"] == 2
    assert len(repo.audit(case.id)) == 2
    assert repo.lista("altro-fascicolo") == repo.audit("altro-fascicolo") == []
    with pytest.raises(ValueError):
        repo.salva("altro-fascicolo", identifier, 2, payload, "altro")


def test_missing_sql_never_falls_back_to_json():
    with pytest.raises(RuntimeError, match="nessun salvataggio su JSON"):
        MediazioneProcedimentiRepository(None)


def test_multiple_attachments_are_deduplicated_and_bound_to_current_case():
    payload = normalizza({"allegati_documenti": ["a", "b", "a"]}, {"a", "b"})
    assert payload["allegati_documenti"] == ["a", "b"]
    for data in ({"allegati_documenti": ["esterno"]}, {"ricevuta_documento": "esterno"}):
        with pytest.raises(ValueError, match="fascicolo corrente"):
            normalizza(data, {"a"})


def test_draft_does_not_become_a_filing():
    draft = normalizza({}, set())
    assert draft["stato"] == "bozza" and not draft["data_deposito"]
    with pytest.raises(ValueError):
        normalizza(dict(draft, stato="depositata"), set())


def test_api_save_read_permissions_and_cross_case_id(procedure):
    manager, case, repo = procedure
    app = Flask(__name__)
    permissions = {"fascicoli.leggi", "fascicoli.scrivi"}

    @app.before_request
    def user():
        g.utente_corrente = SimpleNamespace(id="avvocato", ha_permesso=lambda p: p in permissions)

    register_mediazione_fascicolo_routes(app, get_fascicoli=lambda: manager,
        cliente_accessibile=lambda _: True, salva_documento_fascicolo=None, decrypt_doc=None)
    client = app.test_client()
    url = f"/api/fascicoli/{case.id}/mediazioni"
    response = client.post(url, json={"titolo": "Bozza controllata", "versione": 0})
    assert response.status_code == 200
    assert response.json["id_fascicolo"] == case.id
    assert response.json["source_of_truth"] == "sqlite"
    row = response.json["procedimenti"][0]
    assert row["stato"] == "bozza" and len(repo.audit(case.id)) == 1
    assert client.post(url, json={"id": "altrui", "versione": 1}).status_code == 403
    permissions.remove("fascicoli.scrivi")
    assert client.get(url).status_code == 200
    assert client.post(url, json={"versione": 0}).status_code == 403
    permissions.clear()
    assert client.get(url).status_code == 403
    assert len(repo.lista(case.id)) == 1
