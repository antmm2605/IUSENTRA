"""Guardrail del ciclo autonomo di Lex (fail-closed, mai clamp silenziosi).

Invarianti non negoziabili del ciclo:
- NESSUNA scrittura di codice, commit, push, deploy o apertura PR;
- nessuna credenziale, nessun bypass di paywall o robots.txt;
- modalità web solo con `allow_web=True` E allowlist non vuota;
- limiti oltre gli HARD_LIMITS → errore di configurazione, non riduzione tacita;
- ogni proposta di miglioramento resta `requires_human_review=True` e l'unica
  "apply" esposta (`refuse_apply`) solleva SEMPRE `AutonomyViolation`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NoReturn

from lex.autonomy.models import CycleConfig

HARD_LIMITS: dict[str, int] = {
    "max_cycles": 10,
    "max_queries": 50,
    "max_sources": 40,
    "max_runtime_seconds": 1800,
    "max_questions_per_cycle": 10,
    "max_queries_per_question": 5,
}
MIN_WEB_INTERVAL_SECONDS = 1.0
MAX_FETCH_BYTES = 5_000_000
FORBIDDEN_ACTIONS = frozenset(
    {"code_write", "commit", "push", "deploy", "merge", "open_pr", "apply_proposal", "modify_production"}
)


class CycleConfigError(ValueError):
    """Configurazione del ciclo non valida (exit code CLI: 1)."""


class SourceAccessError(RuntimeError):
    """Nessuna fonte utilizzabile o provider di ricerca guasto (exit code CLI: 2)."""


class CycleError(RuntimeError):
    """Errore irrecuperabile durante l'esecuzione del ciclo (exit code CLI: 3)."""


class AutonomyViolation(RuntimeError):
    """Tentativo di violare un invariante di sicurezza dell'autonomia."""


def assert_no_autonomous_code_write(component: str, *, requested_action: str = "") -> None:
    """Blocca sul nascere qualsiasi azione dispositiva richiesta al ciclo."""

    action = str(requested_action or "").strip().casefold()
    if action and action in FORBIDDEN_ACTIONS:
        raise AutonomyViolation(
            f"{component}: l'azione '{action}' è vietata al ciclo autonomo "
            "(nessuna modifica a codice o produzione senza revisione umana)."
        )


def refuse_apply(proposal: Any) -> NoReturn:
    """Unica 'apply' esposta: rifiuta SEMPRE. Le proposte si applicano a mano."""

    title = str(getattr(proposal, "title", "") or proposal or "proposta")
    raise AutonomyViolation(
        f"Applicazione automatica rifiutata per '{title}': ogni ImprovementProposal "
        "richiede revisione e applicazione umana (requires_human_review=True)."
    )


def validate_cycle_config(raw: Mapping[str, Any] | None) -> CycleConfig:
    """Valida la configurazione grezza (JSON) e restituisce un CycleConfig.

    Fail-closed: valori mancanti → default prudenti; valori oltre gli
    HARD_LIMITS → CycleConfigError (nessun clamp silenzioso)."""

    if not isinstance(raw, Mapping):
        raise CycleConfigError("Configurazione mancante o non valida: atteso un oggetto JSON.")
    mode = str(raw.get("mode") or "offline").strip().casefold()
    if mode not in {"offline", "web"}:
        raise CycleConfigError(f"Modalità sconosciuta: {mode!r} (ammesse: offline, web).")
    allow_web = bool(raw.get("allow_web", False))

    limits = raw.get("limits") if isinstance(raw.get("limits"), Mapping) else {}
    sources = raw.get("sources") if isinstance(raw.get("sources"), Mapping) else {}
    politeness = raw.get("politeness") if isinstance(raw.get("politeness"), Mapping) else {}
    memory = raw.get("memory") if isinstance(raw.get("memory"), Mapping) else {}

    config = CycleConfig(
        mode=mode,
        allow_web=allow_web,
        max_cycles=_positive_int(limits, "max_cycles", 2),
        max_queries=_positive_int(limits, "max_queries", 10),
        max_sources=_positive_int(limits, "max_sources", 6),
        max_runtime_seconds=_positive_int(limits, "max_runtime_seconds", 300),
        max_questions_per_cycle=_positive_int(limits, "max_questions_per_cycle", 5),
        max_queries_per_question=_positive_int(limits, "max_queries_per_question", 3),
        min_sources_per_area=_positive_int(limits, "min_sources_per_area", 2),
        require_official_sources=bool(sources.get("require_official_sources", True)),
        source_mode=str(sources.get("source_mode") or "strict").strip().casefold(),
        allowlist=_domain_list(sources.get("allowlist")),
        denylist=_domain_list(sources.get("denylist")),
        min_interval_seconds=float(politeness.get("min_interval_seconds", 2.0)),
        timeout_seconds=_positive_int(politeness, "timeout_seconds", 20),
        max_bytes=_positive_int(politeness, "max_bytes", 2_000_000),
        respect_robots=bool(politeness.get("respect_robots", True)),
        memory_dir=str(memory.get("dir") or "").strip(),
        offline_results=_offline_results(raw.get("offline_results")),
    )

    for key, ceiling in HARD_LIMITS.items():
        value = int(getattr(config, key))
        if value > ceiling:
            raise CycleConfigError(f"Limite '{key}'={value} oltre il tetto di sicurezza {ceiling}: ridurre il valore.")
    if config.source_mode not in {"strict", "balanced", "broad"}:
        raise CycleConfigError(f"source_mode sconosciuto: {config.source_mode!r}.")
    if config.max_bytes > MAX_FETCH_BYTES:
        raise CycleConfigError(f"politeness.max_bytes={config.max_bytes} oltre il tetto {MAX_FETCH_BYTES}.")
    if mode == "web":
        if not allow_web:
            raise CycleConfigError("Modalità web richiede allow_web=true esplicito.")
        if not config.allowlist:
            raise CycleConfigError("Modalità web richiede una allowlist di domini non vuota.")
        if config.min_interval_seconds < MIN_WEB_INTERVAL_SECONDS:
            raise CycleConfigError(
                f"politeness.min_interval_seconds={config.min_interval_seconds} sotto il minimo "
                f"{MIN_WEB_INTERVAL_SECONDS}s per la modalità web."
            )
        if not config.respect_robots:
            raise CycleConfigError("Modalità web richiede respect_robots=true (mai bypassare robots.txt).")
    elif allow_web:
        raise CycleConfigError("Configurazione incoerente: allow_web=true con mode=offline.")
    return config


def _positive_int(payload: Mapping[str, Any], key: str, default: int) -> int:
    try:
        value = int(payload.get(key, default))
    except (TypeError, ValueError) as exc:
        raise CycleConfigError(f"Limite '{key}' non numerico.") from exc
    if value < 1:
        raise CycleConfigError(f"Limite '{key}' deve essere >= 1 (trovato {value}).")
    return value


def _domain_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip().casefold() for item in value if str(item or "").strip()]


def _offline_results(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, Mapping):
        return {}
    results: dict[str, list[dict[str, Any]]] = {}
    for query, rows in value.items():
        if isinstance(rows, list):
            results[str(query)] = [dict(row) for row in rows if isinstance(row, Mapping)]
    return results


__all__ = [
    "FORBIDDEN_ACTIONS",
    "HARD_LIMITS",
    "AutonomyViolation",
    "CycleConfigError",
    "CycleError",
    "SourceAccessError",
    "assert_no_autonomous_code_write",
    "refuse_apply",
    "validate_cycle_config",
]
