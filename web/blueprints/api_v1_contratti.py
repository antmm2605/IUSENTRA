"""API React della sezione Contratti: catalogo, valutazione, pratiche e bozze.

Base normativa: art. 1322 c.c. e disciplina generale artt. 1321-1469 c.c.;
le norme speciali sono dichiarate voce per voce in ``pct/contratti/dati``.
I punti di valutazione restano all'avvocato: l'approvazione di una pratica è
rifiutata finché restano bloccanti o punti aperti non valutati.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from pct.contratti import carica_catalogo, famiglia, regole_comuni, valuta
from pct.contratti.archivio import STATI
from pct.contratti.bozza import campi_richiesti, componi, ruoli
from pct.contratti.catalogo import clausole_della_famiglia, domande_comuni, libreria_clausole
from pct.contratti.esporta_docx import bozza_docx, nota_docx
from web.blueprints.api_v1_react import _api_key_valida, _audit_event, _richiedi_auth, _session_user_can
from web.services import contratti_runtime as runtime

api_v1_contratti = Blueprint("api_v1_contratti", __name__)


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
            current_app.logger.exception("Errore API contratti")
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


def _docx(dati: bytes, nome: str) -> Response:
    risposta = Response(dati, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    risposta.headers["Content-Disposition"] = f'attachment; filename="{nome}"'
    risposta.headers["Cache-Control"] = "no-store"
    return risposta


@api_v1_contratti.get("/catalogo")
@_richiedi_auth
@_risposta
def catalogo():
    return jsonify({"ok": True, **carica_catalogo(), "regole_comuni": regole_comuni(), "stati": list(STATI)})


@api_v1_contratti.get("/famiglie/<contratto_id>")
@_richiedi_auth
@_risposta
def dettaglio(contratto_id: str):
    contratto = famiglia(contratto_id[:80])
    libreria = libreria_clausole()["clausole"]
    return jsonify({
        "ok": True,
        "contratto": contratto.come_dict(),
        "domande_comuni": [{"id": d.id, "testo": d.testo, "tipo": d.tipo, "opzioni": list(d.opzioni)} for d in domande_comuni()],
        "ruoli": ruoli(contratto.id),
        "campi": campi_richiesti(contratto.id),
        "clausole": [{"chiave": c, "titolo": libreria[c]["titolo"], "norma": libreria[c]["norma"]}
                     for c in clausole_della_famiglia(contratto)],
    })


@api_v1_contratti.post("/famiglie/<contratto_id>/valutazione")
@_richiedi_auth
@_risposta
def valutazione(contratto_id: str):
    fatti = _json().get("fatti", {})
    if not isinstance(fatti, dict):
        return jsonify(ok=False, message="I fatti devono essere un oggetto."), 400
    return jsonify({"ok": True, **valuta(contratto_id[:80], fatti)})


@api_v1_contratti.post("/famiglie/<contratto_id>/bozza")
@_richiedi_auth
@_risposta
def anteprima_bozza(contratto_id: str):
    corpo = _json()
    return jsonify({"ok": True, "bozza": componi(contratto_id[:80], corpo.get("dati") or {}, corpo.get("fatti") or {})})


@api_v1_contratti.get("/fascicoli")
@_richiedi_auth
@_risposta
def scelta_fascicoli():
    return jsonify({"ok": True, "fascicoli": runtime.fascicoli(request.args.get("q", "")[:120])})


@api_v1_contratti.get("/pratiche")
@_richiedi_auth
@_risposta
def elenco_pratiche():
    return jsonify({"ok": True, "pratiche": runtime.archivio().elenco(request.args.get("fascicolo", "")[:80])})


@api_v1_contratti.post("/pratiche")
@_richiedi_auth
@_scrittura
@_risposta
def nuova_pratica():
    corpo = _json()
    pratica = runtime.archivio().crea(str(corpo.get("contratto_id", ""))[:80], corpo, runtime.autore())
    _audit_event("contratti.pratica_creata", "pratica_contrattuale", pratica["id"], pratica["contratto_id"])
    return jsonify({"ok": True, "pratica": pratica}), 201


@api_v1_contratti.get("/pratiche/<pid>")
@_richiedi_auth
@_risposta
def leggi_pratica(pid: str):
    pratica = runtime.archivio().pratica(pid[:40])
    return jsonify({"ok": True, "pratica": pratica,
                    "valutazione": valuta(pratica["contratto_id"], pratica.get("fatti") or {}),
                    "bozza": runtime.bozza_pratica(pratica)})


@api_v1_contratti.put("/pratiche/<pid>")
@_richiedi_auth
@_scrittura
@_risposta
def aggiorna_pratica(pid: str):
    corpo = _json()
    corpo.pop("forza_approvazione", None)
    pratica = runtime.archivio().aggiorna(pid[:40], corpo, runtime.autore())
    _audit_event("contratti.pratica_aggiornata", "pratica_contrattuale", pid, pratica["stato"])
    return jsonify({"ok": True, "pratica": pratica,
                    "valutazione": valuta(pratica["contratto_id"], pratica.get("fatti") or {}),
                    "bozza": runtime.bozza_pratica(pratica)})


@api_v1_contratti.delete("/pratiche/<pid>")
@_richiedi_auth
@_scrittura
@_risposta
def elimina_pratica(pid: str):
    runtime.archivio().elimina(pid[:40])
    _audit_event("contratti.pratica_eliminata", "pratica_contrattuale", pid)
    return jsonify({"ok": True})


@api_v1_contratti.get("/pratiche/<pid>/bozza.docx")
@_richiedi_auth
@_risposta
def scarica_bozza(pid: str):
    pratica = runtime.archivio().pratica(pid[:40])
    return _docx(bozza_docx(runtime.bozza_pratica(pratica)), runtime.nome_file(pratica))


@api_v1_contratti.get("/pratiche/<pid>/nota.docx")
@_richiedi_auth
@_risposta
def scarica_nota(pid: str):
    pratica = runtime.archivio().pratica(pid[:40])
    return _docx(nota_docx(runtime.bozza_pratica(pratica)), runtime.nome_file(pratica, "_nota_avvocato"))


@api_v1_contratti.post("/pratiche/<pid>/fascicolo")
@_richiedi_auth
@_scrittura
@_risposta
def salva_nel_fascicolo(pid: str):
    voce = runtime.salva_nel_fascicolo(pid[:40])
    _audit_event("contratti.bozza_nel_fascicolo", "pratica_contrattuale", pid, voce["fascicolo_id"])
    return jsonify({"ok": True, "documento": voce})
