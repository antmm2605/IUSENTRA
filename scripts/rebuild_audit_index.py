#!/usr/bin/env python
"""Rebuild audit index rows from WORM evidence objects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.hashing import sha256_canonical
from audit.schemas import AuditEventIndexRecord
from audit.service import AuditService


def _now_from_event(event: dict) -> str:
    return str(event.get("event_ts_utc") or "")


def rebuild_index(*, tenant_id: str = "", prefix: str = "", dry_run: bool = False) -> dict:
    service = AuditService.from_config()
    service.worm_store.assert_bucket_worm_ready()
    wanted_prefix = prefix or (f"audit/events/tenant={tenant_id}/" if tenant_id else "audit/events/")
    run_id = str(uuid.uuid4())
    if not dry_run:
        service.repository.start_reconciliation(run_id, tenant_id)
    objects_seen = 0
    created = 0
    conflicts = 0
    for obj in service.worm_store.list_audit_objects(wanted_prefix):
        key = str(obj.get("key") or "")
        if not key.endswith(".json") or key.endswith(".receipt.json"):
            continue
        objects_seen += 1
        raw = service.worm_store.get_object(key, version_id=str(obj.get("version_id") or "") or None)
        envelope = json.loads(raw.decode("utf-8"))
        verified = service.verify_envelope(envelope)
        if not verified.ok:
            conflicts += 1
            continue
        event = envelope["signed_event"]
        event_tenant = str(event["tenant_id"])
        if tenant_id and event_tenant != tenant_id:
            continue
        event_id = str(event["event_id"])
        existing = service.repository.get_event(event_id, tenant_id=event_tenant)
        if existing:
            if existing.get("event_hash") != envelope.get("event_hash"):
                conflicts += 1
            continue
        signature = envelope.get("signature") or {}
        worm_head = service.worm_store.head_object(key, version_id=str(obj.get("version_id") or "") or None)
        record = AuditEventIndexRecord(
            event_id=event_id,
            tenant_id=event_tenant,
            fascicolo_id=str(event["fascicolo_id"]),
            actor_id=str((event.get("actor") or {}).get("actor_id") or ""),
            kind=str(event["kind"]),
            event_ts_utc=_now_from_event(event),
            event_hash=str(envelope["event_hash"]),
            prev_event_hash=str((event.get("chain") or {}).get("prev_event_hash") or ""),
            payload_hash=sha256_canonical(event.get("payload") or {}),
            files_hashes_jsonb={"files": event.get("files") or []},
            signature_alg=str(signature.get("alg") or ""),
            signer_kid=str(signature.get("kid") or ""),
            signer_cert_fingerprint=str(signature.get("cert_fingerprint") or ""),
            worm_bucket=str(getattr(service.worm_store, "bucket", "")),
            worm_key=key,
            worm_version_id=str(obj.get("version_id") or ""),
            worm_retention_until=str(worm_head.get("ObjectLockRetainUntilDate") or ""),
            snapshot_id="",
            idempotency_key=str((event.get("source") or {}).get("idempotency_key") or event_id),
            created_at=_now_from_event(event),
        )
        if not dry_run:
            with service.repository.transaction() as conn:
                if service.repository.upsert_event_from_rebuild(record, conn=conn):
                    created += 1
        else:
            created += 1
    status = "OK" if conflicts == 0 else "CONFLICTS"
    if not dry_run:
        service.repository.complete_reconciliation(
            run_id,
            objects_seen=objects_seen,
            missing_index_rows_created=created,
            conflicts_found=conflicts,
            status=status,
        )
    return {
        "run_id": run_id,
        "tenant_id": tenant_id,
        "prefix": wanted_prefix,
        "objects_seen": objects_seen,
        "missing_index_rows_created": created,
        "conflicts_found": conflicts,
        "status": status,
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ricostruisce audit_events_index dagli oggetti WORM.")
    parser.add_argument("--tenant-id", default="")
    parser.add_argument("--prefix", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = rebuild_index(tenant_id=args.tenant_id, prefix=args.prefix, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
