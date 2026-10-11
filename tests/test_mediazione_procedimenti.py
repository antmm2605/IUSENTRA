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


def test_editor_copy_is_linked_only_to_its_registered_module_and_delivery_is_idempotent(procedure):
    _, case, repo = procedure
    payload = normalizza({"titolo": "Decisione manuale conservata", "modulo_verificato": True}, set())
    payload.update(organismo_numero="429", modulo_ufficiale_documento="originale",
                   moduli_organismo=[{"documento": "originale", "fonte": {"organismo_numero": "429"}, "copie_compilate": []}])
    identifier = repo.salva(case.id, "", 0, payload, "avvocato")
    assert repo.collega_copia_modulo(case.id, "originale", "copia", {"originale", "copia"}, "avvocato") == [identifier]
    revision = repo.db.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0]
    updated = repo.lista(case.id)[0]
    assert updated["moduli_organismo"][0]["copie_compilate"] == ["copia"]
    assert updated["modulo_compilato_documento"] == "copia"
    assert updated["titolo"] == "Decisione manuale conservata" and updated["modulo_verificato"]
    assert updated["stato"] == "bozza" and not updated["data_deposito"]
    assert repo.collega_copia_modulo(case.id, "originale", "copia", {"originale", "copia"}, "avvocato") == [identifier]
    assert len(repo.audit(case.id)) == 2 and repo.lista(case.id)[0]["versione"] == 2
    assert repo.db.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0] == revision
    assert repo.collega_copia_modulo("altro-fascicolo", "originale", "copia", {"originale", "copia"}, "avvocato") == []
    with pytest.raises(ValueError, match="fascicolo corrente"):
        repo.collega_copia_modulo(case.id, "originale", "esterno", {"originale", "copia"}, "avvocato")


def test_editor_copy_rebases_a_concurrent_change_without_overwriting_manual_data(procedure, monkeypatch):
    _, case, repo = procedure
    payload = normalizza({}, set())
    payload.update(organismo_numero="429", modulo_ufficiale_documento="originale",
                   moduli_organismo=[{"documento": "originale", "fonte": {"organismo_numero": "429"}, "copie_compilate": []}])
    identifier = repo.salva(case.id, "", 0, payload, "avvocato")
    native_save = repo.salva
    attempts = []

    def competing_save(fid, pid, version, data, actor):
        if not attempts:
            attempts.append(True)
            native_save(fid, pid, version, dict(payload, note_riservate="Nota concorrente da preservare"), "altro")
        return native_save(fid, pid, version, data, actor)

    monkeypatch.setattr(repo, "salva", competing_save)
    assert repo.collega_copia_modulo(case.id, "originale", "copia", {"originale", "copia"}, "avvocato") == [identifier]
    assert repo.lista(case.id)[0]["note_riservate"] == "Nota concorrente da preservare"
    assert repo.lista(case.id)[0]["moduli_organismo"][0]["copie_compilate"] == ["copia"]
    assert len(repo.audit(case.id)) == 3


def test_viewer_registers_only_a_confirmed_native_copy_and_keeps_external_text_protected(procedure, monkeypatch, tmp_path):
    from flask import jsonify
    import web.helpers
    from web.bootstrap.viewer_editor_routes import register_viewer_editor_routes

    manager, case, repo = procedure
    original = SimpleNamespace(id="originale", nome="Modulo.pdf", tags=["modulo_organismo"], hash_sha256="a" * 64)
    copied = SimpleNamespace(id="copia", nome="Modulo (copia).pdf", tags=[], hash_sha256="b" * 64)
    case.documenti = [original, copied]
    payload = normalizza({}, set())
    payload.update(organismo_numero="429", modulo_ufficiale_documento=original.id,
                   moduli_organismo=[{"documento": original.id, "fonte": {"organismo_numero": "429"}, "copie_compilate": []}])
    repo.salva(case.id, "", 0, payload, "avvocato")
    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: SimpleNamespace(get=lambda fid: case if fid == case.id else None, _studio_db=manager._studio_db))
    monkeypatch.setattr(web.helpers, "_cfg", lambda _: str(tmp_path / "fascicoli.json"))
    app = Flask(__name__)

    @app.before_request
    def user():
        g.utente_corrente = SimpleNamespace(id="avvocato", ha_permesso=lambda p: p in {"fascicoli.leggi", "fascicoli.scrivi"})

    app.view_functions["api_editor_pdf_overlay"] = lambda *_: jsonify(ok=True, destinazione="copia", documento={"id": copied.id})
    register_viewer_editor_routes(app)
    client = app.test_client()
    url = f"/api/v1/ui/fascicoli/{case.id}/documenti/{original.id}/editor-visualizzatore"
    body = {"destinazione": "copia", "expectedHash": original.hash_sha256, "annotations": [{"type": "text", "text": "Controllato"}]}
    headers = {"X-Requested-With": "XMLHttpRequest"}
    assert client.post(url, json=dict(body, annotations=[{"type": "replace"}]), headers=headers).status_code == 403
    assert repo.lista(case.id)[0]["moduli_organismo"][0]["copie_compilate"] == []
    response = client.post(url, json=body, headers=headers)
    assert response.status_code == 200 and response.json["mediazioni_collegate"]
    assert repo.lista(case.id)[0]["moduli_organismo"][0]["copie_compilate"] == [copied.id]


def test_multiple_attachments_are_deduplicated_and_bound_to_current_case():
    payload = normalizza({"allegati_documenti": ["a", "b", "a"]}, {"a", "b"})
    assert payload["allegati_documenti"] == ["a", "b"]
    for data in ({"allegati_documenti": ["esterno"]}, {"ricevuta_documento": "esterno"}):
        with pytest.raises(ValueError, match="fascicolo corrente"):
            normalizza(data, {"a"})


def test_reacquiring_identical_module_preserves_compiled_copies_and_manual_verification(procedure, monkeypatch):
    import web.bootstrap.mediazione_fascicolo_routes as routes

    manager, case, repo = procedure
    original = SimpleNamespace(id="originale", nome="Modulo.pdf")
    copied = SimpleNamespace(id="copia", nome="Copia.pdf")
    case.documenti = [original, copied]
    source = {"organismo_numero": "429", "sha256": "a" * 64, "url": "https://example.org/modulo.pdf"}
    payload = normalizza({"modulo_verificato": True, "note_riservate": "Conservare"}, set())
    payload.update(organismo_numero="429", modulo_ufficiale_documento=original.id,
                   modulo_compilato_documento=copied.id, modulo_fonte=source,
                   moduli_organismo=[{"documento": original.id, "nome": original.nome, "fonte": source, "copie_compilate": [copied.id]}])
    pid = repo.salva(case.id, "", 0, payload, "avvocato")
    monkeypatch.setattr(routes, "acquisisci_modulo", lambda *_: (b"%PDF-test", original.nome, source))
    monkeypatch.setattr(routes, "collega_organismo", lambda target, previous, _: target.update(moduli_organismo=previous["moduli_organismo"]))
    app = Flask(__name__)

    @app.before_request
    def user():
        g.utente_corrente = SimpleNamespace(id="avvocato", ha_permesso=lambda _: True)

    register_mediazione_fascicolo_routes(app, get_fascicoli=lambda: SimpleNamespace(get=lambda _: case, _studio_db=manager._studio_db),
        cliente_accessibile=lambda _: True, salva_documento_fascicolo=lambda *args, **kwargs: original, decrypt_doc=None)
    response = app.test_client().post(f"/api/fascicoli/{case.id}/mediazioni/{pid}/modulo", json={"versione": 1, "url": source["url"]})
    assert response.status_code == 200
    row = repo.lista(case.id)[0]
    assert row["versione"] == 1 and len(repo.audit(case.id)) == 1
    assert row["modulo_verificato"] and row["note_riservate"] == "Conservare"
    assert row["modulo_compilato_documento"] == copied.id and row["moduli_organismo"][0]["copie_compilate"] == [copied.id]


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
