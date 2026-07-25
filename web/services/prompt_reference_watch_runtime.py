"""Runtime web dei riferimenti normativi vivi della libreria prompt.

Legge gli aggiornamenti normativi pubblicati dalla pipeline quotidiana
(Legal Update Repository, ancorato a ``LEGAL_INTELLIGENCE_DB``) e li
incrocia con i riferimenti del catalogo prompt. Fail-soft: senza
repository configurato o leggibile la libreria resta pienamente
utilizzabile, semplicemente senza segnalazioni. Cache breve di processo
per non ripetere la lettura a ogni richiesta.
"""

from __future__ import annotations

import os
import time
from threading import RLock
from typing import Any

from flask import current_app

from lex.legal_skills.prompt_library.reference_watch import revisioni_da_normative, voci_da_rivedere

_TTL_SECONDI = 600
_LIMITE_NORMATIVE = 300

_CACHE_LOCK = RLock()
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def _intelligence_db_path() -> str:
    return str(
        current_app.config.get("LEGAL_INTELLIGENCE_DB")
        or os.getenv("PCT_LEGAL_INTELLIGENCE_DB")
        or ""
    ).strip()


def _normative_pubblicate(db_anchor: str) -> list[dict[str, Any]]:
    try:
        from pct.legal_update_repository import LegalUpdateDbConfig, LegalUpdateRepository

        repo_cfg = LegalUpdateDbConfig.from_anchor(db_anchor)
        repository = LegalUpdateRepository(repo_cfg.db_path, json_path=repo_cfg.json_path)
        return repository.list_published_normative(limit=_LIMITE_NORMATIVE)
    except Exception:
        current_app.logger.exception("Aggiornamenti normativi non leggibili per i riferimenti vivi prompt.")
        return []


def revisioni_prompt_library(force_refresh: bool = False) -> dict[str, Any]:
    """Segnalazioni "da rivedere" per catalogo prompt e percorsi."""
    db_anchor = _intelligence_db_path()
    if not db_anchor:
        return {"revisioni": [], "voci_da_rivedere": [], "totale": 0, "fonte_disponibile": False}

    adesso = time.monotonic()
    with _CACHE_LOCK:
        voce_cache = _CACHE.get(db_anchor)
        if voce_cache and not force_refresh and adesso - voce_cache[0] < _TTL_SECONDI:
            revisioni = voce_cache[1]
        else:
            revisioni = revisioni_da_normative(_normative_pubblicate(db_anchor))
            _CACHE[db_anchor] = (adesso, revisioni)

    return {
        "revisioni": revisioni,
        "voci_da_rivedere": [
            {"area_id": area_id, "voce_id": voce_id} for area_id, voce_id in sorted(voci_da_rivedere(revisioni))
        ],
        "totale": len(revisioni),
        "fonte_disponibile": True,
    }


def revisioni_per_voce(area_id: str, voce_id: str) -> list[dict[str, Any]]:
    """Segnalazioni relative a una singola voce del catalogo."""
    payload = revisioni_prompt_library()
    return [
        voce
        for voce in payload["revisioni"]
        if voce.get("tipo") == "voce" and voce.get("area_id") == area_id and voce.get("voce_id") == voce_id
    ]


__all__ = ["revisioni_per_voce", "revisioni_prompt_library"]
