"""Pagine «Studi legali» e «Nuovo studio» del pannello di piattaforma (React).

Sostituiscono le viste storiche `/admin/studi` (rotta `lista_studi`, modello
`admin/studi_lista.html`) e `/admin/studi/nuovo` (rotta `nuovo_studio`,
modello `admin/studio_nuovo.html`). La lista filtra con le stesse regole della
rotta storica; la creazione chiama, nello stesso ordine, `tm.crea`,
`tm.aggiorna_db_config`, la creazione dell'amministratore dello studio,
`tm.provision_storage_backend` e la sincronizzazione dell'indice utenti.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from web.services.react_piattaforma_sezioni import (
    _t,
    campo,
    esito,
    form,
    link,
    notes,
    status,
    table,
)
from web.services.react_piattaforma_studi_comune import (
    STATI_STUDIO,
    con_navigazione,
    data,
    errore_imprevisto,
    etichetta_stato,
    gestore_studi,
    nome_piano,
    scadenza,
    testo,
    valore,
)

# ------------------------------------------------------------------ lista


def costruisci_lista(q: str = "", stato: str = "", piano: str = "") -> dict[str, Any]:
    """Gli stessi passi della rotta storica `lista_studi`."""
    from pct.tenant import PIANI

    tm = gestore_studi()
    tm.verifica_scadenze()
    filtro_stato = str(stato or "")
    filtro_piano = str(piano or "")
    ricerca = str(q or "").lower().strip()
    studi = tm.lista()
    if filtro_stato:
        studi = [s for s in studi if s.stato == filtro_stato]
    if filtro_piano:
        studi = [s for s in studi if s.piano == filtro_piano]
    if ricerca:
        studi = [s for s in studi if ricerca in s.nome.lower() or ricerca in s.slug or ricerca in (s.piva or "")]
    return {"studi": studi, "piani": PIANI, "filtro_stato": filtro_stato, "filtro_piano": filtro_piano, "q": ricerca}


def _riga_studio(studio: Any) -> dict[str, Any]:
    etichetta, tono = etichetta_stato(studio.stato)
    testo_scadenza, tono_scadenza = scadenza(studio)
    nome = _t(studio.nome)
    return {
        "name": f"{nome} — {_t(studio.avvocato_ref)}" if _t(studio.avvocato_ref) else nome,
        "slug": f"/{_t(studio.slug)}",
        "plan": nome_piano(studio.piano),
        "state": etichetta,
        "expiry": testo_scadenza,
        "created": data(studio.data_creazione) or "—",
        "_href": f"/admin/studi/{_t(studio.slug)}",
        "_tone": "danger" if tono == "danger" else tono_scadenza,
    }


def _modulo_filtri(payload: dict[str, Any]) -> dict[str, Any]:
    piani = payload.get("piani") or {}
    return form(
        "Filtra gli studi",
        "filtra",
        [
            campo("q", "Cerca", value=payload.get("q"), placeholder="Nome, identificativo o partita IVA"),
            campo("stato", "Stato", "select", value=payload.get("filtro_stato"), options=[("", "Tutti gli stati"), *[(k, v[0]) for k, v in STATI_STUDIO.items()]]),
            campo("piano", "Piano", "select", value=payload.get("filtro_piano"), options=[("", "Tutti i piani"), *[(k, (v or {}).get("nome")) for k, v in piani.items()]]),
        ],
        submit_label="Filtra",
        subtitle="Stato e piano si combinano con la ricerca, come nel filtro storico.",
    )


def adatta_lista(payload: dict[str, Any]) -> dict[str, Any]:
    studi = payload.get("studi") or []
    filtri_attivi = any(payload.get(k) for k in ("q", "filtro_stato", "filtro_piano"))
    return {
        "title": "Studi legali",
        "subtitle": f"{len(studi)} {'studio' if len(studi) == 1 else 'studi'}{' con i filtri applicati' if filtri_attivi else ''}.",
        "links": [link("Nuovo studio", "/admin/studi/nuovo", tone="primary")] + ([link("Rimuovi filtri", "/admin/studi")] if filtri_attivi else []),
        "filter": {"name": "q", "label": "Cerca per nome, identificativo o partita IVA", "value": _t(payload.get("q")), "options": []},
        "sections": [
            _modulo_filtri(payload),
            table(
                "Studi registrati",
                [("name", "Studio"), ("slug", "Identificativo"), ("plan", "Piano"), ("state", "Stato"), ("expiry", "Scadenza"), ("created", "Creato il")],
                [_riga_studio(s) for s in studi],
                empty="Nessuno studio trovato.",
            ),
        ],
    }


def _esegui_filtra(values: dict[str, Any]) -> dict[str, Any]:
    parametri = {k: testo(values, k) for k in ("q", "stato", "piano") if testo(values, k)}
    indirizzo = f"/admin/studi?{urlencode(parametri)}" if parametri else "/admin/studi"
    return con_navigazione(esito(True, "Filtri applicati.", tone="info"), indirizzo)


def esegui_lista(azione: str, params: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    if azione == "filtra":
        return _esegui_filtra(values or {})
    return esito(False, "Azione non disponibile in questa pagina.")


# ------------------------------------------------------------------ nuovo studio


def costruisci_nuovo() -> dict[str, Any]:
    from pct.tenant import DB_MODE_INFO, PIANI
    from web.blueprints.admin import _db_mode_choices

    return {"piani": PIANI, "db_mode_info": DB_MODE_INFO, "db_mode_choices": _db_mode_choices()}


def _descrizione_piano(info: dict[str, Any]) -> str:
    utenti = "Utenti illimitati" if not info.get("max_utenti") else f"Massimo {info.get('max_utenti')} utenti"
    archivio = "archivio illimitato" if not info.get("max_storage_mb") else f"{round(int(info.get('max_storage_mb') or 0) / 1000, 1)} GB"
    return f"{utenti} · {archivio} · {len(info.get('moduli') or [])} moduli · durata {info.get('durata_gg')} giorni"


def adatta_nuovo(payload: dict[str, Any]) -> dict[str, Any]:
    piani = payload.get("piani") or {}
    info_modi = payload.get("db_mode_info") or {}
    scelte = list(payload.get("db_mode_choices") or [])
    campi = [
        campo("nome", "Nome dello studio", required=True, placeholder="es. Studio Legale Rossi & Associati"),
        campo("slug", "Identificativo (slug)", required=True, placeholder="studio-rossi", help="Identificativo unico nell'indirizzo: lettere minuscole, cifre e trattini."),
        campo("avvocato_ref", "Avvocato o referente", placeholder="Avv. Mario Rossi"),
        campo("piva", "Partita IVA", placeholder="12345678901"),
        campo("cf", "Codice fiscale", placeholder="RSSMRA80A01H501U"),
        campo("indirizzo", "Indirizzo", placeholder="Via Roma 1, 20100 Milano (MI)"),
        campo("telefono", "Telefono", placeholder="+39 02 12345678"),
        campo("email", "Email", "email", placeholder="info@studio.it"),
        campo("pec", "PEC", "email", placeholder="studio@pec.it"),
        campo("note_admin", "Note interne", "textarea", placeholder="Note visibili solo agli amministratori della piattaforma"),
        campo("piano", "Piano di sottoscrizione", "select", value="TRIAL", options=[(k, (v or {}).get("nome")) for k, v in piani.items()]),
        campo("db_mode", "Strategia di archivio", "select", value="SQLITE", options=[(m, f"{_t((info_modi.get(m) or {}).get('nome')) or m} · {_t((info_modi.get(m) or {}).get('badge'))}") for m in scelte]),
        campo("admin_username", "Nome utente dell'amministratore", value="amministratore", required=True),
        campo("admin_password", "Password dell'amministratore", "password", required=True, help="Password iniziale da comunicare all'amministratore dello studio."),
        campo("admin_nome", "Nome completo dell'amministratore", placeholder="Mario Rossi"),
        campo("admin_email", "Email dell'amministratore", "email", placeholder="admin@studio.it"),
    ]
    note_modi = {
        "SQLITE": "Alla creazione viene predisposto automaticamente studio.db nello studio.",
        "POSTGRESQL": "La connessione esterna si configura e si verifica dopo la creazione; i moduli principali restano sull'archivio locale finché non si completa la migrazione.",
    }
    return {
        "title": "Nuovo studio legale",
        "subtitle": "Dati dello studio, strategia di archivio, piano e amministratore del nuovo studio della piattaforma.",
        "links": [link("Tutti gli studi", "/admin/studi")],
        "sections": [
            form("Dati del nuovo studio", "crea", campi, submit_label="Crea studio", subtitle="L'amministratore potrà creare altri utenti e gestire le impostazioni dello studio."),
            status(
                "Strategie di archivio",
                [
                    {
                        "title": (info_modi.get(m) or {}).get("nome") or m,
                        "summary": (info_modi.get(m) or {}).get("desc"),
                        "detail": " ".join(x for x in (note_modi.get(m, ""), f"Porta predefinita: {(info_modi.get(m) or {}).get('porta')}." if m not in {"JSON", "SQLITE"} and (info_modi.get(m) or {}).get("porta") else "") if x),
                        "status": "info",
                        "statusLabel": (info_modi.get(m) or {}).get("badge"),
                    }
                    for m in scelte
                ],
                subtitle="JSON per installazioni leggere, SQLite per studi locali robusti, PostgreSQL per ambienti cloud e multi-studio.",
            ),
            table(
                "Piani disponibili",
                [("plan", "Piano"), ("limits", "Limiti e durata"), ("modules", "Moduli inclusi")],
                [{"plan": (v or {}).get("nome") or k, "limits": _descrizione_piano(v or {}), "modules": ", ".join((v or {}).get("moduli") or [])} for k, v in piani.items()],
                subtitle="I moduli si assegnano in base al piano e si possono personalizzare dopo la creazione.",
            ),
            notes("Dopo la creazione", ["Con PostgreSQL si apre la configurazione della connessione; negli altri casi il dettaglio del nuovo studio."], tone="info"),
        ],
    }


def _crea_studio(values: dict[str, Any]) -> dict[str, Any]:
    """Stessi passi e stessi messaggi della rotta storica `nuovo_studio` (POST)."""
    from flask import current_app, url_for

    from pct.auth import GestioneUtenti, RuoloUtente
    from pct.tenant import DatabaseConfig, DbMode, PianoTenant, normalize_db_mode
    from web.blueprints.admin import _db_mode_choices, _sync_tenant_user_directory

    nome = testo(values, "nome")
    slug = testo(values, "slug")
    piano = valore(values, "piano", PianoTenant.TRIAL)
    campi = {k: testo(values, k) for k in ("piva", "cf", "indirizzo", "telefono", "email", "pec", "avvocato_ref", "note_admin")}
    admin_username = testo(values, "admin_username", "amministratore")
    admin_password = testo(values, "admin_password")
    admin_nome = testo(values, "admin_nome", nome)
    admin_email = testo(values, "admin_email", campi["email"])
    db_mode = normalize_db_mode(valore(values, "db_mode", DbMode.SQLITE))

    if not nome or not slug:
        return esito(False, "Nome e slug sono obbligatori.")
    if not admin_password:
        return esito(False, "Imposta una password per l'amministratore dello studio.")
    if db_mode not in _db_mode_choices():
        return esito(False, "Strategia di archivio non consentita per i nuovi studi.")

    tm = gestore_studi()
    try:
        tm.crea(nome=nome, slug=slug, piano=piano, **campi)
    except ValueError as exc:
        return esito(False, str(exc))

    # Salva la modalità di archivio scelta, come la rotta storica.
    tm.aggiorna_db_config(slug, DatabaseConfig(mode=db_mode))

    percorsi = tm.percorsi_dati(slug)
    gu = GestioneUtenti(
        db_path=percorsi["AUTH_DB"],
        audit_path=percorsi["AUDIT_DB"],
        secret_key=current_app.secret_key,
        crea_admin_se_vuoto=False,
    )
    try:
        gu.crea(
            username=admin_username,
            password=admin_password,
            ruolo=RuoloUtente.AMMINISTRATORE,
            nome_completo=admin_nome,
            email=admin_email,
            tenant_slug=slug,
        )
    except Exception:
        current_app.logger.exception("Errore creazione amministratore studio")
        risultato = esito(True, "Studio creato, ma la creazione dell'amministratore non è riuscita.", tone="warning")
        return con_navigazione(risultato, url_for("admin.dettaglio_studio", slug=slug))

    provisioning = tm.provision_storage_backend(slug, migrate_existing=db_mode == DbMode.SQLITE)
    _sync_tenant_user_directory()

    avvisi: list[str] = []
    if db_mode == DbMode.SQLITE:
        if provisioning.get("migrated"):
            avvisi.append("SQLite attivato e dati iniziali migrati in studio.db.")
        elif provisioning.get("sqlite_ready"):
            avvisi.append("SQLite attivato: studio.db è pronto per questo studio.")
    destinazione = url_for("admin.dettaglio_studio", slug=slug)
    if db_mode == DbMode.POSTGRESQL:
        avvisi.append("Configura ora i parametri di connessione PostgreSQL.")
        destinazione = url_for("admin.database_studio", slug=slug)
    sezioni = [notes("Archivio dello studio", avvisi, tone="info")] if avvisi else []
    return con_navigazione(esito(True, f"Studio '{nome}' creato con successo!", sections=sezioni), destinazione)


def esegui_nuovo(azione: str, params: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    if azione != "crea":
        return esito(False, "Azione non disponibile in questa pagina.")
    try:
        return _crea_studio(dict(values or {}))
    except Exception:
        return errore_imprevisto("Errore creazione studio dal pannello React")


# Nomi uniformi al registro (`Pagina(chiave, titolo, indirizzo, costruisci, adatta, esegui)`).
costruisci = costruisci_lista
adatta = adatta_lista
esegui = esegui_lista

__all__ = [
    "adatta",
    "adatta_lista",
    "adatta_nuovo",
    "costruisci",
    "costruisci_lista",
    "costruisci_nuovo",
    "esegui",
    "esegui_lista",
    "esegui_nuovo",
]
