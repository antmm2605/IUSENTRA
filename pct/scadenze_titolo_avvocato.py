"""Titolo di una scadenza scelto dall'avvocato: le automazioni non lo riscrivono.

La pipeline PEC tratta come autorevole il titolo che genera per le scadenze con marcatore
``PEC_AUDIT`` e lo riallinea a ogni manutenzione (``repair_pec_deadlines``). Se l'avvocato
cambia il titolo dalla scheda della scadenza, quella è una decisione professionale: resta
com'è. La scelta si registra nella ``provenienza`` della scadenza (chiave
``titolo_scelto_dall_avvocato``: data e titolo precedente), non nelle note che l'avvocato
legge e scrive, ed è affiancata dall'evento di audit ``scadenziario.modifica``.

Base: art. 20 CAD (integrità e tracciabilità del documento informatico); nessuna regola
processuale cambia, si protegge solo la scelta dell'avvocato.
"""

from __future__ import annotations

from typing import Any

from pct.ora_italiana import ROME_TZ

CHIAVE_TITOLO_AVVOCATO = "titolo_scelto_dall_avvocato"


def _provenienza(scadenza: Any) -> dict[str, Any]:
    valore = getattr(scadenza, "provenienza", None)
    return dict(valore) if isinstance(valore, dict) else {}


def titolo_scelto_da_avvocato(scadenza: Any) -> bool:
    return bool(_provenienza(scadenza).get(CHIAVE_TITOLO_AVVOCATO))


def traccia_titolo_avvocato(scadenza: Any, titolo_nuovo: str) -> dict[str, Any]:
    """Campi da aggiungere al salvataggio manuale: ``provenienza`` solo se il titolo cambia."""
    precedente = " ".join(str(getattr(scadenza, "titolo", "") or "").split())
    if not str(titolo_nuovo or "").strip() or " ".join(str(titolo_nuovo).split()) == precedente:
        return {}
    from datetime import datetime

    provenienza = _provenienza(scadenza)
    provenienza[CHIAVE_TITOLO_AVVOCATO] = {
        "il": datetime.now(ROME_TZ).isoformat(timespec="seconds"),
        "titolo_precedente": precedente,
    }
    return {"provenienza": provenienza}


def conserva_scelta_titolo(aggiornamenti: dict[str, Any], scadenza: Any) -> dict[str, Any]:
    """Toglie il titolo dagli aggiornamenti automatici e non perde la traccia nella provenienza."""
    scelta = _provenienza(scadenza).get(CHIAVE_TITOLO_AVVOCATO)
    if not scelta:
        return aggiornamenti
    aggiornamenti.pop("titolo", None)
    if isinstance(aggiornamenti.get("provenienza"), dict):
        aggiornamenti["provenienza"] = {**aggiornamenti["provenienza"], CHIAVE_TITOLO_AVVOCATO: scelta}
    return aggiornamenti


__all__ = ["CHIAVE_TITOLO_AVVOCATO", "conserva_scelta_titolo", "titolo_scelto_da_avvocato", "traccia_titolo_avvocato"]
