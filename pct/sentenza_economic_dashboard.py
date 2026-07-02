"""Aggregazione economica delle sentenze per la dashboard fascicolo e per il
contesto economico condiviso.

Modulo piccolo e a parte per non gonfiare `economic_dashboard`. Non calcola nulla
di nuovo sul piano economico: somma solo gli eventi economici gia' verificati o in
attesa di conferma prodotti dal controllo sentenze (art. 91/93 c.p.c., D.P.R.
115/2002), e li rende come KPI/worklist additivi e come blocco di contesto
pass-through.
"""

from __future__ import annotations

from typing import Any

from pct.economic_dashboard import _currency

_EVENTI_APERTI = {"to_review", "confirmed"}


def _sum_eventi(events: list[dict[str, Any]], event_type: str) -> float:
    total = sum(
        float(event.get("amount") or 0.0)
        for event in events
        if event.get("event_type") == event_type and event.get("status") in _EVENTI_APERTI
    )
    return round(total, 2)


def build_sentenze_economiche_summary(audits: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Riepilogo additivo per la dashboard. Ritorna kpi + worklist + totals."""

    sentenze_lette = len(audits)
    verificate = sum(1 for audit in audits if audit.get("safe_to_attach"))
    da_verificare = sum(
        1 for audit in audits
        if audit.get("human_review_required") or audit.get("status") in {"to_review", "needs_reconciliation"}
    )
    crediti_cliente = _sum_eventi(events, "apri_credito_cliente")
    crediti_avvocato = _sum_eventi(events, "apri_credito_avvocato_antistatario")
    spese_totale = round(crediti_cliente + crediti_avvocato, 2)
    cu_alert = sum(
        1 for event in events
        if event.get("event_type") == "verifica_contributo_unificato" and event.get("status") == "to_review"
    )

    totals = {
        "sentenze_lette": sentenze_lette,
        "sentenze_verificate": verificate,
        "da_verificare": da_verificare,
        "crediti_cliente": crediti_cliente,
        "crediti_avvocato_antistatario": crediti_avvocato,
        "spese_liquidate_totale": spese_totale,
        "contributo_unificato_alert": cu_alert,
    }

    worklist: list[dict[str, Any]] = []
    if da_verificare:
        worklist.append({
            "label": "Sentenze da verificare",
            "hint": "Controllo economico da confermare prima di ogni azione.",
            "value": str(da_verificare),
            "tone": "warning",
        })
    if crediti_cliente > 0:
        worklist.append({
            "label": "Spese liquidate da incassare (cliente)",
            "hint": "Credito della parte ex art. 91 c.p.c.",
            "value": _currency(crediti_cliente),
            "tone": "info",
        })
    if crediti_avvocato > 0:
        worklist.append({
            "label": "Spese distratte in favore dell'avvocato",
            "hint": "Credito diretto ex art. 93 c.p.c.",
            "value": _currency(crediti_avvocato),
            "tone": "info",
        })
    if cu_alert:
        worklist.append({
            "label": "Contributo unificato da verificare",
            "hint": "Controllo D.P.R. 115/2002.",
            "value": str(cu_alert),
            "tone": "warning",
        })

    kpi = {
        "label": "Spese da sentenza",
        "value": _currency(spese_totale),
        "tone": "primary" if spese_totale > 0 else "secondary",
    }
    return {"kpi": kpi, "worklist": worklist, "totals": totals}


def build_sentenza_economic_context_block(audit: dict[str, Any]) -> dict[str, Any]:
    """Blocco di contesto economico pass-through (source=sentenza_economic_audit).

    Pensato per essere annidato nel `log_calcolo` della parcella (incr. 5), non per
    sostituire il contesto tariffario. Sopravvive a `sincronizza_contesto_economico`
    perche' e' una chiave top-level non nota (preservata).
    """

    match = audit.get("match") if isinstance(audit.get("match"), dict) else {}
    sentenza = audit.get("sentenza") if isinstance(audit.get("sentenza"), dict) else {}
    return {
        "source": "sentenza_economic_audit",
        "source_label": "Controllo economico da sentenza",
        "documento_origine": {
            "documento_id": str(audit.get("documento_id", "") or ""),
            "hash_sha256": str(audit.get("document_hash_sha256", "") or ""),
            "fonte": str(audit.get("fonte", "") or ""),
        },
        "sentenza_economic_audit": {
            "match_score": float(match.get("overall_score", 0) or 0),
            "safe_to_attach": bool(audit.get("safe_to_attach", False)),
            "spese_liquidate": sentenza.get("spese_liquidate", {}),
            "contributo_unificato": audit.get("contributo_unificato", {}),
            "azioni": audit.get("azioni", []),
        },
    }


__all__ = ["build_sentenze_economiche_summary", "build_sentenza_economic_context_block"]
