"""Azioni della pagina React «Assistenza remota» del pannello di piattaforma.

Ogni azione ripete i passi del gestore storico di
`web/blueprints/support_remote.py` con gli stessi servizi, gli stessi eventi
(`log_support_event`), le stesse voci di audit (`audit_support_action`) e gli
stessi messaggi; il tipo del messaggio flash diventa il tono dell'esito:

- `configurazione` → `save_support_config`;
- `stato` → `change_console_status` (stati ammessi `SUPPORT_SESSION_STATUSES`);
- `cancella` → `delete_from_console`; `cancella-prove` → `delete_test_sessions_from_console`;
- `chiudi` → `close_from_console` (come il gestore storico, senza voce di audit);
- `note` → `note_api` con ruolo operatore (pulsante «Salva note» dello script);
- `crea-sessione` → `create_session_api` (modulo manuale dello script);
- `prova-notifica` → `support_push_test`;
- `filtra` → ricarica la pagina con `q` e `stato`, come il modulo GET storico.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from flask import current_app
from werkzeug.exceptions import HTTPException

from web.services.react_piattaforma_sezioni import _t, esito, facts, table

INDIRIZZO = "/admin/supporto-remoto"
MESSAGGIO_GENERICO = "Operazione non completata. Il dettaglio tecnico è nei log del server."
AZIONI = {"filtra", "configurazione", "stato", "cancella", "cancella-prove", "chiudi", "note", "crea-sessione", "prova-notifica"}


def _operatore() -> dict[str, str]:
    from web.services.support_runtime import support_operator_identity_or_403

    return support_operator_identity_or_403()


def _repo():
    from web.services.support_runtime import support_repository

    return support_repository()


def _adesso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _valore(values: dict[str, Any], nome: str) -> str:
    return str(values.get(nome) or "").strip()


# ------------------------------------------------------------------ sessioni


def _filtra(values: dict[str, Any]) -> dict[str, Any]:
    parametri = {k: _valore(values, k) for k in ("q", "stato") if _valore(values, k)}
    return esito(True, "Filtri applicati.", tone="info", navigate=f"{INDIRIZZO}?{urlencode(parametri)}" if parametri else INDIRIZZO)


def _stato(public_id: str, values: dict[str, Any]) -> dict[str, Any]:
    from web.blueprints.support_remote import SUPPORT_SESSION_STATUSES
    from web.services.support_runtime import audit_support_action, log_support_event

    operatore = _operatore()
    prossimo = _valore(values, "status")
    if prossimo not in SUPPORT_SESSION_STATUSES:
        return esito(False, "Stato assistenza non valido.")
    repo = _repo()
    if repo.get_session_by_public_id(public_id) is None:
        return esito(False, "Sessione assistenza non trovata.")
    repo.update_session(public_id, status=prossimo)
    log_support_event(public_id, event_type="status_changed", actor_role="operator", actor_name=operatore["name"], payload={"status": prossimo})
    audit_support_action(
        "supporto_remoto.cambia_stato",
        public_id=public_id,
        details=f"{operatore['name']} ha impostato lo stato assistenza a {prossimo}.",
    )
    return esito(True, "Stato assistenza aggiornato.")


def _cancella(public_id: str) -> dict[str, Any]:
    from web.services.support_runtime import audit_support_action

    operatore = _operatore()
    repo = _repo()
    if repo.get_session_by_public_id(public_id) is None:
        return esito(False, "Sessione assistenza non trovata.")
    cancellata = repo.delete_session(public_id)
    audit_support_action(
        "supporto_remoto.cancella_sessione",
        public_id=public_id,
        details=f"{operatore['name']} ha cancellato la sessione assistenza {public_id}.",
    )
    if cancellata:
        return esito(True, "Sessione assistenza cancellata.")
    return esito(False, "Sessione assistenza non cancellata.", tone="warning")


def _cancella_prove() -> dict[str, Any]:
    from web.services.support_runtime import audit_support_action

    operatore = _operatore()
    cancellate = _repo().delete_test_sessions()
    audit_support_action(
        "supporto_remoto.cancella_prove",
        details=f"{operatore['name']} ha cancellato {cancellate} sessioni di prova assistenza remota.",
    )
    return esito(True, f"Sessioni di prova cancellate: {cancellate}.")


def _chiudi(public_id: str) -> dict[str, Any]:
    from web.services.support_runtime import log_support_event

    operatore = _operatore()
    aggiornata = _repo().update_session(public_id, status="closed", ended_at=_adesso())
    if aggiornata is None:
        return esito(False, "Sessione non trovata.", tone="warning")
    log_support_event(public_id, event_type="session_closed", actor_role="operator", actor_name=operatore["name"])
    return esito(True, "Sessione di assistenza chiusa.")


def _note(public_id: str, values: dict[str, Any]) -> dict[str, Any]:
    """Come `note_api` con `role=operator` e senza gettone: l'operatore è il superamministratore collegato."""
    from web.services.support_runtime import log_support_event

    repo = _repo()
    if repo.get_session_by_public_id(public_id) is None:
        return esito(False, "Sessione assistenza non trovata.")
    operatore = _operatore()
    nota = _valore(values, "notes")
    if repo.update_session(public_id, notes=nota) is None:
        return esito(False, "Sessione assistenza non trovata.")
    log_support_event(public_id, event_type="note_updated", actor_role="operator", actor_name=operatore["name"], payload={"has_notes": bool(nota)})
    return esito(True, "Note sessione salvate correttamente.")


def _crea_sessione(values: dict[str, Any]) -> dict[str, Any]:
    """Stessi passi di `create_session_api` (POST /support/api/session)."""
    from flask import g, url_for

    from pct.support_remote import build_support_event_story, issue_operator_token
    from web.services.support_runtime import audit_support_action, log_support_event

    operatore = _operatore()
    studio_richiesta = getattr(g, "tenant", None)
    studio_slug = str(values.get("studio_slug") or getattr(studio_richiesta, "slug", "") or "").strip().lower()
    studio_nome = str(values.get("studio_nome") or getattr(studio_richiesta, "nome", "") or "").strip()
    riga = _repo().create_session({
        "studio_slug": studio_slug,
        "studio_nome": studio_nome,
        "practice_id": _valore(values, "practice_id"),
        "practice_label": _valore(values, "practice_label"),
        "client_id": _valore(values, "client_id"),
        "customer_name": _valore(values, "customer_name"),
        "customer_email": _valore(values, "customer_email"),
        "created_by": operatore["name"],
        "assigned_to": str(values.get("assigned_to") or operatore["name"]).strip(),
        "notes": _valore(values, "notes"),
        "status": "created",
    })
    log_support_event(
        riga["public_id"],
        event_type="session_created",
        actor_role="operator",
        actor_name=operatore["name"],
        payload={
            "customer_name": riga["customer_name"],
            "customer_email": riga["customer_email"],
            "studio_nome": riga["studio_nome"],
            "practice_label": riga["practice_label"],
        },
    )
    audit_support_action(
        "supporto_remoto.crea_sessione",
        public_id=riga["public_id"],
        details=build_support_event_story(
            "session_created",
            actor_role="operator",
            actor_name=operatore["name"],
            payload={"customer_name": riga["customer_name"], "studio_nome": riga["studio_nome"], "practice_label": riga["practice_label"]},
        ),
    )
    gettone = issue_operator_token(riga["public_id"], operatore["name"], operatore["id"])
    stanza_operatore = url_for("support_remote.operator_room", public_id=riga["public_id"], token=gettone, _external=True)
    link_cliente = url_for("support_remote.customer_room", token=riga["client_token"], _external=True)
    sezioni = [
        table(
            "Collegamenti della nuova sessione",
            [("link", "Collegamento"), ("detail", "Uso")],
            [
                {"link": "Apri stanza operatore", "detail": "Link firmato per l'operatore: si apre in una nuova scheda.", "_href": stanza_operatore, "_external": True},
                {"link": "Link cliente", "detail": "Da inviare al cliente: apre la stanza cliente.", "_href": link_cliente, "_external": True},
                {"link": "Apri sessione in cabina", "detail": "Dettaglio e audit in questa pagina.", "_href": f"{INDIRIZZO}?{urlencode({'sessione': riga['public_id']})}"},
            ],
        ),
        facts("Link cliente da copiare", [("Link cliente", link_cliente), ("Cliente", riga.get("customer_name")), ("Sessione", riga["public_id"])]),
    ]
    return esito(True, "Sessione creata. Apri la stanza operatore e invia al cliente il link qui sotto.", sections=sezioni)


# ------------------------------------------------------------------ presidio


def _configurazione(values: dict[str, Any]) -> dict[str, Any]:
    """`save_support_configuration` riceve i campi come `request.form.to_dict()`:
    la chiave del relay vuota conserva quella salvata."""
    from web.services.support_surface import save_support_configuration

    try:
        save_support_configuration(dict(values))
    except ValueError:
        return esito(False, "Configurazione assistenza remota non salvata: le durate devono essere numeri interi di secondi.")
    except Exception:
        current_app.logger.exception("Errore salvataggio configurazione assistenza remota dal pannello React")
        return esito(False, "Configurazione assistenza remota non salvata. Il dettaglio tecnico è nei log del server.")
    return esito(True, "Configurazione assistenza remota aggiornata.")


def _prova_notifica() -> dict[str, Any]:
    from pct.notifications import NotificationServiceError
    from web.services.support_runtime import send_platform_push_test

    try:
        risultato = send_platform_push_test()
    except NotificationServiceError as exc:
        current_app.logger.warning("Test notifiche dispositivo assistenza non completato: %s", exc)
        return esito(False, "Notifiche dispositivo non disponibili.")
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception("Test notifiche dispositivo assistenza non completato")
        return esito(False, "Notifica di test non completata.")
    return esito(True, _t(risultato.get("message")) or "Notifica di test inviata.", tone="success" if risultato.get("sent") else "info")


# ------------------------------------------------------------------ esecutore


def _esegui(chiave: str, public_id: str, values: dict[str, Any]) -> dict[str, Any]:
    if chiave == "filtra":
        return _filtra(values)
    if chiave == "configurazione":
        return _configurazione(values)
    if chiave == "cancella-prove":
        return _cancella_prove()
    if chiave == "crea-sessione":
        return _crea_sessione(values)
    if chiave == "prova-notifica":
        return _prova_notifica()
    if chiave in {"stato", "cancella", "chiudi", "note"} and not public_id:
        return esito(False, "Sessione assistenza non indicata.")
    if chiave == "stato":
        return _stato(public_id, values)
    if chiave == "cancella":
        return _cancella(public_id)
    if chiave == "chiudi":
        return _chiudi(public_id)
    if chiave == "note":
        return _note(public_id, values)
    return esito(False, "Azione non disponibile in questa pagina.")


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    public_id = str((params or {}).get("public_id") or "").strip()
    try:
        return _esegui(chiave, public_id, dict(values or {}))
    except HTTPException as exc:
        # `support_operator_identity_or_403` interrompe con 403: messaggio del servizio.
        return esito(False, _t(exc.description) or "Assistenza remota disponibile solo per il SUPERADMIN di piattaforma.")
    except Exception:
        current_app.logger.exception("Errore azione assistenza remota %s %s", chiave, public_id)
        return esito(False, MESSAGGIO_GENERICO)


__all__ = ["AZIONI", "esegui"]
