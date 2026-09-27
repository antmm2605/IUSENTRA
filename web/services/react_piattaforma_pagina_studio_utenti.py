"""Pagina «Utenti dello studio» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/studi/<slug>/utenti` (rotta
`utenti_studio`, modello `admin/studio_utenti.html`) e i suoi invii:
`utenti/nuovo`, `utenti/<uid>/reset-password`, `utenti/<uid>/attiva-disattiva`
e `utenti/<uid>/elimina`. Le azioni usano lo stesso gestore utenti dello studio
(`_utenti_tenant`), gli stessi controlli di appartenenza allo studio e la
stessa sincronizzazione dell'indice utenti della piattaforma.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_sezioni import (
    _t,
    azione,
    campo,
    esito,
    form,
    metrics,
    notes,
    status,
    table,
)
from web.services.react_piattaforma_studi_comune import (
    collegamenti_studio,
    data,
    errore_imprevisto,
    gestore_studi,
    nome_piano,
    pagina_studio_assente,
    ruolo,
    slug_di,
    studio_non_trovato,
    testo,
    valore,
)

REGOLA = (
    "Il ruolo SUPERADMIN è unico e vive solo a livello di piattaforma: da questa pagina si creano e si "
    "gestiscono solo gli utenti dello studio selezionato."
)


def costruisci(slug: str) -> dict[str, Any]:
    """Gli stessi dati della rotta storica `utenti_studio`."""
    from pct.auth import DESCRIZIONI_RUOLI, RuoloUtente
    from web.blueprints.admin import _utente_del_tenant, _utenti_tenant

    slug = str(slug or "").strip()
    tm = gestore_studi()
    studio = tm.get(slug) if slug else None
    if not studio:
        return {"slug": slug, "studio": None}
    gu = _utenti_tenant(slug)
    utenti = [u for u in gu.lista() if _utente_del_tenant(u, slug)]
    return {"slug": slug, "studio": studio, "utenti": utenti, "ruoli": list(RuoloUtente), "descrizioni_ruoli": DESCRIZIONI_RUOLI}


def _ruoli_studio(ruoli: list[Any]) -> list[tuple[str, str]]:
    return [(r.value, r.value) for r in ruoli if r.value != "SUPERADMIN"]


def _azioni_utente(slug: str, utente: Any) -> list[dict[str, Any]]:
    nome = _t(utente.username)
    parametri = {"slug": slug, "uid": utente.id}
    return [
        azione(
            "reset-password",
            "Reimposta password",
            params=parametri,
            fields=[campo("nuova_password", f"Nuova password per {nome}", "password", required=True, help="Password temporanea: al prossimo accesso l'utente dovrà cambiarla.")],
        ),
        azione(
            "attiva-disattiva",
            "Disattiva" if utente.attivo else "Attiva",
            tone="warning" if utente.attivo else "success",
            params=parametri,
            confirm=f"{'Disattivare' if utente.attivo else 'Riattivare'} l'utente {nome}?",
        ),
        azione("elimina", "Elimina", tone="danger", params=parametri, confirm=f"Eliminare l'utente {nome}? Azione irreversibile."),
    ]


def _riga(slug: str, utente: Any) -> dict[str, Any]:
    nome = _t(utente.username)
    return {
        "user": f"{nome} — {_t(utente.nome_completo)}" if _t(utente.nome_completo) else nome,
        "email": _t(utente.email) or "—",
        "role": ruolo(utente),
        "state": ("Attivo" if utente.attivo else "Inattivo") + (" · verifica in due passaggi attiva" if getattr(utente, "totp_attivato", False) else ""),
        "created": data(utente.creato_il) or "—",
        "last": data(utente.ultimo_accesso) or "Mai",
        "_tone": "" if utente.attivo else "warning",
        "_actions": _azioni_utente(slug, utente),
    }


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    studio = payload.get("studio")
    if studio is None:
        return pagina_studio_assente(_t(payload.get("slug")), "Utenti dello studio")
    slug = _t(payload.get("slug"))
    utenti = list(payload.get("utenti") or [])
    ruoli = list(payload.get("ruoli") or [])
    descrizioni = payload.get("descrizioni_ruoli") or {}
    limite = studio.limite_utenti
    ruoli_studio = _ruoli_studio(ruoli)
    return {
        "title": f"Utenti di {_t(studio.nome)}",
        "subtitle": f"{len(utenti)} {'utente' if len(utenti) == 1 else 'utenti'}" + (f" su {limite} ammessi dal piano {nome_piano(studio.piano)}." if limite > 0 else "."),
        "links": collegamenti_studio(slug, attuale="studio-utenti"),
        "sections": [
            metrics([
                {"label": "Utenti dello studio", "value": len(utenti)},
                {"label": "Limite del piano", "value": limite if limite > 0 else "Illimitati", "tone": "warning" if 0 < limite <= len(utenti) else "neutral"},
                {"label": "Attivi", "value": sum(1 for u in utenti if u.attivo), "tone": "success"},
            ]),
            notes("Regola di piattaforma", [REGOLA], tone="info"),
            form(
                "Nuovo utente",
                "nuovo",
                [
                    campo("username", "Nome utente", required=True),
                    campo("password", "Password", "password", required=True, help="Password iniziale da comunicare all'utente."),
                    campo("nome_completo", "Nome completo"),
                    campo("email", "Email", "email"),
                    campo("ruolo", "Ruolo", "select", value=ruoli_studio[0][0] if ruoli_studio else "", options=ruoli_studio),
                ],
                submit_label="Crea utente",
                params={"slug": slug},
            ),
            table(
                "Utenti",
                [("user", "Utente"), ("email", "Email"), ("role", "Ruolo"), ("state", "Stato"), ("created", "Creato il"), ("last", "Ultimo accesso")],
                [_riga(slug, u) for u in utenti],
                empty="Nessun utente ancora: crea il primo con il modulo «Nuovo utente».",
            ),
            status(
                "Ruoli disponibili",
                [{"title": r.value, "summary": _t((descrizioni.get(r) or {}).get("descrizione")), "status": "info", "statusLabel": r.value} for r in ruoli if r.value != "SUPERADMIN"],
            ),
        ],
    }


# ------------------------------------------------------------------ azioni


def _nuovo(slug: str, studio: Any, values: dict[str, Any]) -> dict[str, Any]:
    """Stessi controlli e stesso ordine della rotta storica `crea_utente`."""
    from pct.auth import RuoloUtente
    from web.blueprints.admin import _sync_tenant_user_directory, _utente_del_tenant, _utenti_tenant

    gu = _utenti_tenant(slug)
    utenti_esistenti = [u for u in gu.lista() if _utente_del_tenant(u, slug)]
    limite = studio.limite_utenti
    if limite > 0 and len(utenti_esistenti) >= limite:
        return esito(False, f"Limite utenti raggiunto ({limite}) per il piano {studio.piano}.")

    username = testo(values, "username")
    password = testo(values, "password")
    nome_completo = testo(values, "nome_completo")
    email = testo(values, "email")
    ruolo_str = valore(values, "ruolo", "SEGRETERIA")
    if not username or not password:
        return esito(False, "Nome utente e password sono obbligatori.")
    try:
        ruolo_scelto = RuoloUtente(ruolo_str)
        if ruolo_scelto == RuoloUtente.SUPERADMIN:
            ruolo_scelto = RuoloUtente.AMMINISTRATORE  # Nessun superamministratore dentro uno studio.
    except ValueError:
        ruolo_scelto = RuoloUtente.SEGRETERIA
    try:
        gu.crea(username=username, password=password, ruolo=ruolo_scelto, nome_completo=nome_completo, email=email, tenant_slug=slug)
    except ValueError as exc:
        return esito(False, f"Errore: {exc}")
    _sync_tenant_user_directory()
    return esito(True, f"Utente '{username}' creato.")


def _utente_dello_studio(gu: Any, slug: str, uid: str):
    from web.blueprints.admin import _utente_del_tenant

    utente = gu.get(uid) if uid else None
    return utente if utente and _utente_del_tenant(utente, slug) else None


def _reset_password(slug: str, studio: Any, values: dict[str, Any]) -> dict[str, Any]:
    from web.blueprints.admin import _sync_tenant_user_directory, _utenti_tenant

    gu = _utenti_tenant(slug)
    nuova_password = testo(values, "nuova_password")
    if not nuova_password:
        return esito(False, "La nuova password non può essere vuota.")
    utente = _utente_dello_studio(gu, slug, testo(values, "uid"))
    if utente is None:
        return esito(False, "Utente non trovato in questo studio.")
    gu.cambia_password(utente.id, nuova_password, must_change_password=True)
    _sync_tenant_user_directory()
    return esito(True, f"Password temporanea di '{utente.username}' aggiornata. Al prossimo accesso dovrà cambiarla.")


def _attiva_disattiva(slug: str, studio: Any, values: dict[str, Any]) -> dict[str, Any]:
    from web.blueprints.admin import _sync_tenant_user_directory, _utenti_tenant

    gu = _utenti_tenant(slug)
    utente = _utente_dello_studio(gu, slug, testo(values, "uid"))
    if utente is None:
        return esito(False, "Utente non trovato in questo studio.")
    # Lo stato si legge prima dell'aggiornamento: `gu.aggiorna` modifica lo stesso oggetto
    # e la vista storica, leggendolo dopo, annunciava l'esito opposto.
    stato = "attivato" if not utente.attivo else "disattivato"
    gu.aggiorna(utente.id, attivo=not utente.attivo)
    _sync_tenant_user_directory()
    return esito(True, f"Utente '{utente.username}' {stato}.", tone="info")


def _elimina(slug: str, studio: Any, values: dict[str, Any]) -> dict[str, Any]:
    from web.blueprints.admin import _sync_tenant_user_directory, _utenti_tenant

    gu = _utenti_tenant(slug)
    utente = _utente_dello_studio(gu, slug, testo(values, "uid"))
    if utente is None:
        return esito(False, "Utente non trovato in questo studio.")
    try:
        gu.elimina(utente.id)
    except ValueError as exc:
        # Es. «Impossibile eliminare l'unico amministratore»: la vista storica rispondeva con un errore interno.
        return esito(False, str(exc))
    _sync_tenant_user_directory()
    return esito(True, f"Utente '{utente.username}' eliminato.", tone="warning")


AZIONI = {"nuovo": _nuovo, "reset-password": _reset_password, "attiva-disattiva": _attiva_disattiva, "elimina": _elimina}


def esegui(nome_azione: str, params: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    gestore = AZIONI.get(str(nome_azione or "").strip())
    if gestore is None:
        return esito(False, "Azione non disponibile in questa pagina.")
    slug = slug_di(params)
    # L'identificativo dell'utente è un parametro fisso della riga, come nell'indirizzo storico.
    valori = {**dict(values or {}), "uid": str((params or {}).get("uid") or "")}
    try:
        studio = gestore_studi().get(slug) if slug else None
        if not studio:
            return studio_non_trovato()
        return gestore(slug, studio, valori)
    except Exception:
        return errore_imprevisto("Errore azione %s sugli utenti dello studio %s dal pannello React", nome_azione, slug)


__all__ = ["adatta", "costruisci", "esegui"]
