"""Catalogo funzioni: le voci operative devono puntare a destinazioni reali.

Guardia del Lotto 1 (inventario 15/08/2026): una voce marcata "operativa" con
deep-link a strumenti legali deve riferire un tool esistente in TOOL_METHODS —
mai promesse a vuoto nel catalogo.
"""

from __future__ import annotations

import re
from pathlib import Path

from pct.applicazioni_catalogo import catalogo_applicazioni


def _tools_reali() -> set[str]:
    testo = Path("web/blueprints/strumenti_legali.py").read_text(encoding="utf-8")
    blocco = re.search(r"TOOL_METHODS[^=]*=\s*\{(.*?)\}", testo, re.S)
    return set(re.findall(r'"([a-z_0-9]+)"\s*:', blocco.group(1)))


def test_voci_operative_su_strumenti_puntano_a_tool_esistenti():
    tools = _tools_reali()
    assert len(tools) >= 30  # sanity: il catalogo tool non e' collassato
    rotte = []
    for entry in catalogo_applicazioni():
        if entry.get("status") != "operativa":
            continue
        if entry.get("endpoint") != "strumenti_legali.index":
            continue
        tool = (entry.get("params") or {}).get("tool", "")
        if tool and tool not in tools:
            rotte.append(f"{entry['id']} -> tool={tool}")
    assert rotte == [], f"Voci operative con tool inesistente: {rotte}"


def test_lotto1_ha_alzato_le_operative():
    operative = sum(1 for e in catalogo_applicazioni() if e.get("status") == "operativa")
    assert operative >= 78  # 34 originarie + 44 del Lotto 1


def test_voci_operative_hanno_endpoint():
    senza = [
        e["id"] for e in catalogo_applicazioni()
        if e.get("status") == "operativa" and not str(e.get("endpoint") or "").strip()
    ]
    assert senza == [], f"Operative senza endpoint: {senza}"
