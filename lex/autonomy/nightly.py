"""Job notturno delegato del ciclo di apprendimento autonomo (default OFF).

Registrato come template `lex_autonomous_learning_nightly` nel registro
pianificazioni (`pct/scheduler_registry.py`) con `enabled=False`: il job
APScheduler nasce IN PAUSA e si attiva solo dalla console Pianificazioni.
Doppia cintura: anche a job attivo, il runner ricontrolla la riga di registro
e salta se risulta disabilitata (protezione dalla finestra di avvio).

Quando attivo esegue il ciclo in modalità WEB con la configurazione governata
committata (`examples/lex_autonomous_config_web.json`) e budget notturni
prudenti; la memoria è quella durevole di default
(`{PCT_DATA_ROOT}/intelligence/lex_memory`), così l'apprendimento si accumula
notte dopo notte con dedup (convergenza a `no_new_information`).
Invarianti immutati: robots.txt, rate-limit, trust fail-closed, proposte SOLO
in revisione umana, nessuna azione dispositiva.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lex.autonomy.autonomous_cycle import run_autonomous_cycle
from lex.autonomy.discovery import ConfigurableWebSearchProvider, SearchProvider
from lex.autonomy.safety import CycleConfigError, SourceAccessError, validate_cycle_config
from lex.learning.models import LegalSourceSample
from lex.sources.polite_fetcher import PoliteFetcher

JOB_ID = "lex_autonomous_learning_nightly"
# Budget notturni prudenti (sotto i tetti HARD_LIMITS e sotto la config diurna).
NIGHTLY_LIMITS = {
    "max_cycles": 2,
    "max_queries": 10,
    "max_sources": 5,
    "max_runtime_seconds": 240,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _registry_state(config: dict[str, Any] | None) -> tuple[bool, str]:
    """(abilitato, motivo). FAIL-CLOSED: senza riga di registro leggibile e
    abilitata, il ciclo notturno NON parte (il default-OFF vale ovunque)."""

    try:
        from pct.scheduler_registry import scheduler_registry_repository

        row = scheduler_registry_repository(dict(config or {})).get_job(JOB_ID)
    except Exception as exc:
        return False, f"registro pianificazioni non leggibile ({exc})"
    if not row:
        return False, "riga di registro assente: job mai abilitato dalla console"
    if not row.get("enabled"):
        return False, "disabilitato dal registro pianificazioni"
    return True, ""


def run_lex_autonomous_learning_nightly(
    *,
    app: Any = None,
    config: dict[str, Any] | None = None,
    search_provider: SearchProvider | None = None,
    fetcher: PoliteFetcher | None = None,
    memory_dir: str | Path | None = None,
    config_path: str | Path | None = None,
    samples_path: str | Path | None = None,
) -> dict[str, Any]:
    """Esegue (o salta, se disabilitato) il ciclo notturno. Mai eccezioni."""

    cfg = dict(config or getattr(app, "config", {}) or {})
    enabled, reason = _registry_state(cfg)
    if not enabled:
        return {"ok": True, "skipped": True, "reason": reason}

    root = _repo_root()
    web_config_path = Path(config_path) if config_path else root / "examples" / "lex_autonomous_config_web.json"
    if not web_config_path.exists():
        return {"ok": True, "skipped": True, "reason": f"configurazione web assente: {web_config_path}"}
    try:
        raw = json.loads(web_config_path.read_text(encoding="utf-8"))
        limits = dict(raw.get("limits") or {})
        limits.update(NIGHTLY_LIMITS)
        raw["limits"] = limits
        cycle_config = validate_cycle_config(raw)
    except (CycleConfigError, ValueError, OSError) as exc:
        return {"ok": False, "skipped": False, "error": f"configurazione web non valida: {exc}"}
    if memory_dir is not None:
        cycle_config.memory_dir = str(memory_dir)

    samples: list[LegalSourceSample] = []
    resolved_samples = Path(samples_path) if samples_path else root / "examples" / "legal_samples.json"
    try:
        payload = json.loads(resolved_samples.read_text(encoding="utf-8"))
        samples = [LegalSourceSample.from_dict(row) for row in payload.get("samples") or [] if isinstance(row, dict)]
    except (OSError, ValueError):
        samples = []

    provider: SearchProvider = search_provider or ConfigurableWebSearchProvider(limit_results=cycle_config.max_sources)
    polite = fetcher or PoliteFetcher(
        min_interval_seconds=cycle_config.min_interval_seconds,
        timeout_seconds=cycle_config.timeout_seconds,
        max_bytes=cycle_config.max_bytes,
        respect_robots=cycle_config.respect_robots,
    )
    try:
        result = run_autonomous_cycle(
            config=cycle_config,
            samples=samples,
            search_provider=provider,
            fetcher=polite,
        )
    except SourceAccessError as exc:
        return {"ok": False, "skipped": False, "error": f"fonti non raggiungibili: {exc}"}
    except Exception as exc:  # difesa: il job notturno non deve mai propagare
        return {"ok": False, "skipped": False, "error": str(exc)}
    return {
        "ok": True,
        "skipped": False,
        "stop_reason": result.stop_reason,
        "cicli": result.cycles_run,
        "domande": result.questions_generated,
        "query": result.queries_executed,
        "letture": result.sources_fetched,
        "respinte": result.sources_rejected,
        "nuove_citazioni": result.new_citations,
        "nuovi_termini": result.new_terms,
        "proposte": result.proposals_count,
        "memoria": result.memory_dir,
    }


__all__ = ["JOB_ID", "NIGHTLY_LIMITS", "run_lex_autonomous_learning_nightly"]
