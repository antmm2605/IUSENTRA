import pytest

from deploy.openga import update_worker


def test_invalid_revision_never_executes_docker(monkeypatch):
    monkeypatch.setattr(update_worker, "command", lambda *args: pytest.fail("unexpected command"))
    with pytest.raises(ValueError, match="SHA"):
        update_worker.run("not-a-revision")


def test_different_server_revision_aborts_without_mutations(monkeypatch):
    monkeypatch.setattr(update_worker, "command", lambda *args: "b" * 40)
    monkeypatch.setattr(update_worker.subprocess, "run", lambda *args, **kwargs: pytest.fail("mutation"))
    with pytest.raises(ValueError, match="Revisione"):
        update_worker.run("a" * 40)


def test_writable_public_mount_aborts_before_build(monkeypatch):
    sha = "a" * 40
    def command(*args):
        if args[0] == "git":
            return sha
        return "old"
    monkeypatch.setattr(update_worker, "command", command)
    monkeypatch.setattr(update_worker, "inspect", lambda name: {
        "Name": "/old", "Config": {"Image": "iusentra-openga:" + "b" * 40},
        "Mounts": [{"Destination": "/catalogo", "RW": True}, {"Destination": "/modello", "RW": False}],
    })
    monkeypatch.setattr(update_worker.subprocess, "run", lambda *args, **kwargs: pytest.fail("mutation"))
    with pytest.raises(ValueError, match="read-only"):
        update_worker.run(sha)


def test_source_parity_rejects_stale_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(update_worker, "command", lambda *args: "{}")
    paths = ["pct/openga_catalogo.py", "pct/openga_query.py", "pct/openga_reranker.py",
             "pct/openga_riformulazione.py", "pct/openga_search.py", "pct/openga_identita.py",
             "pct/__init__.py", "deploy/openga/server.py"]
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("sorgente verificato")
    with pytest.raises(ValueError, match="Sorgenti"):
        update_worker.verify_sources(tmp_path, "candidate")
