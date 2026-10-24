from hashlib import sha256
from types import SimpleNamespace

import pytest

from web.services import openga_document_jobs as jobs


def test_study_isolation_deduplication_and_original_preserved(tmp_path, monkeypatch):
    a, b = str(tmp_path / "a" / "giurisprudenza.db"), str(tmp_path / "b" / "giurisprudenza.db")
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    monkeypatch.setattr(jobs, "document_identity", lambda payload, config: {"sede": "020"})
    monkeypatch.setattr(jobs, "_ensure_worker", lambda *args: None)
    app = SimpleNamespace(config={})
    payload = {"relazione_id": "r", "resource_id": "s", "resource_sha256": "a" * 64}
    first = jobs.start(app, db_path=a, payload=payload)
    second = jobs.start(app, db_path=a, payload=payload)
    assert first["job_id"] == second["job_id"]
    with pytest.raises(KeyError):
        jobs.status(b, first["job_id"])
    queue = jobs._queue(a)
    queue.complete(first["job_id"], result={"stato": "acquisito", "documento": {
        "testo": "testo ufficiale", "originale_base64": "eA==",
        "raw_sha256": sha256(b"x").hexdigest(),
        "provenienza": {"sha256": sha256(b"testo ufficiale").hexdigest()},
        "approvazione_avvocato": False}})
    result = jobs.status(a, first["job_id"])
    assert result["documento"]["testo"] == "testo ufficiale"
    assert "originale_base64" not in result["documento"]
    assert queue.get(first["job_id"]).result["documento"]["originale_base64"] == "eA=="
    corrupted = queue.get(first["job_id"]).result
    corrupted["documento"]["testo"] = "testo alterato"
    queue.complete(first["job_id"], result=corrupted)
    assert jobs.status(a, first["job_id"])["stato"] == "intervento_necessario"


def test_failed_job_does_not_become_text(tmp_path):
    queue = jobs._queue(str(tmp_path / "g.db"))
    job = queue.enqueue(source_code="openga_testo", max_attempts=1)
    queue.claim_next()
    queue.fail(job.job_id, error="errore")
    result = jobs.status(str(tmp_path / "g.db"), job.job_id)
    assert result["stato"] == "intervento_necessario"
    assert "documento" not in result


def test_authenticated_route_uses_study_manager_and_no_browser_identity(tmp_path, monkeypatch):
    from tests.test_giurisprudenza import _cfg_web, _login_admin
    from web.app import create_app
    from web.services import openga_document_jobs
    config = _cfg_web(tmp_path)
    _login_admin(config)
    app = create_app(config)
    seen = []
    def start(app, *, db_path, payload):
        seen.append((db_path, payload))
        return {"ok": True, "stato": "in_corso", "job_id": "job"}
    monkeypatch.setattr(openga_document_jobs, "start", start)
    with app.test_client() as client:
        path = "/api/v1/ui/giurisprudenza/testo-ufficiale"
        assert client.post(path, json={}).status_code in {401, 403}
        assert client.get(path + "/job").status_code in {401, 403}
        client.post("/login", data={"username": "admin-giurisprudenza", "password": "Admin1234!"})
        result = client.post(path, json={"relazione_id": "r", "db_path": "/altro-studio"})
        assert result.status_code == 202
        assert seen[0][0] != "/altro-studio"
        assert client.post(path, json=[]).status_code == 400
        assert client.get(path + "/inesistente").status_code == 404


def test_two_workers_cannot_claim_the_same_job(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = str(tmp_path / "studio.db")
    queue = jobs._queue(path)
    job = queue.enqueue(source_code="openga_testo")
    def claim(worker):
        return jobs._queue(path).claim_next(worker_id=worker, recover_stale=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(claim, ["a", "b"]))
    assert [item.job_id for item in claimed if item] == [job.job_id]


def test_busy_public_source_remains_queued_then_resumes(tmp_path, monkeypatch):
    from contextlib import nullcontext
    path = str(tmp_path / "studio.db")
    queue = jobs._queue(path)
    job = queue.enqueue(source_code="openga_testo", max_attempts=3, payload={"identita": {}})
    values = iter([{"stato": "in_attesa"}, {"stato": "non_trovato"}])
    monkeypatch.setattr(jobs, "recupera_testo", lambda identity: next(values))
    monkeypatch.setattr(jobs, "sleep", lambda seconds: None)
    app = SimpleNamespace(app_context=nullcontext, logger=SimpleNamespace(warning=lambda *args: None))
    jobs._run(app, path)
    final = queue.get(job.job_id)
    assert final.status == "completed"
    assert final.attempts == 2
    assert final.result["stato"] == "non_trovato"


def test_old_negative_is_retried_after_reader_fix_and_keeps_original_result(tmp_path, monkeypatch):
    import json
    path = str(tmp_path / "studio.db")
    monkeypatch.setattr(jobs, "document_identity", lambda payload, config: {"sede": "003"})
    monkeypatch.setattr(jobs, "_ensure_worker", lambda *args: None)
    app = SimpleNamespace(config={})
    payload = {"relazione_id": "r", "resource_id": "s", "resource_sha256": "a" * 64}
    first = jobs.start(app, db_path=path, payload=payload)
    queue = jobs._queue(path)
    queue.complete(first["job_id"], result={"stato": "intervento_necessario", "message": "Sede insufficiente"})
    legacy = queue.get(first["job_id"])
    old_payload = dict(legacy.payload)
    old_payload.pop("lettore_versione", None)
    with queue.connect() as connection:
        connection.execute("UPDATE legal_update_jobs SET payload_json=? WHERE job_id=?",
                           (json.dumps(old_payload), first["job_id"]))
    second = jobs.start(app, db_path=path, payload=payload)
    assert second["job_id"] == first["job_id"]
    assert second["stato"] == "in_corso"
    updated = queue.get(first["job_id"])
    assert updated.payload["tentativi_precedenti"][-1]["result"]["message"] == "Sede insufficiente"
    queue.complete(first["job_id"], result={"stato": "non_trovato"})
    # A reopen alone must not start an endless automatic retry.
    assert jobs.start(app, db_path=path, payload=payload)["stato"] == "non_trovato"
    assert jobs.start(app, db_path=path, payload={**payload, "riprova": True})["stato"] == "in_corso"


def test_html_reader_is_authenticated_tenant_scoped_and_escapes_document_text(tmp_path, monkeypatch):
    import importlib

    from tests.test_giurisprudenza import _cfg_web, _login_admin
    from web.app import create_app
    blueprint = importlib.import_module("web.blueprints.giurisprudenza")
    config = _cfg_web(tmp_path)
    _login_admin(config)
    app = create_app(config)
    current_path = [str(tmp_path / "a.db")]
    monkeypatch.setattr(blueprint, "get_giurisprudenza",
                        lambda: SimpleNamespace(db_path=current_path[0]))
    queue = jobs._queue(current_path[0])
    job = queue.enqueue(source_code="openga_testo")
    text = "Testo sintetico <script>alert(1)</script>"
    queue.complete(job.job_id, result={"stato": "acquisito", "documento": {
        "testo": text, "originale_base64": "eA==", "raw_sha256": sha256(b"x").hexdigest(),
        "sezioni": {"motivazione": text}, "provenienza": {
            "sha256": sha256(text.encode()).hexdigest(),
            "url": "https://mdp.giustizia-amministrativa.it/visualizza/",
            "versione": "01/01/2023", "acquisita_il": "24/10/2026"}}})
    path = "/giurisprudenza/testo-ufficiale/" + job.job_id
    with app.test_client() as client:
        assert client.get(path).status_code in {302, 401, 403}
        client.post("/login", data={"username": "admin-giurisprudenza", "password": "Admin1234!"})
        response = client.get(path)
        assert response.status_code == 200
        assert response.mimetype == "text/html"
        assert b"&lt;script&gt;" in response.data
        assert b"<script>alert(1)</script>" not in response.data
        assert "no-store" in response.headers["Cache-Control"]
        current_path[0] = str(tmp_path / "b.db")
        assert client.get(path).status_code == 404


def test_explicit_retry_never_discards_a_verified_text(tmp_path, monkeypatch):
    path = str(tmp_path / "studio.db")
    monkeypatch.setattr(jobs, "document_identity", lambda payload, config: {"sede": "003"})
    monkeypatch.setattr(jobs, "_ensure_worker", lambda *args: None)
    app = SimpleNamespace(config={})
    payload = {"relazione_id": "r", "resource_id": "s", "resource_sha256": "a" * 64}
    first = jobs.start(app, db_path=path, payload=payload)
    queue = jobs._queue(path)
    text = "Documento già acquisito"
    queue.complete(first["job_id"], result={"stato": "acquisito", "documento": {
        "testo": text, "originale_base64": "eA==", "raw_sha256": sha256(b"x").hexdigest(),
        "provenienza": {"sha256": sha256(text.encode()).hexdigest()}}})
    repeated = jobs.start(app, db_path=path, payload={**payload, "riprova": True})
    assert repeated["stato"] == "acquisito"
    assert repeated["documento"]["testo"] == text
    assert queue.get(first["job_id"]).status == "completed"


def test_reader_fingerprint_changes_when_its_code_changes(tmp_path):
    source = tmp_path / "reader.py"
    source.write_text("versione iniziale")
    first = jobs._reader_fingerprint([source])
    assert jobs._reader_fingerprint([source]) == first
    source.write_text("gestisce i ricorsi riuniti")
    assert jobs._reader_fingerprint([source]) != first
