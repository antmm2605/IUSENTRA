"""Passaggi spiegabili e regole dello studio dentro l'applicazione Flask.

Qui il dominio ``pct/passaggi`` incontra lo studio corrente: il database delle
regole accanto al registro delle letture (stesso tenant, stesso DSN
PostgreSQL se configurato), i dati del fascicolo letti dagli stessi gestori
della Lettura, l'utente che corregge. Le GET consultano e registrano solo la
prima applicazione di una regola a un caso (audit); nessuna lettura di
documenti o PEC avviene qui: i termini PEC arrivano già estratti dal presidio.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from flask import current_app, g, has_app_context, has_request_context

from pct.passaggi import CorrezioneRifiutata, Passaggio, applica_regole, regola_da_correzione
from pct.passaggi.fascicolo import passaggi_del_fascicolo
from pct.passaggi.repository import RegoleStudioError, RegoleStudioRepository

ROME_TZ = ZoneInfo("Europe/Rome")
CHIAVE_PERCORSO = "REGOLE_STUDIO_DB"
logger = logging.getLogger(__name__)


def oggi_roma() -> date:
    return datetime.now(ROME_TZ).date()


def percorso_regole(paths: Mapping[str, Any] | None = None) -> str:
    mappa = dict(paths or {})
    if not mappa and has_request_context():
        mappa = dict(getattr(g, "data_paths", {}) or {})
    if not mappa and has_app_context():
        mappa = {CHIAVE_PERCORSO: current_app.config.get(CHIAVE_PERCORSO, ""), "FASCICOLI_DB": current_app.config.get("FASCICOLI_DB", "")}
    esplicito = str(mappa.get(CHIAVE_PERCORSO) or "").strip()
    if esplicito:
        return esplicito
    fascicoli = str(mappa.get("FASCICOLI_DB") or "./data/fascicoli/fascicoli.json").strip()
    return str(Path(fascicoli).resolve().parent.parent / "intelligence" / "regole_studio.db")


def _dsn() -> str:
    try:
        from pct.postgres_runtime_support import resolve_runtime_postgres_dsn

        return resolve_runtime_postgres_dsn(env_url_keys=("IUSENTRA_REGOLE_STUDIO_DSN",))
    except Exception:
        return ""


def tenant_corrente() -> str:
    from web.services.registro_letture_runtime import tenant_corrente as tenant

    return tenant()


def repository_corrente() -> RegoleStudioRepository:
    return RegoleStudioRepository(percorso_regole(), tenant_id=tenant_corrente(), postgres_dsn=_dsn())


def utente_corrente() -> tuple[str, str]:
    utente = g.get("utente_corrente") if has_request_context() else None
    identificativo = str(getattr(utente, "id", "") or getattr(utente, "username", "") or "").strip()
    nome = str(getattr(utente, "nome_completo", "") or getattr(utente, "username", "") or identificativo).strip()
    return identificativo or "api-key", nome or "accesso tramite chiave API"


def _scadenza(voce: Any) -> dict[str, Any]:
    valore = lambda nome: getattr(getattr(voce, nome, ""), "value", getattr(voce, nome, ""))  # noqa: E731
    return {nome: str(valore(nome) or "") for nome in (
        "id", "titolo", "descrizione", "stato", "note", "id_fascicolo", "deadline_profile_code", "operational_due_at", "data_scadenza",
    )} | {"data": str(getattr(voce, "data_scadenza", "") or getattr(voce, "data", "") or "")}


def dati_del_fascicolo(fascicolo_id: str) -> dict[str, Any] | None:
    """Fascicolo, scadenze e termini proposti dal presidio PEC, dagli stessi gestori della Lettura (tenant della richiesta)."""
    from lex.context.fascicolo_lettura_context import _fascicolo_dict
    from pct.fascicolo_lettura.pec import pec
    from web.helpers import get_fascicoli, get_scadenziario
    from web.services.fascicolo_pec_presidio import messaggi_pec_per_fascicolo

    fascicolo = get_fascicoli().get(str(fascicolo_id or "").strip())
    if fascicolo is None:
        return None
    try:
        scadenze = [_scadenza(voce) for voce in get_scadenziario().tutte(id_fascicolo=str(fascicolo.id), solo_aperte=False)]
    except Exception as exc:
        logger.warning("Scadenze del fascicolo %s non disponibili per i passaggi: %s", fascicolo_id, exc)
        scadenze = []
    try:
        termini = pec(messaggi_pec_per_fascicolo(fascicolo, solo_collegate=True)).get("termini_da_registrare") or []
    except Exception as exc:
        logger.warning("Termini PEC del fascicolo %s non disponibili per i passaggi: %s", fascicolo_id, exc)
        termini = []
    return {"fascicolo": _fascicolo_dict(fascicolo), "scadenze": scadenze, "termini_pec": termini}


def passaggi_software(dati: dict[str, Any], *, oggi: date | None = None) -> list[Passaggio]:
    return passaggi_del_fascicolo(dati["fascicolo"], scadenze=dati["scadenze"], termini_pec=dati["termini_pec"], oggi=oggi or oggi_roma())


def passaggi_con_regole(dati: dict[str, Any], *, repository: RegoleStudioRepository, oggi: date | None = None) -> list[Passaggio]:
    """I passaggi del software corretti dalle regole dello studio; la prima applicazione a ogni caso va nel diario."""
    passaggi = passaggi_software(dati, oggi=oggi)
    regole = repository.attive_per({passaggio.regola_id for passaggio in passaggi})
    corretti, applicazioni = applica_regole(passaggi, regole)
    try:
        repository.registra_applicazioni(applicazioni)
    except Exception as exc:  # la vista resta corretta anche se il diario non si scrive
        logger.warning("Applicazioni delle regole dello studio non registrate: %s", exc)
    return corretti


def payload_passaggi(fascicolo_id: str) -> dict[str, Any] | None:
    dati = dati_del_fascicolo(fascicolo_id)
    if dati is None:
        return None
    passaggi = passaggi_con_regole(dati, repository=repository_corrente())
    return {"passaggi": [passaggio.come_dizionario() for passaggio in passaggi], "totale": len(passaggi)}


def correggi_passaggio(fascicolo_id: str, chiave: str, richiesta: Mapping[str, Any]) -> dict[str, Any]:
    """La correzione dell'avvocato diventa regola dello studio; il passaggio lo ricalcola il server."""
    dati = dati_del_fascicolo(fascicolo_id)
    if dati is None:
        raise LookupError("Fascicolo non trovato.")
    passaggio = next((voce for voce in passaggi_software(dati) if voce.chiave == chiave), None)
    if passaggio is None:
        raise RegoleStudioError("Il passaggio non è più attuale: aggiorna la vista e riprova.")
    autore_id, autore_nome = utente_corrente()
    repository = repository_corrente()
    try:
        regola = regola_da_correzione(
            passaggio, azione=str(richiesta.get("azione") or ""), ambito=str(richiesta.get("ambito") or ""),
            autore_id=autore_id, autore_nome=autore_nome, campo=str(richiesta.get("campo") or ""),
            valore=str(richiesta.get("valore") or ""), motivo=str(richiesta.get("motivo") or ""),
            materia=str(richiesta.get("materia") or ""),
        )
    except CorrezioneRifiutata as rifiuto:
        repository.registra_rifiuto(rifiuto.regola, rifiuto.rifiuto.motivo)
        raise
    except ValueError as errore:
        raise RegoleStudioError(str(errore)) from errore
    return repository.crea(regola).come_dizionario()


def elenco_regole() -> list[dict[str, Any]]:
    repository = repository_corrente()
    return [{**regola.come_dizionario(), "applicazioni": len(repository.applicazioni(regola.id))} for regola in repository.elenco()]


def aggiorna_regola(regola_studio_id: str, richiesta: Mapping[str, Any]) -> dict[str, Any]:
    autore_id, _nome = utente_corrente()
    attiva = richiesta.get("attiva")
    return repository_corrente().aggiorna(
        regola_studio_id, autore_id=autore_id,
        valore=str(richiesta["valore"]) if "valore" in richiesta else None,
        motivo=str(richiesta["motivo"]) if "motivo" in richiesta else None,
        attiva=bool(attiva) if isinstance(attiva, bool) else None,
    ).come_dizionario()


def diario_regola(regola_studio_id: str) -> dict[str, Any]:
    repository = repository_corrente()
    regola = repository.leggi(regola_studio_id)
    return {"regola": regola.come_dizionario(), "eventi": repository.eventi(regola.id), "applicazioni": repository.applicazioni(regola.id)}


__all__ = [
    "aggiorna_regola", "correggi_passaggio", "dati_del_fascicolo", "diario_regola", "elenco_regole", "passaggi_con_regole",
    "passaggi_software", "payload_passaggi", "percorso_regole", "repository_corrente",
]
