"""Bridge React per la superficie "Apprendimento Lex" (read-only).

Costruisce il payload di `/api/v1/ui/lex-learning`: fotografia della memoria
durevole del ciclo autonomo (`lex.autonomy.memory_inspection`, mai side-effect)
più lo stato del job notturno delegato dal registro pianificazioni. La
superficie NON offre azioni dispositive: l'attivazione del job resta nella
console Pianificazioni (`/admin/pianificazioni`) e le proposte si applicano
solo con revisione umana fuori da questa pagina.
"""

from __future__ import annotations

from typing import Any, Mapping

CONSOLE_PIANIFICAZIONI_PATH = "/admin/pianificazioni"


def _stato_job_notturno(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Stato del job `lex_autonomous_learning_nightly`, fail-closed sulle letture."""

    stato: dict[str, Any] = {
        "job_id": "",
        "abilitato": False,
        "stato": "sconosciuto",
        "pianificazione": "",
        "console": CONSOLE_PIANIFICAZIONI_PATH,
    }
    try:
        from lex.autonomy.nightly import JOB_ID

        stato["job_id"] = JOB_ID
        from pct.scheduler_registry import scheduler_registry_repository

        row = scheduler_registry_repository(dict(config or {})).get_job(JOB_ID)
    except Exception:
        stato["stato"] = "registro pianificazioni non leggibile"
        return stato
    if not row:
        stato["stato"] = "mai abilitato dalla console"
        return stato
    stato["abilitato"] = bool(row.get("enabled"))
    stato["stato"] = "attivo" if stato["abilitato"] else "in pausa (default)"
    hour = str(row.get("hour") or "").strip()
    minute = str(row.get("minute") or "").strip()
    if hour:
        stato["pianificazione"] = f"ogni notte alle {int(hour):02d}:{int(minute or 0):02d}" if hour.isdigit() else ""
    return stato


def build_react_lex_learning_payload(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from lex.autonomy.memory_inspection import inspect_memory

    try:
        snapshot = inspect_memory()
    except Exception:
        snapshot = {
            "directory": "",
            "memoria_presente": False,
            "conteggi": {},
            "proposte": [],
            "letture": [],
        }
    return {
        "ok": True,
        "source": "memoria_apprendimento",
        **snapshot,
        "job_notturno": _stato_job_notturno(config),
    }


__all__ = ["build_react_lex_learning_payload", "CONSOLE_PIANIFICAZIONI_PATH"]
