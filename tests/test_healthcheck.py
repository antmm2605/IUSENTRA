from __future__ import annotations

from core.health import dependencies_payload, live_payload, ready_payload


def test_live_payload_is_healthy() -> None:
    payload, status = live_payload("test-version")
    assert status == 200
    assert payload["status"] == "healthy"
    assert payload["versione"] == "test-version"


def test_ready_payload_checks_sqlite_and_filesystem(tmp_path) -> None:
    payload, status = ready_payload(
        version="test",
        database_url=f"sqlite:///{tmp_path / 'app.sqlite'}",
        redis_url="",
        storage_root=tmp_path / "storage",
    )
    assert status == 200
    assert payload["checks"]["database"]["ok"]
    assert payload["checks"]["filesystem"]["ok"]


def test_dependencies_payload_does_not_expose_secrets(tmp_path) -> None:
    payload, status = dependencies_payload(
        version="test",
        database_url=f"sqlite:///{tmp_path / 'app.sqlite'}",
        redis_url="",
        ollama_url="",
        smtp_configured=False,
    )
    serialized = str(payload).lower()
    assert status == 200
    assert "secret" not in serialized
    assert "password" not in serialized
