from __future__ import annotations

import json

import pytest

from audit.exceptions import AuditValidationError
from audit.schemas import ActorContext, AuditFileRef, AuditKind, SourceContext
from audit.repository import AuditRepository, _pg_uuid_or_none
from audit.service import AuditService
from audit.signing import JwsAuditSigner
from audit.worm import InMemoryWormStore

from tests.audit_test_utils import emit_sample_event, make_key_pair, make_service


class _FailingIndexRepository(AuditRepository):
    def insert_event(self, record, *, conn=None) -> None:  # type: ignore[override]
        raise RuntimeError("index unavailable")


def test_emit_event_writes_worm_before_index(tmp_path) -> None:
    service, _public = make_service()
    result = emit_sample_event(service, tmp_path)
    row = service.repository.get_event(result.event_id, tenant_id="tenant-a")
    assert row
    assert row["event_hash"] == result.event_hash
    envelope = json.loads(service.worm_store.get_object(result.worm_key, result.worm_version_id).decode("utf-8"))
    assert envelope["event_hash"] == result.event_hash
    assert service.verify_envelope(envelope).ok
    assert service.worm_store.ready_checked


def test_idempotency_key_returns_existing_event(tmp_path) -> None:
    service, _public = make_service()
    first = emit_sample_event(service, tmp_path, idempotency_key="same")
    second = emit_sample_event(service, tmp_path, idempotency_key="same")
    assert second.event_id == first.event_id
    assert second.warnings == ("idempotency_key_gia_emessa",)
    assert len(service.repository.list_events(tenant_id="tenant-a", fascicolo_id="FASC-1")) == 1


def test_emit_rejects_sensitive_large_payload(tmp_path) -> None:
    service, _public = make_service()
    file_path = tmp_path / "atto.pdf"
    file_path.write_bytes(b"x")
    with pytest.raises(AuditValidationError):
        service.emit_event(
            kind=AuditKind.ACT_GENERATED,
            tenant_id="tenant-a",
            fascicolo_id="FASC-1",
            actor=ActorContext(actor_id="user-1", actor_type="user"),
            payload={"content": "testo integrale vietato"},
            files=[AuditFileRef(label="atto.pdf", storage_ref="dms://atto", path=file_path)],
            source=SourceContext(service="iusentra", module="test"),
            idempotency_key="bad-payload",
        )


def test_emit_records_failure_when_index_fails_after_worm(tmp_path) -> None:
    private_pem, _public_pem = make_key_pair()
    repository = _FailingIndexRepository.in_memory()
    service = AuditService(
        repository=repository,
        worm_store=InMemoryWormStore(),
        signer=JwsAuditSigner(private_key_pem=private_pem, kid="test-signer"),
        config={"AUDIT_ENABLED": True, "AUDIT_ENV": "development", "AUDIT_RETENTION_YEARS": 10},
    )
    with pytest.raises(RuntimeError):
        emit_sample_event(service, tmp_path, idempotency_key="index-fails")
    assert list(service.worm_store.list_audit_objects("audit/events/tenant=tenant-a/"))
    failures = repository._execute(repository._connect(), "SELECT * FROM audit_emit_failures")
    assert failures
    assert failures[0]["failure_stage"] == "index_after_worm"


def test_from_config_uses_pct_data_root_for_dev_sqlite_index(tmp_path) -> None:
    private_pem, _public_pem = make_key_pair()
    key_path = tmp_path / "audit-key.pem"
    key_path.write_bytes(private_pem)

    service = AuditService.from_config(
        {
            "AUDIT_ENV": "development",
            "AUDIT_WORM_BUCKET": "audit-test-bucket",
            "AUDIT_WORM_ACCESS_KEY": "test",
            "AUDIT_WORM_SECRET_KEY": "test",
            "AUDIT_SIGNING_KID": "test-signer",
            "AUDIT_SIGNING_PRIVATE_KEY_FILE": str(key_path),
            "PCT_DATA_ROOT": str(tmp_path),
        }
    )

    assert service.repository.sqlite_path == tmp_path / "audit" / "legal_audit_index.db"
    assert service.repository.sqlite_path.exists()


def test_postgres_optional_uuid_fields_are_stored_as_null() -> None:
    assert _pg_uuid_or_none("") is None
    assert _pg_uuid_or_none(None) is None
    assert _pg_uuid_or_none("6acaaf76-24fe-4c7c-b754-0bf851c64bd7") == "6acaaf76-24fe-4c7c-b754-0bf851c64bd7"
