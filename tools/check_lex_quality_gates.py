from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"[OK] {message}")


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def exists(path: str) -> bool:
    return (REPO_ROOT / path).exists()


def main() -> int:
    required_paths = [
        "lex",
        "lex/orchestrator.py",
    ]
    for path in required_paths:
        if not exists(path):
            fail(f"Manca il path richiesto per Lex quality gates: {path}")
    ok("Struttura Lex minima presente")

    suggestions = []
    if exists("lex/telemetry"):
        ok("Cartella telemetry presente")
    else:
        suggestions.append("Aggiungere lex/telemetry per metriche grounding/latenza/fallback")

    if exists("lex/retrieval"):
        ok("Cartella retrieval presente")
    else:
        suggestions.append("Aggiungere lex/retrieval per separare recupero fonti")

    if exists("lex/guards"):
        ok("Cartella guards presente")
    else:
        suggestions.append("Aggiungere lex/guards per validazioni e filtri")

    orch = read("lex/orchestrator.py")
    if "timeout" in orch.lower():
        ok("Orchestrator sembra gestire timeout o timing")
    else:
        suggestions.append("Introdurre timeout espliciti nell'orchestrator")

    if "fallback" in orch.lower():
        ok("Orchestrator sembra contenere fallback espliciti")
    else:
        suggestions.append("Introdurre fallback espliciti nell'orchestrator")

    report = {
        "ok": True,
        "suggestions": suggestions,
        "score_hint": 95 if len(suggestions) <= 1 else 90,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
