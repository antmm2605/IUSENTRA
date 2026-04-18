"""Snapshot operativo per dimostrare il valore di IUSENTRA in pochi minuti."""

from __future__ import annotations

from typing import Any, Iterable


def _stato_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip().upper()


def _count(items: Iterable[Any]) -> int:
    return len(list(items or []))


def build_studio_demo_snapshot(
    *,
    clienti: Iterable[Any],
    preventivi: Iterable[Any],
    conferimenti: Iterable[Any],
    fascicoli: Iterable[Any],
    timesheet_entries: Iterable[Any],
    parcelle: Iterable[Any],
    payment_links: Iterable[Any] | None = None,
) -> dict[str, Any]:
    clienti = list(clienti or [])
    preventivi = list(preventivi or [])
    conferimenti = list(conferimenti or [])
    fascicoli = list(fascicoli or [])
    timesheet_entries = list(timesheet_entries or [])
    parcelle = list(parcelle or [])
    payment_links = list(payment_links or [])

    accepted_preventivi = [
        row for row in preventivi if _stato_value(getattr(row, "stato", "")) in {"ACCETTATO", "CONVERTITO"}
    ]
    valid_time = [
        row
        for row in timesheet_entries
        if bool(getattr(row, "fatturabile", False))
        and _stato_value(getattr(row, "stato", "")) in {"VALIDATO", "FATTURATO"}
    ]
    emesse = [
        row for row in parcelle if _stato_value(getattr(row, "stato", "")) not in {"BOZZA", "ANNULLATA"}
    ]
    incassate = [row for row in emesse if _stato_value(getattr(row, "stato", "")) == "PAGATA"]
    link_attivi = [
        row for row in payment_links if _stato_value(getattr(row, "stato", "")) == "ATTESO"
    ]

    steps = [
        {
            "key": "cliente",
            "label": "Primo cliente",
            "count": len(clienti),
            "complete": bool(clienti),
            "hint": "Apri l'anagrafica e censisci il primo soggetto o cliente pagante.",
        },
        {
            "key": "preventivo",
            "label": "Primo preventivo",
            "count": len(preventivi),
            "complete": bool(preventivi),
            "hint": "Usa il preventivo guidato per trasformare la richiesta in percorso operativo.",
        },
        {
            "key": "conferimento",
            "label": "Primo conferimento",
            "count": len(conferimenti),
            "complete": bool(conferimenti),
            "hint": "Conferma l'incarico e porta il caso nel workflow formale.",
        },
        {
            "key": "fascicolo",
            "label": "Primo fascicolo",
            "count": len(fascicoli),
            "complete": bool(fascicoli),
            "hint": "Apri il fascicolo come centro unico di attivita', documenti, scadenze ed economia.",
        },
        {
            "key": "attivita",
            "label": "Prima attivita' / tempo",
            "count": len(timesheet_entries),
            "complete": bool(timesheet_entries),
            "hint": "Registra il lavoro reale per non perdere produttivita' e marginalita'.",
        },
        {
            "key": "parcella",
            "label": "Prima parcella",
            "count": len(emesse),
            "complete": bool(emesse),
            "hint": "Trasforma tempo e attivita' validate in parcella senza passaggi manuali ridondanti.",
        },
        {
            "key": "incasso",
            "label": "Primo incasso",
            "count": len(incassate),
            "complete": bool(incassate),
            "hint": "Chiudi il ciclo economico con link di pagamento o registrazione dell'incasso.",
        },
    ]

    next_action = next((row["hint"] for row in steps if not row["complete"]), "")
    if not next_action:
        next_action = "Il ciclo cliente -> incasso e' coperto: presidia scadenze, redditivita' e prossima fatturazione."

    tempo_valorizzabile = round(sum(float(getattr(row, "valore_totale", 0.0) or 0.0) for row in valid_time), 2)
    saldo_aperto = round(
        sum(
            float(getattr(row, "totale", 0.0) or 0.0)
            for row in emesse
            if _stato_value(getattr(row, "stato", "")) in {"EMESSA", "SCADUTA"}
        ),
        2,
    )

    ready_steps = sum(1 for row in steps if row["complete"])
    return {
        "headline": "Studio reale in 5 minuti",
        "ready": ready_steps == len(steps),
        "ready_steps": ready_steps,
        "steps_total": len(steps),
        "next_action": next_action,
        "tempo_valorizzabile": tempo_valorizzabile,
        "saldo_aperto": saldo_aperto,
        "link_incasso_attivi": len(link_attivi),
        "steps": steps,
    }
