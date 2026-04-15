"""Helper condivisi per le route dei portali telematici."""

from __future__ import annotations

import os
from collections import OrderedDict
from typing import Any


def resolve_nome_ufficio(codice_ufficio: str) -> str:
    nome_ufficio = codice_ufficio
    try:
        from pct.uffici_giudiziari import get_gestore as _get_uff

        cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
        ufficio = next(
            (u for u in _get_uff(cache_path).carica() if u.get("codice") == codice_ufficio),
            None,
        )
        nome_ufficio = ufficio["nome"] if ufficio else codice_ufficio
    except Exception:
        pass
    return nome_ufficio


def group_documenti_per_deposito(documenti: list[Any]) -> list[dict[str, Any]]:
    gruppi: dict[str, dict[str, Any]] = OrderedDict()
    for doc in sorted(documenti, key=lambda item: item.data_deposito or "", reverse=True):
        chiave = doc.id_deposito or f"__{doc.data_deposito}__{doc.mittente}"
        if chiave not in gruppi:
            gruppi[chiave] = {
                "id_deposito": doc.id_deposito or chiave,
                "tipo_atto": doc.tipo_atto or doc.tipo.replace("_", " ").title(),
                "data_deposito": doc.data_deposito,
                "mittente": doc.mittente,
                "documenti": [],
            }
        gruppi[chiave]["documenti"].append(doc)
    return list(gruppi.values())
