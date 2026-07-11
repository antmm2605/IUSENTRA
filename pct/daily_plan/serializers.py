"""Serializzazione API del piano del giorno e sintesi deterministica.

Il payload iniziale è minimo (riepilogo, copertura, attività sintetiche,
conteggio evidenze): testi completi ed evidenze si caricano dal dettaglio.
La sintesi per l'avvocato esiste SEMPRE anche senza modello linguistico.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import DailyPlan, DailyWorkItem

_SECTION_BY_SECTOR = {
    "pec": "pec",
    "agenda": "agenda",
    "scadenze": "fascicoli",
    "documenti": "fascicoli",
    "relata": "fascicoli",
    "telematico": "fascicoli",
    "doppioni": "fascicoli",
    "economico": "economico",
}


def _format_date_it(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw[:19])
    except Exception:
        return raw
    if len(raw) > 10:
        return parsed.strftime("%d/%m/%Y %H:%M")
    return parsed.strftime("%d/%m/%Y")


def item_summary_payload(item: DailyWorkItem) -> dict[str, Any]:
    """Riga sintetica: nessun testo lungo, nessuna evidenza (solo conteggio)."""
    return {
        "id": item.id,
        "titolo": item.title,
        "priorita": item.priority,
        "ordine": item.item_rank,
        "stato": item.status,
        "settore": item.sector,
        "tipo_azione": item.action_kind,
        "motivo": item.reason,
        "scadenza": item.due_at,
        "scadenza_label": _format_date_it(item.due_at),
        "fascicolo_id": item.fascicolo_id,
        "fascicolo": item.fascicolo_label,
        "cliente": item.cliente_label,
        "assegnato_a": item.assigned_user_id,
        "assegnato_label": item.assigned_lawyer_label,
        "bloccante": item.blocking,
        "perentorio": item.peremptory,
        "affidabilita": round(float(item.confidence or 0.0), 2),
        "da_rivedere": item.review_required,
        "fascia_proposta": item.scheduled_start,
        "minuti_stimati": item.estimated_minutes,
        "in_backlog": item.in_backlog,
        "evidenze": len(item.evidence),
        "apri": item.href,
        "azioni": list(item.available_actions),
    }


def item_detail_payload(item: DailyWorkItem) -> dict[str, Any]:
    """Dettaglio lazy: evidenze complete + spiegazione della priorità."""
    payload = item_summary_payload(item)
    payload.update(
        {
            "spiegazione_priorita": item.priority_reason,
            "regola_priorita": item.priority_rule,
            "evidenze_dettaglio": [e.to_dict() for e in item.evidence],
            "segnali_origine": list(item.source_signal_ids),
            "nota_stato": item.status_note,
            "stato_aggiornato_da": item.status_actor,
            "stato_aggiornato_il": item.status_updated_at,
            "rinviata_fino_a": item.snoozed_until,
        }
    )
    return payload


def plan_summary_payload(plan: DailyPlan) -> dict[str, Any]:
    """Payload principale della pagina Oggi (solo snapshot, redatto)."""
    sections: dict[str, list[dict[str, Any]]] = {
        "da_fare_ora": [],
        "pec": [],
        "fascicoli": [],
        "economico": [],
        "da_assegnare": [],
    }
    for item in plan.work_items:
        row = item_summary_payload(item)
        if not item.assigned_user_id and plan.user_id == "":
            sections["da_assegnare"].append(row)
            continue
        if item.priority in ("P0", "P1"):
            sections["da_fare_ora"].append(row)
        section = _SECTION_BY_SECTOR.get(item.sector, "fascicoli")
        if section in sections and item.priority not in ("P0", "P1"):
            sections[section].append(row)

    return {
        "ok": True,
        "stato": "pronto",
        "data": plan.target_date,
        "data_label": _format_date_it(plan.target_date),
        "utente": plan.user_id,
        "versione_piano": plan.plan_version,
        "generato_il": plan.generated_at,
        "generato_il_label": _format_date_it(plan.generated_at),
        "modalita_generazione": plan.generation_mode,
        "freschezza": dict(plan.freshness),
        "copertura": [c.to_dict() for c in plan.coverage],
        "copertura_completa": plan.coverage_complete,
        "riepilogo": dict(plan.summary),
        "sezioni": sections,
        "agenda_oggi": list(plan.fixed_agenda_items),
        "avvisi": list(plan.warnings),
        "sintesi": plan.lex_summary or deterministic_summary(plan),
        "sintesi_da_lex": bool(plan.lex_summary),
    }


def plan_missing_payload(target_date: str, user_id: str) -> dict[str, Any]:
    """Il piano non è ancora stato generato: la lettura resta immediata."""
    return {
        "ok": True,
        "stato": "non_generato",
        "data": target_date,
        "data_label": _format_date_it(target_date),
        "utente": user_id,
        "versione_piano": "",
        "copertura": [],
        "copertura_completa": False,
        "riepilogo": {"totale": 0},
        "sezioni": {"da_fare_ora": [], "pec": [], "fascicoli": [], "economico": [], "da_assegnare": []},
        "agenda_oggi": [],
        "avvisi": [
            "Il piano della data selezionata non è ancora stato generato: usa Aggiorna."
        ],
        "sintesi": "Il piano operativo della data selezionata non è ancora disponibile.",
        "sintesi_da_lex": False,
    }


def deterministic_summary(plan: DailyPlan) -> str:
    """Sintesi concreta senza LLM: cosa fare, perché, entro quando, fonte."""
    counts = plan.summary.get("per_priorita") or {}
    p0 = int(counts.get("P0") or 0)
    p1 = int(counts.get("P1") or 0)
    da_assegnare = int(plan.summary.get("da_assegnare_studio") or 0)

    if not plan.work_items:
        if not plan.coverage_complete:
            return (
                "Nessuna attività elencata, ma alcune fonti non sono aggiornate: "
                "verifica la copertura prima di considerare libera la giornata."
            )
        return "Per la data selezionata non risultano attività urgenti: agenda e scadenze sono sotto controllo."

    frasi: list[str] = []
    frasi.append(
        f"Nel giorno selezionato hai {p0} attività immediate e {p1} da completare entro la giornata"
        + (f", con {da_assegnare} elementi da assegnare." if da_assegnare else ".")
    )
    for idx, item in enumerate(plan.work_items[:3], start=1):
        fonte = item.evidence[0].source_type if item.evidence else "presidio"
        pezzi = [f"{idx}. {item.title}."]
        if item.reason:
            pezzi.append(f"Motivo: {item.reason}")
        if item.fascicolo_label:
            pezzi.append(f"Fascicolo: {item.fascicolo_label}.")
        if item.due_at:
            pezzi.append(f"Entro: {_format_date_it(item.due_at)}.")
        pezzi.append(f"Fonte: {fonte}.")
        if item.review_required:
            pezzi.append("Richiede conferma da parte tua.")
        frasi.append(" ".join(pezzi))
    return "\n".join(frasi)


__all__ = [
    "deterministic_summary",
    "item_detail_payload",
    "item_summary_payload",
    "plan_missing_payload",
    "plan_summary_payload",
]
