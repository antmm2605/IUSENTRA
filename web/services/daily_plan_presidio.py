"""Input del presidio fascicolo per il piano del giorno (Lex Oggi).

Unica sorgente delle azioni di presidio di un fascicolo per il collettore e
per l'apertura delle fonti: testi dal catalogo Document AI (nessun OCR) e
riepilogo pagamenti veloce. Separato dal runtime per restare governabile.
"""

from __future__ import annotations

from typing import Any


def operational_presidio_actions(
    fascicolo: Any, *, today, report: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Azioni di presidio di UN fascicolo (catalogo Document AI, nessun OCR).

    Unica sorgente per il collettore del piano e per l'apertura delle fonti.
    """
    from pct.fascicolo_operational_presidio import build_fascicolo_operational_presidio
    from web.services.react_fascicoli_bridge import (
        _document_presidio_for_fascicolo,
        payment_summary_for_fascicolo_fast,
    )

    complete = True
    try:
        document_presidio = _document_presidio_for_fascicolo(fascicolo)
    except Exception:
        complete = False
        document_presidio = {"status": "non_disponibile", "actions": [], "warnings": []}
    try:
        payment_summary = payment_summary_for_fascicolo_fast(fascicolo)
    except Exception:
        complete = False
        payment_summary = {}
    if document_presidio.get("status") == "non_disponibile" and document_presidio.get("sources"):
        # documenti candidati senza testo leggibile: lettura non conclusa
        complete = False
    if report is not None:
        # lettura parziale: i segnali già presenti del fascicolo non vanno chiusi
        report["complete"] = complete
    presidio = build_fascicolo_operational_presidio(
        fascicolo=fascicolo,
        document_presidio=document_presidio,
        notification_relata={},
        payment_summary=payment_summary,
        deposits=[],
        duplicate_group=None,
        sentenze_economiche=None,
        today=today,
    )
    return list(presidio.get("actions") or [])


def scadenza_reason_resolver():
    """Descrizione leggibile della scadenza, la stessa mostrata nello Scadenziario."""
    try:
        from web.services.react_scadenziario_bridge import _legal_scadenza_description

        return _legal_scadenza_description
    except Exception:
        return None


__all__ = ["operational_presidio_actions", "scadenza_reason_resolver"]
