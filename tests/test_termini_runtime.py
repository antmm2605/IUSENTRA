"""Guardrail della transizione: nessun ritorno al JSON dopo l'adozione."""
from types import SimpleNamespace

import pytest

from pct.termini_transition import commit_locked, prepare_locked, source_lock
from web.services.termini_runtime import open_termini_runtime


def runtime(source, *, tenant="studio", profile_tenant="studio", adoption=None, database=None):
    return open_termini_runtime(source, anchor=source.parent / "scadenze.json",
        tenant_key=tenant, actor_key="avvocato",
        get_profile=lambda _anchor: SimpleNamespace(tenant_slug=profile_tenant),
        probe=lambda _profile, _tenant: adoption, get_database=lambda _profile: database)


def fence(source, *, tenant="studio", committed=True):
    with source_lock(source):
        prepare_locked(source, tenant=tenant, source_sha256="a" * 64)
        if committed:
            commit_locked(source, tenant=tenant, source_sha256="a" * 64)


def test_adopted_database_without_marker_does_not_create_json(tmp_path):
    source = tmp_path / "termini.json"
    with pytest.raises(RuntimeError, match="Segnale di transizione"):
        runtime(source, adoption=("a" * 64, "backup"))
    assert not source.exists()


def test_prepared_transition_does_not_create_json(tmp_path):
    source = tmp_path / "termini.json"
    fence(source, committed=False)
    with pytest.raises(RuntimeError, match="non confermata"):
        runtime(source)
    assert not source.exists()


def test_cross_tenant_profile_or_marker_rejected(tmp_path):
    source = tmp_path / "termini.json"
    with pytest.raises(RuntimeError, match="altro studio"):
        runtime(source, profile_tenant="altro")
    fence(source, tenant="altro")
    with pytest.raises(RuntimeError, match="non confermata"):
        runtime(source)
    assert not source.exists()


@pytest.mark.parametrize("adoption", [None, ("b" * 64, "backup"), ("a" * 64, "")])
def test_discordant_adoption_never_reads_historical_json(tmp_path, adoption):
    source = tmp_path / "termini.json"
    source.write_text('{"dato":"preservato"}', encoding="utf-8")
    original = source.read_bytes()
    fence(source)
    with pytest.raises(RuntimeError, match="discordante"):
        runtime(source, adoption=adoption)
    assert source.read_bytes() == original


def test_missing_database_after_commit_is_explicit(tmp_path):
    source = tmp_path / "termini.json"
    fence(source)
    with pytest.raises(RuntimeError, match="indisponibile"):
        runtime(source, adoption=("a" * 64, "backup"))
    assert not source.exists()


def test_confirmed_transition_selects_same_tenant_repository(tmp_path):
    source = tmp_path / "termini.json"
    fence(source)
    database = object()
    result = runtime(source, adoption=("a" * 64, "backup"), database=database)
    assert result.backend == "sql"
    assert result.db is database
    assert result.tenant == "studio"
    assert result.actor == "avvocato"
    assert not source.exists()


def test_existing_legacy_producer_cannot_write_after_fence(tmp_path):
    from pct.termini_processuali import DeadlinePracticeRepository
    source = tmp_path / "termini.json"
    legacy = DeadlinePracticeRepository.json(source)
    original = source.read_bytes()
    fence(source, committed=False)
    with pytest.raises(RuntimeError, match="transizione SQL"):
        legacy._write_json({})
    with pytest.raises(RuntimeError, match="transizione SQL"):
        legacy.list_templates()
    assert source.read_bytes() == original


def test_unreadable_legacy_source_is_preserved(tmp_path):
    from pct.termini_processuali import DeadlinePracticeRepository
    source = tmp_path / "termini.json"
    source.write_bytes(b'{"templates":')
    original = source.read_bytes()
    with pytest.raises(RuntimeError, match="non leggibile"):
        DeadlinePracticeRepository.json(source)
    assert source.read_bytes() == original
