from types import SimpleNamespace

from flask import Flask

from web.services.operational_read_revision import read_authorized_revisions


def setup_reader(monkeypatch, tmp_path):
    from lex.retrieval import normativa_catalog
    path = tmp_path / "catalogue.sqlite"
    path.write_bytes(b"synthetic")
    monkeypatch.setattr(normativa_catalog, "runtime_general_path", lambda: path)
    monkeypatch.setattr("web.services.storage_runtime.get_request_studio_db", lambda _: object())
    monkeypatch.setattr("web.services.tenant_paths.tenant_data_path", lambda *_, **__: "controlled")
    monkeypatch.setattr("pct.operational_live.read_live_revisions", lambda *_: {})
    monkeypatch.setattr("web.services.operational_live_sources.read_vertical_revisions", lambda *_: {})
    return path


def test_catalogue_invalidation_changes_without_document_reads(monkeypatch, tmp_path):
    path = setup_reader(monkeypatch, tmp_path)
    user = SimpleNamespace(ha_permesso=lambda permission: permission == "ai.usa")
    with Flask(__name__).app_context():
        first = read_authorized_revisions(user, requested_domains={"normativa"})
        assert first == read_authorized_revisions(user, requested_domains={"normativa"})
        path.write_bytes(b"new synthetic catalogue identity")
        second = read_authorized_revisions(user, requested_domains={"normativa"})
        assert second != first
        assert 0 <= second["normativa"] < 2 ** 48


def test_unauthorized_or_unrequested_domain_is_not_inspected(monkeypatch, tmp_path):
    setup_reader(monkeypatch, tmp_path)
    def forbidden_read():
        raise AssertionError("No catalog inspection without permission")
    monkeypatch.setattr("lex.retrieval.normativa_catalog.catalog_revision", forbidden_read)
    with Flask(__name__).app_context():
        assert read_authorized_revisions(SimpleNamespace(ha_permesso=lambda _: False)) == {}
        assert read_authorized_revisions(SimpleNamespace(ha_permesso=lambda _: True), requested_domains={"agenda"}) == {}


def test_permission_matches_normative_consultation(monkeypatch, tmp_path):
    setup_reader(monkeypatch, tmp_path)
    with Flask(__name__).app_context():
        user = SimpleNamespace(ha_permesso=lambda permission: permission == "fascicoli.leggi")
        assert "normativa" in read_authorized_revisions(user, requested_domains={"normativa"})


def test_committed_tenant_update_invalidates_only_its_projection(monkeypatch, tmp_path):
    import sqlite3
    from web.services.operational_live_sources import legal_source_file_revision
    from web.services.react_payload_cache import ReactPayloadTTLCache
    setup_reader(monkeypatch, tmp_path)
    tenant_a = tmp_path / "a" / "legal_updates.db"
    tenant_b = tmp_path / "b" / "legal_updates.db"
    for path in (tenant_a, tenant_b):
        path.parent.mkdir()
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE news (id INTEGER PRIMARY KEY, title TEXT)")
    selected = [tenant_a]
    monkeypatch.setattr("web.services.tenant_paths.tenant_data_path",
                        lambda key, *_, **__: str(selected[0]) if key == "LEGAL_UPDATES_DB" else "")
    user = SimpleNamespace(ha_permesso=lambda permission: permission == "ai.usa")
    cache = ReactPayloadTTLCache()
    with Flask(__name__).app_context():
        with sqlite3.connect(tenant_a) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            before = read_authorized_revisions(user, requested_domains={"normativa"})
            cache.set(tuple(before.items()), b"old response")
            conn.execute("INSERT INTO news(title) VALUES (?)", ("synthetic source",))
            conn.commit()
            after = read_authorized_revisions(user, requested_domains={"normativa"})
            assert before != after
            assert cache.get(tuple(after.items())) is None
            selected[0] = tenant_b
            isolated = legal_source_file_revision()
            conn.execute("INSERT INTO news(title) VALUES (?)", ("another synthetic source",))
            conn.commit()
            assert legal_source_file_revision() == isolated
    assert not (tmp_path / "b" / "legal_intelligence_repository.db").exists()


def test_missing_tenant_context_does_not_fall_back_to_global_files(monkeypatch):
    import pytest
    from web.services.operational_live_sources import legal_source_file_revision
    from web.services.tenant_paths import TenantDataPathError
    def blocked(*args, **kwargs):
        assert kwargs["require_tenant"] is True
        raise TenantDataPathError("Missing tenant")
    monkeypatch.setattr("web.services.tenant_paths.tenant_data_path", blocked)
    with pytest.raises(TenantDataPathError):
        legal_source_file_revision()


def test_shared_cassazione_commit_invalidates_legal_views_without_body_reads(monkeypatch, tmp_path):
    import sqlite3
    setup_reader(monkeypatch, tmp_path)
    shared = tmp_path / "public"
    shared.mkdir()
    database = shared / "giurisprudenza_corpus.db"
    user = SimpleNamespace(ha_permesso=lambda permission: permission == "ai.usa")
    app = Flask(__name__)
    app.config["IUSENTRA_SENTENZEWEB_DIRECTORY"] = str(shared)
    with app.app_context(), sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE public_cases(id INTEGER PRIMARY KEY)")
        connection.commit()
        before = read_authorized_revisions(user, requested_domains={"normativa"})
        connection.execute("INSERT INTO public_cases DEFAULT VALUES")
        connection.commit()
        assert read_authorized_revisions(user, requested_domains={"normativa"}) != before
