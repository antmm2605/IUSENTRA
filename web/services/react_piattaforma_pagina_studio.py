"""Pagina «Dettaglio studio» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/studi/<slug>` (rotta `dettaglio_studio`,
modello `admin/studio_dettaglio.html`) e i suoi invii: `modifica`, `moduli`,
`piano`, `sospendi`, `riattiva`, `rigenera-api-key` e `impersona`. Ogni azione
chiama gli stessi metodi di `GestioneTenant` della rotta storica; l'ingresso
nello studio scrive in sessione le stesse chiavi di `impersona_studio`.

La chiave riservata dello studio non compare nei dati della pagina: si mostra
una sola volta, nel risultato della rigenerazione.
"""

from __future__ import annotations

from pathlib import Path
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
    link,
    metrics,
    notes,
    table,
)
from web.services.react_piattaforma_studi_comune import (
    STATI_ATTIVAZIONE,
    collegamenti_studio,
    con_navigazione,
    data,
    errore_imprevisto,
    etichetta_stato,
    gestore_studi,
    nome_piano,
    pagina_studio_assente,
    ruolo,
    slug_di,
    spuntato,
    studio_non_trovato,
    testo,
    trattino,
    valore,
)

CAMPI_ANAGRAFICA = (
    ("nome", "Nome", "text"),
    ("piva", "Partita IVA", "text"),
    ("cf", "Codice fiscale", "text"),
    ("indirizzo", "Indirizzo", "text"),
    ("telefono", "Telefono", "text"),
    ("email", "Email", "email"),
    ("pec", "PEC", "email"),
    ("avvocato_ref", "Referente", "text"),
    ("note_admin", "Note interne", "textarea"),
)


# ------------------------------------------------------------------ lettura


def costruisci(slug: str) -> dict[str, Any]:
    """Gli stessi dati della rotta storica `dettaglio_studio`, in sola lettura."""
    from pct.tenant import DB_MODE_INFO, MODULI_DISPONIBILI, PIANI
    from web.blueprints.admin import _utente_del_tenant, _utenti_tenant

    slug = str(slug or "").strip()
    tm = gestore_studi()
    studio = tm.get(slug) if slug else None
    if not studio:
        return {"slug": slug, "studio": None}
    gu = _utenti_tenant(slug)
    utenti = [u for u in gu.lista() if _utente_del_tenant(u, slug)]
    storage_paths = tm.percorsi_dati(slug, reconcile_aliases=False)
    return {
        "slug": slug,
        "studio": studio,
        "utenti": utenti,
        "moduli_disponibili": MODULI_DISPONIBILI,
        "piani": PIANI,
        "db_mode_info": DB_MODE_INFO,
        "storage_manifest": tm.storage_manifest(slug, reconcile_aliases=False),
        "storage_root_path": str(Path(storage_paths["STUDIO_DB"]).parent),
    }


def _sezione_comandi(studio: Any) -> dict[str, Any]:
    slug = _t(studio.slug)
    voci = [
        azione("impersona", "Entra nello studio", tone="warning", params={"slug": slug}, confirm=f"Entrare nello studio «{_t(studio.nome)}» come suo amministratore? Per tornare al pannello usa «Esci impersonazione»."),
        azione("modifica", "Modifica dati", params={"slug": slug}, fields=[campo(n, etichetta, tipo, value=getattr(studio, n, ""), required=n == "nome") for n, etichetta, tipo in CAMPI_ANAGRAFICA]),
    ]
    if _t(studio.stato).upper() == "SOSPESO":
        voci.append(azione("riattiva", "Riattiva", tone="success", params={"slug": slug}, confirm=f"Riattivare lo studio {_t(studio.nome)}?"))
    else:
        voci.append(azione("sospendi", "Sospendi", tone="danger", params={"slug": slug}, confirm=f"Sospendere lo studio {_t(studio.nome)}?"))
    return actions("Comandi dello studio", voci)


def _sezioni_moduli(studio: Any, moduli: dict[str, Any]) -> list[dict[str, Any]]:
    attivi = set(studio.moduli_attivi or [])
    sottotitolo = f"{len(attivi)} moduli attivi."
    sezioni = [form(
        "Moduli autorizzati",
        "moduli",
        [campo(f"modulo_{k}", _t(v.get("nome")) or k, "checkbox", value=k in attivi, help=_t(v.get("desc"))) for k, v in moduli.items()],
        submit_label="Salva moduli",
        subtitle=sottotitolo,
        params={"slug": studio.slug},
    )]
    if studio.moduli_override:
        # Il pulsante storico «Ripristina dal piano» inviava il modulo senza moduli spuntati.
        sezioni.append(actions(
            "Configurazione manuale dei moduli",
            [azione("ripristina-moduli", "Ripristina i moduli del piano", params={"slug": studio.slug}, confirm=f"Tornare ai moduli previsti dal piano {nome_piano(studio.piano)}?")],
            subtitle=f"I moduli del piano {nome_piano(studio.piano)} sono stati sostituiti da una scelta manuale.",
        ))
    return sezioni


def _sezioni_piano(studio: Any, piani: dict[str, Any]) -> list[dict[str, Any]]:
    giorni = studio.giorni_alla_scadenza
    scade = trattino(data(studio.data_scadenza)) + (f" ({giorni} gg)" if giorni is not None else "")
    return [
        facts("Piano e scadenza", [
            ("Piano", nome_piano(studio.piano)),
            ("Creato", trattino(data(studio.data_creazione))),
            ("Attivato", trattino(data(studio.data_attivazione))),
            ("Scadenza", scade),
            ("Limite utenti", studio.limite_utenti or "illimitati"),
        ]),
        form(
            "Cambia piano",
            "piano",
            [campo("piano", "Piano", "select", value=studio.piano, options=[(k, (v or {}).get("nome")) for k, v in piani.items()])],
            submit_label="Aggiorna piano",
            subtitle="Il cambio di piano rinnova la scadenza, riattiva lo studio e ripristina i moduli del piano.",
            params={"slug": studio.slug},
        ),
    ]


def _sezioni_archivio(studio: Any, info_modi: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    db = studio.database
    modo = db.normalized_mode
    righe: list[tuple[str, Any]] = [("Archivio operativo", _t((info_modi.get(modo) or {}).get("nome")) or modo)]
    if manifest:
        righe.append(("Stato", STATI_ATTIVAZIONE.get(_t(manifest.get("activation_state")), _t(manifest.get("activation_state")))))
    sezioni: list[dict[str, Any]] = []
    if modo == "POSTGRESQL":
        righe.append(("Connessione", "Verificata" if db.connessione_ok else "Errore" if db.ultimo_test else "Non verificata"))
        righe.append(("Ultima verifica", data_ora(db.ultimo_test)))
        if db.errore_connessione:
            sezioni.append(notes("Connessione all'archivio", ["Verifica connessione non riuscita. Apri la configurazione dell'archivio."], tone="danger"))
    limite = studio.limite_storage_mb
    righe.append(("Spazio disponibile", f"{limite} MB" if limite > 0 else "Archivio senza limite"))
    return [
        facts("Archivio dati", righe),
        *sezioni,
        actions(
            "Spazio e chiave riservata",
            [
                azione("calcola-spazio", "Calcola lo spazio occupato", params={"slug": studio.slug}),
                azione("rigenera-api-key", "Rigenera chiave riservata", tone="danger", params={"slug": studio.slug}, confirm="Rigenerare la chiave riservata? La chiave precedente sarà invalidata."),
            ],
            subtitle="Il conteggio dello spazio si interrompe dopo due secondi e lo segnala. La chiave riservata si mostra solo al momento della rigenerazione.",
        ),
    ]


def _sezione_utenti(studio: Any, utenti: list[Any]) -> dict[str, Any]:
    limite = f" su {studio.limite_utenti} ammessi dal piano" if studio.limite_utenti > 0 else ""
    altri = f" Altri {len(utenti) - 5} nell'elenco completo." if len(utenti) > 5 else ""
    return table(
        f"Utenti dello studio ({len(utenti)}{limite})",
        [("user", "Utente"), ("role", "Ruolo"), ("state", "Stato")],
        [
            {"user": f"{_t(u.username)} — {_t(u.nome_completo)}" if _t(u.nome_completo) else _t(u.username), "role": ruolo(u), "state": "Attivo" if u.attivo else "Inattivo", "_tone": "" if u.attivo else "warning"}
            for u in utenti[:5]
        ],
        subtitle=f"Gestione completa dalla pagina «Utenti dello studio».{altri}",
        empty="Nessun utente.",
    )


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    studio = payload.get("studio")
    if studio is None:
        return pagina_studio_assente(_t(payload.get("slug")), "Dettaglio studio")
    stato, tono_stato = etichetta_stato(studio.stato)
    info_modi = payload.get("db_mode_info") or {}
    utenti = list(payload.get("utenti") or [])
    return {
        "title": _t(studio.nome),
        "subtitle": f"Identificativo dello studio: /{_t(studio.slug)}",
        "links": [*collegamenti_studio(_t(studio.slug), attuale="studio"), link("Spazio occupato (dati tecnici)", f"/admin/api/studi/{_t(studio.slug)}/storage", external=True)],
        "sections": [
            metrics([
                {"label": "Stato", "value": stato, "tone": tono_stato},
                {"label": "Piano", "value": nome_piano(studio.piano)},
                {"label": "Archivio", "value": _t((info_modi.get(studio.database.normalized_mode) or {}).get("nome")) or studio.database.normalized_mode},
                {"label": "Utenti", "value": f"{len(utenti)} / {studio.limite_utenti}" if studio.limite_utenti > 0 else len(utenti)},
            ]),
            _sezione_comandi(studio),
            facts("Dati dello studio", [(etichetta, trattino(getattr(studio, nome, ""))) for nome, etichetta, _tipo in CAMPI_ANAGRAFICA if nome != "nome"]),
            *_sezioni_moduli(studio, payload.get("moduli_disponibili") or {}),
            _sezione_utenti(studio, utenti),
            *_sezioni_piano(studio, payload.get("piani") or {}),
            *_sezioni_archivio(studio, info_modi, payload.get("storage_manifest") or {}),
            facts("Dati per assistenza", [("Identificativo interno", studio.id), ("Archivio dati dello studio", payload.get("storage_root_path"))]),
        ],
    }


# ------------------------------------------------------------------ azioni


def _modifica(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    tm.aggiorna(
        slug,
        nome=testo(values, "nome", studio.nome),
        **{nome: testo(values, nome) for nome, _etichetta, _tipo in CAMPI_ANAGRAFICA if nome != "nome"},
    )
    return esito(True, "Dati studio aggiornati.")


def _moduli(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    from pct.tenant import MODULI_DISPONIBILI

    # Come `request.form.getlist("moduli")`: i moduli spuntati, nell'ordine del modulo.
    selezionati = [k for k in MODULI_DISPONIBILI if spuntato(values, f"modulo_{k}")]
    tm.aggiorna_moduli(slug, selezionati)
    return esito(True, f"Moduli aggiornati: {len(selezionati)} attivi.")


def _ripristina_moduli(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    """Come «Ripristina dal piano» della vista storica: nessun modulo spuntato, valgono quelli del piano."""
    tm.aggiorna_moduli(slug, [])
    return esito(True, f"Moduli ripristinati: valgono quelli del piano {nome_piano(studio.piano)}.")


def _piano(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    from pct.tenant import PianoTenant

    piano = valore(values, "piano", PianoTenant.TRIAL)
    if tm.aggiorna_piano(slug, piano):
        return esito(True, f"Piano aggiornato a {nome_piano(piano)}.")
    return studio_non_trovato()


def _sospendi(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    tm.sospendi(slug)
    return esito(True, "Studio sospeso.", tone="warning")


def _riattiva(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    tm.riattiva(slug)
    return esito(True, "Studio riattivato.")


def _rigenera_api_key(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    nuova = tm.rigenera_api_key(slug)
    if not nuova:
        return studio_non_trovato()
    return esito(
        True,
        "Nuova chiave riservata generata.",
        tone="info",
        sections=[
            facts("Nuova chiave riservata dello studio", [("Chiave", nuova)]),
            notes("Conservala ora", ["La chiave non verrà più mostrata: la precedente non è più valida."], tone="warning"),
        ],
    )


def _calcola_spazio(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    """Lo stesso conteggio a tempo di `/admin/api/studi/<slug>/storage`."""
    from web.blueprints.admin import _calc_storage_mb_budget

    storage_paths = tm.percorsi_dati(slug, reconcile_aliases=False)
    mb, completo = _calc_storage_mb_budget(Path(storage_paths["STUDIO_DB"]).parent)
    limite = studio.limite_storage_mb
    percentuale = min(round(mb / limite * 100), 100) if limite > 0 else 0
    tono = "danger" if percentuale > 90 else "warning" if percentuale > 70 else "success"
    nota = "" if completo else "Conteggio parziale: il tempo disponibile è terminato."
    valore_mb = f"{mb:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return esito(True, "Spazio occupato calcolato.", tone="info", sections=[metrics([
        {"label": "Spazio usato", "value": f"{valore_mb} MB", "note": nota},
        {"label": "Limite del piano", "value": f"{limite} MB" if limite > 0 else "Senza limite"},
        {"label": "Utilizzo", "value": f"{percentuale}%" if limite > 0 else "n.d.", "tone": tono if limite > 0 else "neutral"},
    ], title="Spazio archivio")])


def _impersona(tm: Any, studio: Any, slug: str, values: dict[str, Any]) -> dict[str, Any]:
    """Stesse chiavi di sessione e stessa destinazione della rotta storica `impersona_studio`."""
    from flask import current_app, session, url_for

    from pct.auth import RuoloUtente
    from pct.tenant import StatoTenant
    from web.blueprints.admin import _utente_del_tenant, _utenti_tenant

    if studio.stato == StatoTenant.SOSPESO:
        return esito(False, "Lo studio è sospeso: riattivalo prima di entrarvi.")
    gu = _utenti_tenant(slug)
    admin_studio = next((u for u in gu.lista() if u.ruolo == RuoloUtente.AMMINISTRATORE and _utente_del_tenant(u, slug)), None)
    if not admin_studio:
        return esito(False, "Nessun utente AMMINISTRATORE trovato per questo studio.")

    # Sessione del superamministratore da ripristinare con «Esci impersonazione».
    session["superadmin_user_id"] = session.get("user_id")
    session["superadmin_auth_db"] = current_app.config.get("AUTH_DB")
    session["superadmin_tenant_slug"] = ""
    # Contesto dello studio.
    session["user_id"] = admin_studio.id
    session["tenant_slug"] = slug
    session["auth_scope"] = "tenant"
    session["auth_tenant_slug"] = slug
    session["_fresh"] = True

    messaggio = f"Stai operando come studio '{studio.nome}'. Clicca 'Esci impersonazione' per tornare."
    return con_navigazione(esito(True, messaggio, tone="warning"), url_for("dashboard"))


AZIONI = {
    "modifica": _modifica,
    "moduli": _moduli,
    "ripristina-moduli": _ripristina_moduli,
    "piano": _piano,
    "sospendi": _sospendi,
    "riattiva": _riattiva,
    "rigenera-api-key": _rigenera_api_key,
    "calcola-spazio": _calcola_spazio,
    "impersona": _impersona,
}


def esegui(nome_azione: str, params: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    gestore = AZIONI.get(str(nome_azione or "").strip())
    if gestore is None:
        return esito(False, "Azione non disponibile in questa pagina.")
    slug = slug_di(params)
    try:
        tm = gestore_studi()
        studio = tm.get(slug) if slug else None
        if not studio:
            return studio_non_trovato()
        return gestore(tm, studio, slug, dict(values or {}))
    except Exception:
        return errore_imprevisto("Errore azione %s sullo studio %s dal pannello React", nome_azione, slug)


__all__ = ["adatta", "costruisci", "esegui"]
