"""Pipeline economica operativa: tempo lavorato -> parcella -> incasso."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from pct.fatturazione import VoceParcella
from pct.timesheet import StatoTimesheet


@dataclass(frozen=True)
class TimesheetBillingSelection:
    entries: list[Any]
    id_cliente: str
    id_fascicolo: str
    ore_totali: float
    valore_totale: float
    issues: list[str]

    @property
    def ready(self) -> bool:
        return not self.issues and bool(self.entries)


def _normalize_entry_ids(entry_ids: Iterable[str] | None) -> set[str]:
    if not entry_ids:
        return set()
    return {
        str(value or "").strip()
        for value in entry_ids
        if str(value or "").strip()
    }


def _eligible_timesheet_entries(entries: Iterable[Any], *, entry_ids: Iterable[str] | None = None) -> list[Any]:
    selected_ids = _normalize_entry_ids(entry_ids)
    rows = []
    for entry in entries:
        if selected_ids and entry.id not in selected_ids:
            continue
        if not getattr(entry, "fatturabile", False):
            continue
        if getattr(entry, "stato", None) != StatoTimesheet.VALIDATO:
            continue
        rows.append(entry)
    rows.sort(key=lambda item: (item.data_attivita, item.creato_il, item.id))
    return rows


def select_billable_timesheet_entries(entries: Iterable[Any], *, entry_ids: Iterable[str] | None = None) -> TimesheetBillingSelection:
    rows = _eligible_timesheet_entries(entries, entry_ids=entry_ids)
    if not rows:
        return TimesheetBillingSelection(
            entries=[],
            id_cliente="",
            id_fascicolo="",
            ore_totali=0.0,
            valore_totale=0.0,
            issues=["Non ci sono voci validate e fatturabili pronte da trasformare in parcella."],
        )

    clienti = {str(getattr(entry, "id_cliente", "") or "").strip() for entry in rows if getattr(entry, "id_cliente", "")}
    fascicoli = {
        str(getattr(entry, "id_fascicolo", "") or "").strip()
        for entry in rows
        if getattr(entry, "id_fascicolo", "")
    }
    issues: list[str] = []
    if len(clienti) > 1:
        issues.append("Le voci selezionate appartengono a clienti diversi: genera una parcella per cliente.")

    id_cliente = next(iter(clienti), "")
    id_fascicolo = next(iter(fascicoli), "") if len(fascicoli) == 1 else ""
    ore_totali = round(sum(float(getattr(entry, "ore", 0.0) or 0.0) for entry in rows), 2)
    valore_totale = round(sum(float(getattr(entry, "valore_totale", 0.0) or 0.0) for entry in rows), 2)

    return TimesheetBillingSelection(
        entries=rows,
        id_cliente=id_cliente,
        id_fascicolo=id_fascicolo,
        ore_totali=ore_totali,
        valore_totale=valore_totale,
        issues=issues,
    )


def build_timesheet_billing_summary(entries: Iterable[Any], *, entry_ids: Iterable[str] | None = None) -> dict[str, Any]:
    selection = select_billable_timesheet_entries(entries, entry_ids=entry_ids)
    next_action = "Valida le voci aperte per trasformare il tempo in parcella."
    if selection.ready:
        next_action = "Le voci validate possono essere aggregate in una parcella di revisione."
    elif selection.entries and selection.issues:
        next_action = selection.issues[0]

    return {
        "ready": selection.ready,
        "issues": selection.issues,
        "count": len(selection.entries),
        "ore_totali": selection.ore_totali,
        "valore_totale": selection.valore_totale,
        "id_cliente": selection.id_cliente,
        "id_fascicolo": selection.id_fascicolo,
        "entry_ids": [entry.id for entry in selection.entries],
        "next_action": next_action,
    }


def _timesheet_voice(entry: Any) -> VoceParcella:
    data_label = str(getattr(entry, "data_attivita", "") or date.today().isoformat()).strip()
    descrizione = str(getattr(entry, "descrizione", "") or "Attivita' professionale").strip()
    return VoceParcella(
        descrizione=f"{data_label} - {descrizione}",
        quantita=float(getattr(entry, "ore", 0.0) or 0.0),
        prezzo_unitario=float(getattr(entry, "valore_unitario", 0.0) or 0.0),
    )


def genera_parcella_da_timesheet(
    *,
    timesheet,
    fatturazione,
    creato_da: str = "",
    entry_ids: Iterable[str] | None = None,
    data_scadenza: str | None = None,
) -> dict[str, Any]:
    selection = select_billable_timesheet_entries(timesheet.tutte(), entry_ids=entry_ids)
    if not selection.ready:
        raise ValueError(selection.issues[0] if selection.issues else "Nessuna voce timesheet pronta per la parcella.")

    voci = [_timesheet_voice(entry) for entry in selection.entries]
    date_values = sorted(str(getattr(entry, "data_attivita", "") or "") for entry in selection.entries if getattr(entry, "data_attivita", ""))
    periodo = ""
    if date_values:
        periodo = date_values[0] if len(date_values) == 1 else f"{date_values[0]} / {date_values[-1]}"

    note = (
        f"Parcella generata da {len(selection.entries)} voci timesheet validate"
        + (f" ({periodo})" if periodo else "")
        + "."
    )
    parcella = fatturazione.crea(
        id_cliente=selection.id_cliente,
        id_fascicolo=selection.id_fascicolo or None,
        creato_da=creato_da,
        voci=voci,
        data_scadenza=data_scadenza or "",
        note=note,
        origine="timesheet",
    )

    for entry in selection.entries:
        timesheet.cambia_stato(entry.id, StatoTimesheet.FATTURATO)

    return {
        "parcella": parcella,
        "entries": selection.entries,
        "summary": build_timesheet_billing_summary(selection.entries, entry_ids=[entry.id for entry in selection.entries]),
    }
