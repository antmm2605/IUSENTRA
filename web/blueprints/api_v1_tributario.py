"""API React del deposito tributario telematico (PTT sul SIGIT).

Base normativa: artt. 16-bis, 18, 22 D.Lgs. 546/1992; D.M. 163/2013; decreto
direttoriale 4/8/2015 modificato il 21/4/2023; art. 13 c. 6-quater d.P.R.
115/2002. Il SIGIT non ha servizi per i gestionali (Circolare 1/DF 2019):
queste rotte preparano la nota di iscrizione a ruolo, controllano i file,
calcolano CUT e termini, preparano il pacchetto e registrano lo stato che
l'avvocato riporta dall'area riservata del PTT.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, Response, current_app, jsonify, request

from pct.ptt_sigit import catalogo
from web.blueprints.api_v1_react import _api_key_valida, _audit_event, _richiedi_auth, _session_user_can
from web.services import ptt_sigit_azioni as azioni
from web.services import ptt_sigit_contesto as contesto

api_v1_tributario = Blueprint("api_v1_tributario", __name__)


def _risposta(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        try:
            return func(*args, **kwargs)
        except LookupError as exc:
            return jsonify(ok=False, message=str(exc).strip("'")), 404
        except ValueError as exc:
            return jsonify(ok=False, message=str(exc)), 400
        except Exception:
            current_app.logger.exception("Errore API deposito tributario PTT")
            return jsonify(ok=False, message="Operazione non riuscita: riprova fra poco."), 500
    return wrapper


def _scrittura(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if not (_api_key_valida() or _session_user_can("fascicoli.scrivi")):
            return jsonify(ok=False, message="Operazione non autorizzata."), 403
        return func(*args, **kwargs)
    return wrapper


def _json() -> dict[str, Any]:
    dati = request.get_json(silent=True)
    return dati if isinstance(dati, dict) else {}


def _scarica(dati: bytes, nome: str, tipo: str) -> Response:
    risposta = Response(dati, mimetype=tipo)
    risposta.headers["Content-Disposition"] = f'attachment; filename="{nome}"'
    risposta.headers["Cache-Control"] = "no-store"
    return risposta


def _tipo() -> str:
    return request.args.get("tipo", "")[:40]


@api_v1_tributario.get("/catalogo")
@_richiedi_auth
@_risposta
def catalogo_ptt():
    return jsonify({"ok": True, **catalogo.catalogo()})


@api_v1_tributario.get("/panoramica")
@_richiedi_auth
@_risposta
def panoramica():
    from web.services.ptt_sigit_panoramica import panoramica as costruisci

    return jsonify(costruisci())


@api_v1_tributario.get("/catalogo-apertura")
@_richiedi_auth
@_risposta
def catalogo_apertura():
    from web.services.ptt_sigit_apertura import catalogo_apertura as costruisci

    return jsonify(costruisci(request.args.get("ufficio", "")[:200]))


@api_v1_tributario.get("/connessione")
@_richiedi_auth
@_risposta
def connessione():
    return jsonify({"ok": True, **azioni.connessione()})


@api_v1_tributario.get("/fascicoli/<fid>")
@_richiedi_auth
@_risposta
def quadro(fid: str):
    return jsonify(contesto.quadro(fid, _tipo()))


@api_v1_tributario.post("/fascicoli/<fid>/procedimento")
@_richiedi_auth
@_scrittura
@_risposta
def procedimento(fid: str):
    azioni.salva_procedimento(fid, _json())
    _audit_event("ptt_sigit_procedimento", "fascicolo", fid, str(sorted(_json())))
    return jsonify(contesto.quadro(fid, _tipo()))


@api_v1_tributario.post("/fascicoli/<fid>/documenti/<documento>")
@_richiedi_auth
@_scrittura
@_risposta
def documento(fid: str, documento: str):
    dati = _json()
    azioni.ruolo_documento(fid, documento, str(dati.get("ruolo") or ""), str(dati.get("tipologia") or ""),
                           str(dati.get("descrizione") or ""))
    return jsonify(contesto.quadro(fid, _tipo()))


@api_v1_tributario.post("/fascicoli/<fid>/controllo")
@_richiedi_auth
@_scrittura
@_risposta
def controllo(fid: str):
    esito = azioni.controlla_file(fid)
    _audit_event("ptt_sigit_controllo", "fascicolo", fid, "conforme" if esito["conforme"] else "da sistemare")
    return jsonify({"ok": True, **esito})


@api_v1_tributario.get("/fascicoli/<fid>/pacchetto")
@_richiedi_auth
@_risposta
def pacchetto(fid: str):
    dati, nome = azioni.pacchetto(fid)
    _audit_event("ptt_sigit_pacchetto", "fascicolo", fid, nome)
    return _scarica(dati, nome, "application/zip")


@api_v1_tributario.post("/fascicoli/<fid>/termini/<termine>")
@_richiedi_auth
@_scrittura
@_risposta
def termine(fid: str, termine: str):
    esito = azioni.registra_termine(fid, termine)
    _audit_event("ptt_sigit_termine", "fascicolo", fid, termine)
    return jsonify(esito)


@api_v1_tributario.post("/fascicoli/<fid>/depositi")
@_richiedi_auth
@_scrittura
@_risposta
def deposito(fid: str):
    voce = azioni.aggiorna_deposito(fid, _json())
    _audit_event("ptt_sigit_deposito", "fascicolo", fid, str(voce.get("stato")))
    return jsonify({"ok": True, "deposito": voce})
