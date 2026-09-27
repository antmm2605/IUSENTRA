"""Registro delle pagine del pannello di piattaforma (superamministratore).

Ogni pagina storica `/admin/*` migrata a React si dichiara qui con:

- l'indirizzo storico, che resta quello dei collegamenti;
- il costruttore dei dati (gli stessi servizi della vista Jinja);
- l'adattatore che traduce i dati in sezioni (`react_piattaforma_sezioni`);
- l'esecutore delle azioni, quando la pagina ne ha.

Le sezioni e gli adattatori vivono in moduli dedicati:
`react_piattaforma_pagine_sistema` (installazione, salute, siti, Lex,
osservabilità), `react_piattaforma_pagine_governo` (panoramica, governance) e un
modulo per ciascuna pagina con azioni.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from web.services import react_piattaforma_pagine_governo as governo
from web.services import react_piattaforma_pagine_sistema as sistema
from web.services.react_piattaforma_sezioni import (  # noqa: F401 - riesportate per i moduli esistenti
    _t,
    actions,
    azione,
    campo,
    data_ora,
    esito,
    facts,
    form,
    link,
    metrics,
    notes,
    sezione_visibile,
    shortcuts,
    status,
    table,
)

Costruttore = Callable[[], dict[str, Any]]
Adattatore = Callable[[dict[str, Any]], dict[str, Any]]
Esecutore = Callable[[str, dict[str, str], dict[str, str]], dict[str, Any]]


def _arg(nome: str) -> str:
    from flask import request

    return str(request.args.get(nome) or "").strip()


@dataclass(frozen=True)
class Pagina:
    chiave: str
    titolo: str
    indirizzo: str
    costruisci: Costruttore
    adatta: Adattatore
    esegui: Esecutore | None = None


def _pagine() -> list[Pagina]:
    from web.services import react_piattaforma_pagina_assistente_migrazione as migrazione
    from web.services import react_piattaforma_pagina_crash_test as crash
    from web.services import react_piattaforma_pagina_installazione_pack as pack
    from web.services import react_piattaforma_pagina_pianificazioni as pianificazioni

    return [
        Pagina("cruscotto", "Panoramica", "/admin/", governo.costruisci_cruscotto, governo.cruscotto),
        Pagina("governance", "Governance del prodotto", "/admin/governance", lambda: governo.costruisci_governance(_arg("slug")), governo.governance),
        Pagina("stato-installazione", "Stato installazione", "/admin/stato-installazione", sistema.costruisci_installazione, sistema.stato_installazione),
        Pagina("salute-sistema", "Salute del sistema", "/admin/salute-sistema", sistema.costruisci_salute, sistema.salute_sistema),
        Pagina("pianificazioni", "Pianificazioni", "/admin/pianificazioni", pianificazioni.costruisci, pianificazioni.adatta, pianificazioni.esegui),
        Pagina("crash-test", "Crash test operativo", "/admin/crash-test-operativo", lambda: crash.costruisci(_arg("slug")), crash.adatta, crash.esegui),
        Pagina("installazione-pack", "Pacchetto di installazione", "/admin/installazione-pack/", lambda: pack.costruisci(_arg("slug")), pack.adatta, pack.esegui),
        Pagina("assistente-migrazione", "Assistente migrazione", "/admin/assistente-migrazione", lambda: migrazione.costruisci(_arg("slug")), migrazione.adatta, migrazione.esegui),
        Pagina("siti-studio", "Siti degli studi", "/admin/siti-studio/", lambda: sistema.costruisci_siti(_arg("q")), sistema.siti_studio),
        Pagina("lex-scorecard", "Valutazione di Lex", "/admin/lex-scorecard", sistema.costruisci_scorecard, sistema.lex_scorecard),
        Pagina("osservabilita", "Osservabilità", "/admin/osservabilita", sistema.costruisci_osservabilita, sistema.osservabilita),
    ]


def _registro() -> dict[str, Pagina]:
    return {p.chiave: p for p in _pagine()}


def menu() -> list[dict[str, str]]:
    return [{"key": p.chiave, "label": p.titolo, "href": p.indirizzo} for p in _pagine()]


def titolo(chiave: str) -> str:
    voce = _registro().get(chiave)
    return voce.titolo if voce else "Pannello di piattaforma"


def pagina(chiave: str) -> tuple[dict[str, Any], int]:
    voce = _registro().get(chiave)
    if voce is None:
        return {"ok": False, "message": "Pagina del pannello non trovata."}, 404
    corpo = voce.adatta(voce.costruisci() or {})
    corpo["sections"] = [s for s in corpo.get("sections") or [] if sezione_visibile(s)]
    visti: set[str] = set()
    corpo["links"] = [c for c in corpo.get("links") or [] if not (c["href"] in visti or visti.add(c["href"]))]
    return {"ok": True, "page": chiave, "menu": menu(), **corpo}, 200


def _testo(valore: Any) -> str:
    """I valori arrivano dal JSON: si riportano al testo che inviava il modulo storico."""
    if isinstance(valore, bool):
        return "1" if valore else "0"
    if valore is None:
        return ""
    if isinstance(valore, float) and valore.is_integer():
        return str(int(valore))
    return str(valore)


def esegui(chiave: str, nome_azione: str, params: Any, values: Any) -> tuple[dict[str, Any], int]:
    voce = _registro().get(chiave)
    if voce is None or voce.esegui is None:
        return {"ok": False, "message": "Azione non disponibile in questa pagina."}, 404
    parametri = {str(k): _testo(v) for k, v in (params or {}).items()} if isinstance(params, dict) else {}
    valori = {str(k): _testo(v) for k, v in (values or {}).items()} if isinstance(values, dict) else {}
    risultato = voce.esegui(nome_azione, parametri, valori)
    risultato["sections"] = [s for s in risultato.get("sections") or [] if sezione_visibile(s)]
    return risultato, 200


__all__ = ["Pagina", "esegui", "menu", "pagina", "titolo"]
