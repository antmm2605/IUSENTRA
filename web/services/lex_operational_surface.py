"""Superfici operative vere per Lex oltre la sola chat."""

from __future__ import annotations

from typing import Any

from web.services.hearing_preparation_dashboard import build_hearing_preparation_dashboard
from web.services.telematico_control_tower import build_telematico_control_tower


def _build_fascicolo_surface(overview: dict[str, Any]) -> dict[str, Any]:
    fascicoli_hot = list(overview.get("fascicoli_hot") or [])
    cards = []
    for row in fascicoli_hot[:6]:
        scadenze = list(row.get("scadenze") or [])
        appuntamenti = list(row.get("appuntamenti") or [])
        warnings = []
        if scadenze:
            warnings.append("scadenze aperte")
        if appuntamenti:
            warnings.append("udienza o appuntamento vicino")
        if not row.get("giurisprudenza"):
            warnings.append("ricerca giurisprudenziale da presidiare")
        cards.append(
            {
                "id": row.get("id"),
                "title": row.get("titolo"),
                "numero": row.get("numero"),
                "tribunale": row.get("tribunale"),
                "warnings": warnings[:3],
                "missing": "Collegare atti, allegati o fonti ufficiali residue." if not row.get("giurisprudenza") else "Verificare completezza degli ultimi documenti.",
                "next_actions": list(row.get("azioni") or [])[:3],
            }
        )

    return {
        "label": "Lex Fascicolo",
        "summary": "Sintesi pratica, documenti chiave, rischi aperti e cosa manca davvero.",
        "cards": cards,
    }


def _build_udienza_surface() -> dict[str, Any]:
    dashboard = build_hearing_preparation_dashboard()
    cases = []
    for row in list(dashboard.get("cases") or [])[:6]:
        critical = [badge.get("label") for badge in list(row.get("critical_badges") or []) if badge.get("label")]
        cases.append(
            {
                "id": row.get("id"),
                "title": row.get("titolo"),
                "cliente": row.get("cliente"),
                "udienza": row.get("data_udienza_label"),
                "timeline": row.get("timeline_label"),
                "documenti": {
                    "acquisiti": row.get("documenti_acquisiti"),
                    "mancanti": row.get("documenti_mancanti"),
                },
                "critical_points": critical[:4],
            }
        )
    return {
        "label": "Lex Udienza",
        "summary": "Preparazione udienza, timeline, allegati da rivedere e punti critici.",
        "metrics": list(dashboard.get("metrics") or []),
        "cases": cases,
    }


def _build_telematico_surface(control_tower: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": "Lex Telematico",
        "summary": "Spiegazione errori, stato import e deposito, piu' verifiche prima del prossimo passo.",
        "summary_counts": dict(control_tower.get("summary") or {}),
        "warning_cases": list(control_tower.get("warning_cases") or [])[:6],
        "predeposito": list(control_tower.get("predeposito") or [])[:6],
    }


def _build_operativo_surface(overview: dict[str, Any]) -> dict[str, Any]:
    urgent_deadlines = list(overview.get("urgent_deadlines") or [])
    upcoming_appointments = list(overview.get("upcoming_appointments") or [])
    actions = list(overview.get("actions") or [])
    return {
        "label": "Lex Operativo",
        "summary": "La prossima azione giusta della giornata, con priorita e scadenze che stanno diventando problemi.",
        "actions": actions[:6],
        "urgent_deadlines": urgent_deadlines[:6],
        "upcoming_appointments": upcoming_appointments[:6],
    }


def build_lex_operational_payload(
    *,
    get_workspace_intelligente,
    get_fascicoli,
    get_telematico,
    horizon_days: int = 14,
) -> dict[str, Any]:
    overview = get_workspace_intelligente().panoramica(horizon_days=horizon_days, hot_limit=8)
    control_tower = build_telematico_control_tower(
        get_telematico=get_telematico,
        get_fascicoli=get_fascicoli,
    )
    return {
        "overview": overview,
        "control_tower": control_tower,
        "fascicolo": _build_fascicolo_surface(overview),
        "udienza": _build_udienza_surface(),
        "telematico": _build_telematico_surface(control_tower),
        "operativo": _build_operativo_surface(overview),
    }

