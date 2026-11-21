"""Job notturno delegato dell'apprendimento autonomo Lex (default OFF, fail-closed)."""

from __future__ import annotations

import json

import lex.autonomy.nightly as nightly
from lex.autonomy.discovery import StaticSearchProvider
from lex.autonomy.nightly import JOB_ID, NIGHTLY_LIMITS, run_lex_autonomous_learning_nightly


def test_template_registrato_default_on_disattivabile():
    from pct.scheduler_registry import default_scheduler_templates

    templates = {template.key: template for template in default_scheduler_templates({})}
    template = templates.get(JOB_ID)
    assert template is not None, "template del job notturno assente dal registro"
    # Default ON per scelta esplicita dello studio (2026-07-04): il job resta
    # disattivabile dalla console e il runner ricontrolla comunque il registro.
    assert template.enabled is True
    assert template.built_in is True
    assert template.trigger_kind == "cron"
    assert (template.hour, template.minute) == ("2", "40")
    assert any("revisione umana" in criterio for criterio in template.criteria)
    assert any("robots" in criterio for criterio in template.criteria)


def _abilita_registro(monkeypatch, *, enabled: bool | None):
    """Stub del registro: riga presente/assente con enabled dato."""

    def _fake_state(config):
        if enabled is None:
            return False, "riga di registro assente: job mai abilitato dalla console"
        if not enabled:
            return False, "disabilitato dal registro pianificazioni"
        return True, ""

    monkeypatch.setattr(nightly, "_registry_state", _fake_state)


def test_salta_senza_riga_di_registro_fail_closed(monkeypatch):
    _abilita_registro(monkeypatch, enabled=None)
    report = run_lex_autonomous_learning_nightly(config={})
    assert report["skipped"] is True
    assert "registro" in report["reason"]


def test_salta_quando_disabilitato_dalla_console(monkeypatch):
    _abilita_registro(monkeypatch, enabled=False)
    report = run_lex_autonomous_learning_nightly(config={})
    assert report["skipped"] is True
    assert "disabilitato" in report["reason"]


def test_salta_se_manca_la_configurazione_web(monkeypatch, tmp_path):
    _abilita_registro(monkeypatch, enabled=True)
    report = run_lex_autonomous_learning_nightly(config={}, config_path=tmp_path / "assente.json")
    assert report["skipped"] is True
    assert "configurazione web assente" in report["reason"]


def test_run_abilitata_scrive_memoria_con_budget_notturni(monkeypatch, tmp_path):
    _abilita_registro(monkeypatch, enabled=True)
    # Chiave per-contenimento: serve QUALUNQUE query con site:normattiva.it,
    # indipendentemente dalla norma chiesta (le domande derivano dai campioni).
    provider = StaticSearchProvider(
        {
            "site:normattiva.it": [
                {
                    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:test-2043",
                    "title": "Art. 2043 c.c.",
                    "content": "Art. 2043 c.c. Risarcimento per fatto illecito: il danno ingiusto obbliga al risarcimento.",
                }
            ]
        }
    )
    memoria = tmp_path / "memoria"
    report = run_lex_autonomous_learning_nightly(
        config={},
        search_provider=provider,
        memory_dir=memoria,
    )
    assert report["skipped"] is False
    assert report["ok"] is True
    # Budget notturni prudenti applicati sopra la config web committata.
    assert report["query"] <= NIGHTLY_LIMITS["max_queries"]
    assert report["letture"] <= NIGHTLY_LIMITS["max_sources"]
    assert report["cicli"] <= NIGHTLY_LIMITS["max_cycles"]
    assert report["nuove_citazioni"] > 0
    assert (memoria / "research_questions.jsonl").exists()
    assert (memoria / "citations.jsonl").exists()
    letture = [
        json.loads(line)["payload"]
        for line in (memoria / "source_readings.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(riga["status"] == "ok" for riga in letture)


def test_errore_del_ciclo_non_propaga(monkeypatch, tmp_path):
    _abilita_registro(monkeypatch, enabled=True)

    def _esplode(**kwargs):
        raise RuntimeError("guasto notturno simulato")

    monkeypatch.setattr(nightly, "run_autonomous_cycle", _esplode)
    report = run_lex_autonomous_learning_nightly(config={}, memory_dir=tmp_path / "memoria")
    assert report["ok"] is False
    assert "guasto notturno simulato" in report["error"]


def test_promozione_default_on_rispetta_le_scelte_umane(tmp_path):
    """Il flip una-tantum a ON tocca solo righe mai modificate da un umano."""

    from pct.scheduler_registry import SchedulerRegistryRepository

    repo = SchedulerRegistryRepository(tmp_path / "scheduler_registry.sqlite")
    repo.upsert_default_jobs({})
    row = repo.get_job(JOB_ID)
    assert row and row.get("enabled") is True  # seed fresco: default ON

    # Riga legacy (seminata enabled=0 dai deploy precedenti, mai toccata): promossa.
    with repo.connect() as conn:
        conn.execute(
            "UPDATE scheduled_jobs SET enabled=0, updated_by='system' WHERE job_id=?",
            (JOB_ID,),
        )
    repo.upsert_default_jobs({})
    assert (repo.get_job(JOB_ID) or {}).get("enabled") is True

    # Scelta umana dalla console (updated_by valorizzato): MAI sovrascritta.
    with repo.connect() as conn:
        conn.execute(
            "UPDATE scheduled_jobs SET enabled=0, updated_by='avvocato' WHERE job_id=?",
            (JOB_ID,),
        )
    repo.upsert_default_jobs({})
    assert (repo.get_job(JOB_ID) or {}).get("enabled") is False


def test_registro_non_leggibile_e_stati_reali_non_avviano_job(monkeypatch, tmp_path):
    import pct.scheduler_registry as sched
    from pct.scheduler_registry import SchedulerRegistryRepository

    repo = SchedulerRegistryRepository(tmp_path / "registro.sqlite")
    monkeypatch.setattr(sched, "scheduler_registry_repository", lambda _cfg: repo)
    assert "riga di registro assente" in run_lex_autonomous_learning_nightly()["reason"]
    repo.upsert_default_jobs({})
    assert nightly._registry_state({}) == (True, "")
    with repo.connect() as conn:
        conn.execute("UPDATE scheduled_jobs SET enabled=0 WHERE job_id=?", (JOB_ID,))
    assert "disabilitato" in run_lex_autonomous_learning_nightly()["reason"]

    def archivio_indisponibile(_cfg):
        raise OSError("disco indisponibile")

    monkeypatch.setattr(sched, "scheduler_registry_repository", archivio_indisponibile)
    assert "registro pianificazioni non leggibile" in run_lex_autonomous_learning_nightly()["reason"]


def test_configurazione_errata_e_fonti_irraggiungibili_restano_distinte(monkeypatch, tmp_path):
    from lex.autonomy.safety import SourceAccessError

    _abilita_registro(monkeypatch, enabled=True)
    config = tmp_path / "config.json"
    config.write_text("non è JSON", encoding="utf-8")
    esito = run_lex_autonomous_learning_nightly(config_path=config)
    assert esito["ok"] is False and "configurazione web non valida" in esito["error"]

    def ricerca(**parametri):
        assert parametri["samples"] == []
        raise SourceAccessError("ricerca non disponibile")

    monkeypatch.setattr(nightly, "run_autonomous_cycle", ricerca)
    esito = run_lex_autonomous_learning_nightly(samples_path=tmp_path / "campioni-assenti.json")
    assert esito["ok"] is False and "fonti non raggiungibili" in esito["error"]


def test_protocollo_ricerca_fallito_produce_un_esito_diagnostico(monkeypatch, tmp_path):
    _abilita_registro(monkeypatch, enabled=True)

    class ProviderIndisponibile:
        def search(self, query, *, limit):
            raise OSError("catalogo irraggiungibile")

    esito = run_lex_autonomous_learning_nightly(
        search_provider=ProviderIndisponibile(), memory_dir=tmp_path / "memoria",
    )
    assert esito["ok"] is False
    assert "Tutte le ricerche del provider sono fallite" in esito["error"]


def test_rapporto_distingue_errori_dalla_raccolta_delle_fonti(tmp_path):
    from lex.autonomy.models import LearningCycleResult
    from lex.autonomy.report import render_text

    esito = LearningCycleResult(mode="offline", started_at="2026-11-15", memory_dir=str(tmp_path))
    esito.errors = ["Fonte non raggiungibile"]
    testo = render_text(esito)
    assert "Errori non bloccanti:" in testo
    assert "Fonte non raggiungibile" in testo


def _archivio_gazzette(percorso, gazzette):
    import sqlite3

    con = sqlite3.connect(percorso)
    con.execute("CREATE TABLE official_documents (id INTEGER PRIMARY KEY, source_id TEXT, title TEXT, original_url TEXT,"
                " published_at TEXT)")
    con.execute("CREATE TABLE official_chunks (id INTEGER PRIMARY KEY, document_id INTEGER, chunk_index INTEGER,"
                " text TEXT)")
    for numero, (data, frammenti) in enumerate(gazzette, start=1):
        con.execute("INSERT INTO official_documents VALUES (?, 'gazzetta_ufficiale', ?, ?, ?)",
                    (numero, f"Gazzetta Ufficiale - Serie Generale n. {numero}",
                     f"https://www.gazzettaufficiale.it/gazzetta/{numero}", data))
        for indice, testo in enumerate(frammenti):
            con.execute("INSERT INTO official_chunks (document_id, chunk_index, text) VALUES (?, ?, ?)",
                        (numero, indice, testo))
    con.commit()
    con.close()


def test_gazzetta_letta_per_intero_e_non_solo_il_primo_frammento(tmp_path):
    """Collaudo 21/11: di ogni Gazzetta si leggevano 3.500 caratteri, cioè un solo frammento dell'archivio."""
    from lex.autonomy.discovery import LatestGazzettaProvider, testo_intero_documento

    db = tmp_path / "fonti.sqlite"
    frammenti = ["A" * 3500, "decreto legislativo 10 ottobre 2022, n. 149 " * 10, "fine del fascicolo"]
    _archivio_gazzette(db, [("2026-11-20", frammenti)])
    testo = testo_intero_documento(1, db_path=db)
    assert len(testo) > 3500 and testo.endswith("fine del fascicolo")
    candidati = LatestGazzettaProvider(limit=3, db_path=db)()
    assert len(candidati) == 1 and candidati[0].content == testo


def test_le_gazzette_nuove_si_leggono_anche_se_le_domande_sono_sempre_le_stesse(monkeypatch, tmp_path):
    """Collaudo 21/11: dal 16/11 le domande ripetute consumavano il budget e nessuna Gazzetta nuova veniva letta."""
    from lex.autonomy.discovery import LatestGazzettaProvider

    _abilita_registro(monkeypatch, enabled=True)
    db = tmp_path / "fonti.sqlite"
    _archivio_gazzette(db, [("2026-11-19", ["Art. 2043 c.c. risarcimento del danno ingiusto."]),
                            ("2026-11-20", ["Art. 1385 c.c. caparra confirmatoria e recesso."])])
    memoria = tmp_path / "memoria"
    novita = LatestGazzettaProvider(limit=3, db_path=db)
    primo = run_lex_autonomous_learning_nightly(config={}, search_provider=StaticSearchProvider({}),
                                                novelty_provider=novita, memory_dir=memoria)
    assert primo["ok"] is True and primo["letture"] == 2
    letture = (memoria / "source_readings.jsonl").read_text(encoding="utf-8")
    assert "Serie Generale n. 2" in letture
    # La notte dopo le stesse Gazzette non si rileggono.
    secondo = run_lex_autonomous_learning_nightly(config={}, search_provider=StaticSearchProvider({}),
                                                  novelty_provider=novita, memory_dir=memoria)
    assert secondo["letture"] == 0
