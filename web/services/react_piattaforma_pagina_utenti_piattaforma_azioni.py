"""Azioni della pagina «Utenti di piattaforma» del pannello di piattaforma (React).

Replicano gli invii storici di `/admin/utenti-piattaforma` (`web/blueprints/admin.py`):
`genera-superadmin`, `<uid>/reset-password`, `<uid>/modifica`,
`<uid>/trasferisci-superadmin` e `<uid>/sposta-nello-studio`, con gli stessi metodi
di `GestioneUtenti`, gli stessi eventi di audit e la stessa chiusura della
sessione (con ritorno alla pagina di accesso) dopo il passaggio del ruolo SUPERADMIN.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_sezioni import esito
from web.services.react_piattaforma_studi_comune import (
    con_navigazione,
    gestore_studi,
    indirizzo_ip,
    spuntato,
    testo,
    utente_corrente,
    valore,
)

#: Nome del campo «studio di destinazione» (il valore corrisponde a `tenant_slug` della rotta storica).
CAMPO_STUDIO = "studio_destinazione"


def _log(messaggio: str, *argomenti: Any) -> None:
    from flask import current_app

    current_app.logger.exception(messaggio, *argomenti)


def _ruolo_da(values: dict[str, Any], nome: str, predefinito: str):
    from pct.auth import RuoloUtente

    return RuoloUtente(str(valore(values, nome, predefinito) or "").strip().upper())


def _account_globale(gu: Any, uid: str):
    utente = gu.get(uid) if uid else None
    return None if not utente or str(getattr(utente, "tenant_slug", "") or "").strip() else utente


def _alla_pagina_di_accesso(messaggio: str) -> dict[str, Any]:
    from flask import session, url_for

    session.clear()
    return con_navigazione(esito(True, messaggio), url_for("login"))


def _genera(uid: str, values: dict[str, Any]) -> dict[str, Any]:
    from web.blueprints.admin import _superadmin_corrente_piattaforma, _sync_tenant_user_directory, _utenti_piattaforma

    gu = _utenti_piattaforma()
    corrente = _superadmin_corrente_piattaforma(gu)
    corrente_id = corrente.id if corrente else ""
    try:
        ruolo_precedente = _ruolo_da(values, "ruolo_superadmin_precedente", "AMMINISTRATORE")
    except ValueError:
        return esito(False, "Ruolo del SUPERADMIN uscente non valido.")
    try:
        nuovo = gu.genera_superadmin_piattaforma(
            username=testo(values, "username").lower(),
            password=testo(values, "password"),
            email=testo(values, "email"),
            nome_completo=testo(values, "nome_completo"),
            must_change_password=True,
            ruolo_superadmin_precedente=ruolo_precedente,
        )
        gu.registra_evento(
            azione="piattaforma.superadmin.generato",
            id_utente=nuovo.id,
            username=nuovo.username,
            risorsa_tipo="utente_piattaforma",
            risorsa_id=nuovo.id,
            dettagli=f"Generato o riallineato account SUPERADMIN dalla piattaforma con ruolo precedente assegnato a {ruolo_precedente.value}.",
            ip=indirizzo_ip(),
            esito="OK",
        )
        _sync_tenant_user_directory()
    except ValueError as exc:
        _log("Errore generazione superadmin piattaforma")
        return esito(False, f"Errore durante la generazione del SUPERADMIN: {exc}")
    except Exception:
        _log("Errore generazione superadmin piattaforma")
        return esito(False, "Errore durante la generazione del SUPERADMIN. Il dettaglio tecnico è nei log del server.")
    if corrente_id and nuovo.id != corrente_id:
        return _alla_pagina_di_accesso("Il ruolo SUPERADMIN è stato trasferito al nuovo account di piattaforma. Accedi di nuovo con le nuove credenziali per continuare.")
    return esito(True, f"Account di piattaforma '{nuovo.username}' riallineato come SUPERADMIN.")


def _reset_password(uid: str, values: dict[str, Any]) -> dict[str, Any]:
    from web.blueprints.admin import _utenti_piattaforma

    gu = _utenti_piattaforma()
    nuova_password = testo(values, "nuova_password")
    if not nuova_password:
        return esito(False, "La nuova password non può essere vuota.")
    utente = _account_globale(gu, uid)
    if utente is None:
        return esito(False, "Account di piattaforma non trovato.")
    gu.cambia_password(uid, nuova_password, must_change_password=True)
    return esito(True, f"Password temporanea dell'account di piattaforma '{utente.username}' aggiornata. Al prossimo accesso dovrà cambiarla.")


def _modifica(uid: str, values: dict[str, Any]) -> dict[str, Any]:
    from pct.auth import RuoloUtente
    from web.blueprints.admin import _sync_tenant_user_directory, _utenti_piattaforma

    gu = _utenti_piattaforma()
    utente = _account_globale(gu, uid)
    if utente is None:
        return esito(False, "Account di piattaforma non trovato.")
    attivo = spuntato(values, "attivo")
    if utente.ruolo == RuoloUtente.SUPERADMIN and not attivo:
        return esito(False, "Il SUPERADMIN di piattaforma non può essere disattivato da qui. Trasferisci prima il ruolo a un altro account globale.")
    try:
        aggiornato = gu.aggiorna(
            uid,
            nome_completo=testo(values, "nome_completo"),
            email=testo(values, "email"),
            attivo=(True if utente.ruolo == RuoloUtente.SUPERADMIN else attivo),
        )
        gu.registra_evento(
            azione="piattaforma.utente.modificato",
            id_utente=aggiornato.id,
            username=aggiornato.username,
            risorsa_tipo="utente_piattaforma",
            risorsa_id=aggiornato.id,
            dettagli="Account piattaforma aggiornato dal pannello superadmin.",
            ip=indirizzo_ip(),
            esito="OK",
        )
        _sync_tenant_user_directory()
    except ValueError as exc:
        _log("Errore modifica account piattaforma %s", uid)
        return esito(False, f"Errore durante la modifica dell'account di piattaforma: {exc}")
    return esito(True, f"Account di piattaforma '{aggiornato.username}' aggiornato correttamente.")


def _trasferisci(uid: str, values: dict[str, Any]) -> dict[str, Any]:
    from web.blueprints.admin import _superadmin_corrente_piattaforma, _sync_tenant_user_directory, _utenti_piattaforma

    gu = _utenti_piattaforma()
    destinazione = _account_globale(gu, uid)
    if destinazione is None:
        return esito(False, "Account di piattaforma non trovato.")
    sorgente = _superadmin_corrente_piattaforma(gu)
    if not sorgente:
        return esito(False, "Nessun SUPERADMIN globale attivo trovato in piattaforma.")
    try:
        ruolo_precedente = _ruolo_da(values, "ruolo_superadmin_precedente", "AMMINISTRATORE")
    except ValueError:
        return esito(False, "Ruolo dell'account SUPERADMIN uscente non valido.")
    try:
        nuovo = gu.trasferisci_superadmin_piattaforma(source_id=sorgente.id, target_id=destinazione.id, ruolo_sorgente=ruolo_precedente)
        gu.registra_evento(
            azione="piattaforma.superadmin.trasferito",
            id_utente=nuovo.id,
            username=nuovo.username,
            risorsa_tipo="utente_piattaforma",
            risorsa_id=nuovo.id,
            dettagli=f"Ruolo SUPERADMIN trasferito da {sorgente.username} a {nuovo.username}. Il ruolo precedente e' diventato {ruolo_precedente.value}.",
            ip=indirizzo_ip(),
            esito="OK",
        )
        _sync_tenant_user_directory()
    except ValueError as exc:
        _log("Errore trasferimento ruolo SUPERADMIN a %s", uid)
        return esito(False, f"Errore durante il trasferimento del ruolo SUPERADMIN: {exc}")
    if getattr(utente_corrente(), "id", "") == sorgente.id:
        return _alla_pagina_di_accesso("Il ruolo SUPERADMIN è stato trasferito a un altro account di piattaforma. Accedi di nuovo con il nuovo account SUPERADMIN per continuare.")
    return esito(True, f"Il ruolo SUPERADMIN ora appartiene all'account di piattaforma '{nuovo.username}'.")


def _sposta(uid: str, values: dict[str, Any]) -> dict[str, Any]:
    from pct.auth import RuoloUtente
    from web.blueprints.admin import _sync_tenant_user_directory, _utenti_piattaforma, _utenti_tenant

    # Il campo storico `tenant_slug` è una chiave riservata al server nelle richieste JSON
    # (`backend_security.UNSAFE_BACKEND_CONTROL_KEYS`): il modulo React usa un nome proprio.
    tenant_slug = testo(values, CAMPO_STUDIO).lower()
    if not tenant_slug:
        return esito(False, "Seleziona lo studio di destinazione.")
    try:
        ruolo_destinazione = _ruolo_da(values, "ruolo", RuoloUtente.AVVOCATO.value)
    except ValueError:
        return esito(False, "Ruolo di studio non valido.")
    if ruolo_destinazione == RuoloUtente.SUPERADMIN:
        return esito(False, "Il ruolo SUPERADMIN non può essere assegnato dentro uno studio.")
    studio = gestore_studi().get(tenant_slug)
    if not studio:
        return esito(False, "Studio di destinazione non trovato.")
    gu_piattaforma = _utenti_piattaforma()
    utente = _account_globale(gu_piattaforma, uid)
    if utente is None:
        return esito(False, "Account di piattaforma non trovato.")
    if utente.ruolo == RuoloUtente.SUPERADMIN:
        return esito(False, "Non puoi spostare fuori dalla piattaforma l'unico SUPERADMIN. Trasferisci prima il ruolo a un altro account.")
    gu_tenant = _utenti_tenant(tenant_slug)
    if gu_tenant.get_by_username(utente.username):
        return esito(False, f"Nello studio '{studio.nome}' esiste già un utente con nome utente '{utente.username}'.")

    importato = None
    try:
        importato = gu_tenant.importa_utente_esistente(utente, ruolo=ruolo_destinazione, tenant_slug=tenant_slug, preserve_id=False)
        gu_tenant.registra_evento(
            azione="tenant.utente.importato_da_piattaforma",
            id_utente=importato.id,
            username=importato.username,
            risorsa_tipo="utente",
            risorsa_id=importato.id,
            dettagli=f"Utente importato dalla piattaforma nello studio {tenant_slug} con ruolo {ruolo_destinazione.value}.",
            ip=indirizzo_ip(),
            esito="OK",
        )
        gu_piattaforma.elimina(uid, force=True)
        gu_piattaforma.registra_evento(
            azione="piattaforma.utente.spostato_nello_studio",
            id_utente=uid,
            username=utente.username,
            risorsa_tipo="utente_piattaforma",
            risorsa_id=uid,
            dettagli=f"Account globale spostato nello studio {tenant_slug} come {ruolo_destinazione.value}.",
            ip=indirizzo_ip(),
            esito="OK",
        )
        _sync_tenant_user_directory()
    except Exception:
        _log("Errore spostamento utente piattaforma %s nello studio %s", uid, tenant_slug)
        if importato is not None:
            try:
                gu_tenant.elimina(importato.id, force=True)
            except Exception:
                _log("Rollback import utente piattaforma %s fallito nello studio %s", uid, tenant_slug)
        return esito(False, "Errore durante lo spostamento nello studio. Il dettaglio tecnico è nei log del server.")
    return esito(True, f"L'account di piattaforma '{utente.username}' ora appartiene allo studio '{studio.nome}' come {ruolo_destinazione.value}.")


AZIONI = {
    "genera-superadmin": _genera,
    "reset-password": _reset_password,
    "modifica": _modifica,
    "trasferisci-superadmin": _trasferisci,
    "sposta-nello-studio": _sposta,
}


def esegui(nome_azione: str, params: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    gestore = AZIONI.get(str(nome_azione or "").strip())
    if gestore is None:
        return esito(False, "Azione non disponibile in questa pagina.")
    uid = str((params or {}).get("uid") or "").strip()
    try:
        return gestore(uid, dict(values or {}))
    except Exception:
        _log("Errore azione %s sugli account di piattaforma dal pannello React", nome_azione)
        return esito(False, "Operazione non completata. Il dettaglio tecnico è nei log del server.")


__all__ = ["AZIONI", "CAMPO_STUDIO", "esegui"]
