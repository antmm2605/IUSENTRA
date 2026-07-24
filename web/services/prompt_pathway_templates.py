"""Arricchimento dei percorsi guidati con i template del catalogo master.

Risolve i ``template_refs`` dei passi (id del catalogo master, es.
``MON_001``) in schede consultabili: titolo e link di apertura nel
catalogo template. Fail-soft: un id non più presente nel catalogo viene
scartato con log, senza bloccare il percorso.
"""

from __future__ import annotations

from threading import RLock
from typing import Any

from flask import current_app

_LOCK = RLock()
_INDICE: dict[str, dict[str, str]] | None = None


def _indice_template() -> dict[str, dict[str, str]]:
    global _INDICE
    with _LOCK:
        if _INDICE is None:
            indice: dict[str, dict[str, str]] = {}
            try:
                from pct.template_atti_master_catalog import load_master_templates

                for item in load_master_templates():
                    template_id = str(item.get("id") or "").strip()
                    if template_id:
                        indice[template_id] = {
                            "id": template_id,
                            "titolo": str(item.get("titolo") or template_id),
                            "url": f"/template-atti/catalogo?scheda={template_id}",
                        }
            except Exception:
                current_app.logger.exception("Catalogo master template non leggibile per i percorsi guidati.")
            _INDICE = indice
        return _INDICE


def templates_per_refs(template_refs: list[str]) -> list[dict[str, str]]:
    """Schede template per i riferimenti di un passo (id sconosciuti scartati)."""
    indice = _indice_template()
    schede: list[dict[str, str]] = []
    for ref in template_refs or []:
        scheda = indice.get(str(ref or "").strip())
        if scheda:
            schede.append(dict(scheda))
        else:
            current_app.logger.warning("Template ref sconosciuto nei percorsi guidati: %s", ref)
    return schede


__all__ = ["templates_per_refs"]
