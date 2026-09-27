"""Pagina «Configurazione archivio» dello studio nel pannello di piattaforma (React).

Sostituisce la vista storica `/admin/studi/<slug>/database` (rotta
`database_studio` GET e POST, modelli `admin/studio_database.html` e
`admin/_db_form_sql.html`) e gli invii `database/ripara-runtime` e
`database/test`. Il salvataggio costruisce la stessa `DatabaseConfig` della
rotta storica, con le stesse precedenze fra valori inviati e valori salvati;
la password dell'archivio non torna mai nei dati della pagina.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_sezioni import (
    _t,
    actions,
    azione,
    campo,
    data_ora,
    esito,
    facts,
    form,
    notes,
    status,
)
from web.services.react_piattaforma_studi_comune import (
    ARCHIVI_EFFETTIVI,
    STATI_ATTIVAZIONE,
    collegamenti_studio,
    errore_imprevisto,
    gestore_studi,
    indirizzo_ip,
    pagina_studio_assente,
    slug_di,
    spuntato,
    studio_non_trovato,
    utente_corrente,
    valore,
)

#: Campi del riquadro PostgreSQL: la vista storica li disattivava (e non li inviava) con le altre strategie.
CAMPI_CONNESSIONE = ("host", "porta", "db_name", "db_utente", "db_password", "pool_size", "pool_timeout", "ssl")

REGOLE = (
    "PostgreSQL diventa l'archivio effettivo solo dopo verifica della connessione, migrazione e attivazione esplicita.",
    "Se PostgreSQL è attivo e non raggiungibile, i moduli principali non ripiegano in silenzio su JSON.",
    "SQLite resta l'archivio locale o il ripiego controllato per gli studi non ancora passati a PostgreSQL.",
    "I documenti restano nella cartella dello studio anche quando i dati principali passano su database SQL.",
)


def costruisci(slug: str) -> dict[str, Any]:
    """Gli stessi dati della rotta storica `database_studio` (GET)."""
    from pct.tenant import DB_MODE_INFO
    from web.blueprints.admin import _db_mode_choices

    slug = str(slug or "").strip()
    tm = gestore_studi()
    studio = tm.get(slug) if slug else None
    if not studio:
        return {"slug": slug, "studio": None}
    return {
        "slug": slug,
        "studio": studio,
        "db": studio.database,
        "db_mode_info": DB_MODE_INFO,
        "db_mode_choices": _db_mode_choices(studio.database.mode),
        "storage_manifest": tm.storage_manifest(slug, reconcile_aliases=False),
        "storage_paths": tm.percorsi_dati(slug, reconcile_aliases=False),
    }


def _nome_modo(info_modi: dict[str, Any], modo: str) -> str:
    return _t((info_modi.get(modo) or {}).get("nome")) or modo


def _campi_connessione(db: Any, info_modi: dict[str, Any]) -> list[dict[str, Any]]:
    porta = _t((info_modi.get(db.normalized_mode) or {}).get("porta")) or "5432"
    return [
        campo("host", "Host", value=db.host or "", placeholder="es. ep-esempio-pooler.eu-central-1.aws.neon.tech"),
        campo("porta", "Porta", "number", value=db.porta or "", placeholder=porta, help=f"Vuota: porta predefinita {porta}."),
        campo("db_name", "Nome del database", value=db.db_name, placeholder="es. neondb"),
        campo("db_utente", "Utente", value=db.utente, placeholder="es. neondb_owner"),
        campo(
            "db_password",
            "Password",
            "password",
            help="Lascia vuoto per mantenere quella attuale." if db.password else "Nessuna password salvata: inseriscila per PostgreSQL.",
            placeholder="••••••••" if db.password else "Inserisci la password",
        ),
        campo("pool_size", "Connessioni nel gruppo", "number", value=db.pool_size or 5),
        campo("pool_timeout", "Attesa massima (secondi)", "number", value=db.pool_timeout or 30),
        campo("ssl", "Usa SSL/TLS", "checkbox", value=bool(db.ssl)),
    ]


def _note_modo(db: Any, manifest: dict[str, Any], percorsi: dict[str, Any]) -> list[dict[str, Any]]:
    modo = db.normalized_mode
    if modo == "JSON":
        return [notes("JSON locale", ["Compatibilità con le installazioni storiche: file JSON nella cartella dello studio, adatti a installazioni storiche o di transizione, non al passaggio professionale dei moduli principali."], tone="warning")]
    if modo == "SQLITE":
        return [
            notes("SQLite per studio", [f"I moduli principali usano {_t(percorsi.get('STUDIO_DB'))}. Se il database non è ancora popolato, il sistema resta su JSON in modo dichiarato e tracciato."], tone="info"),
            facts("Archivio SQLite", [
                ("File del database", percorsi.get("STUDIO_DB")),
                ("Archivio effettivo", ARCHIVI_EFFETTIVI.get(_t(manifest.get("effective_runtime_kind")), _t(manifest.get("effective_runtime_kind")))),
                ("Stato", STATI_ATTIVAZIONE.get(_t(manifest.get("activation_state")), _t(manifest.get("activation_state")))),
            ]),
        ]
    if modo != "POSTGRESQL":
        return []
    if manifest.get("core_runtime_enabled"):
        nota = notes("PostgreSQL", ["Archivio principale attivo in lettura e scrittura: utenti, clienti, fascicoli, agenda e scadenziario usano PostgreSQL per questo studio."], tone="success")
    elif db.connessione_ok:
        nota = notes("PostgreSQL", ["Connessione pronta, passaggio non ancora eseguito: salva i parametri, poi usa l'attivazione per migrare i moduli principali e generare il report di consistenza."], tone="warning")
    else:
        nota = notes("PostgreSQL", ["Attivazione esplicita richiesta: PostgreSQL non diventa mai l'archivio principale in modo invisibile. Prima salvi, poi verifichi la connessione, poi attivi la migrazione con report."], tone="info")
    sezioni = [nota, facts("Connessione PostgreSQL", [
        ("Indirizzo di connessione attuale", db.connection_url_safe),
        ("Esito dell'ultima verifica", "Riuscita" if db.connessione_ok else "Non riuscita" if db.ultimo_test else "Non eseguita"),
        ("Ultima verifica", data_ora(db.ultimo_test)),
    ])]
    if manifest.get("last_migration_at"):
        sezioni.append(facts("Ultima migrazione registrata", [("Eseguita il", data_ora(manifest.get("last_migration_at"))), ("Report", manifest.get("last_migration_report"))]))
    if db.errore_connessione and not db.connessione_ok:
        sezioni.append(notes("Ultimo errore di connessione", [db.errore_connessione], tone="danger"))
    return sezioni


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    studio = payload.get("studio")
    if studio is None:
        return pagina_studio_assente(_t(payload.get("slug")), "Configurazione archivio")
    slug = _t(payload.get("slug"))
    db = payload.get("db") or studio.database
    info_modi = payload.get("db_mode_info") or {}
    scelte = list(payload.get("db_mode_choices") or [])
    manifest = payload.get("storage_manifest") or {}
    modo = db.normalized_mode
    effettivo = ARCHIVI_EFFETTIVI.get(_t(manifest.get("effective_runtime_kind")), _t(manifest.get("effective_runtime_kind")))
    comandi = []
    if modo == "POSTGRESQL":
        comandi += [
            azione("test", "Verifica connessione", params={"slug": slug}),
            azione(
                "attiva-postgres",
                "Attiva PostgreSQL e migra i moduli principali",
                tone="primary",
                params={"slug": slug, "db_mode": "POSTGRESQL"},
                fields=_campi_connessione(db, info_modi),
                confirm="Salvare i parametri, migrare utenti, clienti, fascicoli, agenda e scadenziario su PostgreSQL e attivarlo come archivio principale?",
            ),
        ]
    comandi.append(azione("ripara-runtime", "Ripara studio", params={"slug": slug}, confirm="Riallineare appartenenza degli utenti, indice degli accessi, cartelle dati e controllo SQLite dello studio?"))
    return {
        "title": "Configurazione archivio",
        "subtitle": f"Studio {_t(studio.nome)} · strategia selezionata: {_nome_modo(info_modi, modo)}" + (f" · archivio effettivo dei moduli principali: {effettivo}" if manifest else ""),
        "links": collegamenti_studio(slug, attuale="studio-database"),
        "sections": [
            status(
                "Strategie di archivio",
                [
                    {"title": _nome_modo(info_modi, m), "summary": (info_modi.get(m) or {}).get("desc"), "detail": (info_modi.get(m) or {}).get("badge"), "status": "ok" if m == modo else "info", "statusLabel": "Selezionata" if m == modo else "Disponibile"}
                    for m in scelte
                ],
            ),
            *_note_modo(db, manifest, payload.get("storage_paths") or {}),
            form(
                "Salva la configurazione",
                "salva",
                [campo("db_mode", "Strategia di archivio", "select", value=modo, options=[(m, _nome_modo(info_modi, m)) for m in scelte]), *_campi_connessione(db, info_modi)],
                submit_label="Salva configurazione",
                subtitle="I parametri di connessione valgono solo per PostgreSQL: con JSON o SQLite restano quelli già salvati.",
                params={"slug": slug},
            ),
            actions("Presidio del superamministratore", comandi, subtitle="«Ripara studio» si usa quando uno studio risulta bloccato o non vede i propri dati dopo una migrazione."),
            notes("Regole operative", list(REGOLE), tone="info"),
        ],
    }


# ------------------------------------------------------------------ azioni


def _intero(value: Any, predefinito: int) -> int:
    try:
        return int(value or predefinito)
    except (TypeError, ValueError):
        return predefinito


def _primo(values: dict[str, Any], *nomi: str) -> str | None:
    """`request.form.get(a) or request.form.get(b) or ...`."""
    for nome in nomi:
        trovato = valore(values, nome)
        if trovato:
            return trovato
    return None


def _configurazione(studio: Any, mode: str, values: dict[str, Any]):
    from pct.tenant import DatabaseConfig, DbMode

    salvato = studio.database
    return DatabaseConfig(
        mode=mode,
        host=(_primo(values, "host", "db_host") or salvato.host or "localhost").strip(),
        porta=_intero(_primo(values, "porta", "db_porta") or salvato.porta, 0),
        db_name=(_primo(values, "db_name", "database", "nome_database") or salvato.db_name or "").strip(),
        utente=(_primo(values, "db_utente", "utente", "username") or salvato.utente or "").strip(),
        password=(_primo(values, "db_password", "password") or salvato.password or "").strip(),
        ssl=spuntato(values, "ssl"),
        pool_size=_intero(valore(values, "pool_size", "5"), 5),
        pool_timeout=_intero(valore(values, "pool_timeout", "30"), 30),
        connessione_ok=salvato.connessione_ok,
        ultimo_test=salvato.ultimo_test,
        errore_connessione=salvato.errore_connessione,
        core_runtime_enabled=salvato.core_runtime_enabled if mode == DbMode.POSTGRESQL else False,
        last_migration_report=salvato.last_migration_report if mode == DbMode.POSTGRESQL else "",
        last_migration_at=salvato.last_migration_at if mode == DbMode.POSTGRESQL else "",
    )


def _salva(tm: Any, studio: Any, slug: str, values: dict[str, Any], *, attiva: bool = False) -> dict[str, Any]:
    """Stessi passi della rotta storica `database_studio` (POST, `storage_action` save/activate_postgres)."""
    from flask import current_app

    from pct.tenant import DbMode, normalize_db_mode
    from web.blueprints.admin import _db_mode_choices

    mode = normalize_db_mode(valore(values, "db_mode", studio.database.mode))
    current_mode = studio.database.normalized_mode
    if mode not in _db_mode_choices(studio.database.mode):
        return esito(False, "Strategia di archivio non consentita per questo studio.")
    if current_mode == DbMode.SQLITE and mode == DbMode.JSON:
        return esito(False, "Il ritorno diretto da SQLite a JSON non è consentito senza una migrazione esplicita dei dati.")
    if mode != DbMode.POSTGRESQL:
        values = {k: v for k, v in values.items() if k not in CAMPI_CONNESSIONE}

    tm.aggiorna_db_config(slug, _configurazione(studio, mode, values))

    if mode == DbMode.SQLITE:
        provisioning = tm.provision_storage_backend(slug, migrate_existing=current_mode != DbMode.SQLITE)
        dettaglio = []
        if provisioning.get("migrated"):
            dettaglio.append("Dati JSON migrati in studio.db.")
        elif provisioning.get("sqlite_ready"):
            dettaglio.append("SQLite pronto: studio.db disponibile per i moduli principali compatibili.")
        return esito(True, "Configurazione dell'archivio salvata.", sections=[notes("SQLite per studio", dettaglio, tone="info")] if dettaglio else [])

    if mode == DbMode.POSTGRESQL and attiva:
        provisioning = tm.provision_storage_backend(slug, migrate_existing=True, activate_external=True, secret_key=current_app.secret_key)
        if provisioning.get("ok") and provisioning.get("activated"):
            percorso = _t(provisioning.get("migration_report_path"))
            return esito(
                True,
                "PostgreSQL attivato come archivio in lettura e scrittura per utenti, clienti, fascicoli, agenda e scadenziario.",
                sections=[notes("Report di consistenza", [f"Report di consistenza generato: {percorso}"], tone="info")] if percorso else [],
            )
        # La vista storica mostrava l'errore dell'attivazione così com'era: qui resta come dettaglio
        # sotto un messaggio italiano (spesso è il testo tecnico del driver di PostgreSQL).
        dettaglio = _t(provisioning.get("error"))
        return esito(
            False,
            "Attivazione PostgreSQL non completata: verifica connessione e report di migrazione.",
            sections=[notes("Dettaglio dell'errore", [dettaglio], tone="danger")] if dettaglio else [],
        )

    if mode == DbMode.JSON:
        return esito(True, "Configurazione dell'archivio salvata.")
    return esito(True, "Configurazione PostgreSQL salvata. Esegui la verifica della connessione e poi l'attivazione esplicita dell'archivio principale.")


def _ripara(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    """Stessi passi della rotta storica `ripara_runtime_studio`, con lo stesso evento di audit."""
    from flask import current_app

    from web.blueprints.admin import _utenti_piattaforma

    report = tm.repair_studio_runtime(slug, secret_key=current_app.secret_key)
    utente = utente_corrente()
    try:
        _utenti_piattaforma().registra_evento(
            azione="studio.runtime.ripara",
            id_utente=str(getattr(utente, "id", "") or ""),
            username=str(getattr(utente, "username", "") or "superadmin"),
            risorsa_tipo="studio",
            risorsa_id=slug,
            dettagli=(
                f"Riparazione studio: utenti controllati {report.get('users_checked', 0)}, "
                f"utenti corretti {report.get('users_repaired', 0)}, "
                f"indice utenti {report.get('directory_entries', 0)} voci."
            ),
            ip=indirizzo_ip(),
            esito="OK" if report.get("ok") else "ERRORE",
        )
    except Exception:  # noqa: BLE001 - l'audit di piattaforma non deve impedire il report al superamministratore
        current_app.logger.exception("Audit riparazione studio non registrato")

    riepilogo = facts("Esito della riparazione", [
        ("Utenti controllati", report.get("users_checked", 0)),
        ("Utenti corretti", report.get("users_repaired", 0)),
        ("Voci nell'indice utenti", report.get("directory_entries", 0)),
    ])
    if report.get("ok"):
        return esito(True, "Riparazione completata: accesso studio, indice utenti e archivio sono stati riallineati.", sections=[riepilogo])
    errori = [str(e) for e in (report.get("errors") or [])[:3]]
    return esito(
        False,
        "Riparazione non completata: controlla gli avvisi e riprova dal pannello del superamministratore.",
        sections=[riepilogo, notes("Avvisi", errori, tone="warning")],
    )


def _test(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    """Come la rotta storica `testa_connessione_db`: stesso metodo, errore generico se il test si interrompe."""
    from flask import current_app

    try:
        risultato = tm.testa_connessione(slug)
    except Exception:
        current_app.logger.exception("Errore test connessione DB")
        return esito(False, "Test connessione non completato.")
    if risultato.get("ok"):
        return esito(True, "Connessione riuscita.", sections=[notes("Verifica della connessione", [_t(risultato.get("messaggio")) or "Test completato con successo."], tone="success")])
    dettaglio = _t(risultato.get("errore")) or _t(risultato.get("messaggio")) or "Errore sconosciuto."
    return esito(False, "Connessione fallita.", sections=[notes("Verifica della connessione", [dettaglio], tone="danger")])


def _salva_azione(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    return _salva(tm, studio, slug, values)


def _attiva_postgres(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    return _salva(tm, studio, slug, values, attiva=True)


AZIONI = {"salva": _salva_azione, "attiva-postgres": _attiva_postgres, "ripara-runtime": _ripara, "test": _test}


def esegui(nome_azione: str, params: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    gestore = AZIONI.get(str(nome_azione or "").strip())
    if gestore is None:
        return esito(False, "Azione non disponibile in questa pagina.")
    slug = slug_di(params)
    valori = dict(values or {})
    if (params or {}).get("db_mode"):
        valori["db_mode"] = str(params["db_mode"])
    try:
        tm = gestore_studi()
        studio = tm.get(slug) if slug else None
        if not studio:
            return studio_non_trovato()
        return gestore(tm, studio, slug, valori)
    except Exception:
        return errore_imprevisto("Errore azione %s sull'archivio dello studio %s dal pannello React", nome_azione, slug)


__all__ = ["adatta", "costruisci", "esegui"]
