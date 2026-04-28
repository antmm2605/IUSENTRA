"""Filtri di vista per lo scadenziario legale."""

from __future__ import annotations

from typing import Any

from pct.scadenziario import PrioritaTermine, Scadenza, StatoTermine, TipoTermine


VISTE_SCADENZIARIO_AMMESSE = {
    "aperte",
    "critiche",
    "alte",
    "completate",
    "scadute",
    "imminenti",
    "avanzate",
    "operative",
    "da_presidiare",
    "tutte",
}

VISTA_LABEL_SCADENZIARIO = {
    "aperte": "scadenze aperte",
    "critiche": "scadenze critiche",
    "alte": "scadenze ad alta priorità",
    "completate": "scadenze completate",
    "scadute": "scadenze scadute",
    "imminenti": "scadenze entro 7 giorni",
    "avanzate": "scadenze con calcolo avanzato",
    "operative": "scadenze operative",
    "da_presidiare": "scadenze da presidiare",
    "tutte": "scadenze totali",
}


def normalizza_vista_scadenziario(value: str | None) -> str:
    vista = (value or "aperte").strip() or "aperte"
    return vista if vista in VISTE_SCADENZIARIO_AMMESSE else "aperte"


def label_vista_scadenziario(vista: str) -> str:
    return VISTA_LABEL_SCADENZIARIO.get(vista, "scadenze")


def scadenze_per_vista(
    gestione_scadenziario: Any,
    *,
    vista: str,
    tipo: TipoTermine | None = None,
    priorita: PrioritaTermine | None = None,
    id_fascicolo: str = "",
) -> list[Scadenza]:
    """Restituisce le scadenze della vista richiesta, mantenendo i filtri attivi."""
    gs = gestione_scadenziario
    vista = normalizza_vista_scadenziario(vista)
    gs.scadute()

    def _base(solo_aperte: bool = True, stato: StatoTermine | None = None) -> list[Scadenza]:
        return gs.tutte(
            stato=stato,
            tipo=tipo,
            priorita=priorita,
            id_fascicolo=id_fascicolo,
            solo_aperte=solo_aperte,
        )

    if vista == "completate":
        return _base(solo_aperte=False, stato=StatoTermine.COMPLETATO)
    if vista == "scadute":
        return _base(solo_aperte=False, stato=StatoTermine.SCADUTO)
    if vista == "critiche":
        return [s for s in _base(solo_aperte=True, stato=StatoTermine.APERTO) if s.priorita == PrioritaTermine.CRITICA]
    if vista == "alte":
        return [s for s in _base(solo_aperte=True, stato=StatoTermine.APERTO) if s.priorita == PrioritaTermine.ALTA]
    if vista == "imminenti":
        scadenze = gs.imminenti(entro_giorni=7)
        if tipo:
            scadenze = [s for s in scadenze if s.tipo == tipo]
        if priorita:
            scadenze = [s for s in scadenze if s.priorita == priorita]
        if id_fascicolo:
            scadenze = [s for s in scadenze if s.id_fascicolo == id_fascicolo]
        return scadenze
    if vista == "avanzate":
        return [s for s in _base(solo_aperte=False) if s.ha_calcolo_avanzato]
    if vista == "operative":
        return [s for s in _base(solo_aperte=False) if bool(s.operational_due_at)]
    if vista == "da_presidiare":
        return [
            s
            for s in _base(solo_aperte=False)
            if s.stato == StatoTermine.SCADUTO
            or (s.stato == StatoTermine.APERTO and s.priorita == PrioritaTermine.CRITICA)
        ]
    if vista == "tutte":
        return _base(solo_aperte=False)
    return _base(solo_aperte=True, stato=StatoTermine.APERTO)
