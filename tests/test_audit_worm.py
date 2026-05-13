from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from audit.exceptions import AuditConfigError, AuditWormError
from audit.worm import InMemoryWormStore, S3WormStore, WormConfig


class _FakeS3NoObjectLock:
    def head_bucket(self, **_kwargs):
        return {}

    def get_bucket_versioning(self, **_kwargs):
        return {"Status": "Enabled"}

    def get_object_lock_configuration(self, **_kwargs):
        return {"ObjectLockConfiguration": {"ObjectLockEnabled": "Disabled"}}


def test_in_memory_worm_rejects_overwrite() -> None:
    store = InMemoryWormStore()
    retention = datetime.now(UTC) + timedelta(days=3650)
    first = store.put_immutable_json("audit/events/e1.json", b"{}", retention, {"event-id": "e1"})
    assert first.version_id
    with pytest.raises(AuditWormError):
        store.put_immutable_json("audit/events/e1.json", b'{"changed":true}', retention, {})


def test_worm_store_does_not_expose_delete_api() -> None:
    assert not hasattr(S3WormStore, "delete_object")
    assert not hasattr(InMemoryWormStore, "delete_object")


def test_production_worm_requires_compliance_mode() -> None:
    with pytest.raises(AuditConfigError):
        WormConfig(
            endpoint_url="",
            region="eu-central-1",
            bucket="audit",
            access_key="a",
            secret_key="b",
            mode="GOVERNANCE",
            env="production",
        ).validate()


def test_s3_worm_rejects_bucket_without_object_lock() -> None:
    store = S3WormStore(
        WormConfig(endpoint_url="", region="eu-central-1", bucket="audit", access_key="a", secret_key="b"),
        client=_FakeS3NoObjectLock(),
    )
    with pytest.raises(AuditWormError):
        store.assert_bucket_worm_ready()
