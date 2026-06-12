from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from time import monotonic

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lex.contracts import LexRequest
from lex.context.builder import LexContextBuilder
from lex.retrieval.orchestrator import RetrievalOrchestrator
from web.app import create_app


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {"nome": "Studio Benchmark"},
                "pec": {},
                "smtp": {},
                "scheduler": {},
                "ai": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _cfg(tmp_root: Path) -> dict[str, str]:
    return {
        "TESTING": True,
        "AUTH_DB": str(tmp_root / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_root / "auth" / "audit.json"),
        "CLIENTI_DB": str(tmp_root / "clienti" / "anagrafica.json"),
        "FASCICOLI_DB": str(tmp_root / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_root / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_root / "fascicoli" / "archivio"),
        "AGENDA_DB": str(tmp_root / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(tmp_root / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_root / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(tmp_root / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_root / "search" / "index.db"),
        "OCR_QUEUE_DB": str(tmp_root / "search" / "ocr_jobs.db"),
        "PRIVACY_DB": str(tmp_root / "privacy" / "registro.json"),
        "NOTIFICHE_LOG": str(tmp_root / "notifiche" / "log.json"),
        "TENANTS_REGISTRY": str(tmp_root / "tenants.json"),
        "STUDIO_CONFIG": str(tmp_root / "config" / "studio.json"),
        "PCT_SQLITE_MODE": "1",
    }


def _measure(callable_):
    started = monotonic()
    result = callable_()
    return result, round((monotonic() - started) * 1000, 2)


def run_performance_smoke() -> dict[str, object]:
    tmp_root = Path(tempfile.mkdtemp(prefix="iusentra-performance-smoke-"))
    _write_studio_config(tmp_root / "config" / "studio.json")

    app, startup_ms = _measure(lambda: create_app(_cfg(tmp_root)))
    client = app.test_client()

    login_response, login_ms = _measure(lambda: client.get("/login"))
    health_response, health_ms = _measure(lambda: client.get("/api/health"))
    runtime_response, runtime_ms = _measure(lambda: client.get("/api/metriche/runtime"))

    request = LexRequest(
        tenant_id="benchmark",
        user_id="superadmin",
        session_id="smoke-session",
        query="Prepara un riepilogo del fascicolo",
        fascicolo_id="FASC-001",
        document_id="DOC-001",
        workflow_hint="chat",
        allow_external_research=False,
        metadata={
            "benchmark_mode": "performance_smoke",
            "disable_official_web": True,
            "lightweight_context": True,
        },
    )
    with app.app_context():
        context_builder = LexContextBuilder()
        context, context_ms = _measure(lambda: context_builder.build_request_context(request, "chat"))
        retrieval = RetrievalOrchestrator()
        retrieval_payload, retrieval_ms = _measure(lambda: retrieval.collect(request, context, "chat"))

    return {
        "startup_ms": startup_ms,
        "login_ms": login_ms,
        "health_ms": health_ms,
        "runtime_metrics_ms": runtime_ms,
        "lex_context_build_ms": context_ms,
        "lex_retrieval_ms": retrieval_ms,
        "status_codes": {
            "login": login_response.status_code,
            "health": health_response.status_code,
            "runtime_metrics": runtime_response.status_code,
        },
        "lex_retrieval_items": len(retrieval_payload.get("items", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke benchmark leggero di IUSENTRA.")
    parser.add_argument("--output", default="", help="Percorso JSON di output.")
    parser.add_argument("--strict", action="store_true", help="Fallisce se supera le soglie base.")
    args = parser.parse_args()

    payload = run_performance_smoke()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    if not args.strict:
        return 0

    thresholds = {
        # Cold start dell'app completa: sui runner condivisi oscilla più delle
        # singole rotte. I budget delle route e di Lex restano stretti.
        "startup_ms": 3200,
        "login_ms": 800,
        "health_ms": 800,
        "runtime_metrics_ms": 800,
        "lex_context_build_ms": 1500,
        "lex_retrieval_ms": 1500,
    }
    failed = [
        key for key, threshold in thresholds.items() if float(payload.get(key, 0.0)) > threshold
    ]
    if failed:
        print(f"Soglie performance superate: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
