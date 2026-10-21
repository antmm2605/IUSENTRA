import base64
import hashlib
import sqlite3
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pct.offline_replication import (
    SignedOperation, enroll_device, ensure_schema, reserve_operation,
    revoke_device, verify_operation,
)


@pytest.fixture
def pc():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    private = Ed25519PrivateKey.generate()
    public = base64.b64encode(private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    enroll_device(conn, tenant="studio-a", device="pc-a", public_key=public,
                  actor="admin", now=100, expires_at=1000)
    conn.commit()
    operation = SignedOperation("studio-a", "pc-a", "operation-1", "server-a",
                                200, 300, "clienti", "cliente-1", "revision-1", {"nome": "Mario"})
    yield conn, private, public, operation
    conn.close()


def verify(conn, private, operation, **kwargs):
    signature = base64.b64encode(private.sign(operation.canonical_bytes())).decode()
    return verify_operation(conn, operation, signature, authenticated_tenant="studio-a",
                            expected_audience="server-a", now=kwargs.get("now", 250))


def test_commit_retry_and_rollback(pc):
    conn, private, _, operation = pc
    digest = verify(conn, private, operation)
    assert reserve_operation(conn, operation, digest, now=250)
    conn.rollback()
    assert reserve_operation(conn, operation, digest, now=251)
    conn.commit()
    assert not reserve_operation(conn, operation, digest, now=252)
    assert conn.execute("SELECT count(*) FROM offline_received_operations").fetchone()[0] == 1


@pytest.mark.parametrize("changes", [
    {"tenant": "studio-b"}, {"device": "pc-b"}, {"audience": "server-b"},
    {"issued_at": 251}, {"expires_at": 250}, {"expires_at": 600},
])
def test_scope_expiry_and_unknown_device_rejected(pc, changes):
    conn, private, _, operation = pc
    with pytest.raises(PermissionError):
        verify(conn, private, replace(operation, **changes))


def test_revocation_rejects_even_replayed_operation(pc):
    conn, private, _, operation = pc
    verify(conn, private, operation)
    assert revoke_device(conn, tenant="studio-a", device="pc-a", now=240)
    assert not revoke_device(conn, tenant="studio-a", device="pc-a", now=241)
    with pytest.raises(PermissionError):
        verify(conn, private, operation)


def test_key_replacement_not_allowed(pc):
    conn, _, public, _ = pc
    with pytest.raises(sqlite3.IntegrityError):
        enroll_device(conn, tenant="studio-a", device="pc-a", public_key=public,
                      actor="admin", now=101, expires_at=1100)


def test_changed_payload_same_id_is_not_a_retry(pc):
    conn, private, _, operation = pc
    reserve_operation(conn, operation, verify(conn, private, operation), now=250)
    changed = replace(operation, payload={"nome": "Altro"})
    with pytest.raises(ValueError, match="operazione diversa"):
        reserve_operation(conn, changed, verify(conn, private, changed), now=251)


def test_signature_binds_payload_and_revision(pc):
    conn, private, _, operation = pc
    signature = base64.b64encode(private.sign(operation.canonical_bytes())).decode()
    for changed in (replace(operation, payload={"nome": "Altro"}),
                    replace(operation, base_revision="revision-2")):
        with pytest.raises(PermissionError, match="Firma"):
            verify_operation(conn, changed, signature, authenticated_tenant="studio-a",
                             expected_audience="server-a", now=250)


def test_canonical_order_and_invalid_payload(pc):
    _, _, _, operation = pc
    assert replace(operation, payload={"a": 1, "b": 2}).canonical_bytes() == replace(
        operation, payload={"b": 2, "a": 1}).canonical_bytes()
    with pytest.raises(ValueError):
        replace(operation, payload={"value": float("nan")}).canonical_bytes()
    with pytest.raises(ValueError):
        replace(operation, payload={"value": "x" * (1024 * 1024)}).canonical_bytes()


def test_canonical_wire_preserves_numeric_and_unicode_bytes(pc):
    _, private, _, operation = pc
    operation = replace(operation, payload={
        "a": 20.0, "small": 1e-07, "\ue000": 1, "💼": -0.0,
    })
    wire = operation.canonical_bytes()
    decoded = SignedOperation.from_canonical(wire)
    assert decoded.canonical_bytes() == wire
    assert b'20.0' in wire and b'1e-07' in wire and b'-0.0' in wire
    private.public_key().verify(private.sign(wire), decoded.canonical_bytes())
    from cryptography.exceptions import InvalidSignature
    rewritten = SignedOperation.from_canonical(wire.replace(b'20.0', b'20'))
    with pytest.raises(InvalidSignature):
        private.public_key().verify(private.sign(wire), rewritten.canonical_bytes())


@pytest.mark.parametrize("mutation", [
    lambda raw: b' ' + raw,
    lambda raw: raw.replace(b'"protocol":1', b'"protocol":true'),
    lambda raw: raw.replace(b'"protocol":1', b'"protocol":1,"protocol":1'),
    lambda raw: raw.replace(b'"protocol":1', b'"protocol":1,"unknown":0'),
])
def test_noncanonical_wire_is_rejected(pc, mutation):
    operation = replace(pc[3], payload={"amount": 20.0})
    with pytest.raises(ValueError):
        SignedOperation.from_canonical(mutation(operation.canonical_bytes()))


def test_browser_signature_vector_matches_python():
    private = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    operation = SignedOperation(
        'studio-test', 'pc-controlled-test', 'op-bytes-test', 'https://app.iusentra.it',
        1792610000, 1792610100, 'timesheet', 'entry-test', 'base',
        {'after': {'a': 20.0, 'small': 1e-07, '\ue000': 1, '💼': -0.0}, 'before': None},
        actor='admin-test')
    raw = operation.canonical_bytes()
    assert SignedOperation.from_canonical(raw) == operation
    assert base64.b64encode(private.sign(raw)).decode() == (
        'LqK2vLrK3jj/EIX69RCVXF3aUZwVBw0kMJatocM3y8N+3R38Awi9Sy0esRH9XnY5OsvEHGNd4WjuoJlV1U/gBg==')


def test_schema_does_not_commit_callers_transaction():
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE business(value TEXT)")
        conn.execute("INSERT INTO business VALUES ('bozza')")
        ensure_schema(conn)
        conn.rollback()
        assert conn.execute("SELECT count(*) FROM business").fetchone()[0] == 0


def test_unverified_digest_not_reserved(pc):
    conn, _, _, operation = pc
    with pytest.raises(ValueError, match="Impronta"):
        reserve_operation(conn, operation, hashlib.sha256(b"altro").hexdigest(), now=250)


def test_retry_resigned_after_disconnect_preserves_operation_identity(pc):
    conn, private, _, operation = pc
    digest = verify(conn, private, operation)
    assert reserve_operation(conn, operation, digest, now=250)
    conn.commit()
    resumed = replace(operation, issued_at=600, expires_at=700)
    resumed_digest = verify(conn, private, resumed, now=650)
    assert resumed_digest == digest
    assert not reserve_operation(conn, resumed, resumed_digest, now=650)
