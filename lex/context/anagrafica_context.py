"""Contesto anagrafico cliente/parti per Lex."""

from __future__ import annotations

from typing import Any

from web.helpers import get_clienti, get_soggetti


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load_anagrafica_context(*, pratica_id: str = "", limit: int = 5) -> dict[str, list[dict[str, Any]]]:
    target = _clean_spaces(pratica_id).lower()
    clienti_rows: list[dict[str, Any]] = []
    soggetti_rows: list[dict[str, Any]] = []

    for row in get_clienti().tutti()[:100]:
        haystack = " ".join(
            _clean_spaces(part).lower()
            for part in [getattr(row, "nome", ""), getattr(row, "cognome", ""), getattr(row, "cf", "")]
        )
        if target and target not in haystack:
            continue
        clienti_rows.append(
            {
                "id": getattr(row, "id", ""),
                "nome": getattr(row, "nome", ""),
                "cognome": getattr(row, "cognome", ""),
                "cf": getattr(row, "cf", ""),
                "email": getattr(row, "email", ""),
            }
        )
        if len(clienti_rows) >= max(int(limit or 0), 1):
            break

    try:
        for row in get_soggetti().tutti()[:100]:
            haystack = " ".join(
                _clean_spaces(part).lower()
                for part in [row.get("nome"), row.get("cognome"), row.get("denominazione"), row.get("cf")]
            )
            if target and target not in haystack:
                continue
            soggetti_rows.append(
                {
                    "id": row.get("id") or "",
                    "nome": row.get("nome") or row.get("denominazione") or "",
                    "cognome": row.get("cognome") or "",
                    "cf": row.get("cf") or "",
                    "ruolo": row.get("ruolo") or "",
                }
            )
            if len(soggetti_rows) >= max(int(limit or 0), 1):
                break
    except Exception:
        soggetti_rows = []

    return {"clienti": clienti_rows, "soggetti": soggetti_rows}
