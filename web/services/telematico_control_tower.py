"""Servizi di sintesi per la Control Tower telematica."""

from __future__ import annotations

from typing import Any


SERVICE_LABELS = {
    "polisweb_consultazione": "PST / PolisWeb",
    "pdp_penale": "PDP Penale",
    "pat_siga": "PAT / SIGA",
    "ptt_sigit": "PTT / SIGIT",
}

PENDING_STATUSES = {
    "submitted",
    "in_review",
    "integration_requested",
    "download_available",
    "ready_for_filing",
}

WARNING_STATUSES = {
    "manual_review_required",
    "download_available",
    "integration_requested",
    "technical_error",
    "rejected",
}

BLOCKED_STATUSES = {
    "technical_error",
    "rejected",
    "manual_review_required",
}


def _service_label(service_code: str) -> str:
    return SERVICE_LABELS.get(str(service_code or "").strip(), str(service_code or "").replace("_", " ").title())


def _decorate_case(row: dict[str, Any], fascicoli_index: dict[str, Any]) -> dict[str, Any]:
    practice_id = str(row.get("practice_id") or "")
    fascicolo = fascicoli_index.get(practice_id)
    return {
        **row,
        "service_label": _service_label(str(row.get("service_code") or "")),
        "practice_title": getattr(fascicolo, "titolo", "") if fascicolo else "",
        "practice_number": getattr(fascicolo, "numero", "") if fascicolo else "",
        "warning": str(row.get("internal_status") or "") in WARNING_STATUSES,
        "blocked": str(row.get("internal_status") or "") in BLOCKED_STATUSES,
    }


def _predeposito_checks(case_row: dict[str, Any]) -> list[str]:
    checks: list[str] = []
    if int(case_row.get("documents_count") or 0) <= 0:
        checks.append("mancano documenti collegati")
    if int(case_row.get("open_tasks_count") or 0) > 0:
        checks.append("restano task operativi aperti")
    status = str(case_row.get("internal_status") or "")
    if status in {"draft", "ready_for_filing"}:
        checks.append("verificare allegati, firma e stato finale")
    if status == "integration_requested":
        checks.append("integrazione richiesta dal canale telematico")
    if status == "technical_error":
        checks.append("presidiare errore tecnico prima del nuovo invio")
    return checks


def build_telematico_control_tower(
    *,
    get_telematico,
    get_fascicoli,
    limit: int = 24,
) -> dict[str, Any]:
    repo = get_telematico()
    fascicoli_index = {fasc.id: fasc for fasc in get_fascicoli().tutti()}
    practice_ids = {str(practice_id) for practice_id in fascicoli_index if str(practice_id)}
    stats = repo.case_stats(practice_ids=practice_ids)
    recent_cases = [
        _decorate_case(row, fascicoli_index)
        for row in repo.list_cases(practice_ids=practice_ids, limit=max(int(limit or 24), 24))
    ]
    recent_events = list(repo.list_recent_events(practice_ids=practice_ids, limit=12))

    pending_outcomes = [row for row in recent_cases if str(row.get("internal_status") or "") in PENDING_STATUSES][:8]
    incomplete_imports = [
        row
        for row in recent_cases
        if str(row.get("internal_status") or "") in {"draft", "opened_official_portal", "manual_review_required"}
    ][:8]
    warning_cases = [row for row in recent_cases if row.get("warning")][:8]
    blocked_cases = [row for row in recent_cases if row.get("blocked")][:8]

    predeposito = []
    for row in recent_cases:
        checks = _predeposito_checks(row)
        if not checks:
            continue
        predeposito.append(
            {
                "case": row,
                "checks": checks,
            }
        )
    predeposito = predeposito[:8]

    channel_cards = []
    per_service = dict(stats.get("per_service") or {})
    for service_code, label in SERVICE_LABELS.items():
        item = dict(per_service.get(service_code) or {})
        channel_cases = [row for row in recent_cases if row.get("service_code") == service_code]
        channel_cards.append(
            {
                "service_code": service_code,
                "label": label,
                "totale": int(item.get("totale") or 0),
                "import_completed": int(item.get("import_completed") or 0),
                "attention_needed": int(item.get("attention_needed") or 0),
                "pending": len([row for row in channel_cases if str(row.get("internal_status") or "") in PENDING_STATUSES]),
                "blocked": len([row for row in channel_cases if row.get("blocked")]),
            }
        )

    return {
        "summary": {
            "totale": int(stats.get("totale") or 0),
            "pending_outcomes": len(pending_outcomes),
            "imports_incomplete": len(incomplete_imports),
            "warnings": len(warning_cases),
            "blocked": len(blocked_cases),
        },
        "channel_cards": channel_cards,
        "pending_outcomes": pending_outcomes,
        "incomplete_imports": incomplete_imports,
        "warning_cases": warning_cases,
        "predeposito": predeposito,
        "blocked_cases": blocked_cases,
        "recent_events": recent_events,
    }
