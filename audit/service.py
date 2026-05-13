"""Audit emission service.

Flow guarantee: no event is reported as emitted unless the signed evidence
object has been written to WORM storage first. The SQL repository is updated
only after the immutable write succeeds.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import uuid
from typing import Any

from .canonical import canonicalize
from .exceptions import AuditConfigError, AuditError, AuditIndexError, AuditValidationError
from .hashing import HASH_ALG, is_sha256_hex, sha256_bytes, sha256_canonical, sha256_file
from .models import AuditEmitResult, AuditVerificationResult
from .repository import AuditRepository
from .schemas import (
    ENVELOPE_VERSION,
    EVENT_VERSION,
    RECEIPT_VERSION,
    ActorContext,
    AuditEventIndexRecord,
    AuditFileRef,
    AuditKind,
    SourceContext,
)
from .signing import AuditSigner, build_signing_payload, signer_from_config
from .worm import S3WormStore, WormPutResult, retention_until_for_years, worm_config_from_env


_FORBIDDEN_PAYLOAD_KEYS = {
    "body",
    "content",
    "raw",
    "raw_content",
    "html",
    "eml",
    "file_bytes",
    "document_bytes",
    "testo_integrale",
    "contenuto_integrale",
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _new_id() -> str:
    if hasattr(uuid, "uuid7"):
        return str(uuid.uuid7())
    return str(uuid.uuid4())


def _safe_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    forbidden = ("secret", "password", "token", "authorization", "bearer")
    lowered = text.lower()
    if any(item in lowered for item in forbidden):
        return f"{type(exc).__name__}: errore riservato redatto"
    return text[:800]


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    return default if not text else text in {"1", "true", "yes", "on"}


def _kind_value(kind: AuditKind | str) -> str:
    if isinstance(kind, AuditKind):
        return kind.value
    value = str(kind or "").strip().upper()
    try:
        return AuditKind(value).value
    except ValueError as exc:
        raise AuditValidationError(f"Audit kind non ammesso: {value}.") from exc


def _validate_payload_minimal(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, raw in value.items():
            key_text = str(key or "").strip()
            if key_text.lower() in _FORBIDDEN_PAYLOAD_KEYS:
                raise AuditValidationError(f"{path}.{key_text} contiene contenuto integrale non ammesso.")
            _validate_payload_minimal(raw, path=f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, raw in enumerate(value):
            _validate_payload_minimal(raw, path=f"{path}[{index}]")
    elif isinstance(value, str) and len(value) > 4096:
        raise AuditValidationError(f"{path} troppo esteso per payload probatorio minimale.")


class AuditService:
    def __init__(
        self,
        *,
        repository: AuditRepository,
        worm_store: Any,
        signer: AuditSigner,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.repository = repository
        self.worm_store = worm_store
        self.signer = signer
        self.config = dict(config or {})
        self.env = str(self.config.get("AUDIT_ENV") or os.getenv("AUDIT_ENV") or "development").strip().lower()
        self.enabled = _bool(self.config.get("AUDIT_ENABLED") if "AUDIT_ENABLED" in self.config else os.getenv("AUDIT_ENABLED"), True)
        self.require_worm = _bool(
            self.config.get("AUDIT_REQUIRE_WORM") if "AUDIT_REQUIRE_WORM" in self.config else os.getenv("AUDIT_REQUIRE_WORM"),
            True,
        )
        self.require_signature = _bool(
            self.config.get("AUDIT_REQUIRE_SIGNATURE") if "AUDIT_REQUIRE_SIGNATURE" in self.config else os.getenv("AUDIT_REQUIRE_SIGNATURE"),
            True,
        )
        retention = int(self.config.get("AUDIT_RETENTION_YEARS") or self.config.get("AUDIT_WORM_RETENTION_YEARS") or os.getenv("AUDIT_RETENTION_YEARS") or os.getenv("AUDIT_WORM_RETENTION_YEARS") or 10)
        if retention < 10:
            raise AuditConfigError("Retention audit inferiore a 10 anni non ammessa.")
        self.retention_years = retention
        if self.env == "production":
            if not self.require_worm:
                raise AuditConfigError("In produzione AUDIT_REQUIRE_WORM=false e' vietato.")
            if not self.require_signature:
                raise AuditConfigError("In produzione AUDIT_REQUIRE_SIGNATURE=false e' vietato.")

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> "AuditService":
        cfg = dict(config or {})
        env = str(cfg.get("AUDIT_ENV") or os.getenv("AUDIT_ENV") or "development").strip().lower()
        database_url = str(cfg.get("AUDIT_DATABASE_URL") or os.getenv("AUDIT_DATABASE_URL") or "").strip()
        data_root = str(cfg.get("PCT_DATA_ROOT") or os.getenv("PCT_DATA_ROOT") or "").strip()
        default_sqlite = str(Path(data_root) / "audit" / "legal_audit_index.db") if data_root else "data/audit/legal_audit_index.db"
        sqlite_path = str(cfg.get("AUDIT_INDEX_SQLITE") or os.getenv("AUDIT_INDEX_SQLITE") or default_sqlite)
        if env == "production" and not database_url.startswith(("postgres://", "postgresql://")):
            raise AuditConfigError("In produzione l'indice audit deve usare PostgreSQL.")
        repository = AuditRepository(postgres_dsn=database_url if database_url.startswith(("postgres://", "postgresql://")) else "", sqlite_path=sqlite_path if not database_url else None)
        worm_store = S3WormStore(worm_config_from_env(cfg))
        signer = signer_from_config(cfg)
        return cls(repository=repository, worm_store=worm_store, signer=signer, config=cfg)

    def emit_event(
        self,
        *,
        kind: AuditKind | str,
        tenant_id: str,
        fascicolo_id: str,
        actor: ActorContext,
        payload: dict[str, Any],
        files: list[AuditFileRef],
        source: SourceContext,
        idempotency_key: str,
    ) -> AuditEmitResult:
        if not self.enabled:
            raise AuditConfigError("Audit probatorio disabilitato: emissione evento rifiutata.")
        kind_value = _kind_value(kind)
        tenant = str(tenant_id or "").strip()
        fascicolo = str(fascicolo_id or "").strip()
        idem = str(idempotency_key or "").strip()
        if not tenant:
            raise AuditValidationError("tenant_id obbligatorio.")
        if not fascicolo:
            raise AuditValidationError("fascicolo_id obbligatorio.")
        if not idem:
            raise AuditValidationError("idempotency_key obbligatoria.")
        actor.validate()
        source = replace(source, idempotency_key=source.idempotency_key or idem)
        source.validate()
        _validate_payload_minimal(payload)
        for file_ref in files:
            file_ref.validate()

        chain_key = self.repository.chain_key(tenant, fascicolo)
        worm_written = False
        failure_stage = "emit_prepare"
        try:
            with self.repository.transaction(chain_key=chain_key) as conn:
                existing = self.repository.find_by_idempotency(tenant, fascicolo, idem, conn=conn)
                if existing:
                    return AuditEmitResult(
                        event_id=str(existing.get("event_id") or ""),
                        event_hash=str(existing.get("event_hash") or ""),
                        worm_uri=f"s3://{existing.get('worm_bucket')}/{existing.get('worm_key')}?versionId={existing.get('worm_version_id')}",
                        worm_bucket=str(existing.get("worm_bucket") or ""),
                        worm_key=str(existing.get("worm_key") or ""),
                        worm_version_id=str(existing.get("worm_version_id") or ""),
                        worm_retention_until=str(existing.get("worm_retention_until") or ""),
                        indexed=True,
                        warnings=("idempotency_key_gia_emessa",),
                    )
                self.worm_store.assert_bucket_worm_ready()
                prev_hash = self.repository.last_event_hash(tenant, fascicolo, conn=conn)
                normalised_files = self._normalise_files(files)
                event_id = _new_id()
                event_ts = _now()
                signed_event = self._build_event(
                    event_id=event_id,
                    tenant_id=tenant,
                    fascicolo_id=fascicolo,
                    actor=actor,
                    kind=kind_value,
                    event_ts_utc=event_ts,
                    source=source,
                    prev_event_hash=prev_hash or None,
                    payload=payload,
                    files=normalised_files,
                )
                event_bytes = canonicalize(signed_event)
                event_hash = sha256_bytes(event_bytes)
                signing_payload = build_signing_payload(signed_event=signed_event, event_hash=event_hash)
                signature = self.signer.sign(signing_payload, event_format_version=EVENT_VERSION).to_dict()
                envelope = {
                    "format": ENVELOPE_VERSION,
                    "signed_event": signed_event,
                    "event_hash": event_hash,
                    "signature": signature,
                }
                envelope_bytes = canonicalize(envelope)
                retention_until = retention_until_for_years(self.retention_years)
                worm_key = self._event_worm_key(tenant, fascicolo, event_ts, event_id)
                failure_stage = "worm_event_upload"
                put_result = self.worm_store.put_immutable_json(
                    worm_key,
                    envelope_bytes,
                    retention_until,
                    {
                        "audit-format": ENVELOPE_VERSION,
                        "event-id": event_id,
                        "event-hash": event_hash,
                        "tenant-id": tenant,
                        "fascicolo-id": fascicolo,
                    },
                )
                worm_written = True
                failure_stage = "worm_receipt_upload"
                receipt_result = self._write_worm_receipt(
                    event_id=event_id,
                    event_hash=event_hash,
                    put_result=put_result,
                    retention_until=retention_until,
                )
                record = AuditEventIndexRecord(
                    event_id=event_id,
                    tenant_id=tenant,
                    fascicolo_id=fascicolo,
                    actor_id=str(actor.actor_id or ""),
                    kind=kind_value,
                    event_ts_utc=event_ts,
                    event_hash=event_hash,
                    prev_event_hash=prev_hash or "",
                    payload_hash=sha256_canonical(payload),
                    files_hashes_jsonb={"files": normalised_files},
                    signature_alg=str(signature.get("alg") or ""),
                    signer_kid=str(signature.get("kid") or ""),
                    signer_cert_fingerprint=str(signature.get("cert_fingerprint") or ""),
                    worm_bucket=put_result.bucket,
                    worm_key=put_result.key,
                    worm_version_id=put_result.version_id,
                    worm_retention_until=put_result.retention_until,
                    snapshot_id="",
                    idempotency_key=idem,
                    created_at=_now(),
                )
                failure_stage = "index_after_worm"
                self.repository.insert_event(record, conn=conn)
                return AuditEmitResult(
                    event_id=event_id,
                    event_hash=event_hash,
                    worm_uri=put_result.uri,
                    worm_bucket=put_result.bucket,
                    worm_key=put_result.key,
                    worm_version_id=put_result.version_id,
                    worm_retention_until=put_result.retention_until,
                    indexed=True,
                    receipt_worm_key=receipt_result.key,
                    receipt_worm_version_id=receipt_result.version_id,
                )
        except Exception as exc:
            if worm_written:
                self.record_failure_safe(
                    tenant_id=tenant,
                    fascicolo_id=fascicolo,
                    attempted_kind=kind_value,
                    idempotency_key=idem,
                    failure_stage=failure_stage,
                    exc=exc,
                )
            raise

    def _normalise_files(self, files: list[AuditFileRef]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for file_ref in files:
            digest = str(file_ref.sha256 or "").lower()
            size = file_ref.size_bytes
            if file_ref.path:
                path = Path(file_ref.path)
                digest_from_file = sha256_file(path)
                if digest and digest != digest_from_file:
                    raise AuditValidationError("Hash file fornito non coincide con il contenuto binario.")
                digest = digest_from_file
                size = path.stat().st_size
            if not digest:
                raise AuditValidationError("Hash SHA-256 file mancante.")
            if not is_sha256_hex(digest):
                raise AuditValidationError("Hash SHA-256 file non valido.")
            result.append(
                {
                    "label": str(file_ref.label).strip(),
                    "storage_ref": str(file_ref.storage_ref).strip(),
                    "sha256": digest,
                    "size_bytes": int(size or 0),
                    "mime": str(file_ref.mime or "").strip(),
                }
            )
        return result

    def _build_event(
        self,
        *,
        event_id: str,
        tenant_id: str,
        fascicolo_id: str,
        actor: ActorContext,
        kind: str,
        event_ts_utc: str,
        source: SourceContext,
        prev_event_hash: str | None,
        payload: dict[str, Any],
        files: list[dict[str, Any]],
    ) -> dict[str, Any]:
        display_hash = actor.display_name_hash
        if actor.display_name and not display_hash:
            display_hash = sha256_bytes(actor.display_name.encode("utf-8"))
        return {
            "version": EVENT_VERSION,
            "event_id": event_id,
            "tenant_id": tenant_id,
            "fascicolo_id": fascicolo_id,
            "actor": {
                "actor_id": actor.actor_id,
                "actor_type": actor.actor_type,
                "display_name_hash": display_hash or "",
            },
            "kind": kind,
            "event_ts_utc": event_ts_utc,
            "source": {
                "service": source.service,
                "module": source.module,
                "request_id": source.request_id,
                "idempotency_key": source.idempotency_key,
            },
            "chain": {
                "prev_event_hash": prev_event_hash,
                "hash_alg": HASH_ALG,
                "canonicalization": "RFC8785-JCS",
            },
            "payload": payload,
            "files": files,
        }

    def _event_worm_key(self, tenant_id: str, fascicolo_id: str, event_ts_utc: str, event_id: str) -> str:
        dt = datetime.fromisoformat(event_ts_utc.replace("Z", "+00:00"))
        return (
            f"audit/events/tenant={tenant_id}/fascicolo={fascicolo_id}/"
            f"{dt.year:04d}/{dt.month:02d}/{event_id}.json"
        )

    def _write_worm_receipt(
        self,
        *,
        event_id: str,
        event_hash: str,
        put_result: WormPutResult,
        retention_until: datetime,
    ) -> WormPutResult:
        receipt = {
            "version": RECEIPT_VERSION,
            "event_id": event_id,
            "event_hash": event_hash,
            "worm": {
                "bucket": put_result.bucket,
                "key": put_result.key,
                "version_id": put_result.version_id,
                "retention_until": put_result.retention_until,
                "mode": put_result.mode,
            },
            "created_at_utc": _now(),
        }
        receipt_hash = sha256_canonical(receipt)
        signature = self.signer.sign(
            build_signing_payload(signed_event=receipt, event_hash=receipt_hash),
            event_format_version=RECEIPT_VERSION,
        ).to_dict()
        envelope = {
            "format": "audit-worm-receipt-envelope-v1",
            "receipt": receipt,
            "receipt_hash": receipt_hash,
            "signature": signature,
        }
        key = put_result.key.replace(".json", ".receipt.json")
        return self.worm_store.put_immutable_json(
            key,
            canonicalize(envelope),
            retention_until,
            {"audit-format": RECEIPT_VERSION, "event-id": event_id, "event-hash": event_hash},
        )

    def load_envelope(self, record: dict[str, Any]) -> dict[str, Any]:
        raw = self.worm_store.get_object(str(record["worm_key"]), version_id=str(record.get("worm_version_id") or "") or None)
        return json.loads(raw.decode("utf-8"))

    def verify_envelope(self, envelope: dict[str, Any]) -> AuditVerificationResult:
        errors: list[str] = []
        if envelope.get("format") != ENVELOPE_VERSION:
            errors.append("Formato envelope non valido.")
        signed_event = envelope.get("signed_event")
        if not isinstance(signed_event, dict):
            errors.append("signed_event mancante.")
            signed_event = {}
        expected_hash = sha256_bytes(canonicalize(signed_event))
        if expected_hash != str(envelope.get("event_hash") or "").lower():
            errors.append("Event hash non coerente con JCS.")
        signature = envelope.get("signature") if isinstance(envelope.get("signature"), dict) else {}
        signing_payload = build_signing_payload(signed_event=signed_event, event_hash=expected_hash)
        if not self.signer.verify(signing_payload, signature):
            errors.append("Firma evento non verificata.")
        return AuditVerificationResult(ok=not errors, errors=tuple(errors), details={"event_hash": expected_hash})

    def verify_chain(self, tenant_id: str, fascicolo_id: str) -> AuditVerificationResult:
        rows = self.repository.list_events(tenant_id=tenant_id, fascicolo_id=fascicolo_id, limit=10000)
        errors: list[str] = []
        previous = ""
        for row in rows:
            try:
                envelope = self.load_envelope(row)
                verified = self.verify_envelope(envelope)
                if not verified.ok:
                    errors.extend(f"{row.get('event_id')}: {err}" for err in verified.errors)
                signed_event = envelope.get("signed_event") or {}
                prev = ((signed_event.get("chain") or {}).get("prev_event_hash") or "")
                if prev != previous:
                    errors.append(f"Catena interrotta su {row.get('event_id')}.")
                previous = str(envelope.get("event_hash") or "")
            except Exception as exc:
                errors.append(f"{row.get('event_id')}: {_safe_error(exc)}")
        return AuditVerificationResult(ok=not errors, errors=tuple(errors), details={"events": len(rows)})

    def record_failure_safe(
        self,
        *,
        tenant_id: str = "",
        fascicolo_id: str = "",
        attempted_kind: str = "",
        idempotency_key: str = "",
        failure_stage: str,
        exc: BaseException,
    ) -> None:
        try:
            code = getattr(exc, "code", type(exc).__name__)
            self.repository.record_failure(
                failure_id=_new_id(),
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                attempted_kind=attempted_kind,
                idempotency_key=idempotency_key,
                failure_stage=failure_stage,
                error_code=str(code),
                error_message_sanitized=_safe_error(exc),
            )
        except Exception:
            return


def emit_event(
    kind: AuditKind | str,
    tenant_id: str,
    fascicolo_id: str,
    actor: ActorContext,
    payload: dict[str, Any],
    files: list[AuditFileRef],
    source: SourceContext,
    idempotency_key: str,
    *,
    service: AuditService | None = None,
) -> AuditEmitResult:
    active = service or AuditService.from_config()
    try:
        return active.emit_event(
            kind=kind,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            actor=actor,
            payload=payload,
            files=files,
            source=source,
            idempotency_key=idempotency_key,
        )
    except AuditError:
        raise
    except Exception as exc:
        raise AuditIndexError(_safe_error(exc)) from exc
