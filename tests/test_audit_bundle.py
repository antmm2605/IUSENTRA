from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from audit.bundle import AuditBundleBuilder
from audit.snapshot_job import AuditSnapshotJob
from scripts.verify_audit import main as verify_main

from tests.audit_test_utils import emit_sample_event, make_service


def test_fascicolo_bundle_is_verifiable_offline(tmp_path) -> None:
    service, _public = make_service()
    result = emit_sample_event(service, tmp_path, idempotency_key="bundle-1")
    AuditSnapshotJob(service).run(tenant_id="tenant-a")
    bundle = AuditBundleBuilder(service).build_fascicolo_bundle(tenant_id="tenant-a", fascicolo_id="FASC-1")
    bundle_path = Path(tmp_path) / bundle.filename
    bundle_path.write_bytes(bundle.content)
    assert bundle.events_count == 1
    with ZipFile(bundle_path, "r") as zf:
        assert f"events/{result.event_id}.json" in zf.namelist()
        assert f"proofs/{result.event_id}.json" in zf.namelist()
        assert "files_manifest.json" in zf.namelist()
    assert verify_main(["verify-bundle", str(bundle_path)]) == 0
