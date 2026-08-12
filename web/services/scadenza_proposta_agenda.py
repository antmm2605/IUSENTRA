"""Aggancio agenda alla conferma di una proposta di udienza.

Quando l'avvocato conferma una proposta di scadenza di tipo udienza (letta da
PEC o dal registro di cancelleria), l'evento entra anche nel calendario dello
studio, collegato al fascicolo tramite il back-link ``id_appuntamento``.
Idempotente: se la scadenza ha gia' un appuntamento collegato, non ne crea un
altro. All-day di default quando manca l'orario preciso; nessun blocco per
sovrapposizione (allow_overlap) perche' l'udienza e' un dato di fatto, non una
prenotazione.
"""

from __future__ import annotations

from typing import Any


def _orario(scadenza: Any) -> str:
    for attr in ("hearing_time", "remote_hearing_time"):
        value = str(getattr(scadenza, attr, "") or "").strip()
        if value and ":" in value:
            return value.replace(".", ":")[:5]
    return ""


def crea_agenda_da_udienza_confermata(
    scadenza: Any,
    *,
    gestione_agenda: Any,
    gestione_scadenziario: Any,
    gestione_fascicoli: Any = None,
    attore: str = "",
) -> bool:
    """Crea l'appuntamento agenda per un'udienza confermata. Ritorna True se creato."""

    if gestione_agenda is None:
        return False
    if str(getattr(scadenza, "id_appuntamento", "") or "").strip():
        return False  # gia' collegata a un evento agenda
    data = str(getattr(scadenza, "data_scadenza", "") or "")[:10]
    if not data:
        return False
    from pct.agenda import TipoAppuntamento

    orario = _orario(scadenza)
    data_ora = f"{data}T{orario}:00" if orario else f"{data}T09:00:00"
    procedimento = ""
    if gestione_fascicoli is not None:
        fascicolo = gestione_fascicoli.get(str(getattr(scadenza, "id_fascicolo", "") or ""))
        if fascicolo is not None:
            numero = str(getattr(fascicolo, "numero_rg", "") or "").strip()
            anno = str(getattr(fascicolo, "anno_rg", "") or "").strip()
            if numero and anno:
                procedimento = f"RG {numero}/{anno}"
    appuntamento = gestione_agenda.aggiungi(
        titolo=str(getattr(scadenza, "titolo", "") or "Udienza"),
        tipo=TipoAppuntamento.UDIENZA,
        data_ora=data_ora,
        durata_minuti=60,
        allow_overlap=True,
        procedimento=procedimento,
        avvocato=attore,
        note="Creato dalla conferma di una proposta di udienza.",
    )
    appuntamento_id = str(getattr(appuntamento, "id", "") or "")
    if appuntamento_id:
        try:
            gestione_scadenziario.aggiorna(scadenza.id, id_appuntamento=appuntamento_id)
        except Exception:
            pass
    return bool(appuntamento_id)
