"""Pipeline operativa cliente -> incasso per le superfici UI."""

from __future__ import annotations

from typing import Any, Iterable


def _stato_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip().upper()


def _sum_importo(items: Iterable[Any]) -> float:
    return round(sum(float(getattr(item, "totale", 0.0) or 0.0) for item in items), 2)


def build_cliente_workflow_pipeline(
    *,
    cliente: Any,
    preventivi: Iterable[Any],
    conferimenti: Iterable[Any],
    fascicoli: Iterable[Any],
    parcelle: Iterable[Any],
    timesheet_entries: Iterable[Any],
) -> dict[str, Any]:
    preventivi = list(preventivi or [])
    conferimenti = list(conferimenti or [])
    fascicoli = list(fascicoli or [])
    parcelle = list(parcelle or [])
    timesheet_entries = list(timesheet_entries or [])

    accepted = [
        row
        for row in preventivi
        if _stato_value(getattr(row, "stato", "")) in {"ACCETTATO", "CONVERTITO"}
    ]
    emesse = [
        row for row in parcelle if _stato_value(getattr(row, "stato", "")) not in {"BOZZA", "ANNULLATA"}
    ]
    pagate = [row for row in emesse if _stato_value(getattr(row, "stato", "")) == "PAGATA"]
    insolute = [row for row in emesse if _stato_value(getattr(row, "stato", "")) in {"EMESSA", "SCADUTA"}]

    open_balance = round(_sum_importo(insolute), 2)
    hours_total = round(sum(float(getattr(row, "ore", 0.0) or 0.0) for row in timesheet_entries), 2)

    current_key = "preventivo"
    current_label = "Apri il primo preventivo guidato."
    tone = "secondary"
    if not preventivi:
        current_key = "preventivo"
        current_label = "Apri il primo preventivo guidato."
        tone = "primary"
    elif not conferimenti:
        current_key = "conferimento"
        current_label = "Trasforma il preventivo accettato in conferimento di incarico."
        tone = "info"
    elif not fascicoli:
        current_key = "fascicolo"
        current_label = "Apri il fascicolo operativo dal workflow commerciale."
        tone = "warning"
    elif not timesheet_entries:
        current_key = "attivita"
        current_label = "Registra il tempo sulle attivita' della pratica per misurare il lavoro reale."
        tone = "warning"
    elif not emesse:
        current_key = "fattura"
        current_label = "Valida il lavoro svolto e genera la prima parcella."
        tone = "danger"
    elif open_balance > 0:
        current_key = "incasso"
        current_label = "Sollecita gli incassi aperti e aggiorna il saldo cliente."
        tone = "danger"
    else:
        current_key = "presidio"
        current_label = "La pipeline e' coperta: presidia scadenze, ore e prossima fatturazione."
        tone = "success"

    stages = [
        {
            "key": "cliente",
            "label": "Cliente",
            "complete": bool(cliente),
            "count": 1 if cliente else 0,
            "tone": "success" if cliente else "secondary",
        },
        {
            "key": "preventivo",
            "label": "Preventivo",
            "complete": bool(preventivi),
            "count": len(preventivi),
            "tone": "primary" if preventivi else "secondary",
        },
        {
            "key": "conferimento",
            "label": "Conferimento",
            "complete": bool(conferimenti),
            "count": len(conferimenti),
            "tone": "success" if conferimenti else "secondary",
        },
        {
            "key": "fascicolo",
            "label": "Fascicolo",
            "complete": bool(fascicoli),
            "count": len(fascicoli),
            "tone": "info" if fascicoli else "secondary",
        },
        {
            "key": "attivita",
            "label": "Attivita' / tempo",
            "complete": bool(timesheet_entries),
            "count": len(timesheet_entries),
            "tone": "warning" if timesheet_entries else "secondary",
        },
        {
            "key": "fattura",
            "label": "Fattura / incasso",
            "complete": bool(emesse),
            "count": len(emesse),
            "tone": "danger" if emesse else "secondary",
        },
    ]

    issues: list[str] = []
    if preventivi and not accepted:
        issues.append("Esistono preventivi ma nessuno e' ancora accettato.")
    if conferimenti and not fascicoli:
        issues.append("Ci sono conferimenti attivi senza fascicolo operativo collegato.")
    if hours_total > 0 and not emesse:
        issues.append("Hai gia' ore registrate ma nessuna parcella emessa.")
    if open_balance > 0:
        issues.append("Sono presenti importi da incassare sul cliente.")

    return {
        "stages": stages,
        "current_key": current_key,
        "current_label": current_label,
        "tone": tone,
        "accepted_preventivi": len(accepted),
        "totale_preventivi": len(preventivi),
        "totale_conferimenti": len(conferimenti),
        "totale_fascicoli": len(fascicoli),
        "totale_voci_timesheet": len(timesheet_entries),
        "ore_lavorate": hours_total,
        "totale_fatture_emesse": len(emesse),
        "totale_fatture_pagate": len(pagate),
        "saldo_aperto": open_balance,
        "issues": issues,
    }


def build_fascicolo_workflow_pipeline(
    *,
    fascicolo: Any,
    cliente: Any = None,
    preventivo: Any = None,
    conferimento: Any = None,
    parcelle: Iterable[Any] | None = None,
    timesheet_entries: Iterable[Any] | None = None,
) -> dict[str, Any]:
    parcelle = list(parcelle or [])
    timesheet_entries = list(timesheet_entries or [])
    emesse = [row for row in parcelle if _stato_value(getattr(row, "stato", "")) not in {"BOZZA", "ANNULLATA"}]
    pagate = [row for row in emesse if _stato_value(getattr(row, "stato", "")) == "PAGATA"]
    attivita_count = int(getattr(fascicolo, "attivita_count", 0) or 0)
    saldo_aperto = round(
        sum(
            float(getattr(row, "totale", 0.0) or 0.0)
            for row in emesse
            if _stato_value(getattr(row, "stato", "")) in {"EMESSA", "SCADUTA"}
        ),
        2,
    )

    stages = [
        {
            "key": "cliente",
            "label": "Cliente collegato",
            "complete": bool(cliente or getattr(fascicolo, "id_cliente", "")),
            "count": 1 if (cliente or getattr(fascicolo, "id_cliente", "")) else 0,
            "tone": "success" if (cliente or getattr(fascicolo, "id_cliente", "")) else "secondary",
        },
        {
            "key": "preventivo",
            "label": "Preventivo / conferimento",
            "complete": bool(preventivo or conferimento),
            "count": (1 if preventivo else 0) + (1 if conferimento else 0),
            "tone": "primary" if (preventivo or conferimento) else "secondary",
        },
        {
            "key": "attivita",
            "label": "Attivita' procedurali",
            "complete": bool(attivita_count),
            "count": attivita_count,
            "tone": "info" if attivita_count else "secondary",
        },
        {
            "key": "timesheet",
            "label": "Timesheet",
            "complete": bool(timesheet_entries),
            "count": len(timesheet_entries),
            "tone": "warning" if timesheet_entries else "secondary",
        },
        {
            "key": "fattura",
            "label": "Parcella / incasso",
            "complete": bool(emesse),
            "count": len(emesse),
            "tone": "danger" if emesse else "secondary",
        },
    ]

    next_action = "Registra la prima attivita' di fascicolo."
    tone = "secondary"
    if not attivita_count:
        next_action = "Registra le prime attivita' operative del fascicolo."
        tone = "info"
    elif not timesheet_entries:
        next_action = "Inizia a tracciare il tempo lavorato per questa pratica."
        tone = "warning"
    elif not emesse:
        next_action = "Consolida il lavoro svolto e genera la parcella collegata."
        tone = "danger"
    elif saldo_aperto > 0:
        next_action = "Aggiorna l'incasso o attiva il sollecito cliente."
        tone = "danger"
    else:
        next_action = "Pipeline economica coperta: presidia le prossime attivita'."
        tone = "success"

    return {
        "stages": stages,
        "next_action": next_action,
        "tone": tone,
        "saldo_aperto": saldo_aperto,
        "parcelle_emesse": len(emesse),
        "parcelle_pagate": len(pagate),
        "ore_lavorate": round(sum(float(getattr(row, "ore", 0.0) or 0.0) for row in timesheet_entries), 2),
    }
