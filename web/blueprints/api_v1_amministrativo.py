"""API React del deposito amministrativo telematico (Formweb del Portale dell'Avvocato).

Base normativa: art. 136 c.p.a.; d.P.C.M. 40/2016; regole tecnico-operative
d.P.C.S. 2025; avviso del Segretariato generale 28/01/2026 (priorità Formweb).
Il Formweb non ha API per i gestionali: queste rotte preparano i dati, il
foglio delle parti e il pacchetto dei file, verificano il riepilogo e
registrano lo stato che l'avvocato riporta dal portale.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, Response, current_app, jsonify, request

from pct.pat_formweb import catalogo
from web.blueprints.api_v1_react import _api_key_valida, _audit_event, _richiedi_auth, _session_user_can
from web.services import pat_formweb_azioni as azioni
from web.services import pat_formweb_contesto as contesto

api_v1_amministrativo = Blueprint("api_v1_amministrativo", __name__)
LIMITE_UPLOAD = 30 * 1024 * 1024
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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
            current_app.logger.exception("Errore API deposito amministrativo")
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


def _file(nome: str) -> tuple[str, bytes]:
    caricato = request.files.get(nome)
    if caricato is None:
        return "", b""
    contenuto = caricato.read(LIMITE_UPLOAD + 1)
    if len(contenuto) > LIMITE_UPLOAD:
        raise ValueError("File troppo grande (massimo 30 MB).")
    return str(caricato.filename or ""), contenuto


def _scarica(dati: bytes, nome: str, tipo: str) -> Response:
    risposta = Response(dati, mimetype=tipo)
    risposta.headers["Content-Disposition"] = f'attachment; filename="{nome}"'
    risposta.headers["Cache-Control"] = "no-store"
    return risposta


@api_v1_amministrativo.get("/catalogo")
@_richiedi_auth
@_risposta
def catalogo_formweb():
    return jsonify({"ok": True, **catalogo.catalogo()})


@api_v1_amministrativo.get("/panoramica")
@_richiedi_auth
@_risposta
def panoramica():
    from web.services.pat_formweb_panoramica import panoramica as costruisci

    return jsonify(costruisci())


@api_v1_amministrativo.get("/catalogo-apertura")
@_richiedi_auth
@_risposta
def catalogo_apertura():
    from web.services.pat_formweb_apertura import catalogo_apertura as costruisci

    return jsonify(costruisci(request.args.get("ufficio", "")[:200]))


@api_v1_amministrativo.get("/connessione")
@_richiedi_auth
@_risposta
def connessione():
    return jsonify({"ok": True, **azioni.connessione()})


@api_v1_amministrativo.get("/fascicoli/<fid>")
@_richiedi_auth
@_risposta
def quadro(fid: str):
    return jsonify(contesto.quadro(fid, request.args.get("tipo", "ricorso")))


@api_v1_amministrativo.post("/fascicoli/<fid>/procedimento")
@_richiedi_auth
@_scrittura
@_risposta
def procedimento(fid: str):
    azioni.salva_procedimento(fid, _json())
    _audit_event("pat_formweb_procedimento", "fascicolo", fid, str(sorted(_json())))
    return jsonify(contesto.quadro(fid, request.args.get("tipo", "ricorso")))


@api_v1_amministrativo.post("/fascicoli/<fid>/parti/<soggetto>")
@_richiedi_auth
@_scrittura
@_risposta
def parte(fid: str, soggetto: str):
    azioni.ruolo_parte(fid, soggetto, str(_json().get("ruolo") or ""))
    return jsonify(contesto.quadro(fid, request.args.get("tipo", "ricorso")))


@api_v1_amministrativo.post("/fascicoli/<fid>/documenti/<documento>")
@_richiedi_auth
@_scrittura
@_risposta
def documento(fid: str, documento: str):
    dati = _json()
    azioni.ruolo_documento(fid, documento, str(dati.get("ruolo") or ""), str(dati.get("descrizione") or ""))
    return jsonify(contesto.quadro(fid, request.args.get("tipo", "ricorso")))


@api_v1_amministrativo.get("/fascicoli/<fid>/excel-parti/<ruolo>")
@_richiedi_auth
@_risposta
def excel_parti(fid: str, ruolo: str):
    dati, nome = azioni.excel(fid, ruolo)
    return _scarica(dati, nome, _XLSX)


@api_v1_amministrativo.get("/fascicoli/<fid>/pacchetto")
@_richiedi_auth
@_risposta
def pacchetto(fid: str):
    dati, nome = azioni.pacchetto(fid)
    _audit_event("pat_formweb_pacchetto", "fascicolo", fid, nome)
    return _scarica(dati, nome, "application/zip")


@api_v1_amministrativo.post("/fascicoli/<fid>/riepilogo")
@_richiedi_auth
@_scrittura
@_risposta
def riepilogo(fid: str):
    nome, dati = _file("file")
    esito = azioni.verifica_riepilogo(fid, nome, dati, request.form.get("tipo", "ricorso"),
                                      salva=request.form.get("salva", "1") != "0")
    _audit_event("pat_formweb_riepilogo", "fascicolo", fid, "conforme" if esito["esito"]["conforme"] else "da verificare")
    return jsonify(esito)


@api_v1_amministrativo.post("/fascicoli/<fid>/depositi")
@_richiedi_auth
@_scrittura
@_risposta
def deposito(fid: str):
    voce = azioni.aggiorna_deposito(fid, _json())
    _audit_event("pat_formweb_deposito", "fascicolo", fid, str(voce.get("stato")))
    return jsonify({"ok": True, "deposito": voce})
