"""Le fonti della mediazione partono all'apertura, non a orario fisso.

Fino alla 2.334.0 il controllo girava ogni dieci minuti. La coda pero' ha
una scadenza per organismo — sette giorni dopo un controllo riuscito — e in
produzione risultava quasi sempre vuota: 144 giri al giorno che rileggevano
quasi cinquecento organismi per scoprire che non era scaduto niente.

Adesso si apre la mediazione e, se c'e' qualcosa di scaduto, si chiede un
giro allo scheduler. La pagina non aspetta la rete, e a orario resta la
sola passata notturna.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from pct.mediazione_directory_repository import MediazioneDirectoryRepository
from pct.mediazione_source_refresh import seed_jobs, verifiche_in_attesa

NOW = datetime(2026, 9, 20, 12, tzinfo=UTC)


@pytest.fixture
def repo(tmp_path):
    repository = MediazioneDirectoryRepository(
        tmp_path / "public.db", postgres_dsn=os.getenv("MEDIAZIONE_TEST_DSN", "")
    )
    numero = "test-" + uuid4().hex
    repository.import_registry(
        [
            dict(
                registration_number=numero,
                registry_kind="organismo",
                name="Organismo di prova",
                is_active=True,
                website="https://organismo.example.test/",
            )
        ],
        source="https://mediazione.giustizia.it/ROM/",
        checked_at=NOW.isoformat(),
    )
    return repository, numero


def _rimanda_gli_altri(repository, numero, *, quando):
    """Il DSN condiviso puo' portare righe di altri test: restano fuori."""
    with repository.connection() as conn:
        conn.execute(
            "UPDATE mediazione_source_jobs SET due_at=? WHERE registration_number<>?",
            (quando.isoformat(), numero),
        )


# ------------------------------------------------------- la domanda a poco prezzo


def test_una_verifica_scaduta_viene_contata(repo):
    repository, numero = repo
    seed_jobs(repository, now=NOW)
    _rimanda_gli_altri(repository, numero, quando=NOW + timedelta(days=30))

    assert verifiche_in_attesa(repository, now=NOW) == 1


def test_una_verifica_non_ancora_scaduta_non_si_conta(repo):
    repository, numero = repo
    seed_jobs(repository, now=NOW)
    _rimanda_gli_altri(repository, numero, quando=NOW + timedelta(days=30))
    with repository.connection() as conn:
        conn.execute(
            "UPDATE mediazione_source_jobs SET due_at=? WHERE registration_number=?",
            ((NOW + timedelta(days=7)).isoformat(), numero),
        )

    assert verifiche_in_attesa(repository, now=NOW) == 0


def test_un_organismo_disattivato_non_si_conta(repo):
    """Il registro tiene anche gli organismi cancellati: non vanno controllati."""

    repository, numero = repo
    seed_jobs(repository, now=NOW)
    _rimanda_gli_altri(repository, numero, quando=NOW + timedelta(days=30))
    with repository.connection() as conn:
        conn.execute(
            "UPDATE mediazione_organismi SET active=0 WHERE registration_number=?", (numero,)
        )

    assert verifiche_in_attesa(repository, now=NOW) == 0


# ------------------------------------------------------------------ la sveglia


def test_con_la_coda_vuota_non_sveglia_nessuno(monkeypatch):
    """Il caso normale: aprire la mediazione non deve costare un giro."""

    import web.services.mediazione_source_runtime as runtime

    chiamate = []
    monkeypatch.setattr(runtime, "directory", lambda _c: object())
    monkeypatch.setattr(runtime, "verifiche_in_attesa", lambda _r: 0)
    monkeypatch.setattr(
        "web.services.scheduler_admin_surface.request_scheduler_run",
        lambda *a, **k: chiamate.append((a, k)),
    )

    esito = runtime.sveglia_se_ci_sono_verifiche({})

    assert esito == {"svegliato": False, "in_attesa": 0}
    assert chiamate == []


def test_con_qualcosa_di_scaduto_chiede_un_giro(monkeypatch):
    import web.services.mediazione_source_runtime as runtime

    chiamate = []
    monkeypatch.setattr(runtime, "directory", lambda _c: object())
    monkeypatch.setattr(runtime, "verifiche_in_attesa", lambda _r: 3)
    monkeypatch.setattr(
        "web.services.scheduler_admin_surface.request_scheduler_run",
        lambda *a, **k: chiamate.append((a, k)),
    )

    esito = runtime.sveglia_se_ci_sono_verifiche({})

    assert esito == {"svegliato": True, "in_attesa": 3}
    assert chiamate and chiamate[0][0][0] == "mediazione_sources_refresh"
    assert chiamate[0][1]["dedupe_open"] is True


def test_senza_registro_non_sveglia_e_non_solleva(monkeypatch):
    import web.services.mediazione_source_runtime as runtime

    monkeypatch.setattr(runtime, "directory", lambda _c: None)

    assert runtime.sveglia_se_ci_sono_verifiche({}) == {"svegliato": False, "in_attesa": 0}


def test_un_guasto_non_rompe_l_apertura_della_pagina(monkeypatch):
    """Aprire la mediazione deve funzionare anche se la sveglia non parte."""

    import web.services.mediazione_source_runtime as runtime

    def esplode(_c):
        raise RuntimeError("registro irraggiungibile")

    monkeypatch.setattr(runtime, "directory", esplode)

    assert runtime.sveglia_se_ci_sono_verifiche({}) == {"svegliato": False, "in_attesa": 0}
