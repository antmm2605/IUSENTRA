"""Vista unificata di comprensione dell'evento legale della PEC (deterministica).

Aggrega i segnali GIÀ prodotti dalla pipeline in un unico schema pulito, senza
creare una nuova source of truth né riscrivere logica:
- classificazione legale (`parsed["legal_workflow"]`);
- udienza (`report["remote_hearing"]` — modalità unificata, link, verificato);
- termine legale proposto (`pec_legal_deadline_proposer` — motore deterministico);
- catena ricevute PCT (`parsed["pct_deposit_receipt"]`).

È il "cosa devo fare" per l'avvocato/Lex. Lex va chiamato SOLO per disambiguare i
casi `incerto` (non implementato qui: deterministico-first, fail-closed). Le web push
non devono mai contenere PII: usare `web_push_safe_title`.
"""

from __future__ import annotations

from typing import Any

from pct.pec_legal_deadline_proposer import propose_legal_deadline

SCHEMA = "iusentra.pec.legal_event_understanding.v2"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _hearing_view(remote_hearing: dict[str, Any]) -> dict[str, Any] | None:
    if not remote_hearing or not (remote_hearing.get("detected") or remote_hearing.get("pdf_required")):
        return None
    links = [str(link.get("url") or "") for link in remote_hearing.get("links", []) if isinstance(link, dict)]
    return {
        "mode": remote_hearing.get("mode_unified") or remote_hearing.get("mode") or "incerta",
        "links": [url for url in links if url],
        "link_verified": bool(remote_hearing.get("verified") or remote_hearing.get("remote_hearing_verified")),
        "times": list(remote_hearing.get("times") or []),
        "pdf_required": bool(remote_hearing.get("pdf_required")),
        "human_review_required": not links,
    }


def build_legal_event_understanding(
    parsed: dict[str, Any],
    report: dict[str, Any] | None = None,
    *,
    dies_a_quo_date: str = "",
) -> dict[str, Any]:
    """Aggrega i segnali esistenti nello schema v2. Sola lettura, deterministico."""

    parsed = _dict(parsed)
    report = _dict(report)
    legal_workflow = _dict(parsed.get("legal_workflow"))
    remote_hearing = _dict(report.get("remote_hearing")) or _dict(_dict(report.get("procedural_profile")).get("remote_hearing"))
    body = _dict(parsed.get("body"))
    headers = _dict(parsed.get("headers"))

    event_type = str(legal_workflow.get("event_type") or "")
    text = " ".join(str(v) for v in (headers.get("subject"), body.get("text"), body.get("ics_text")) if v)

    hearing = _hearing_view(remote_hearing)
    deadline = propose_legal_deadline(
        text, dies_a_quo_date=dies_a_quo_date or headers.get("date") or "", event_type=event_type
    )

    pct_receipt = _dict(parsed.get("pct_deposit_receipt")) or None

    human_review = bool(
        legal_workflow.get("human_review_required")
        or (hearing and hearing.get("human_review_required"))
        or (isinstance(deadline, dict) and deadline.get("human_review_required"))
        or not event_type
    )

    return {
        "schema": SCHEMA,
        "classification": {
            "family": legal_workflow.get("family") or "",
            "family_label": legal_workflow.get("family_label") or "",
            "primary_event": event_type,
            "event_label": legal_workflow.get("event_label") or "",
            "priority": legal_workflow.get("priority") or "media",
        },
        "hearing": hearing,
        "deadline": deadline if isinstance(deadline, dict) else None,
        "pct_receipt": pct_receipt,
        "human_review_required": human_review,
        "web_push_safe_title": _safe_title(legal_workflow, hearing, deadline),
    }


def _safe_title(legal_workflow: dict[str, Any], hearing: dict[str, Any] | None, deadline: Any) -> str:
    """Titolo sintetico per web push: nessuna PII, solo la natura dell'evento."""

    if hearing and hearing.get("mode") in {"remoto", "mista"} and not hearing.get("links"):
        return "P0 · Udienza da remoto senza link"
    if isinstance(deadline, dict) and deadline.get("ok") and str(deadline.get("tipo")) == "perentorio":
        return "Termine perentorio rilevato in PEC"
    label = str(legal_workflow.get("event_label") or legal_workflow.get("family_label") or "Evento legale")
    return label[:80]


__all__ = ["build_legal_event_understanding", "SCHEMA"]
