"""API React della sezione «Conoscenza»: schede di istituto per materia (lex/conoscenza).

Montato sotto ``/api/v1/ui/conoscenza``. Le schede sono conoscenza giuridica comune generata dalle fonti del software
(sola lettura); le annotazioni sono dello studio, nel suo SQL, con il nome di chi le scrive e nel registro attività.
Lettura: chi usa Lex o consulta i fascicoli. Annotazioni: chi può scrivere nei fascicoli.
"""
from __future__ import annotations

import sqlite3

from flask import Blueprint, current_app, g, jsonify, request

from web.blueprints.api_v1_react import _audit_event, _request_json_object, _richiedi_auth

api_v1_conoscenza = Blueprint("api_v1_conoscenza", __name__)


def _ha(permesso: str) -> bool:
    return bool(getattr(g.get("utente_corrente"), "ha_permesso", lambda _p: False)(permesso))


def _lettura_negata():
    if not (_ha("ai.usa") or _ha("fascicoli.leggi")):
        return jsonify(ok=False, message="Non hai il permesso per consultare le schede di istituto."), 403
    return None


def _nome_utente() -> str:
    u = g.get("utente_corrente")
    return str(getattr(u, "nome_completo", "") or getattr(u, "nome", "") or getattr(u, "username", "") or "").strip()


def _studio_db(scrittura: bool = False):
    from web.blueprints.api_v1_schede_fonti import _studio_db as studio_db

    return studio_db(scrittura)


def _non_disponibile():
    current_app.logger.exception("Schede di istituto non disponibili")
    return jsonify(ok=False, message="Le schede di istituto non sono disponibili in questo momento: riprova fra poco."), 503


@api_v1_conoscenza.get("")
@_richiedi_auth
def catalogo():
    negato = _lettura_negata()
    if negato is not None:
        return negato
    from lex.conoscenza import consultazione

    try:
        dati = consultazione.catalogo()
        # Lo stato mostrato è quello di oggi: una fonte cambiata dopo la generazione rende la scheda da riesaminare.
        for m in dati["materie"]:
            for v in m["schede"]:
                s = consultazione.scheda(v["id"])
                v["stato"] = consultazione.stato_attuale(s)["stato"] if s else v["stato"]
            m["conteggi"] = consultazione._conteggi(m["schede"])
        dati["conteggi"] = consultazione._conteggi([v for m in dati["materie"] for v in m["schede"]])
        return jsonify(ok=True, **dati, puo_annotare=_ha("fascicoli.scrivi"))
    except (OSError, ValueError, KeyError):
        return _non_disponibile()


@api_v1_conoscenza.get("/cerca")
@_richiedi_auth
def cerca():
    negato = _lettura_negata()
    if negato is not None:
        return negato
    from lex.conoscenza import consultazione

    q = str(request.args.get("q", "") or "")[:300]
    materia = str(request.args.get("materia", "") or "")[:120]
    try:
        risultati = consultazione.cerca(q, materia=materia, limite=50)
    except (OSError, ValueError, KeyError):
        return _non_disponibile()
    return jsonify(ok=True, q=q, risultati=risultati, modalita="ricerca testuale (senza embeddings)")


@api_v1_conoscenza.get("/schede/<scheda_id>")
@_richiedi_auth
def scheda(scheda_id: str):
    negato = _lettura_negata()
    if negato is not None:
        return negato
    from lex.conoscenza import annotazioni, consultazione

    s = consultazione.scheda(scheda_id)
    if s is None:
        return jsonify(ok=False, message="Scheda non trovata."), 404
    try:
        note = annotazioni.con_stato(annotazioni.Annotazioni(_studio_db()).elenco(scheda_id), s)
    except (OSError, sqlite3.Error, RuntimeError):
        current_app.logger.warning("Annotazioni della scheda non leggibili", exc_info=True)
        note = None
    return jsonify(ok=True, scheda=s, stato_attuale=consultazione.stato_attuale(s), annotazioni=note or [],
                   annotazioni_disponibili=note is not None, puo_annotare=_ha("fascicoli.scrivi"),
                   **_applicabilita(s))


def _applicabilita(s: dict) -> dict:
    """Testo vigente o anteriore alla riforma secondo la data di instaurazione: indicata (?data_instaurazione=AAAA-MM-GG)
    o letta nel fascicolo (?fascicolo=ID, solo se l'utente lo può vedere). Senza data certa: entrambe le versioni."""
    from lex.conoscenza.applicabile import applicabilita_scheda, data_instaurazione

    fid = str(request.args.get("fascicolo", "") or "")[:80]
    indicata = str(request.args.get("data_instaurazione", "") or "")[:10]
    if not fid and not indicata:
        return {}
    if indicata:
        dati = {"data": indicata, "certa": True, "motivo": "data indicata dall'avvocato"}
    else:
        from lex.fascicolo_accesso import fascicolo_accessibile

        if not fascicolo_accessibile(fid):
            return {"instaurazione": {"data": "", "certa": False, "motivo": "fascicolo non accessibile"}}
        try:
            from lex.fascicolo_accesso import _carica_fascicolo
            from web.services.archivio_letture_runtime import fatti_fascicolo

            fascicolo = _carica_fascicolo(fid)
            dati = data_instaurazione(fatti_fascicolo(fascicolo), fascicolo)
        except RuntimeError:
            dati = {"data": "", "certa": False, "motivo": "archivio delle letture non disponibile"}
    return {"instaurazione": dati, "applicabilita": applicabilita_scheda(s, dati)}


@api_v1_conoscenza.get("/norma/<chiave>")
@_richiedi_auth
def norma(chiave: str):
    negato = _lettura_negata()
    if negato is not None:
        return negato
    from lex.conoscenza import consultazione

    if request.args.get("versione") == "anteriore":
        dati = consultazione.testo_anteriore(chiave)
        if dati is None:
            return jsonify(ok=False, message="Nessun testo anteriore registrato per questa norma."), 404
        return jsonify(ok=True, norma=dati)
    dati = consultazione.passaggio_norma(chiave, str(request.args.get("ancora", "") or "")[:600])
    if dati is None:
        return jsonify(ok=False, message="Testo della norma non disponibile nell'archivio."), 404
    return jsonify(ok=True, norma=dati)


@api_v1_conoscenza.get("/registro")
@_richiedi_auth
def registro():
    negato = _lettura_negata()
    if negato is not None:
        return negato
    from lex.conoscenza import consultazione, deposito

    operazione = str(request.args.get("operazione", "") or "")
    materia = str(request.args.get("materia", "") or "")
    eventi = [e for e in deposito.leggi_registro(consultazione.registro_attivo())
              if (not operazione or e["operazione"] == operazione) and (not materia or e.get("materia") == materia)]
    eventi.reverse()
    return jsonify(ok=True, eventi=eventi[:300], totale=len(eventi))


@api_v1_conoscenza.post("/schede/<scheda_id>/annotazioni")
@_richiedi_auth
def annota(scheda_id: str):
    if not _ha("fascicoli.scrivi"):
        return jsonify(ok=False, message="Solo chi può scrivere nei fascicoli può annotare le schede."), 403
    from lex.conoscenza import annotazioni, consultazione

    s = consultazione.scheda(scheda_id)
    if s is None:
        return jsonify(ok=False, message="Scheda non trovata."), 404
    corpo, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        nota = annotazioni.Annotazioni(_studio_db(scrittura=True)).aggiungi(
            scheda_id, sezione=str(corpo.get("sezione") or "generale"), voce=str(corpo.get("voce") or ""),
            testo=str(corpo.get("testo") or ""), esito=str(corpo.get("esito") or ""), attore=_nome_utente(),
            revisione_scheda=int(s.get("revisione", 0)), sostituisce=str(corpo.get("sostituisce") or "")[:40])
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400
    except (OSError, sqlite3.Error, RuntimeError):
        return _non_disponibile()
    _audit_event("conoscenza.annotazione", "conoscenza", scheda_id, "Annotazione sulla scheda di istituto.")
    return jsonify(ok=True, message="Annotazione registrata.", annotazione=nota)
