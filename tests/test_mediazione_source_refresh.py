"""Small SQL guards for the refresh observed on the real local mediazione UI.

The optional DSN must name an isolated test schema, never a tenant database.
Each test gets a distinct registry number; no operational tables are cleared.
"""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from pct.mediazione_directory_repository import MediazioneDirectoryRepository
from pct.mediazione_source_history import acquisition_outcome, source_status
from pct.mediazione_source_refresh import claim_jobs, finish_job, seed_jobs

NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path):
    repository = MediazioneDirectoryRepository(tmp_path / "public.db", postgres_dsn=os.getenv("MEDIAZIONE_TEST_DSN", ""))
    number = "test-" + uuid4().hex
    row = dict(registration_number=number, registry_kind="organismo", name="Organismo di prova controllata",
               is_active=True, website="https://organismo.example.test/")
    repository.import_registry([row], source="https://mediazione.giustizia.it/ROM/", checked_at=NOW.isoformat())
    return repository, number, row


def evidence(number, *, after=0, contacts=None, errors=None, remaining=None):
    return dict(registration_number=number, checked_at=(NOW + timedelta(minutes=after)).isoformat(),
                status="fonti_senza_canale_rilevato", identity_match=True,
                pages=[dict(status=200, parsed=True, url="https://organismo.example.test/", sha256="a" * 64)],
                contacts=contacts or [], resources=[], errors=errors or [], remaining_urls=remaining or [])


def job_for(repo, number, *, now=NOW):
    seed_jobs(repo, now=now)
    # Other parametrized tests may share the isolated PostgreSQL schema.
    with repo.connection() as conn:
        conn.execute("UPDATE mediazione_source_jobs SET due_at=? WHERE registration_number<>?",
                     ((now + timedelta(days=30)).isoformat(), number))
    return next(j for j in claim_jobs(repo, now=now, limit=20) if j["registration_number"] == number)


def test_full_then_error_preserves_success_and_revision(repo):
    r, number, _ = repo
    r.save_channel_check(number, evidence(number))
    r.save_channel_check(number, dict(evidence(number, after=1), pages=[], errors=[{"error": "Timeout"}]))
    status = source_status(r, number, now=NOW + timedelta(minutes=2))
    assert status["stato"] == "fonte_non_raggiunta"
    assert status["revisione"] == 1
    assert status["ultima_acquisizione"] == NOW.isoformat()
    assert status["invio_autorizzato"] is False


def test_semantic_change_versions_but_page_banner_does_not(repo):
    r, number, _ = repo
    r.save_channel_check(number, evidence(number))
    changed_markup = evidence(number, after=1)
    changed_markup["pages"][0]["sha256"] = "b" * 64
    r.save_channel_check(number, changed_markup)
    assert source_status(r, number, now=NOW)["revisione"] == 1
    contact = dict(address="istanze@pec.example.test", source_url="https://organismo.example.test/",
                   excerpt="Inviare la domanda via PEC", pec_explicit=True, filing_context=True)
    r.save_channel_check(number, evidence(number, after=2, contacts=[contact]))
    status = source_status(r, number, now=NOW)
    assert status["revisione"] == 2
    assert status["ultima_variazione"] == (NOW + timedelta(minutes=2)).isoformat()
    assert status["invio_autorizzato"] is False


def test_old_observation_is_audited_without_overwriting_latest(repo):
    r, number, _ = repo
    r.save_channel_check(number, evidence(number, after=2))
    r.save_channel_check(number, evidence(number, after=1))
    assert source_status(r, number, now=NOW)["ultimo_controllo"] == (NOW + timedelta(minutes=2)).isoformat()
    with r.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM mediazione_source_history WHERE registration_number=? AND outcome='esito_superato'", (number,)).fetchone()[0] == 1


@pytest.mark.parametrize("pages", [[], [{"status": 200}], [{"status": 404, "parsed": True}]])
def test_http_success_alone_is_not_an_acquisition(pages):
    assert acquisition_outcome({"pages": pages}) == "non_acquisita"


def test_partial_never_replaces_last_success(repo):
    r, number, _ = repo
    r.save_channel_check(number, evidence(number))
    r.save_channel_check(number, evidence(number, after=1, remaining=["https://organismo.example.test/moduli"]))
    assert source_status(r, number, now=NOW)["stato"] == "acquisizione_parziale"
    assert source_status(r, number, now=NOW)["revisione"] == 1


def test_job_claim_is_exclusive_and_expired_completion_is_rejected(repo):
    r, number, _ = repo
    old = job_for(r, number)
    assert not any(j["registration_number"] == number for j in claim_jobs(r, now=NOW))
    later = NOW + timedelta(minutes=16)
    new = next(j for j in claim_jobs(r, now=later) if j["registration_number"] == number)
    assert finish_job(r, old, evidence(number), now=later) == "esito_superato"
    assert finish_job(r, new, evidence(number, after=16), now=later) == "acquisita"


def test_changed_registry_during_fetch_invalidates_old_job_without_seed(repo):
    r, number, row = repo
    old = job_for(r, number)
    r.import_registry([dict(row, website="https://nuovo.example.test/")], source="ministero", checked_at=NOW.isoformat())
    assert finish_job(r, old, evidence(number), now=NOW) == "esito_superato"
    assert source_status(r, number)["stato"] == "da_controllare"


def test_inactive_organism_cannot_finish_or_be_reclaimed(repo):
    r, number, row = repo
    old = job_for(r, number)
    r.import_registry([dict(row, is_active=False)], source="ministero", checked_at=NOW.isoformat())
    assert finish_job(r, old, evidence(number), now=NOW) == "organismo_non_attivo"
    assert not any(j["registration_number"] == number for j in claim_jobs(r, now=NOW))


def test_refresh_continuation_is_durable_and_success_is_due_in_seven_days(repo):
    r, number, _ = repo
    job = job_for(r, number)
    assert finish_job(r, job, evidence(number, remaining=["https://organismo.example.test/moduli"]), now=NOW) == "acquisizione_parziale"
    with r.connection() as conn:
        row = conn.execute("SELECT * FROM mediazione_source_jobs WHERE registration_number=?", (number,)).fetchone()
    assert row["due_at"] == (NOW + timedelta(minutes=10)).isoformat()
    later = NOW + timedelta(minutes=11)
    new = next(j for j in claim_jobs(r, now=later) if j["registration_number"] == number)
    assert new["organism"]["channel_check"]["remaining_urls"]
    assert finish_job(r, new, evidence(number, after=11), now=later) == "acquisita"
    assert source_status(r, number, now=later + timedelta(days=8))["stato"] == "da_aggiornare"


@pytest.mark.parametrize("timestamp", ["2026-09-05T12:00:00", "2099-01-01T00:00:00+00:00"])
def test_invalid_clock_is_rejected_without_persistence(repo, timestamp):
    r, number, _ = repo
    with pytest.raises(ValueError):
        r.save_channel_check(number, dict(evidence(number), checked_at=timestamp))
    assert source_status(r, number)["stato"] == "da_controllare"
