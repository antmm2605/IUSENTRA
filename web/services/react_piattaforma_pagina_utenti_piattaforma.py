"""Pagina «Utenti di piattaforma» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/utenti-piattaforma` (rotta
`utenti_piattaforma`, modello `admin/utenti_piattaforma.html`) e i suoi cinque
invii: `genera-superadmin`, `<uid>/reset-password`, `<uid>/modifica`,
`<uid>/trasferisci-superadmin` e `<uid>/sposta-nello-studio`. Ogni azione
chiama gli stessi metodi di `GestioneUtenti`, scrive gli stessi eventi di audit
e, quando la rotta storica chiudeva la sessione e riportava all'accesso, fa lo
stesso (`session.clear()`) e chiede al browser di aprire la pagina di accesso.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_pagina_utenti_piattaforma_azioni import CAMPO_STUDIO, esegui
from web.services.react_piattaforma_sezioni import (
    _t,
    actions,
    azione,
    campo,
    data_ora,
    facts,
    notes,
    table,
)
from web.services.react_piattaforma_studi_comune import ruolo

REGOLE = (
    "Il SUPERADMIN crea e governa gli studi, assegna gli amministratori degli studi, usa Aggiornamenti legali e "
    "Copertura AI come presìdi condivisi e non può essere creato da uno studio.",
    "Un account in questa pagina è un account globale di piattaforma: non appartiene a nessuno studio e si corregge, "
    "si trasferisce o si sposta nello studio giusto solo da qui.",
)

SEPARAZIONE = (
    "Il SUPERADMIN usa il pannello di piattaforma e non appartiene a uno studio.",
    "Ogni studio ha solo utenti propri: AMMINISTRATORE, AVVOCATO, SEGRETERIA e gli altri ruoli di studio.",
    "Aggiornamenti legali e Copertura AI usano archivi condivisi per tutti gli studi.",
    "Se un account globale non è SUPERADMIN, la correzione è trasferire il ruolo oppure spostarlo nello studio corretto.",
)


def costruisci() -> dict[str, Any]:
    """Gli stessi passi della rotta storica `utenti_piattaforma` (compreso `ensure_platform_superadmin`)."""
    from pct.auth import RuoloUtente
    from web.blueprints.admin import _studi_assegnabili, _utenti_globali_piattaforma, _utenti_piattaforma

    gu = _utenti_piattaforma()
    gu.ensure_platform_superadmin()
    utenti_globali = _utenti_globali_piattaforma(gu)
    superadmin_rows = [u for u in utenti_globali if u.ruolo == RuoloUtente.SUPERADMIN]
    anomalie = []
    if len(superadmin_rows) != 1:
        anomalie.append("La piattaforma deve avere un solo SUPERADMIN attivo. Verifica gli utenti globali e riallinea il ruolo.")
    for utente in utenti_globali:
        if utente.ruolo != RuoloUtente.SUPERADMIN:
            anomalie.append(f"L'utente globale {utente.username} non è SUPERADMIN: correggere il ruolo o spostarlo dentro uno studio.")
    return {
        "utenti": utenti_globali,
        "superadmin_corrente": superadmin_rows[0] if len(superadmin_rows) == 1 else None,
        "anomalie": anomalie,
        "studi": _studi_assegnabili(),
        "ruoli_studio": [r.value for r in RuoloUtente if r != RuoloUtente.SUPERADMIN],
    }


def _opzioni_ruoli(ruoli: list[str]) -> list[tuple[str, str]]:
    return [(r, r) for r in ruoli]


def _azione_genera(corrente: Any, ruoli: list[str]) -> dict[str, Any]:
    if corrente is not None:
        avviso = (
            f"Il nuovo account verrà creato o riallineato e riceverà il ruolo SUPERADMIN; l'account attuale "
            f"{_t(corrente.username)} passerà al ruolo scelto e la sessione corrente si chiuderà. Continuare?"
        )
    else:
        avviso = "Non esiste ancora un SUPERADMIN attivo: verrà generato il primo account di piattaforma con ruolo SUPERADMIN. Continuare?"
    return azione(
        "genera-superadmin",
        "Genera o sostituisci SUPERADMIN",
        tone="primary",
        confirm=avviso,
        fields=[
            campo("username", "Nome utente di piattaforma", required=True),
            campo("password", "Password temporanea", "password", required=True, help="Al primo accesso andrà cambiata."),
            campo("nome_completo", "Nome completo"),
            campo("email", "Email", "email"),
            campo("ruolo_superadmin_precedente", "Ruolo del SUPERADMIN uscente", "select", value="AMMINISTRATORE", options=_opzioni_ruoli(ruoli), help="Se l'account esiste già in piattaforma verrà riallineato e poi diventerà il nuovo SUPERADMIN."),
        ],
    )


def _azioni_riga(utente: Any, corrente: Any, studi: list[Any], ruoli: list[str]) -> list[dict[str, Any]]:
    nome = _t(utente.username)
    uid = {"uid": utente.id}
    e_superadmin = ruolo(utente) == "SUPERADMIN"
    voci = [azione(
        "modifica",
        "Modifica",
        params=uid,
        fields=[
            campo("nome_completo", "Nome completo", value=utente.nome_completo or ""),
            campo("email", "Email", "email", value=utente.email or ""),
            campo(
                "attivo",
                "Account attivo",
                "checkbox",
                value=bool(utente.attivo or e_superadmin),
                help="Il SUPERADMIN di piattaforma resta attivo: per disattivarlo trasferisci prima il ruolo." if e_superadmin else "",
            ),
        ],
    )]
    if corrente is not None and utente.id != corrente.id:
        voci.append(azione(
            "trasferisci-superadmin",
            "Rendi SUPERADMIN",
            tone="warning",
            params=uid,
            confirm=f"Trasferire il ruolo SUPERADMIN da {_t(corrente.username)} a {nome}? La sessione dell'account uscente verrà chiusa subito dopo.",
            fields=[campo("ruolo_superadmin_precedente", "Ruolo dell'account SUPERADMIN uscente", "select", value="AMMINISTRATORE", options=_opzioni_ruoli(ruoli))],
        ))
    if not e_superadmin and studi:
        voci.append(azione(
            "sposta-nello-studio",
            "Sposta nello studio",
            tone="warning",
            params=uid,
            confirm=f"L'account {nome} verrà rimosso dalla piattaforma e diventerà un utente dello studio scelto. Continuare?",
            fields=[
                campo(CAMPO_STUDIO, "Studio di destinazione", "select", required=True, options=[("", "Seleziona uno studio"), *[(s.slug, f"{s.nome} - {s.slug}") for s in studi]]),
                campo("ruolo", "Ruolo nello studio", "select", required=True, value=ruolo(utente) or "AVVOCATO", options=_opzioni_ruoli(ruoli), help="Credenziali, nome, email, stato e storico accessi vengono conservati."),
            ],
        ))
    voci.append(azione(
        "reset-password",
        "Reimposta password",
        params=uid,
        fields=[campo("nuova_password", f"Nuova password temporanea per {nome}", "password", required=True)],
    ))
    return voci


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    corrente = payload.get("superadmin_corrente")
    studi = list(payload.get("studi") or [])
    ruoli = list(payload.get("ruoli_studio") or [])
    righe = []
    for u in payload.get("utenti") or []:
        anomalo = ruolo(u) != "SUPERADMIN"
        righe.append({
            "user": " — ".join(x for x in (_t(u.username), _t(u.nome_completo), "account globale da riallineare" if anomalo else "") if x),
            "email": _t(u.email) or "-",
            "role": ruolo(u),
            "state": "Attivo" if u.attivo else "Inattivo",
            "scope": "Piattaforma",
            "last": data_ora(u.ultimo_accesso) or "Mai",
            "_tone": "warning" if anomalo else "",
            "_actions": _azioni_riga(u, corrente, studi, ruoli),
        })
    sezioni = [
        notes("Regola di piattaforma", list(REGOLE), tone="info"),
        actions("Account SUPERADMIN", [_azione_genera(corrente, ruoli)]),
    ]
    if corrente is not None:
        sezioni.append(facts("SUPERADMIN attivo", [
            ("Nome utente", corrente.username),
            ("Nome completo", _t(corrente.nome_completo) or "Account di piattaforma senza nome completo"),
            ("Email", _t(corrente.email) or "Email non configurata"),
        ]))
    sezioni.append(notes("Anomalie", list(payload.get("anomalie") or []), tone="warning"))
    if not studi:
        sezioni.append(notes("Studi di destinazione", ["Per riallineare gli account globali devi prima creare almeno uno studio di destinazione."], tone="warning"))
    sezioni += [
        table(
            "Account di piattaforma",
            [("user", "Utente"), ("email", "Email"), ("role", "Ruolo"), ("state", "Stato"), ("scope", "Ambito"), ("last", "Ultimo accesso")],
            righe,
            empty="Nessun account di piattaforma trovato.",
        ),
        notes("Separazione professionale dei ruoli", list(SEPARAZIONE), tone="info"),
    ]
    return {
        "title": "Account di piattaforma",
        "subtitle": "Il SUPERADMIN è unico, governa gli studi e non vive dentro alcuno studio.",
        "links": [],
        "sections": sezioni,
    }


__all__ = ["adatta", "costruisci", "esegui"]
