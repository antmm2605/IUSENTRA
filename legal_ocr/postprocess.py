from __future__ import annotations

import re
import uuid
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from typing import Any


def compute_metrics(tokens: list[dict[str, Any]], *, language_confidence: float = 0.0) -> dict[str, Any]:
    if not tokens:
        return {"avg_confidence": 0.0, "pct_tokens_<0.75": 100.0, "pct_tokens_<0.50": 100.0, "lang_conf": float(language_confidence or 0.0), "layout_anomalies": {"missing_bbox_pct": 100.0, "line_order_anomalies": 0}}
    total = sum(max(1, len(str(t.get("token") or ""))) for t in tokens)
    weighted = sum(float(t.get("confidence") or 0.0) * max(1, len(str(t.get("token") or ""))) for t in tokens)
    low = sum(1 for t in tokens if float(t.get("confidence") or 0.0) < 0.75)
    very_low = sum(1 for t in tokens if float(t.get("confidence") or 0.0) < 0.50)
    missing_bbox = sum(1 for t in tokens if not t.get("bbox"))
    return {"avg_confidence": round(weighted / total, 4), "pct_tokens_<0.75": round(low / len(tokens) * 100, 3), "pct_tokens_<0.50": round(very_low / len(tokens) * 100, 3), "lang_conf": float(language_confidence or 0.0), "layout_anomalies": {"missing_bbox_pct": round(missing_bbox / len(tokens) * 100, 3), "line_order_anomalies": 0}}


def apply_deterministic_corrections(text: str, *, user: str = "system") -> tuple[str, list[dict[str, Any]]]:
    corrected = str(text or "")
    history: list[dict[str, Any]] = []
    for rule_id, pattern, replacement, reason in [
        ("punct.art.v1", re.compile(r"\bart\s+\.", re.I), "art.", "Normalizzazione forense art."),
        ("punct.n.v1", re.compile(r"\bN\s+\.", re.I), "N.", "Normalizzazione N."),
        ("ocr.rg.zero.v1", re.compile(r"\bR\s*[G6]\s*0\b", re.I), "RG n.", "Correzione OCR comune per RG n."),
        ("space.pec.v1", re.compile(r"\s+@\s+"), "@", "Rimozione spazi in indirizzo PEC."),
    ]:
        next_text = pattern.sub(replacement, corrected)
        if next_text != corrected:
            history.append({"timestamp": datetime.now(timezone.utc).isoformat(), "user": user, "from": corrected, "to": next_text, "reason": reason, "rule_id": rule_id})
            corrected = next_text
    return corrected, history


def suggested_hil_fixes(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for before, after, rule_id, reason in [("art .", "art.", "punct.art.v1", "Normalizzazione forense art."), ("N .", "N.", "punct.n.v1", "Normalizzazione N."), (" @ ", "@", "space.pec.v1", "Rimozione spazi in indirizzo PEC.")]:
        if before.lower() in str(text or "").lower():
            out.append({"from": before, "to": after, "rule_id": rule_id, "reason": reason})
    return out


def build_lex_export(tokens: list[dict[str, Any]], *, min_confidence: float = 0.75) -> dict[str, Any]:
    kept = [t for t in tokens if float(t.get("confidence") or 0.0) >= min_confidence]
    return {"confidence_policy": "solo token ad alta/media confidenza", "min_confidence": min_confidence, "text": " ".join(str(t.get("token") or "") for t in kept).strip(), "tokens": kept, "fragile_count": len(tokens) - len(kept)}


def build_vector_source_manifest(
    text: str,
    page_texts: list[str],
    *,
    tenant_id: str,
    run_id: str,
    document_id: str = "",
    fascicolo_id: str = "",
    engine: str = "",
    metrics: dict[str, Any] | None = None,
    hil_required: bool = False,
) -> dict[str, Any]:
    complete_text = _normalize_vector_text(text)
    pages_source = [str(item or "") for item in page_texts]
    if not any(item.strip() for item in pages_source) and complete_text:
        pages_source = [complete_text]
    pages: list[dict[str, Any]] = []
    missing_pages: list[int] = []
    for index, raw_page_text in enumerate(pages_source, start=1):
        page_text = _normalize_vector_text(raw_page_text)
        if not page_text:
            missing_pages.append(index)
        pages.append(
            {
                "page": index,
                "chars": len(page_text),
                "empty": not bool(page_text),
                "sha256": sha256(page_text.encode("utf-8")).hexdigest() if page_text else "",
            }
        )
    warnings: list[str] = []
    if missing_pages:
        warnings.append("Una o più pagine non hanno prodotto testo OCR completo.")
    if hil_required:
        warnings.append("Il controllo qualità richiede revisione prima di usare il testo OCR come fonte definitiva.")
    status = "needs_review" if hil_required or missing_pages or not complete_text else "ready"
    return {
        "version": 1,
        "status": status,
        "tenant_id": tenant_id,
        "run_id": run_id,
        "document_id": document_id,
        "fascicolo_id": fascicolo_id,
        "engine": engine,
        "full_text_chars": len(complete_text),
        "full_text_sha256": sha256(complete_text.encode("utf-8")).hexdigest() if complete_text else "",
        "page_count": len(pages),
        "pages_with_text": sum(1 for page in pages if not page["empty"]),
        "missing_pages": missing_pages,
        "metrics": metrics or {},
        "warnings": warnings,
        "pages": pages,
    }


def build_notification_proposals(text: str, *, document_id: str, run_id: str, fascicolo_id: str = "") -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for match in re.finditer(r"\b(?:udienza|comparizione|scadenza|depositare|produrre)\b.{0,80}?(\d{1,2}[/-]\d{1,2}[/-]\d{4})", str(text or ""), flags=re.I):
        proposals.append({"id": str(uuid.uuid4()), "kind": "ocr_legal_deadline", "title": "Data rilevata nel documento", "body": match.group(0).strip(), "priority": "high", "document_id": document_id, "fascicolo_id": fascicolo_id, "run_id": run_id, "due_at": _due(match.group(1)), "href": f"/documenti?documento={document_id}" if document_id else "/documenti"})
    return proposals


def _normalize_vector_text(value: str) -> str:
    text = str(value or "").replace("\ufeff", "").replace("\r", "").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()




def _due(value: str) -> str:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return (datetime.strptime(value, fmt).replace(tzinfo=timezone.utc) - timedelta(hours=9)).isoformat()
        except ValueError:
            pass
    return ""
