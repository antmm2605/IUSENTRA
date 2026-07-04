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
