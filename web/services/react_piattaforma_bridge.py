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
    nel_menu: bool = True


def _pagine() -> list[Pagina]:
    from web.services import react_piattaforma_pagina_aggiornamenti as aggiornamenti
    from web.services import react_piattaforma_pagina_aggiornamenti_acquisizione as acquisizione
    from web.services import react_piattaforma_pagina_aggiornamenti_analisi as analisi
    from web.services import react_piattaforma_pagina_aggiornamenti_archivio as archivio_legale
    from web.services import react_piattaforma_pagina_aggiornamenti_fonti as fonti
    from web.services import react_piattaforma_pagina_aggiornamenti_revisione as revisione
    from web.services import react_piattaforma_pagina_assistente_migrazione as migrazione
    from web.services import react_piattaforma_pagina_copertura_ai as copertura
    from web.services import react_piattaforma_pagina_copertura_ai_revisione as copertura_revisione
    from web.services import react_piattaforma_pagina_crash_test as crash
    from web.services import react_piattaforma_pagina_installazione_pack as pack
    from web.services import react_piattaforma_pagina_pianificazioni as pianificazioni
    from web.services import react_piattaforma_pagina_server_manutenzione as server
    from web.services import react_piattaforma_pagina_studi as studi
    from web.services import react_piattaforma_pagina_studio as studio
    from web.services import react_piattaforma_pagina_studio_database as archivio
    from web.services import react_piattaforma_pagina_studio_utenti as utenti_studio
    from web.services import react_piattaforma_pagina_supporto as supporto
    from web.services import react_piattaforma_pagina_utenti_piattaforma as utenti_piattaforma

    return [
        Pagina("cruscotto", "Panoramica", "/admin/", governo.costruisci_cruscotto, governo.cruscotto),
        Pagina("governance", "Governance del prodotto", "/admin/governance", lambda: governo.costruisci_governance(_arg("slug")), governo.governance),
        Pagina("studi", "Studi legali", "/admin/studi", lambda: studi.costruisci_lista(_arg("q"), _arg("stato"), _arg("piano")), studi.adatta_lista, studi.esegui_lista),
        Pagina("studio-nuovo", "Nuovo studio", "/admin/studi/nuovo", studi.costruisci_nuovo, studi.adatta_nuovo, studi.esegui_nuovo, nel_menu=False),
        Pagina("studio", "Scheda dello studio", "/admin/studi/<slug>", lambda: studio.costruisci(_arg("slug")), studio.adatta, studio.esegui, nel_menu=False),
        Pagina("studio-utenti", "Utenti dello studio", "/admin/studi/<slug>/utenti", lambda: utenti_studio.costruisci(_arg("slug")), utenti_studio.adatta, utenti_studio.esegui, nel_menu=False),
        Pagina("studio-database", "Archivio dello studio", "/admin/studi/<slug>/database", lambda: archivio.costruisci(_arg("slug")), archivio.adatta, archivio.esegui, nel_menu=False),
        Pagina("utenti-piattaforma", "Utenti di piattaforma", "/admin/utenti-piattaforma", utenti_piattaforma.costruisci, utenti_piattaforma.adatta, utenti_piattaforma.esegui),
        Pagina("stato-installazione", "Stato installazione", "/admin/stato-installazione", sistema.costruisci_installazione, sistema.stato_installazione),
        Pagina("salute-sistema", "Salute del sistema", "/admin/salute-sistema", sistema.costruisci_salute, sistema.salute_sistema),
        Pagina("pianificazioni", "Pianificazioni", "/admin/pianificazioni", pianificazioni.costruisci, pianificazioni.adatta, pianificazioni.esegui),
        Pagina("server-manutenzione", "Server e manutenzione", "/admin/server-manutenzione", server.costruisci, server.adatta, server.esegui),
        Pagina("crash-test", "Crash test operativo", "/admin/crash-test-operativo", lambda: crash.costruisci(_arg("slug")), crash.adatta, crash.esegui),
        Pagina("installazione-pack", "Pacchetto di installazione", "/admin/installazione-pack/", lambda: pack.costruisci(_arg("slug")), pack.adatta, pack.esegui),
        Pagina("assistente-migrazione", "Assistente migrazione", "/admin/assistente-migrazione", lambda: migrazione.costruisci(_arg("slug")), migrazione.adatta, migrazione.esegui),
        Pagina("siti-studio", "Siti degli studi", "/admin/siti-studio/", lambda: sistema.costruisci_siti(_arg("q")), sistema.siti_studio),
        Pagina("lex-scorecard", "Valutazione di Lex", "/admin/lex-scorecard", sistema.costruisci_scorecard, sistema.lex_scorecard),
        Pagina("osservabilita", "Osservabilità", "/admin/osservabilita", sistema.costruisci_osservabilita, sistema.osservabilita),
        Pagina("supporto-remoto", "Assistenza remota", "/admin/supporto-remoto", lambda: supporto.costruisci(_arg("sessione"), _arg("stato"), _arg("q")), supporto.adatta, supporto.esegui),
        Pagina("aggiornamenti-legali", "Aggiornamenti legali", "/admin/aggiornamenti-legali/", aggiornamenti.costruisci, aggiornamenti.adatta, aggiornamenti.esegui),
        Pagina("aggiornamenti-fonti", "Fonti degli aggiornamenti", "/admin/aggiornamenti-legali/fonti", fonti.costruisci, fonti.adatta, fonti.esegui),
        Pagina("aggiornamenti-staging", "Acquisizione dei documenti", "/admin/aggiornamenti-legali/staging", lambda: acquisizione.costruisci(_arg("source"), _arg("classification"), _arg("status")), acquisizione.adatta, acquisizione.esegui),
        Pagina("aggiornamenti-staging-scheda", "Dettaglio acquisizione", "/admin/aggiornamenti-legali/staging/<id>", lambda: acquisizione.costruisci_scheda(_arg("id")), acquisizione.adatta_scheda, acquisizione.esegui_scheda, nel_menu=False),
        Pagina("aggiornamenti-analisi", "Catalogazione", "/admin/aggiornamenti-legali/analisi", lambda: analisi.costruisci(_arg("classification"), _arg("materia")), analisi.adatta, analisi.esegui),
        Pagina("aggiornamenti-archivio", "Archivio degli aggiornamenti", "/admin/aggiornamenti-legali/archivio", lambda: archivio_legale.costruisci(_arg("tab")), archivio_legale.adatta, archivio_legale.esegui),
        Pagina("aggiornamenti-revisione", "Coda revisioni aggiornamenti", "/admin/aggiornamenti-legali/review", revisione.costruisci, revisione.adatta, revisione.esegui),
        Pagina("copertura-ai", "Copertura AI", "/admin/copertura-ai/", copertura.costruisci, copertura.adatta, copertura.esegui),
        Pagina("copertura-ai-revisione", "Revisione copertura AI", "/admin/copertura-ai/review", lambda: copertura_revisione.costruisci(_arg("draft"), _arg("q")), copertura_revisione.adatta, copertura_revisione.esegui),
    ]


# Schede fuori menu che accendono la voce della pagina madre.
MENU_DELLE_SCHEDE = {"aggiornamenti-staging-scheda": "aggiornamenti-staging"}


def _registro() -> dict[str, Pagina]:
    return {p.chiave: p for p in _pagine()}


def menu() -> list[dict[str, str]]:
    return [{"key": p.chiave, "label": p.titolo, "href": p.indirizzo} for p in _pagine() if p.nel_menu]


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
    # Le schede di uno studio accendono la voce «Studi legali» del menu.
    voce_menu = chiave if voce.nel_menu else ("studi" if chiave.startswith("studio") else MENU_DELLE_SCHEDE.get(chiave, ""))
    return {"ok": True, "page": chiave, "menuKey": voce_menu, "menu": menu(), **corpo}, 200


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
