"""S3-compatible WORM storage with Object Lock enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import os
from typing import Any, Iterable

from .exceptions import AuditConfigError, AuditWormError


@dataclass(frozen=True)
class WormPutResult:
    bucket: str
    key: str
    version_id: str
    retention_until: str
    mode: str
    etag: str = ""

    @property
    def uri(self) -> str:
        version = f"?versionId={self.version_id}" if self.version_id else ""
        return f"s3://{self.bucket}/{self.key}{version}"


@dataclass(frozen=True)
class WormConfig:
    endpoint_url: str
    region: str
    bucket: str
    access_key: str
    secret_key: str
    retention_years: int = 10
    mode: str = "COMPLIANCE"
    require_object_lock: bool = True
    env: str = "development"

    @property
    def normalized_mode(self) -> str:
        return self.mode.strip().upper() or "COMPLIANCE"

    def validate(self) -> None:
        if not self.bucket:
            raise AuditConfigError("AUDIT_WORM_BUCKET obbligatorio.")
        if self.retention_years < 10:
            raise AuditConfigError("Retention audit inferiore a 10 anni non ammessa.")
        if self.normalized_mode not in {"COMPLIANCE", "GOVERNANCE"}:
            raise AuditConfigError("AUDIT_WORM_MODE deve essere COMPLIANCE o GOVERNANCE.")
        if self.env.lower() == "production" and self.normalized_mode != "COMPLIANCE":
            raise AuditConfigError("In produzione WORM deve usare Object Lock COMPLIANCE.")


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def worm_config_from_env(config: dict[str, Any] | None = None) -> WormConfig:
    cfg = dict(config or {})
    years = int(cfg.get("AUDIT_WORM_RETENTION_YEARS") or cfg.get("AUDIT_RETENTION_YEARS") or os.getenv("AUDIT_WORM_RETENTION_YEARS") or os.getenv("AUDIT_RETENTION_YEARS") or 10)
    result = WormConfig(
        endpoint_url=str(cfg.get("AUDIT_WORM_ENDPOINT_URL") or os.getenv("AUDIT_WORM_ENDPOINT_URL") or ""),
        region=str(cfg.get("AUDIT_WORM_REGION") or os.getenv("AUDIT_WORM_REGION") or "eu-central-1"),
        bucket=str(cfg.get("AUDIT_WORM_BUCKET") or os.getenv("AUDIT_WORM_BUCKET") or ""),
        access_key=str(cfg.get("AUDIT_WORM_ACCESS_KEY") or os.getenv("AUDIT_WORM_ACCESS_KEY") or ""),
        secret_key=str(cfg.get("AUDIT_WORM_SECRET_KEY") or os.getenv("AUDIT_WORM_SECRET_KEY") or ""),
        retention_years=years,
        mode=str(cfg.get("AUDIT_WORM_MODE") or os.getenv("AUDIT_WORM_MODE") or "COMPLIANCE"),
        require_object_lock=_bool(
            cfg.get("AUDIT_WORM_REQUIRE_OBJECT_LOCK") if "AUDIT_WORM_REQUIRE_OBJECT_LOCK" in cfg else os.getenv("AUDIT_WORM_REQUIRE_OBJECT_LOCK"),
            default=True,
        ),
        env=str(cfg.get("AUDIT_ENV") or os.getenv("AUDIT_ENV") or "development"),
    )
    result.validate()
    return result


def retention_until_for_years(years: int, *, now: datetime | None = None) -> datetime:
    base = now or datetime.now(UTC)
    return base + timedelta(days=int(years) * 365)


class S3WormStore:
    def __init__(self, config: WormConfig, client: Any | None = None) -> None:
        config.validate()
        self.config = config
        if client is not None:
            self.client = client
            return
        try:
            import boto3
        except Exception as exc:  # pragma: no cover - exercised when dependency missing
            raise AuditConfigError("boto3 non disponibile: richiesto per storage WORM S3-compatible.") from exc
        self.client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url or None,
            region_name=config.region or None,
            aws_access_key_id=config.access_key or None,
            aws_secret_access_key=config.secret_key or None,
        )

    @property
    def bucket(self) -> str:
        return self.config.bucket

    def assert_bucket_worm_ready(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception as exc:
            raise AuditWormError("Bucket WORM non raggiungibile.") from exc

        try:
            versioning = self.client.get_bucket_versioning(Bucket=self.bucket)
        except Exception as exc:
            raise AuditWormError("Impossibile verificare versioning bucket WORM.") from exc
        if str(versioning.get("Status") or "").upper() != "ENABLED":
            raise AuditWormError("Bucket WORM rifiutato: versioning non abilitato.")

        if not self.config.require_object_lock:
            if self.config.env.lower() == "production":
                raise AuditWormError("In produzione Object Lock e' obbligatorio.")
            return

        try:
            lock_cfg = self.client.get_object_lock_configuration(Bucket=self.bucket)
        except Exception as exc:
            raise AuditWormError("Bucket WORM rifiutato: Object Lock non verificabile.") from exc
        object_lock = lock_cfg.get("ObjectLockConfiguration") or {}
        if str(object_lock.get("ObjectLockEnabled") or "").upper() != "ENABLED":
            raise AuditWormError("Bucket WORM rifiutato: Object Lock non attivo.")
        default_retention = (object_lock.get("Rule") or {}).get("DefaultRetention") or {}
        default_mode = str(default_retention.get("Mode") or "").upper()
        if self.config.env.lower() == "production" and default_mode and default_mode != "COMPLIANCE":
            raise AuditWormError("Bucket WORM rifiutato: default retention non COMPLIANCE.")

    def _assert_key_absent(self, key: str) -> None:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception:
            return
        raise AuditWormError("Overwrite audit WORM vietato: oggetto gia' presente.")

    def put_immutable_json(
        self,
        key: str,
        data: bytes,
        retention_until: datetime,
        metadata: dict[str, str] | None = None,
    ) -> WormPutResult:
        if not key.strip():
            raise AuditWormError("WORM key mancante.")
        self._assert_key_absent(key)
        kwargs = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
            "ContentType": "application/json; charset=utf-8",
            "Metadata": {str(k): str(v) for k, v in (metadata or {}).items()},
        }
        if self.config.require_object_lock:
            kwargs["ObjectLockMode"] = self.config.normalized_mode
            kwargs["ObjectLockRetainUntilDate"] = retention_until
        response = self.client.put_object(**kwargs)
        version_id = str(response.get("VersionId") or "")
        if self.config.require_object_lock and not version_id:
            raise AuditWormError("Upload WORM senza VersionId: Object Lock non verificabile.")
        head = self.head_object(key, version_id=version_id or None)
        retention = str(head.get("ObjectLockRetainUntilDate") or retention_until.isoformat().replace("+00:00", "Z"))
        mode = str(head.get("ObjectLockMode") or self.config.normalized_mode)
        if self.config.require_object_lock:
            if not mode:
                raise AuditWormError("Oggetto WORM senza modalita Object Lock.")
            if self.config.env.lower() == "production" and mode.upper() != "COMPLIANCE":
                raise AuditWormError("Oggetto WORM non salvato in COMPLIANCE mode.")
        return WormPutResult(
            bucket=self.bucket,
            key=key,
            version_id=version_id,
            retention_until=retention,
            mode=mode,
            etag=str(response.get("ETag") or "").strip('"'),
        )

    def get_object(self, key: str, version_id: str | None = None) -> bytes:
        kwargs: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id
        response = self.client.get_object(**kwargs)
        body = response.get("Body")
        return body.read() if hasattr(body, "read") else bytes(body or b"")

    def head_object(self, key: str, version_id: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id
        return dict(self.client.head_object(**kwargs))

    def list_audit_objects(self, prefix: str) -> Iterable[dict[str, Any]]:
        paginator = self.client.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Versions", []) or []:
                if not item.get("IsLatest", True):
                    continue
                yield {
                    "key": item.get("Key", ""),
                    "version_id": item.get("VersionId", ""),
                    "last_modified": item.get("LastModified"),
                    "size": item.get("Size", 0),
                }

    def prove_immutability_test_object(self) -> WormPutResult:
        now = datetime.now(UTC)
        key = f"audit/immutability-tests/{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        result = self.put_immutable_json(
            key,
            b'{"purpose":"iusentra-audit-worm-immutability-test"}',
            retention_until_for_years(self.config.retention_years, now=now),
            {"purpose": "immutability-test"},
        )
        try:
            self.put_immutable_json(
                key,
                b'{"purpose":"overwrite-must-fail"}',
                retention_until_for_years(self.config.retention_years, now=now),
                {"purpose": "immutability-test-overwrite"},
            )
        except AuditWormError:
            return result
        raise AuditWormError("Test immutabilita fallito: overwrite accettato.")


class InMemoryWormStore:
    """Object-Lock preserving test double; never used by production config."""

    def __init__(self, bucket: str = "test-worm", *, mode: str = "COMPLIANCE") -> None:
        self.bucket = bucket
        self.mode = mode
        self._objects: dict[tuple[str, str], bytes] = {}
        self._heads: dict[tuple[str, str], dict[str, Any]] = {}
        self._latest: dict[str, str] = {}
        self.ready_checked = False

    def assert_bucket_worm_ready(self) -> None:
        self.ready_checked = True

    def put_immutable_json(
        self,
        key: str,
        data: bytes,
        retention_until: datetime,
        metadata: dict[str, str] | None = None,
    ) -> WormPutResult:
        if key in self._latest:
            raise AuditWormError("Overwrite audit WORM vietato: oggetto gia' presente.")
        version_id = f"v{len(self._objects) + 1}"
        self._latest[key] = version_id
        storage_key = (key, version_id)
        retention = retention_until.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self._objects[storage_key] = bytes(data)
        self._heads[storage_key] = {
            "ObjectLockMode": self.mode,
            "ObjectLockRetainUntilDate": retention,
            "Metadata": dict(metadata or {}),
        }
        return WormPutResult(self.bucket, key, version_id, retention, self.mode, etag="")

    def get_object(self, key: str, version_id: str | None = None) -> bytes:
        vid = version_id or self._latest.get(key, "")
        return self._objects[(key, vid)]

    def head_object(self, key: str, version_id: str | None = None) -> dict[str, Any]:
        vid = version_id or self._latest.get(key, "")
        return dict(self._heads[(key, vid)])

    def list_audit_objects(self, prefix: str) -> Iterable[dict[str, Any]]:
        for key, version_id in sorted(self._latest.items()):
            if key.startswith(prefix):
                yield {"key": key, "version_id": version_id, "size": len(self._objects[(key, version_id)])}

    def prove_immutability_test_object(self) -> WormPutResult:
        result = self.put_immutable_json(
            "audit/immutability-tests/test.json",
            b"{}",
            retention_until_for_years(10),
            {},
        )
        try:
            self.put_immutable_json(
                "audit/immutability-tests/test.json",
                b'{"overwrite":true}',
                retention_until_for_years(10),
                {},
            )
        except AuditWormError:
            return result
        raise AuditWormError("Test immutabilita fallito: overwrite accettato.")
