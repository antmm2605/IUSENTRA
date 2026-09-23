"""Codifiche ufficiali PST dei beni mobili usate nei DatiAtto."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "cataloghi" / "codifiche_beni_mobili_pst.json"
SOURCE_PAGE = "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC705"
SOURCE_DOCUMENT = "https://pst.giustizia.it/PST/resources/cms/documents/Codifiche_Beni_Mobili.pdf"
SOURCE_SHA256 = "C081D674CCA3F965DF54B38A564F44A66E8DC5552A92454BF6C1129C6C834DC5"
SCOPE_INDIVIDUAL_ENFORCEMENT = "esecuzioni_individuali"
SCOPE_INSOLVENCY = "procedure_concorsuali"


@lru_cache(maxsize=1)
def load_mobile_asset_catalog() -> dict[str, Any]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if str(payload.get("sourceSha256") or "").upper() != SOURCE_SHA256:
        raise RuntimeError("Il catalogo beni mobili non dichiara l'impronta della fonte PST attesa.")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("Il catalogo beni mobili PST e' vuoto o non valido.")
    return payload


def mobile_asset_entries(*, scope: str | None = None) -> tuple[dict[str, str], ...]:
    rows = load_mobile_asset_catalog()["entries"]
    return tuple(
        {
            "code": str(row.get("code") or "").strip(),
            "label": str(row.get("label") or "").strip(),
            "scope": str(row.get("scope") or "").strip(),
        }
        for row in rows
        if isinstance(row, dict) and (scope is None or str(row.get("scope") or "") == scope)
    )


def mobile_asset_codes(*, scope: str) -> frozenset[str]:
    return frozenset(row["code"] for row in mobile_asset_entries(scope=scope))


def mobile_asset_options(*, scope: str = SCOPE_INDIVIDUAL_ENFORCEMENT) -> tuple[tuple[str, str], ...]:
    """Restituisce opzioni uniche senza nascondere etichette duplicate del PDF.

    Il PDF ACC705 assegna in alcuni casi lo stesso codice a piu' descrizioni.
    DatiAtto trasmette soltanto il codice; percio' la UI unisce le descrizioni
    ufficiali associate allo stesso valore, mantenendone l'ordine originale.
    """

    labels_by_code: dict[str, list[str]] = {}
    for row in mobile_asset_entries(scope=scope):
        labels = labels_by_code.setdefault(row["code"], [])
        if row["label"] not in labels:
            labels.append(row["label"])
    return tuple(
        (code, " / ".join(labels))
        for code, labels in labels_by_code.items()
    )


def require_mobile_asset_code(value: Any, *, scope: str = SCOPE_INDIVIDUAL_ENFORCEMENT) -> str:
    code = str(value if value is not None else "").strip()
    if not code:
        raise ValueError("Tipologia del bene mobile mancante: seleziona un codice ufficiale PST.")
    if code not in mobile_asset_codes(scope=scope):
        raise ValueError(
            f"Tipologia del bene mobile non valida ({code}): seleziona un codice ufficiale PST."
        )
    return code


__all__ = [
    "CATALOG_PATH",
    "SCOPE_INDIVIDUAL_ENFORCEMENT",
    "SCOPE_INSOLVENCY",
    "SOURCE_DOCUMENT",
    "SOURCE_PAGE",
    "SOURCE_SHA256",
    "load_mobile_asset_catalog",
    "mobile_asset_codes",
    "mobile_asset_entries",
    "mobile_asset_options",
    "require_mobile_asset_code",
]
