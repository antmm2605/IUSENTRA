import sqlite3

import pytest

from pct.offline_change_log import append_change, ensure_schema, read_changes


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    ensure_schema(connection)
    connection.commit()
    yield connection
    connection.close()


def append(conn, operation="op-1", **changes):
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    values = dict(tenant="studio-a", operation_id=operation, domain="clienti",
                  resource_id="cliente-1", actor="utente-1", source_device="pc-1",
                  base_revision="rev-1", content={"after": {"nome": "Mario"}},
                  allowed_domains=frozenset({"clienti", "agenda"}))
    values.update(changes)
    return append_change(conn, **values)


def page(conn, **changes):
    args = dict(tenant="studio-a", after=0, domains=frozenset({"clienti"}), limit=1,
                authorized_resource=lambda domain, resource: True)
    args.update(changes)
    return read_changes(conn, **args)


def test_commit_order_and_pagination(conn):
    assert append(conn) == 1
    assert append(conn, "op-2", resource_id="cliente-2") == 2
    conn.commit()
    first = page(conn)
    assert first["cursor"] == 1 and first["has_more"]
    second = page(conn, after=first["cursor"])
    assert second["cursor"] == 2 and not second["has_more"]
    assert second["items"][0]["resource_id"] == "cliente-2"


def test_rollback_and_idempotent_retry(conn):
    assert append(conn) == 1
    conn.rollback()
    assert page(conn)["items"] == []
    assert append(conn) == 1
    conn.commit()
    assert append(conn) == 1
    assert append(conn, "op-2") == 2


def test_operation_identity_mismatch_is_explicit(conn):
    append(conn)
    conn.commit()
    for change in ({"content": {"after": {"nome": "Altro"}}},
                   {"resource_id": "cliente-2"}, {"base_revision": "rev-2"},
                   {"source_device": "pc-2"}, {"actor": "utente-2"}):
        with pytest.raises(ValueError, match="differente"):
            append(conn, **change)
        conn.rollback()


def test_tenant_and_permission_boundaries(conn):
    append(conn)
    append(conn, "op-2", domain="agenda")
    append(conn, tenant="studio-b", content={"after": {"nome": "Riservato"}})
    conn.commit()
    assert len(page(conn, limit=100)["items"]) == 1
    assert page(conn, domains=frozenset())["items"] == []
    assert len(page(conn, tenant="studio-b")["items"]) == 1
    assert page(conn, tenant="studio-c")["items"] == []


def test_unknown_domain_and_invalid_cursor_rejected(conn):
    with pytest.raises(ValueError):
        append(conn, domain="invio-pec")
    with pytest.raises(ValueError):
        page(conn, after=-1)
    with pytest.raises(ValueError):
        page(conn, limit=501)


def test_resource_acl_filters_content_and_bounded_cursor_moves(conn):
    append(conn)
    append(conn, "op-2", resource_id="cliente-2")
    denied = page(conn, authorized_resource=lambda domain, resource: resource == "cliente-2")
    assert denied["items"] == [] and denied["cursor"] == 1 and denied["has_more"]
    allowed = page(conn, after=1, authorized_resource=lambda domain, resource: resource == "cliente-2")
    assert allowed["items"][0]["resource_id"] == "cliente-2"


def test_journal_requires_business_transaction(conn):
    with pytest.raises(RuntimeError, match="transazione"):
        append_change(conn, tenant="studio-a", operation_id="op-1", domain="clienti",
                      resource_id="cliente-1", actor="utente-1", source_device="pc-1",
                      base_revision="rev-1", content={}, allowed_domains=frozenset({"clienti"}))
