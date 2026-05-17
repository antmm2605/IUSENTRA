"""Coda di revisione locale per le domande candidate del dataset Lex."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from web.services.lex_dataset_training_status import _candidate_roots, _resolve_data_root


MAX_QUEUE_FILES = 120
PLACEHOLDER_RE = re.compile(r"@@@[^@]+@@@")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _display_text(value: Any) -> str:
    cleaned = PLACEHOLDER_RE.sub(" ", str(value or ""))
    return " ".join(cleaned.split()).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _append_review_event(path: Path, event: Mapping[str, Any]) -> None:
    try:
        events_path = path.parent / "review_events.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(event), ensure_ascii=False) + "\n")
    except Exception:
        return


def _queue_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("items", "qa_pairs", "pairs", "rows"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def _with_rows(payload: Any, rows: list[dict[str, Any]]) -> Any:
    if isinstance(payload, list):
        return rows
    if isinstance(payload, Mapping):
        updated = dict(payload)
        for key in ("items", "qa_pairs", "pairs", "rows"):
            if isinstance(updated.get(key), list):
                updated[key] = rows
                return updated
        updated["items"] = rows
        return updated
    return rows


def _iter_queue_paths(data_root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for root in _candidate_roots(data_root):
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob("qa_review_queue.json"):
            if len(paths) >= MAX_QUEUE_FILES:
                break
            if path.is_file():
                paths.append(path)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return tuple(unique)


def _status_label(status: str) -> tuple[str, str]:
    normalized = _text(status).lower().replace("_", " ")
    if normalized in {"approved", "approvata", "approvato"}:
        return "Approvata", "success"
    if normalized in {"rejected", "scartata", "scartato"}:
        return "Scartata", "danger"
    return "Da revisionare", "warning"


def _source_label(row: Mapping[str, Any]) -> dict[str, str]:
    source = row.get("source") if isinstance(row.get("source"), Mapping) else {}
    source_map = source if isinstance(source, Mapping) else {}
    metadata = source_map.get("metadata") if isinstance(source_map.get("metadata"), Mapping) else {}
    metadata_map = metadata if isinstance(metadata, Mapping) else {}
    title = _text(source_map.get("title") or source_map.get("source_name") or row.get("document_id") or "Documento studio")
    fascicolo = _text(source_map.get("fascicolo_id") or metadata_map.get("fascicolo_id"))
    page_start = _text(source_map.get("page_start"))
    page_end = _text(source_map.get("page_end"))
    page_label = ""
    if page_start and page_end and page_start != page_end:
        page_label = f"pagine {page_start}-{page_end}"
    elif page_start:
        page_label = f"pagina {page_start}"
    pieces = [piece for piece in (title, f"fascicolo {fascicolo}" if fascicolo else "", page_label) if piece]
    return {
        "title": title,
        "detail": " · ".join(pieces),
    }


def _normalize_item(row: Mapping[str, Any], queue_path: Path) -> dict[str, Any]:
    label, tone = _status_label(_text(row.get("review_status") or row.get("status")))
    source = _source_label(row)
    return {
        "id": _text(row.get("qa_id") or row.get("id")),
        "question": _display_text(row.get("question")),
        "answer": _display_text(row.get("answer")),
        "status": label,
        "tone": tone,
        "sourceTitle": source["title"],
        "sourceDetail": source["detail"],
        "privacy": "dato riservato" if _text(row.get("privacy_classification")).lower() in {"sensitive", "highly_sensitive"} else "uso interno",
        "tenantId": _text(row.get("tenant_id")),
        "reviewNote": _text(row.get("review_note")),
        "queueFile": queue_path.parent.name,
    }


def load_lex_dataset_review_queue(
    *,
    data_root: str | Path | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Restituisce la coda di revisione locale senza esportare o addestrare."""
    root = _resolve_data_root(data_root)
    paths = _iter_queue_paths(root)
    rows_with_paths: list[tuple[dict[str, Any], Path]] = []
    summary = {
        "total": 0,
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "files": len(paths),
    }
    for path in paths:
        payload = _read_json(path)
        for row in _queue_rows(payload):
            status = _text(row.get("review_status") or row.get("status")).lower()
            summary["total"] += 1
            if status in {"approved", "approvata", "approvato"}:
                summary["approved"] += 1
            elif status in {"rejected", "scartata", "scartato"}:
                summary["rejected"] += 1
            else:
                summary["pending"] += 1
                rows_with_paths.append((row, path))
    capped = max(1, min(int(limit or 12), 50))
    items = [_normalize_item(row, path) for row, path in rows_with_paths[:capped]]
    return {
        "ok": True,
        "generated_at": _utc_now(),
        "summary": summary,
        "items": items,
        "message": "Domande generate da IUSENTRA: lo studio corregge, approva o scarta. Nessun addestramento parte da questa coda.",
        "automatic_training": False,
        "external_transfer": False,
    }


def update_lex_dataset_review_item(
    qa_id: str,
    *,
    action: str,
    question: str = "",
    answer: str = "",
    note: str = "",
    reviewer_id: str = "",
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    """Aggiorna una domanda candidata nella coda locale."""
    target_id = _text(qa_id)
    normalized_action = _text(action).lower()
    if normalized_action not in {"approve", "approved", "reject", "rejected"}:
        return {"ok": False, "message": "Azione non disponibile.", "errors": {"action": "Scegli approvazione o scarto."}}
    root = _resolve_data_root(data_root)
    for path in _iter_queue_paths(root):
        payload = _read_json(path)
        rows = _queue_rows(payload)
        for index, row in enumerate(rows):
            if _text(row.get("qa_id") or row.get("id")) != target_id:
                continue
            approved = normalized_action in {"approve", "approved"}
            clean_question = _display_text(question) or _display_text(row.get("question"))
            clean_answer = _display_text(answer) or _display_text(row.get("answer"))
            if approved and (not clean_question or not clean_answer):
                return {
                    "ok": False,
                    "message": "Domanda e risposta sono obbligatorie prima dell'approvazione.",
                    "errors": {
                        "question": "Completa la domanda.",
                        "answer": "Completa la risposta.",
                    },
                }
            updated = dict(row)
            if approved:
                updated["question"] = clean_question
                updated["answer"] = clean_answer
            updated["review_status"] = "approved" if approved else "rejected"
            updated["requires_human_review"] = not approved
            updated["reviewer_id"] = _text(reviewer_id) or "studio"
            updated["review_note"] = _text(note) or ("Approvata dallo studio." if approved else "Scartata dallo studio.")
            updated["reviewed_at"] = _utc_now()
            rows[index] = updated
            _write_json_atomic(path, _with_rows(payload, rows))
            _append_review_event(path, {
                "qa_id": target_id,
                "action": "approved" if approved else "rejected",
                "reviewer_id": updated["reviewer_id"],
                "reviewed_at": updated["reviewed_at"],
                "source_title": _source_label(updated)["title"],
                "automatic_training": False,
                "external_transfer": False,
            })
            refreshed = load_lex_dataset_review_queue(data_root=root)
            refreshed["message"] = "Revisione salvata. Il modello non viene addestrato automaticamente."
            refreshed["updated_item"] = _normalize_item(updated, path)
            return refreshed
    return {"ok": False, "message": "Domanda non trovata nella coda di revisione.", "errors": {"id": "Elemento non disponibile."}}


__all__ = [
    "load_lex_dataset_review_queue",
    "update_lex_dataset_review_item",
]
