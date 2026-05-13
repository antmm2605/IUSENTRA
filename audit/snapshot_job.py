"""Merkle snapshot generation for WORM audit events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid
from typing import Any

from .canonical import canonicalize
from .exceptions import AuditTimestampError
from .hashing import sha256_bytes
from .merkle import MERKLE_ALG, merkle_proof, merkle_root
from .models import AuditSnapshotResult
from .schemas import SNAPSHOT_VERSION, AuditSnapshotIndexRecord
from .signing import build_signing_payload
from .tsa import AuditTSAClient
from .worm import retention_until_for_years


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_day(value: datetime | None = None) -> tuple[datetime, datetime]:
    base = value or datetime.now(UTC)
    start = datetime(base.year, base.month, base.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AuditSnapshotJob:
    def __init__(self, service: Any, *, tsa_client: AuditTSAClient | None = None) -> None:
        self.service = service
        self.tsa_client = tsa_client or AuditTSAClient.from_config(service.config)

    def run(self, *, period: str = "daily", tenant_id: str | None = None, at: datetime | None = None) -> list[AuditSnapshotResult]:
        if period != "daily":
            raise ValueError("Solo snapshot giornalieri supportati in questa versione.")
        start, end = _parse_day(at)
        tenants = [tenant_id] if tenant_id else self._tenants_with_open_events(_iso(start), _iso(end))
        results: list[AuditSnapshotResult] = []
        for tenant in tenants:
            if not tenant:
                continue
            result = self._run_for_tenant(str(tenant), start, end)
            if result is not None:
                results.append(result)
        return results

    def _tenants_with_open_events(self, start: str, end: str) -> list[str]:
        return self.service.repository.tenants_with_open_events(date_from=start, date_to=end)

    def _run_for_tenant(self, tenant_id: str, start: datetime, end: datetime) -> AuditSnapshotResult | None:
        rows = self.service.repository.list_events(
            tenant_id=tenant_id,
            date_from=_iso(start),
            date_to=_iso(end),
            include_snapshotted=False,
            limit=100000,
        )
        rows = sorted(rows, key=lambda item: (str(item.get("event_ts_utc") or ""), str(item.get("event_id") or "")))
        if not rows:
            return None
        event_ids = [str(row["event_id"]) for row in rows]
        event_hashes = [str(row["event_hash"]) for row in rows]
        snapshot_id = str(uuid.uuid4())
        snapshot = {
            "version": SNAPSHOT_VERSION,
            "snapshot_id": snapshot_id,
            "tenant_id": tenant_id,
            "period_start_utc": _iso(start),
            "period_end_utc": _iso(end),
            "event_ids": event_ids,
            "event_hashes": event_hashes,
            "merkle_root": merkle_root(event_hashes),
            "merkle_alg": MERKLE_ALG,
            "created_at_utc": _now(),
        }
        snapshot_hash = sha256_bytes(canonicalize(snapshot))
        signature = self.service.signer.sign(
            build_signing_payload(signed_event=snapshot, event_hash=snapshot_hash),
            event_format_version=SNAPSHOT_VERSION,
        ).to_dict()
        envelope = {
            "format": "audit-snapshot-envelope-v1",
            "signed_snapshot": snapshot,
            "snapshot_hash": snapshot_hash,
            "signature": signature,
        }
        retention_until = retention_until_for_years(self.service.retention_years)
        ts_token = self.tsa_client.timestamp_hash(snapshot_hash)
        key_base = f"audit/snapshots/tenant={tenant_id}/{start.year:04d}/{start.month:02d}/{start.day:02d}/{snapshot_id}"
        put_result = self.service.worm_store.put_immutable_json(
            key_base + ".json",
            canonicalize(envelope),
            retention_until,
            {
                "audit-format": "audit-snapshot-envelope-v1",
                "snapshot-id": snapshot_id,
                "tenant-id": tenant_id,
                "snapshot-hash": snapshot_hash,
            },
        )
        tsa_key = ""
        if ts_token is not None:
            tsa_payload = ts_token.token if ts_token.content_type == "application/json" else ts_token.token
            tsa_key = key_base + (".nonqualified-timestamp.json" if not ts_token.qualified else ".tsr")
            self.service.worm_store.put_immutable_json(
                tsa_key,
                tsa_payload,
                retention_until,
                {
                    "audit-format": "audit-timestamp-token-v1",
                    "snapshot-id": snapshot_id,
                    "snapshot-hash": snapshot_hash,
                    "qualified": str(ts_token.qualified).lower(),
                },
            )
        with self.service.repository.transaction() as conn:
            self.service.repository.insert_snapshot(
                AuditSnapshotIndexRecord(
                    snapshot_id=snapshot_id,
                    tenant_id=tenant_id,
                    period_start_utc=_iso(start),
                    period_end_utc=_iso(end),
                    merkle_root=snapshot["merkle_root"],
                    events_count=len(event_ids),
                    snapshot_hash=snapshot_hash,
                    signature_alg=str(signature.get("alg") or ""),
                    signer_kid=str(signature.get("kid") or ""),
                    tsa_token_worm_key=tsa_key,
                    worm_bucket=put_result.bucket,
                    worm_key=put_result.key,
                    worm_version_id=put_result.version_id,
                    created_at=_now(),
                ),
                conn=conn,
            )
            self.service.repository.mark_events_snapshot(event_ids, snapshot_id, conn=conn)
        return AuditSnapshotResult(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            period_start_utc=_iso(start),
            period_end_utc=_iso(end),
            events_count=len(event_ids),
            merkle_root=snapshot["merkle_root"],
            snapshot_hash=snapshot_hash,
            worm_uri=put_result.uri,
            tsa_token_worm_key=tsa_key,
        )


def audit_snapshot_job(period: str = "daily", tenant_id: str | None = None, *, service: Any | None = None) -> list[AuditSnapshotResult]:
    from .service import AuditService

    active_service = service or AuditService.from_config()
    return AuditSnapshotJob(active_service).run(period=period, tenant_id=tenant_id)


def proof_for_event(event_hash: str, ordered_event_hashes: list[str]) -> list[dict[str, str]]:
    return [step.to_dict() for step in merkle_proof(event_hash, ordered_event_hashes)]
