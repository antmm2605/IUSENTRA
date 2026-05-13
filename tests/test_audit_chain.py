from __future__ import annotations

import json

from audit.schemas import AuditKind

from tests.audit_test_utils import emit_sample_event, make_service


def test_prev_event_hash_chain_is_recorded_and_verified(tmp_path) -> None:
    service, _public = make_service()
    first = emit_sample_event(service, tmp_path, idempotency_key="chain-1", kind=AuditKind.ACT_GENERATED)
    second = emit_sample_event(service, tmp_path, idempotency_key="chain-2", kind=AuditKind.PEC_SENT)
    second_row = service.repository.get_event(second.event_id, tenant_id="tenant-a")
    assert second_row
    assert second_row["prev_event_hash"] == first.event_hash
    envelope = json.loads(service.worm_store.get_object(second.worm_key, second.worm_version_id).decode("utf-8"))
    assert envelope["signed_event"]["chain"]["prev_event_hash"] == first.event_hash
    assert service.verify_chain("tenant-a", "FASC-1").ok
