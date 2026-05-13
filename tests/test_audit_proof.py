from __future__ import annotations

import json
from datetime import UTC, datetime

from audit.merkle import verify_merkle_proof
from audit.snapshot_job import AuditSnapshotJob, proof_for_event

from tests.audit_test_utils import emit_sample_event, make_service


def test_merkle_proof_for_snapshotted_event_verifies(tmp_path) -> None:
    service, _public = make_service()
    result = emit_sample_event(service, tmp_path, idempotency_key="proof-1")
    emit_sample_event(service, tmp_path, idempotency_key="proof-2", content=b"secondo")
    snapshot = AuditSnapshotJob(service).run(tenant_id="tenant-a", at=datetime.now(UTC))[0]
    snap_row = service.repository.get_snapshot(snapshot.snapshot_id, tenant_id="tenant-a")
    assert snap_row
    envelope = json.loads(service.worm_store.get_object(snap_row["worm_key"], snap_row["worm_version_id"]).decode("utf-8"))
    signed_snapshot = envelope["signed_snapshot"]
    proof = proof_for_event(result.event_hash, signed_snapshot["event_hashes"])
    assert verify_merkle_proof(result.event_hash, proof, signed_snapshot["merkle_root"])
