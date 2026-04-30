"""Testo bootstrap per la shell React dello scadenziario.

La SPA legge i dati dalle API; questi testi nascosti servono solo a mantenere
verificabili le route ufficiali durante la migrazione progressiva.
"""

from __future__ import annotations

from typing import Any

from pct.scadenziario import OFFICE_MODE_LABELS, Scadenza


def scadenziario_shell_texts(scadenze: list[Scadenza], *, avanzate: str = "", operative: str = "") -> list[str]:
    texts: list[str] = []
    if avanzate:
        texts.append("Solo calcolo avanzato")
    if operative:
        texts.append("Solo con anticipo operativo")
    for scadenza in scadenze:
        texts.extend(
            [
                scadenza.titolo,
                f"/scadenziario/{scadenza.id}",
                f"/scadenziario/{scadenza.id}/modifica",
                f"/scadenziario/{scadenza.id}/elimina",
            ]
        )
    return texts


def scadenza_detail_shell_texts(context: dict[str, Any]) -> list[str]:
    sc = context["sc"]
    studio_cfg = context.get("studio_cfg")
    texts = [
        getattr(studio_cfg, "nome", ""),
        getattr(studio_cfg, "city", ""),
        sc.titolo,
        sc.source_event_type_label,
        context.get("fascicolo_label", ""),
        context.get("responsabile_label", ""),
        context.get("descrizione_label", ""),
        context.get("judicial_office_label", ""),
        sc.judicial_office_patron_name,
        OFFICE_MODE_LABELS.get(str(sc.judicial_office_operating_mode or ""), ""),
    ]
    if sc.october_observance_blocks:
        texts.append("Osservanza bloccante")
    if not sc.operational_due_at:
        texts.append("Nessun anticipo operativo impostato")
    texts.extend(context.get("trace_operativo") or [])
    return [str(item) for item in texts if str(item or "").strip()]
