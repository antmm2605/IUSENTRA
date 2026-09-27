"""Pagina «Assistenza remota» del pannello di piattaforma (React).

Sostituisce la console storica `/admin/supporto-remoto` (rotta
`support_console` di `web/blueprints/support_remote.py`, modello
`admin/support_console.html`, script `support_console.js`). I dati sono quelli
di `build_support_console_payload` con gli stessi argomenti della rotta
(`sessione`, `stato`, `q`); le azioni stanno in
`react_piattaforma_supporto_azioni` e chiamano gli stessi servizi dei gestori
storici.

La chiave del relay (TURN) non torna mai nella pagina: il campo resta vuoto e,
se non si compila, `save_support_configuration` conserva quella salvata.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from web.services.react_piattaforma_sezioni import (
    _t,
    actions,
    azione,
    campo,
    data_ora,
    facts,
    form,
    link,
    metrics,
    notes,
    status,
    table,
)
from web.services.react_piattaforma_supporto_azioni import AZIONI, esegui

INDIRIZZO = "/admin/supporto-remoto"

# Etichette del filtro della console storica (diverse da quelle del cambio stato).
STATI_FILTRO = (
    ("created", "Creata"),
    ("waiting_operator", "Attesa operatore"),
    ("waiting_client", "Attesa cliente"),
    ("waiting_peer", "Attesa altra parte"),
    ("active", "Attiva"),
    ("closed", "Chiusa"),
)
STATI_SESSIONE = (
    ("created", "Creata"),
    ("waiting_operator", "In attesa operatore"),
    ("waiting_client", "In attesa cliente"),
    ("waiting_peer", "In attesa dell'altra parte"),
    ("active", "Attiva"),
    ("closed", "Chiusa"),
)

PERCORSO = (
    ("1. Lo studio chiede aiuto", "L'utente preme «Assistenza» nella barra alta. IUSENTRA apre la stanza cliente e registra la richiesta."),
    ("2. Il superamministratore la vede qui", "La richiesta appare in «Richieste dallo studio». Selezionala per leggere studio, cliente, stato e audit."),
    ("3. Apri la stanza operatore", "Apri «Prendi in carico», poi premi «Entra» nella stanza operatore."),
    ("4. Il cliente autorizza", "Il cliente conferma chat, schermo e, solo se serve, controllo PC tramite agente locale."),
)


def costruisci(sessione: str = "", stato: str = "", q: str = "") -> dict[str, Any]:
    """Gli stessi argomenti della rotta storica `support_console`."""
    from web.services.support_surface import build_support_console_payload

    return build_support_console_payload(
        selected_public_id=str(sessione or "").strip(),
        status_filter=str(stato or "").strip(),
        query=str(q or "").strip(),
    )


# ------------------------------------------------------------------ elementi


def _tono_stato(stato: Any) -> str:
    """Colori del distintivo storico: attiva verde, chiusa grigio, le altre in attesa."""
    valore = _t(stato)
    if valore == "active":
        return "success"
    return "" if valore == "closed" else "warning"


def _stanza_operatore(public_id: str) -> str:
    """Come il modello storico: `url_for('support_remote.operator_room', public_id=…)`
    senza gettone, la stanza lo emette per il superamministratore collegato."""
    from flask import url_for

    return url_for("support_remote.operator_room", public_id=public_id)


def _indirizzo_sessione(public_id: str, filtri: dict[str, Any]) -> str:
    parametri = {"sessione": public_id, "q": _t(filtri.get("q")), "stato": _t(filtri.get("status"))}
    return f"{INDIRIZZO}?{urlencode({k: v for k, v in parametri.items() if v})}"


def _prossimo_passo(sessione: dict[str, Any]) -> str:
    presenza = sessione.get("presence") or {}
    if not presenza.get("operator"):
        return "Prendi in carico la richiesta: apri la stanza operatore e premi «Entra»."
    if not presenza.get("client"):
        return "Attendi che il cliente resti nella stanza cliente aperta dal bottone Assistenza."
    if not sessione.get("consent_screen"):
        return "Chiedi al cliente di autorizzare la condivisione schermo nella stanza cliente."
    if not sessione.get("advanced_control_approved"):
        return "Puoi assistere via schermo e chat. Per guidare mouse e tastiera, richiedi «Controllo PC» nella stanza operatore e attendi l'approvazione del cliente."
    return "Controllo PC approvato: nella stanza operatore puoi usare mouse, tastiera e testo sulla macchina cliente."


def _si_no(valore: Any) -> str:
    return "sì" if valore else "no"


def _controllo_pc(sessione: dict[str, Any]) -> str:
    if sessione.get("advanced_control_approved"):
        return "Approvato"
    return "In attesa" if sessione.get("advanced_control_requested") else "Non richiesto"


def _pratica_studio(sessione: dict[str, Any]) -> str:
    pratica = _t(sessione.get("practice_label")) or "Nessuna pratica collegata"
    studio = _t(sessione.get("studio_nome"))
    return f"{pratica} · {studio}" if studio else pratica


# ------------------------------------------------------------------ sezioni


def _notifiche_dispositivo(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Stato e prova delle notifiche cellulare. Attivazione e disattivazione usano
    l'interfaccia Push del browser: restano nella vista classica."""
    stato = payload.get("push_status") or {}
    configurato = bool(stato.get("configured"))
    attivi = int(stato.get("activeSubscriptions") or 0)
    mancanti = [_t(m) for m in ((stato.get("diagnostics") or {}).get("missing") or []) if _t(m)]
    if not stato.get("ok", True) and not configurato:
        etichetta, tono = "Non disponibile", "warning"
    elif not configurato:
        etichetta, tono = "Server da configurare", "warning"
    elif attivi:
        etichetta, tono = (f"{attivi} dispositivo attivo" if attivi == 1 else f"{attivi} dispositivi attivi"), "info"
    else:
        etichetta, tono = "Pronto", "info"
    dispositivi = "1 dispositivo SUPERADMIN attivo." if attivi == 1 else f"{attivi} dispositivi SUPERADMIN attivi."
    sezioni = [
        status(
            "Notifiche cellulare SUPERADMIN",
            [{
                "title": "Richieste di assistenza sul cellulare",
                "summary": _t(stato.get("message")) or "Stato notifiche dispositivo letto.",
                "detail": f"Server incompleto: {', '.join(mancanti)}." if mancanti else dispositivi,
                "status": tono,
                "statusLabel": etichetta,
            }],
            subtitle="Quando uno studio preme «Assistenza», il superamministratore riceve una notifica interna e, se il dispositivo è attivo, una notifica sul cellulare anche senza tenere aperta l'applicazione. La notifica esterna mostra solo che è arrivata una richiesta e da quale studio.",
        ),
    ]
    if configurato and attivi:
        sezioni.append(actions("Prova delle notifiche", [azione("prova-notifica", "Invia test", tone="primary")]))
    avvisi = ["Attivazione e disattivazione di questo dispositivo richiedono il permesso del browser: si eseguono dalla vista classica («Vista classica per le notifiche»)."]
    if not configurato or not attivi:
        avvisi.append("La prova si abilita quando Web Push è configurato sul server e almeno un dispositivo SUPERADMIN è attivo.")
    sezioni.append(notes("Dispositivo", avvisi, tone="info"))
    recenti = payload.get("support_notifications") or {}
    voci = list(recenti.get("items") or [])[:3]
    da_leggere = int(recenti.get("unread") or 0)
    sezioni.append(table(
        f"Ultime notifiche assistenza{f' · {da_leggere} da leggere' if da_leggere else ''}",
        [("title", "Notifica"), ("body", "Dettaglio"), ("when", "Quando")],
        [{"title": v.get("title"), "body": v.get("body"), "when": data_ora(v.get("created_at")) or "—", "_href": _t(v.get("href")) or INDIRIZZO, "_tone": "" if v.get("read") else "info"} for v in voci],
        empty="Nessuna notifica di assistenza recente.",
    ))
    return sezioni


def _elenco_sessioni(payload: dict[str, Any], selezionata: dict[str, Any] | None) -> list[dict[str, Any]]:
    filtri = payload.get("filters") or {}
    scelta = _t((selezionata or {}).get("public_id"))
    righe = []
    for voce in payload.get("sessions") or []:
        public_id = _t(voce.get("public_id"))
        righe.append({
            "customer": _t(voce.get("customer_name")) or "Cliente non indicato",
            "practice": _pratica_studio(voce),
            "state": f"{_t(voce.get('status_label'))}{' · selezionata' if public_id == scelta else ''}",
            "updated": data_ora(voce.get("updated_at")) or "—",
            "_href": _indirizzo_sessione(public_id, filtri),
            "_tone": "info" if public_id == scelta else _tono_stato(voce.get("status")),
        })
    return [
        form(
            "Filtra le richieste",
            "filtra",
            [
                campo("q", "Cerca", value=filtri.get("q"), placeholder="Cerca cliente, pratica o studio"),
                campo("stato", "Stato", "select", value=filtri.get("status"), options=[("", "Tutti gli stati"), *STATI_FILTRO]),
            ],
            submit_label="Filtra",
        ),
        table(
            "Richieste dallo studio",
            [("customer", "Cliente"), ("practice", "Pratica e studio"), ("state", "Stato"), ("updated", "Aggiornata")],
            righe,
            subtitle="Apri una richiesta per leggerne dettaglio e audit.",
            empty="Nessuna sessione di assistenza remota registrata.",
        ),
        actions("Pulizia", [
            azione("cancella-prove", "Cancella prove/test", tone="danger", confirm="Cancellare tutte le sessioni che sembrano prove o test (test, prova, smoke, e2e…)?"),
        ]),
    ]


def _sessione_selezionata(payload: dict[str, Any], sessione: dict[str, Any]) -> list[dict[str, Any]]:
    public_id = _t(sessione.get("public_id"))
    presenza = sessione.get("presence") or {}
    chiusa = _t(sessione.get("status")) == "closed"
    collegamenti = [
        {"link": "Prendi in carico nella stanza operatore", "detail": "Apre la stanza operatore in una nuova scheda.", "_href": _stanza_operatore(public_id), "_external": True},
        {"link": "Apri link cliente", "detail": "Stanza del cliente (link firmato).", "_href": _t(sessione.get("join_path")), "_external": True},
    ]
    if _t(sessione.get("advanced_url")):
        collegamenti.append({"link": "Collegamento esterno opzionale", "detail": "Solo dopo l'approvazione esplicita del cliente.", "_href": _t(sessione.get("advanced_url")), "_external": True})
    comandi = [
        azione("stato", "Aggiorna stato", params={"public_id": public_id}, fields=[
            campo("status", "Cambia stato assistenza", "select", value=sessione.get("status"), options=STATI_SESSIONE, required=True),
        ]),
        azione("note", "Salva note", params={"public_id": public_id}, fields=[
            campo("notes", "Note finali sessione", "textarea", value=sessione.get("notes")),
        ]),
    ]
    if not chiusa:
        comandi.append(azione("chiudi", "Chiudi sessione", tone="warning", params={"public_id": public_id}, confirm="Chiudere la sessione di assistenza? Il cliente non potrà più usare il link."))
    comandi.append(azione("cancella", "Cancella sessione", tone="danger", params={"public_id": public_id}, confirm="Cancellare definitivamente la sessione di assistenza e il suo audit?"))
    return [
        facts(f"Richiesta selezionata · {_t(sessione.get('status_label'))}", [
            ("Cliente", _t(sessione.get("customer_name")) or "—"),
            ("Email", _t(sessione.get("customer_email")) or "—"),
            ("Studio", _t(sessione.get("studio_nome")) or "—"),
            ("Pratica", _t(sessione.get("practice_label")) or "—"),
            ("Stato", sessione.get("status_label")),
            ("Presenza", f"Operatore {_si_no(presenza.get('operator'))} · Cliente {_si_no(presenza.get('client'))}"),
            ("Consensi", f"Schermo {_si_no(sessione.get('consent_screen'))} · Audio {_si_no(sessione.get('consent_audio'))} · Chat {_si_no(sessione.get('consent_chat'))}"),
            ("Controllo PC", _controllo_pc(sessione)),
            ("Creata", data_ora(sessione.get("created_at")) or "—"),
            ("Avviata", data_ora(sessione.get("started_at")) or "—"),
            ("Chiusa", data_ora(sessione.get("ended_at")) or "—"),
            ("Note finali", sessione.get("notes")),
        ]),
        notes("Prossimo passo", [_prossimo_passo(sessione)], tone="info"),
        table(
            "Stanze della sessione",
            [("link", "Collegamento"), ("detail", "Uso")],
            collegamenti,
            subtitle="Si aprono in una nuova scheda.",
        ),
        actions("Gestione della sessione", comandi),
        table(
            "Audit sessione",
            [("event", "Evento"), ("when", "Quando"), ("story", "Descrizione")],
            [{"event": e.get("event_type"), "when": data_ora(e.get("created_at")) or "—", "story": _t(e.get("story_line")) or "Evento registrato."} for e in payload.get("events") or []],
            empty="Nessun evento registrato per questa sessione.",
        ),
    ]


def _sessione_manuale(payload: dict[str, Any]) -> list[dict[str, Any]]:
    esterno = (
        "Collegamento esterno opzionale configurato: usalo solo dopo approvazione esplicita del cliente."
        if payload.get("advanced_ready")
        else "La cabina copre già schermo, audio, chat, audit e controllo PC con consenso cliente."
    )
    return [
        form(
            "Sessione manuale, solo se il cliente non usa Assistenza",
            "crea-sessione",
            [
                campo("customer_name", "Cliente", placeholder="Nome e cognome cliente"),
                campo("customer_email", "Email cliente", placeholder="email@cliente.it"),
                campo("studio_nome", "Studio", placeholder="Studio di riferimento"),
                campo("practice_label", "Riferimento pratica", placeholder="RG 1025/2024 - Vendita immobili"),
                campo("notes", "Note operative", "textarea", placeholder="Motivo dell'assistenza, anomalia da verificare, canale di contatto."),
            ],
            submit_label="Apri assistenza remota",
            subtitle="Nel flusso normale non devi creare nulla qui: selezioni la richiesta arrivata dallo studio e la prendi in carico.",
        ),
        notes("Sessione manuale", [
            payload.get("operator_rule"),
            "Questa creazione manuale serve solo quando il cliente non parte dal bottone Assistenza dello studio.",
            esterno,
        ], tone="info"),
    ]


def _impostazioni_rete(payload: dict[str, Any]) -> dict[str, Any]:
    rete = payload.get("runtime_config") or {}
    segreto = bool(rete.get("turn_shared_secret_present"))
    return form(
        "Impostazioni rete avanzate",
        "configurazione",
        [
            campo("stun_urls", "Connessione browser già operativa", "textarea", value=rete.get("stun_urls_text"), placeholder="stun:stun.l.google.com:19302", help="Presidio predefinito già operativo. Usa un indirizzo per riga solo se vuoi sostituirlo con un presidio proprietario."),
            campo("turn_urls", "Relay per reti difficili", "textarea", value=rete.get("turn_urls_text"), placeholder="turn:turn.tuodominio.it:3478?transport=udp", help="Opzionale: aumenta affidabilità per clienti con firewall o NAT restrittivi."),
            # La chiave salvata non si rimanda mai al browser: campo vuoto, vuoto = invariata.
            campo(
                "turn_shared_secret",
                "Chiave relay temporanea",
                "password",
                value="",
                placeholder="Chiave già salvata: reinseriscila solo se vuoi cambiarla" if segreto else "Chiave lunga e casuale",
                help="Chiave già presente. Lascia vuoto se non vuoi cambiarla." if segreto else "Necessaria solo se colleghi il relay per reti difficili.",
            ),
            campo("turn_ttl_seconds", "Durata relay (secondi)", "number", value=rete.get("turn_ttl_seconds"), help="Minimo 60 secondi."),
            campo("ws_token_max_age", "Durata link operatore (secondi)", "number", value=rete.get("ws_token_max_age"), help="Minimo 300 secondi."),
            campo("advanced_url_template", "URL collegamento esterno opzionale", value=rete.get("advanced_url_template"), placeholder="https://support.tuodominio.it/advanced/{public_id}", help="Opzionale: il controllo PC integrato resta nella stanza operatore e non richiede questo campo."),
        ],
        submit_label="Salva presidio",
        subtitle="Da aprire solo per cambiare STUN/TURN o durata dei link: la connessione standard è già pronta. Preferenze salvate nel presidio piattaforma.",
    )


def _prontezza(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Dati del servizio non mostrati dal modello storico (contatori, capacità, suggerimenti)."""
    totali = payload.get("stats") or {}
    return [
        metrics([
            {"label": "Sessioni aperte", "value": totali.get("aperte", 0), "tone": "warning" if totali.get("aperte") else "neutral"},
            {"label": "Attive ora", "value": totali.get("attive", 0), "tone": "success" if totali.get("attive") else "neutral"},
            {"label": "Chiuse", "value": totali.get("chiuse", 0)},
            {"label": "Totale sessioni", "value": totali.get("totale_sessioni", 0)},
        ]),
        status(
            "Capacità della cabina",
            [{"title": c.get("label"), "status": "ok" if c.get("ready") else "info", "statusLabel": c.get("state")} for c in payload.get("capabilities") or []],
        ),
        notes("Suggerimenti", list(payload.get("advisories") or []), tone="info"),
    ]


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    selezionata = payload.get("selected_session") or None
    filtri = payload.get("filters") or {}
    filtri_attivi = bool(_t(filtri.get("q")) or _t(filtri.get("status")))
    sezioni: list[dict[str, Any]] = [
        notes("Intervento richiesto prima dell'assistenza da remoto", list(payload.get("warnings") or []), tone="danger"),
        *_prontezza(payload),
        notes("Percorso reale di assistenza", [f"{t}: {s}" for t, s in PERCORSO], tone="info"),
        *_elenco_sessioni(payload, selezionata),
    ]
    if selezionata:
        sezioni.extend(_sessione_selezionata(payload, selezionata))
    sezioni.extend(_notifiche_dispositivo(payload))
    sezioni.extend(_sessione_manuale(payload))
    sezioni.append(_impostazioni_rete(payload))
    collegamenti = [link("Vista classica per le notifiche", f"{INDIRIZZO}?_legacy=1")]
    if filtri_attivi:
        collegamenti.insert(0, link("Rimuovi filtri", INDIRIZZO))
    return {
        "title": "Assistenza remota cliente",
        "subtitle": "Le richieste inviate dallo studio compaiono qui: il superamministratore le prende in carico, apre la stanza operatore e guida il cliente con schermo, chat, audit e controllo PC su consenso esplicito.",
        "links": collegamenti,
        "filter": {"name": "q", "label": "Cerca cliente, pratica o studio", "value": _t(filtri.get("q")), "options": []},
        "sections": sezioni,
    }


__all__ = ["AZIONI", "adatta", "costruisci", "esegui"]
