"""Safe report serialization for Legal Source Engine dry-runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .dogfood import run_dogfood_scenarios
from .registry import LegalSourceRegistry, create_default_registry


DEFAULT_REPORT_DIR = Path("artifacts/legal_sources/reports")


def source_registry_report(registry: LegalSourceRegistry | None = None) -> dict[str, Any]:
    active = registry or create_default_registry()
    return active.registry_report()


def source_manuscript_report(registry: LegalSourceRegistry | None = None) -> dict[str, Any]:
    active = registry or create_default_registry()
    return {
        "report_type": "source_manuscripts",
        "manuscripts": [manuscript.to_dict() for manuscript in active.manuscripts()],
    }


def scorecard_report(registry: LegalSourceRegistry | None = None) -> dict[str, Any]:
    active = registry or create_default_registry()
    return {
        "report_type": "source_scorecards",
        "scorecards": [scorecard.to_dict() for scorecard in active.scorecards()],
    }


def dogfood_report() -> dict[str, Any]:
    results = run_dogfood_scenarios()
    return {
        "report_type": "dogfood",
        "network_used": False,
        "customer_data_used": False,
        "results": [result.to_dict() for result in results],
        "passed": all(result.passed for result in results),
    }


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def write_json_report(report: dict[str, Any], filename: str, *, output_dir: Path = DEFAULT_REPORT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / filename
    target.write_text(to_json(report), encoding="utf-8")
    return target


__all__ = [
    "DEFAULT_REPORT_DIR",
    "dogfood_report",
    "scorecard_report",
    "source_manuscript_report",
    "source_registry_report",
    "to_json",
    "write_json_report",
]
