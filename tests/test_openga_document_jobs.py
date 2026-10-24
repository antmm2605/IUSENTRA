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
