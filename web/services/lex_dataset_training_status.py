"""Stato operativo del percorso dataset Lex per Impostazioni AI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from flask import current_app, g, has_app_context


MAX_SCAN_FILES = 320
DATASET_DIR_NAMES = (
    "lex_dataset",
    "dataset_lex",
    "lex-studio-dataset",
    "studio_dataset",
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_from_mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except OSError:
        return ""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _iter_dataset_files(root: Path) -> Iterable[Path]:
    if not root.exists() or not root.is_dir():
        return ()
    files: list[Path] = []
    for path in root.rglob("*"):
        if len(files) >= MAX_SCAN_FILES:
            break
        if path.is_file() and path.suffix.lower() in {".json", ".jsonl", ".csv"}:
            files.append(path)
    return tuple(files)


def _candidate_roots(data_root: Path) -> list[Path]:
    candidates = [data_root / "intelligence" / name for name in DATASET_DIR_NAMES]
    candidates.extend(data_root / name for name in DATASET_DIR_NAMES)
    if data_root.name.lower() in {"intelligence", "lex_dataset", "dataset_lex"}:
        candidates.insert(0, data_root / "lex_dataset")
        candidates.insert(0, data_root)
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _resolve_data_root(data_root: str | Path | None = None) -> Path:
    if data_root:
        return Path(data_root)
    if has_app_context():
        paths = getattr(g, "data_paths", {}) or {}
        if getattr(g, "tenant_context_missing", False):
            raise RuntimeError("Contesto studio non disponibile per leggere lo stato Lex.")
        for key in ("LOCAL_AI_DB", "WORKSPACE_INTELLIGENCE_DB", "LEGAL_INTELLIGENCE_DB", "CLIENTI_DB"):
            value = paths.get(key) or current_app.config.get(key)
            if value:
                base = Path(str(value))
                if base.name:
                    base = base.parent
                if base.name.lower() in {"intelligence", "legal_intelligence", "clienti"}:
                    return base.parent
                return base
        configured = current_app.config.get("PCT_DATA_ROOT") or current_app.config.get("DATA_DIR")
        if configured:
            return Path(str(configured))
    return Path("data")


def _rows(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Mapping):
        for key in ("items", "rows", "qa_pairs", "pairs", "documents", "chunks", "jobs", "errors"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


def _jsonl_count(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except Exception:
        return 0


def _scan_dataset(data_root: Path) -> dict[str, Any]:
    stats = {
        "documents": 0,
        "chunks": 0,
        "qa_pending": 0,
        "qa_approved": 0,
        "alpaca_rows": 0,
        "sharegpt_rows": 0,
        "latest_job": {},
        "errors": [],
        "latest_at": "",
        "roots_found": 0,
    }
    latest_file_at = ""
    for root in _candidate_roots(data_root):
        files = tuple(_iter_dataset_files(root))
        if not files:
            continue
        stats["roots_found"] += 1
        for file_path in files:
            lower_name = file_path.name.lower()
            latest_file_at = max(latest_file_at, _iso_from_mtime(file_path))
            if lower_name.endswith(".jsonl"):
                rows = _jsonl_count(file_path)
                if "alpaca" in lower_name:
                    stats["alpaca_rows"] += rows
                if "sharegpt" in lower_name or "share_gpt" in lower_name:
                    stats["sharegpt_rows"] += rows
                continue
            payload = _read_json(file_path)
            if payload is None:
                continue
            if "manifest" in lower_name or (isinstance(payload, Mapping) and "documents" in payload):
                stats["documents"] = max(int(stats["documents"]), len(_rows(payload.get("documents") if isinstance(payload, Mapping) else payload)))
            if isinstance(payload, Mapping):
                manifest = payload.get("manifest")
                if isinstance(manifest, Mapping):
                    stats["documents"] = max(int(stats["documents"]), len(_rows(manifest.get("documents"))))
                stats["chunks"] = max(int(stats["chunks"]), len(_rows(payload.get("chunks"))))
                qa_rows = _rows(payload.get("qa_pairs") or payload.get("pairs") or payload)
            else:
                qa_rows = _rows(payload)
            for row in qa_rows:
                if not isinstance(row, Mapping):
                    continue
                status = _text(row.get("review_status") or row.get("stato") or row.get("status")).lower()
                if status in {"approved", "approvata", "approvato"}:
                    stats["qa_approved"] += 1
                elif status in {"pending_human_review", "pending", "in revisione", "da revisionare", ""}:
                    stats["qa_pending"] += 1
            if "job" in lower_name or (isinstance(payload, Mapping) and ("latest_job" in payload or "jobs" in payload)):
                jobs = _rows(payload.get("jobs") if isinstance(payload, Mapping) else payload)
                latest = payload.get("latest_job") if isinstance(payload, Mapping) and isinstance(payload.get("latest_job"), Mapping) else {}
                for job in jobs:
                    if not isinstance(job, Mapping):
                        continue
                    job_at = _text(job.get("completed_at") or job.get("ended_at") or job.get("updated_at") or job.get("created_at"))
                    latest_at = _text(latest.get("completed_at") or latest.get("ended_at") or latest.get("updated_at") or latest.get("created_at")) if latest else ""
                    if not latest or job_at >= latest_at:
                        latest = dict(job)
                stats["latest_job"] = latest
            if "error" in lower_name or (isinstance(payload, Mapping) and "errors" in payload):
                for error in _rows(payload.get("errors") if isinstance(payload, Mapping) else payload):
                    if isinstance(error, Mapping):
                        stats["errors"].append({
                            "label": _text(error.get("label") or error.get("title") or "Verifica non riuscita"),
                            "message": _text(error.get("message") or error.get("note") or error.get("error")),
                        })
    stats["latest_at"] = latest_file_at
    return stats


def _card(
    cid: str,
    label: str,
    status: str,
    note: str,
    tone: str,
    *,
    value: int | str = "",
    action_label: str = "Apri Lex",
) -> dict[str, Any]:
    return {
        "id": cid,
        "label": label,
        "status": status,
        "value": value,
        "note": note,
        "tone": tone,
        "action_label": action_label,
        "action_context": f"impostazioni-ai-{cid}",
    }


def _job_status_label(status: str) -> str:
    normalized = _text(status).lower().replace("_", " ")
    if normalized in {"ok", "completed", "completato", "success"}:
        return "Completato"
    if normalized in {"running", "in corso", "working"}:
        return "In corso"
    if normalized in {"failed", "error", "errore", "fallito"}:
        return "Verifica non riuscita"
    if normalized in {"pending", "queued", "in attesa"}:
        return "In attesa"
    return normalized[:1].upper() + normalized[1:] if normalized else "Nessun lavoro"


def _job_status_tone(status: str) -> str:
    normalized = _text(status).lower().replace("_", " ")
    if normalized in {"ok", "completed", "completato", "success"}:
        return "success"
    if normalized in {"failed", "error", "errore", "fallito"}:
        return "danger"
    if normalized:
        return "warning"
    return "neutral"


def _manual_capabilities() -> dict[str, Any]:
    try:
        from lex.dataset import llama_factory_supported_capabilities

        llama = llama_factory_supported_capabilities()
    except Exception:
        llama = {}
    return {
        "llama_factory": {
            "label": "LLaMA Factory",
            "status": "manuale",
            "note": "Import, anteprima, addestramento e valutazione restano passaggi approvati dall'operatore.",
            "license": _text((llama.get("reference") or {}).get("license")) if isinstance(llama, Mapping) else "",
        },
        "ollama": {
            "label": "Ollama",
            "status": "manuale",
            "note": "Il modello adattato va importato sul PC dello studio solo dopo test di accettazione.",
        },
    }


def build_lex_dataset_training_status(
    *,
    data_root: str | Path | None = None,
    ai_enabled: bool | None = None,
    auto_index_documents: bool | None = None,
) -> dict[str, Any]:
    root = _resolve_data_root(data_root)
    stats = _scan_dataset(root)
    rag_ready = bool(auto_index_documents) or int(stats["chunks"]) > 0
    qa_pending = int(stats["qa_pending"])
    qa_approved = int(stats["qa_approved"])
    alpaca_rows = int(stats["alpaca_rows"])
    sharegpt_rows = int(stats["sharegpt_rows"])
    latest_job = stats["latest_job"] if isinstance(stats["latest_job"], Mapping) else {}
    latest_status = _text(latest_job.get("status") or latest_job.get("stato"))
    latest_at = _text(latest_job.get("completed_at") or latest_job.get("ended_at") or latest_job.get("updated_at") or stats["latest_at"])
    errors = [error for error in stats["errors"] if error.get("message")][:5]
    latest_label = _job_status_label(latest_status)

    cards = [
        _card(
            "rag",
            "Contesto documenti",
            "Pronto" if rag_ready else "Da preparare",
            "I nuovi fascicoli entrano nel contesto quando documenti e dati sono indicizzati: non serve riaddestrare il modello." if rag_ready else "Attiva l'indicizzazione dei documenti per usare il contesto dello studio.",
            "success" if rag_ready else "warning",
            value=int(stats["chunks"]),
            action_label="Controlla documenti",
        ),
        _card(
            "qa_review",
            "Domande in revisione",
            "Da revisionare" if qa_pending else ("Approvate" if qa_approved else "Nessuna coda"),
            "Gli esempi domanda/risposta non entrano negli export facoltativi senza revisione umana.",
            "warning" if qa_pending else ("success" if qa_approved else "neutral"),
            value=qa_pending or qa_approved,
            action_label="Apri revisione",
        ),
        _card(
            "alpaca",
            "File istruzioni",
            "Disponibile" if alpaca_rows else "Non esportato",
            "Export Alpaca pronto solo con esempi approvati; non addestra il modello.",
            "success" if alpaca_rows else "neutral",
            value=alpaca_rows,
            action_label="Verifica export",
        ),
        _card(
            "sharegpt",
            "File conversazioni",
            "Disponibile" if sharegpt_rows else "Non esportato",
            "Export ShareGPT disponibile solo dopo approvazione degli esempi.",
            "success" if sharegpt_rows else "neutral",
            value=sharegpt_rows,
            action_label="Verifica export",
        ),
        _card(
            "manual_training",
            "Addestramento modello",
            "Manuale",
            "Il language model di produzione risponde già con RAG; LLaMA Factory e Ollama servono solo per un fine-tuning manuale approvato.",
            "info",
            value="manuale",
            action_label="Apri guida",
        ),
        _card(
            "latest_job",
            "Ultimo lavoro",
            latest_label,
            f"Ultimo aggiornamento: {latest_at}" if latest_at else "Nessun lavoro dataset registrato per questo studio.",
            _job_status_tone(latest_status),
            value=latest_at,
            action_label="Controlla stato",
        ),
        _card(
            "errors",
            "Errori",
            "Da verificare" if errors else "Nessun errore",
            errors[0]["message"] if errors else "Nessun errore dataset registrato.",
            "danger" if errors else "success",
            value=len(errors),
            action_label="Apri controlli",
        ),
    ]
    return {
        "ok": True,
        "generated_at": _iso_now(),
        "enabled": bool(ai_enabled),
        "storage_label": "Archivio riservato dello studio",
        "summary": {
            "documents": int(stats["documents"]),
            "chunks": int(stats["chunks"]),
            "qa_pending_review": qa_pending,
            "qa_approved": qa_approved,
            "alpaca_rows": alpaca_rows,
            "sharegpt_rows": sharegpt_rows,
            "errors": len(errors),
        },
        "cards": cards,
        "latest_job": {
            "status": latest_status,
            "label": latest_label,
            "updated_at": latest_at,
            "message": _text(latest_job.get("message") or latest_job.get("note")),
        },
        "schedule": {
            "job_id": "lex_dataset_nightly",
            "label": "Preparazione archivio Lex",
            "family": "Lex AI",
            "time": "01:45",
            "message": "Preparazione automatica dell'archivio e degli export facoltativi, senza addestramento automatico.",
        },
        "errors": errors,
        "manual_tools": _manual_capabilities(),
        "privacy": {
            "automatic_training": False,
            "external_transfer": False,
            "human_review_required": True,
            "message": "Il contesto resta nell'ambiente IUSENTRA autorizzato dello studio e nessun addestramento parte automaticamente.",
        },
    }
