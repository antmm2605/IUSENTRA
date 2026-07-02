"""KPI economici e operativi per studio, clienti e fascicoli."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from pct.formatting import format_euro_it
from pct.fascicoli import StatoFascicolo
from pct.fatturazione import StatoParcella


_STATI_CHIUSI = {StatoFascicolo.ARCHIVIATO, StatoFascicolo.DEFINITO}


def _round_amount(value: float | int) -> float:
    return round(float(value or 0.0), 2)


def _currency(value: float | int) -> str:
    return format_euro_it(_round_amount(value))


def _safe_ratio(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return round((num / den) * 100.0, 1)


def _fascicoli_attivi(fascicoli: list[Any]) -> list[Any]:
    return [fascicolo for fascicolo in fascicoli if fascicolo.stato not in _STATI_CHIUSI]


def _build_fascicolo_rows(fascicoli: list[Any], parcelle: list[Any], timesheet_entries: list[Any]) -> list[dict[str, Any]]:
    parcelle_per_fascicolo: dict[str, list[Any]] = defaultdict(list)
    for parcella in parcelle:
        if parcella.id_fascicolo:
            parcelle_per_fascicolo[parcella.id_fascicolo].append(parcella)

    timesheet_per_fascicolo: dict[str, list[Any]] = defaultdict(list)
    for entry in timesheet_entries:
        if entry.id_fascicolo:
            timesheet_per_fascicolo[entry.id_fascicolo].append(entry)

    rows: list[dict[str, Any]] = []
    for fascicolo in fascicoli:
        parcelle_fascicolo = parcelle_per_fascicolo.get(fascicolo.id, [])
        timesheet_fascicolo = timesheet_per_fascicolo.get(fascicolo.id, [])
        emesso = _round_amount(
            sum(
                parcella.totale
                for parcella in parcelle_fascicolo
                if parcella.stato not in {StatoParcella.BOZZA, StatoParcella.ANNULLATA}
            )
        )
        incassato = _round_amount(
            sum(parcella.totale for parcella in parcelle_fascicolo if parcella.stato == StatoParcella.PAGATA)
        )
        insoluto = _round_amount(
            sum(
                parcella.totale
                for parcella in parcelle_fascicolo
                if parcella.stato in {StatoParcella.EMESSA, StatoParcella.SCADUTA}
            )
        )
        ore = round(sum((entry.minuti or 0) for entry in timesheet_fascicolo) / 60.0, 2)
        valore_lavorato = _round_amount(sum(entry.valore_totale for entry in timesheet_fascicolo))
        valore_pratica = _round_amount(
            getattr(fascicolo, "compenso_pattuito", 0.0)
            or getattr(fascicolo, "valore_preventivato", 0.0)
            or getattr(fascicolo, "valore_causa", 0.0)
        )
        marginalita = _round_amount(incassato - valore_lavorato)
        redditivita = _safe_ratio(incassato, valore_lavorato) if valore_lavorato else 0.0
        rows.append(
            {
                "id": fascicolo.id,
                "numero": fascicolo.numero,
                "titolo": fascicolo.titolo,
                "stato": fascicolo.stato.value,
                "ore": ore,
                "valore_pratica": valore_pratica,
                "valore_lavorato": valore_lavorato,
                "emesso": emesso,
                "incassato": incassato,
                "insoluto": insoluto,
                "marginalita": marginalita,
                "redditivita_pct": redditivita,
                "next_action": (
                    "Fatturare ore validate"
                    if valore_lavorato and emesso < valore_lavorato
                    else "Sollecitare incasso"
                    if insoluto > 0
                    else "Monitorare attivita"
                ),
            }
        )
    rows.sort(key=lambda row: (row["insoluto"], row["valore_pratica"], row["ore"]), reverse=True)
    return rows


def _build_produttivita_utenti(timesheet_entries: list[Any]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for entry in timesheet_entries:
        username = entry.username or entry.id_utente or "Operatore"
        bucket = buckets.setdefault(
            username,
            {
                "username": username,
                "ore": 0.0,
                "minuti": 0,
                "valore": 0.0,
                "voci": 0,
                "fatturabili": 0,
                "fascicoli": set(),
            },
        )
        minuti = int(entry.minuti or 0)
        bucket["minuti"] += minuti
        bucket["ore"] = round(bucket["minuti"] / 60.0, 2)
        bucket["valore"] = _round_amount(bucket["valore"] + entry.valore_totale)
        bucket["voci"] += 1
        if entry.fatturabile:
            bucket["fatturabili"] += 1
        if entry.id_fascicolo:
            bucket["fascicoli"].add(entry.id_fascicolo)

    rows = []
    for bucket in buckets.values():
        rows.append(
            {
                "username": bucket["username"],
                "ore": bucket["ore"],
                "valore": bucket["valore"],
                "voci": bucket["voci"],
                "fatturabili": bucket["fatturabili"],
                "fascicoli": len(bucket["fascicoli"]),
                "produttivita": _safe_ratio(bucket["fatturabili"], bucket["voci"]) if bucket["voci"] else 0.0,
            }
        )
    rows.sort(key=lambda row: (row["valore"], row["ore"], row["voci"]), reverse=True)
    return rows


def build_studio_economic_dashboard(
    *,
    fascicoli: list[Any],
    parcelle: list[Any],
    timesheet_entries: list[Any],
    scadenze_imminenti: list[Any] | None = None,
) -> dict[str, Any]:
    fascicoli_attivi = _fascicoli_attivi(fascicoli)
    rows = _build_fascicolo_rows(fascicoli_attivi, parcelle, timesheet_entries)
    produttivita_utenti = _build_produttivita_utenti(timesheet_entries)
    fatturato = _round_amount(
        sum(parcella.totale for parcella in parcelle if parcella.stato not in {StatoParcella.BOZZA, StatoParcella.ANNULLATA})
    )
    incassi = _round_amount(sum(parcella.totale for parcella in parcelle if parcella.stato == StatoParcella.PAGATA))
    insoluti = _round_amount(
        sum(parcella.totale for parcella in parcelle if parcella.stato in {StatoParcella.EMESSA, StatoParcella.SCADUTA})
    )
    valore_pratiche = _round_amount(sum(row["valore_pratica"] for row in rows))
    ore_totali = round(sum(row["ore"] for row in rows), 2)
    valore_lavorato = _round_amount(sum(row["valore_lavorato"] for row in rows))
    worklist = []
    if insoluti > 0:
        worklist.append(
            {
                "label": "Incassi da presidiare",
                "hint": "Fatture emesse o scadute ancora aperte.",
                "value": _currency(insoluti),
                "tone": "warning",
            }
        )
    if valore_lavorato > fatturato:
        worklist.append(
            {
                "label": "Tempo non ancora valorizzato",
                "hint": "Ore tracciate con copertura economica incompleta.",
                "value": _currency(valore_lavorato - fatturato),
                "tone": "danger",
            }
        )
    if scadenze_imminenti:
        worklist.append(
            {
                "label": "Pratiche con scadenze vicine",
                "hint": "Scadenze aperte che impattano fatturazione e priorita'.",
                "value": str(len(scadenze_imminenti)),
                "tone": "info",
            }
        )

    next_action = "Presidiare incassi e pratiche con tempo non ancora fatturato."
    if not worklist:
        next_action = "Il portafoglio economico e' in equilibrio: mantieni il monitoraggio settimanale."
    elif insoluti > 0:
        next_action = "Avvia i solleciti sui saldi aperti e collega le ore validate a nuove parcelle."

    return {
        "scope": "studio",
        "generated_on": date.today().isoformat(),
        "headline": "Controllo economico studio",
        "next_action": next_action,
        "kpis": [
            {"label": "Valore pratiche", "value": _currency(valore_pratiche), "tone": "primary"},
            {"label": "Fatturato", "value": _currency(fatturato), "tone": "success"},
            {"label": "Incassi", "value": _currency(incassi), "tone": "info"},
            {"label": "Tempo lavorato", "value": f"{ore_totali:.1f} h", "tone": "secondary"},
        ],
        "totals": {
            "valore_pratiche": valore_pratiche,
            "fatturato": fatturato,
            "incassi": incassi,
            "insoluti": insoluti,
            "ore_totali": ore_totali,
            "valore_lavorato": valore_lavorato,
            "copertura_fatturazione_pct": _safe_ratio(fatturato, valore_lavorato) if valore_lavorato else 0.0,
        },
        "worklist": worklist,
        "top_fascicoli": rows[:6],
        "produttivita_utenti": produttivita_utenti[:6],
    }


def build_cliente_economic_dashboard(
    *,
    cliente: Any,
    fascicoli: list[Any],
    parcelle: list[Any],
    timesheet_entries: list[Any],
    preventivi: list[Any] | None = None,
    conferimenti: list[Any] | None = None,
) -> dict[str, Any]:
    rows = _build_fascicolo_rows(fascicoli, parcelle, timesheet_entries)
    fatturato = _round_amount(
        sum(parcella.totale for parcella in parcelle if parcella.stato not in {StatoParcella.BOZZA, StatoParcella.ANNULLATA})
    )
    incassi = _round_amount(sum(parcella.totale for parcella in parcelle if parcella.stato == StatoParcella.PAGATA))
    insoluti = _round_amount(
        sum(parcella.totale for parcella in parcelle if parcella.stato in {StatoParcella.EMESSA, StatoParcella.SCADUTA})
    )
    ore_totali = round(sum((entry.minuti or 0) for entry in timesheet_entries) / 60.0, 2)
    valore_lavorato = _round_amount(sum(entry.valore_totale for entry in timesheet_entries))
    saldo = _round_amount(fatturato - incassi)
    preventivi = preventivi or []
    conferimenti = conferimenti or []

    return {
        "scope": "cliente",
        "headline": f"Controllo economico cliente {cliente.nome_completo}",
        "next_action": (
            "Trasforma il preventivo in conferimento e apri il fascicolo."
            if preventivi and not conferimenti
            else "Sollecita le partite aperte e consolida le attivita' tracciate."
        ),
        "kpis": [
            {"label": "Saldo cliente", "value": _currency(saldo), "tone": "warning" if saldo > 0 else "success"},
            {"label": "Fatturato", "value": _currency(fatturato), "tone": "primary"},
            {"label": "Incassato", "value": _currency(incassi), "tone": "success"},
            {"label": "Tempo tracciato", "value": f"{ore_totali:.1f} h", "tone": "secondary"},
        ],
        "totals": {
            "fatturato": fatturato,
            "incassi": incassi,
            "insoluti": insoluti,
            "saldo": saldo,
            "ore_totali": ore_totali,
            "valore_lavorato": valore_lavorato,
            "preventivi_aperti": len([item for item in preventivi if item.stato.value not in {"ACCETTATO", "CONVERTITO"}]),
            "conferimenti_attivi": len([item for item in conferimenti if item.stato.value == "ATTIVO"]),
        },
        "top_fascicoli": rows[:4],
        "produttivita_utenti": _build_produttivita_utenti(timesheet_entries)[:4],
        "worklist": [
            {
                "label": "Insoluti cliente",
                "hint": "Importo ancora da regolarizzare.",
                "value": _currency(insoluti),
                "tone": "danger" if insoluti > 0 else "success",
            },
            {
                "label": "Tempo valorizzato",
                "hint": "Ore fatturabili gia' registrate sul cliente.",
                "value": _currency(valore_lavorato),
                "tone": "info",
            },
        ],
    }


def build_fascicolo_economic_dashboard(
    *,
    fascicolo: Any,
    parcelle: list[Any],
    timesheet_entries: list[Any],
    preventivo: Any | None = None,
    conferimento: Any | None = None,
    sentenze: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = _build_fascicolo_rows([fascicolo], parcelle, timesheet_entries)
    row = rows[0] if rows else {
        "emesso": 0.0,
        "incassato": 0.0,
        "insoluto": 0.0,
        "ore": 0.0,
        "valore_pratica": 0.0,
        "valore_lavorato": 0.0,
        "marginalita": 0.0,
        "redditivita_pct": 0.0,
        "next_action": "Registra il primo tempo lavorato.",
    }
    parcelle_aperte = [parcella for parcella in parcelle if parcella.stato in {StatoParcella.EMESSA, StatoParcella.SCADUTA}]
    next_action = row["next_action"]
    if preventivo and not conferimento:
        next_action = "Converti il preventivo in conferimento per chiudere il workflow commerciale."
    elif conferimento and not parcelle:
        next_action = "Trasforma le attivita' e il timesheet in prima parcella."

    payload = {
        "scope": "fascicolo",
        "headline": f"Economia fascicolo {fascicolo.numero}",
        "next_action": next_action,
        "kpis": [
            {"label": "Valore pratica", "value": _currency(row["valore_pratica"]), "tone": "primary"},
            {"label": "Emesso", "value": _currency(row["emesso"]), "tone": "info"},
            {"label": "Incassato", "value": _currency(row["incassato"]), "tone": "success"},
            {"label": "Ore lavorate", "value": f"{row['ore']:.1f} h", "tone": "secondary"},
        ],
        "totals": {
            "emesso": row["emesso"],
            "incassato": row["incassato"],
            "insoluto": row["insoluto"],
            "ore": row["ore"],
            "valore_lavorato": row["valore_lavorato"],
            "marginalita": row["marginalita"],
            "redditivita_pct": row["redditivita_pct"],
            "parcelle_aperte": len(parcelle_aperte),
        },
        "worklist": [
            {
                "label": "Insoluto fascicolo",
                "hint": "Saldo aperto da presidiare.",
                "value": _currency(row["insoluto"]),
                "tone": "warning" if row["insoluto"] > 0 else "success",
            },
            {
                "label": "Valore lavoro registrato",
                "hint": "Tempo fatturabile gia' tracciato.",
                "value": _currency(row["valore_lavorato"]),
                "tone": "info",
            },
        ],
        "produttivita_utenti": _build_produttivita_utenti(timesheet_entries)[:4],
        "top_fascicoli": rows,
    }
    # Blocco sentenze additivo: i loop del template rendono i nuovi item senza modifiche.
    if sentenze:
        if sentenze.get("kpi"):
            payload["kpis"].append(sentenze["kpi"])
        payload["worklist"].extend(sentenze.get("worklist", []))
        payload["totals"]["sentenze_economiche"] = sentenze.get("totals", {})
    return payload
