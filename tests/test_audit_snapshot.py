from __future__ import annotations

import json
from datetime import UTC, datetime

from audit.snapshot_job import AuditSnapshotJob

from tests.audit_test_utils import emit_sample_event, make_service


def test_snapshot_job_signs_and_indexes_daily_snapshot(tmp_path) -> None:
    service, _public = make_service()
    first = emit_sample_event(service, tmp_path, idempotency_key="snap-1")
    emit_sample_event(service, tmp_path, idempotency_key="snap-2", content=b"secondo")
    results = AuditSnapshotJob(service).run(tenant_id="tenant-a", at=datetime.now(UTC))
    assert len(results) == 1
    result = results[0]
    assert result.events_count == 2
    row = service.repository.get_event(first.event_id, tenant_id="tenant-a")
    assert row and row["snapshot_id"] == result.snapshot_id
    snap_row = service.repository.get_snapshot(result.snapshot_id, tenant_id="tenant-a")
    assert snap_row
    envelope = json.loads(service.worm_store.get_object(snap_row["worm_key"], snap_row["worm_version_id"]).decode("utf-8"))
    assert envelope["signed_snapshot"]["merkle_root"] == result.merkle_root
    assert envelope["signature"]["format"] == "JWS"


def test_snapshot_job_discovers_tenants_with_open_events(tmp_path) -> None:
    service, _public = make_service()
    emit_sample_event(service, tmp_path, idempotency_key="snap-auto")

    results = AuditSnapshotJob(service).run(at=datetime.now(UTC))

    assert len(results) == 1
    assert results[0].tenant_id == "tenant-a"
