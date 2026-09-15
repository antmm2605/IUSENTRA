"""Quanto è completo il presidio: si contano le verifiche che il software misura.

La percentuale deve essere spiegabile: è la quota delle verifiche pertinenti e
misurabili che risultano superate. Non entrano nel conto le voci che nessun
controllo automatico può decidere (restano all'avvocato) né quelle rinviate al
momento del deposito. Così un fascicolo in ordine arriva davvero al cento per
cento, e un fascicolo incompleto mostra che cosa manca.
"""

from __future__ import annotations

from typing import Any, Iterable

from .models import SlotStatus

SLOT_SUPERATI = {SlotStatus.VALIDO.value, SlotStatus.NON_APPLICABILE.value, SlotStatus.WARNING.value}


def completamento(
    voci: Iterable[dict[str, Any]],
    slot: Iterable[Any],
    *,
    in_deposito: bool = True,
    motivo_fase: str = "",
) -> tuple[int, dict[str, Any]]:
    """La percentuale e il dettaglio che la rende verificabile."""
    voci = list(voci)
    slot = list(slot)
    misurabili = [voce for voce in voci if voce.get("measured")]
    superate = [voce for voce in misurabili if voce.get("status") == "COMPLETATO"]
    pertinenti = [riga for riga in slot if getattr(riga, "required", False) and (in_deposito or str(getattr(riga, "document_id", "") or "").strip())]
    slot_superati = [riga for riga in pertinenti if str(getattr(riga, "status", "")) in SLOT_SUPERATI]
    totali = len(misurabili) + len(pertinenti)
    fatte = len(superate) + len(slot_superati)
    percentuale = int(round(min(1.0, fatte / totali) * 100)) if totali else 100
    dettaglio = {
        "checked": fatte,
        "total": totali,
        "checklistMeasured": len(misurabili),
        "checklistPassed": len(superate),
        "slotsRelevant": len(pertinenti),
        "slotsPassed": len(slot_superati),
        "deferred": len([voce for voce in voci if voce.get("status") == "NON_PERTINENTE"]),
        "manual": len([voce for voce in voci if not voce.get("measured") and voce.get("status") != "NON_PERTINENTE"]),
        "note": "La percentuale conta solo le verifiche che il software può misurare ora." + (f" {motivo_fase}" if not in_deposito and motivo_fase else ""),
    }
    return percentuale, dettaglio


def stato_operativo(
    *,
    sessione: Any = None,
    deposito: Any = None,
    in_deposito: bool = True,
    stato_derivato: str = "",
    stato_fascicolo_aperto: str = "FASCICOLO_APERTO",
) -> str:
    """Lo stato operativo: il deposito reale del fascicolo viene prima di ogni deduzione."""
    if sessione is not None and str(getattr(sessione, "status", "") or ""):
        return str(sessione.status)
    if deposito is not None and bool(getattr(deposito, "presente", False)):
        return str(getattr(deposito, "stato_operativo", "") or stato_derivato)
    if not in_deposito:
        return stato_fascicolo_aperto
    return stato_derivato


__all__ = ["SLOT_SUPERATI", "completamento", "stato_operativo"]
