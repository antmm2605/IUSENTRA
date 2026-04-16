"""Scorecard e suite casi reali per valutazione operativa di Lex."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EVAL_CASES_PATH = Path(__file__).resolve().parents[2] / "lex" / "eval" / "cases.json"


def build_lex_eval_scorecard() -> dict[str, Any]:
    payload = json.loads(EVAL_CASES_PATH.read_text(encoding="utf-8"))
    cases = list(payload.get("cases") or [])
    by_area: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rubric_counter: Counter[str] = Counter()
    for case in cases:
        area = str(case.get("area") or "generale").strip()
        by_area[area].append(case)
        rubric_counter.update(case.get("rubric") or [])

    summary = {
        "cases_total": len(cases),
        "areas_total": len(by_area),
        "citations_target": "85%",
        "high_risk_without_warning_target": "0",
        "response_time_target": "-25% / -35%",
    }

    areas = [
        {
            "area": area,
            "count": len(rows),
            "titles": [row.get("title") for row in rows],
        }
        for area, rows in sorted(by_area.items())
    ]

    rubric = [
        {
            "name": name,
            "count": count,
        }
        for name, count in sorted(rubric_counter.items())
    ]

    kpi = [
        {"label": "Risposte con fonti utili", "target": "85%"},
        {"label": "Risposte operative nude a rischio alto", "target": "0"},
        {"label": "Tempo medio risposta Lex", "target": "-25% / -35%"},
        {"label": "Riduzione click per capire cosa fare adesso", "target": "in miglioramento continuo"},
        {"label": "Tempo medio preparazione udienza", "target": "riduzione misurata"},
    ]

    return {
        "summary": summary,
        "areas": areas,
        "rubric": rubric,
        "cases": cases,
        "kpi": kpi,
    }

