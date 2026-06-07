"""Scorecard e suite casi reali per valutazione operativa di Lex."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


EVAL_CASES_PATH = Path(__file__).resolve().parents[2] / "lex" / "eval" / "cases.json"
DEFAULT_RESULTS_PATHS = (
    Path("artifacts/lex-eval/results.json"),
    Path("data/lex/eval/results.json"),
    Path("lex/eval/results.json"),
)


def _candidate_result_paths() -> list[Path]:
    configured = str(os.getenv("IUSENTRA_LEX_EVAL_RESULTS") or "").strip()
    paths = [Path(configured)] if configured else []
    paths.extend(DEFAULT_RESULTS_PATHS)
    return paths


def _load_results_payload() -> dict[str, Any]:
    for path in _candidate_result_paths():
        try:
            resolved = path.resolve()
            if not resolved.is_file():
                continue
            payload = json.loads(resolved.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                payload = {"results": payload}
            if not isinstance(payload, dict):
                continue
            stat = resolved.stat()
            payload["_path"] = str(resolved)
            payload["_mtime"] = datetime.fromtimestamp(stat.st_mtime).replace(microsecond=0).isoformat()
            return payload
        except Exception:
            continue
    return {"results": [], "_path": "", "_mtime": ""}


def _result_case_id(row: dict[str, Any]) -> str:
    return str(row.get("case_id") or row.get("id") or row.get("case") or "").strip()


def _result_duration_ms(row: dict[str, Any]) -> int:
    for key in ("duration_ms", "response_ms", "elapsed_ms", "latency_ms"):
        try:
            value = row.get(key)
            if value is not None:
                return max(0, int(float(value)))
        except (TypeError, ValueError):
            continue
    return 0


def _result_sources_useful(row: dict[str, Any]) -> bool | None:
    for key in ("sources_useful", "fonti_utili", "useful_sources"):
        if key in row:
            return bool(row.get(key))
    scores = row.get("scores") if isinstance(row.get("scores"), dict) else {}
    citation = scores.get("citation_fidelity") if isinstance(scores.get("citation_fidelity"), dict) else {}
    if "precision" in citation:
        try:
            return float(citation.get("precision") or 0) >= 0.85
        except (TypeError, ValueError):
            return False
    return None


def _result_passed(row: dict[str, Any]) -> bool:
    if "passed" in row:
        return bool(row.get("passed"))
    if "ok" in row:
        return bool(row.get("ok"))
    warnings = row.get("warnings") or row.get("errori") or []
    return not bool(warnings)


def _result_warnings(row: dict[str, Any]) -> list[str]:
    values = row.get("warnings") or row.get("errori") or row.get("errors") or []
    if isinstance(values, str):
        return [values]
    if isinstance(values, list):
        return [str(value) for value in values if str(value or "").strip()]
    return []


def build_lex_eval_scorecard() -> dict[str, Any]:
    payload = json.loads(EVAL_CASES_PATH.read_text(encoding="utf-8"))
    cases = list(payload.get("cases") or [])
    results_payload = _load_results_payload()
    result_rows = [row for row in list(results_payload.get("results") or []) if isinstance(row, dict)]
    results_by_case = {_result_case_id(row): row for row in result_rows if _result_case_id(row)}
    by_area: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rubric_counter: Counter[str] = Counter()
    for case in cases:
        area = str(case.get("area") or "generale").strip()
        by_area[area].append(case)
        rubric_counter.update(case.get("rubric") or [])

    measured_cases = len(results_by_case)
    passed_cases = sum(1 for row in results_by_case.values() if _result_passed(row))
    failed_cases = max(0, measured_cases - passed_cases)
    duration_values = [_result_duration_ms(row) for row in results_by_case.values() if _result_duration_ms(row)]
    source_values = [
        value
        for value in (_result_sources_useful(row) for row in results_by_case.values())
        if value is not None
    ]
    sources_useful_percent = round((sum(1 for value in source_values if value) / len(source_values)) * 100, 1) if source_values else None
    avg_response_ms = round(sum(duration_values) / len(duration_values), 1) if duration_values else None
    measurement_status = (
        "non_misurata"
        if measured_cases == 0
        else ("parziale" if measured_cases < len(cases) or failed_cases else "misurata")
    )
    measurement_status_label = {
        "non_misurata": "Nessuna prova reale eseguita",
        "parziale": "Misurazione parziale o con errori",
        "misurata": "Prove reali eseguite",
    }[measurement_status]

    summary = {
        "cases_total": len(cases),
        "areas_total": len(by_area),
        "measured_cases": measured_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "sources_useful_percent": sources_useful_percent,
        "avg_response_ms": avg_response_ms,
        "measurement_status": measurement_status,
        "measurement_status_label": measurement_status_label,
        "results_path": str(results_payload.get("_path") or ""),
        "results_updated_at": str(results_payload.get("_mtime") or ""),
        "citations_target": "85%",
        "high_risk_without_warning_target": "0",
        "response_time_target": "-25% / -35%",
    }

    areas = [
        {
            "area": area,
            "count": len(rows),
            "measured": sum(1 for row in rows if str(row.get("id") or "") in results_by_case),
            "passed": sum(1 for row in rows if str(row.get("id") or "") in results_by_case and _result_passed(results_by_case[str(row.get("id") or "")])),
            "failed": sum(1 for row in rows if str(row.get("id") or "") in results_by_case and not _result_passed(results_by_case[str(row.get("id") or "")])),
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
        {
            "label": "Risposte con fonti utili",
            "target": "85%",
            "value": f"{sources_useful_percent}%" if sources_useful_percent is not None else "non misurato",
            "status": "ok" if sources_useful_percent is not None and sources_useful_percent >= 85 else "warning",
        },
        {
            "label": "Risposte operative nude a rischio alto",
            "target": "0",
            "value": "non misurato" if not measured_cases else str(sum(1 for row in results_by_case.values() if row.get("high_risk_without_warning"))),
            "status": "warning" if not measured_cases else "ok",
        },
        {
            "label": "Tempo medio risposta Lex",
            "target": "-25% / -35%",
            "value": f"{avg_response_ms} ms" if avg_response_ms is not None else "non misurato",
            "status": "warning" if avg_response_ms is None else "info",
        },
        {
            "label": "Riduzione click per capire cosa fare adesso",
            "target": "misura su flusso reale",
            "value": "non misurato" if not measured_cases else "da confrontare con baseline",
            "status": "warning" if not measured_cases else "info",
        },
        {
            "label": "Tempo medio preparazione udienza",
            "target": "riduzione misurata",
            "value": "non misurato" if not measured_cases else "da confrontare con baseline",
            "status": "warning" if not measured_cases else "info",
        },
    ]

    case_rows = []
    for case in cases:
        case_id = str(case.get("id") or "")
        result = results_by_case.get(case_id)
        case_rows.append(
            {
                **case,
                "measured": result is not None,
                "passed": _result_passed(result) if result else False,
                "duration_ms": _result_duration_ms(result) if result else 0,
                "sources_useful": _result_sources_useful(result) if result else None,
                "warnings": _result_warnings(result) if result else [],
            }
        )

    actions = [
        {
            "label": "Risultati mancanti",
            "detail": (
                "Nessun run reale salvato: la pagina mostra il catalogo casi, non una qualità misurata."
                if not measured_cases
                else f"{measured_cases}/{len(cases)} casi hanno un risultato salvato."
            ),
        },
        {
            "label": "Percorso risultati",
            "detail": summary["results_path"] or "Salvare un run reale in artifacts/lex-eval/results.json o configurare IUSENTRA_LEX_EVAL_RESULTS.",
        },
    ]

    return {
        "summary": summary,
        "areas": areas,
        "rubric": rubric,
        "cases": case_rows,
        "kpi": kpi,
        "actions": actions,
    }
