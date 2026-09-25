"""API React del deposito penale telematico (Portale Deposito atti Penali).

Base normativa: art. 111-bis c.p.p.; D.M. 217/2023 e modifiche; provvedimento
DGSIA 11/07/2023. Il deposito lo invia l'avvocato dal PDP: queste API
preparano, controllano, registrano ricevute e stati, importano gli export.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, current_app, jsonify, request

from pct.penale_pdp import catalogo
from web.blueprints.api_v1_react import _api_key_valida, _audit_event, _richiedi_auth, _session_user_can
from web.services import penale_pdp_contesto as contesto
from web.services import penale_pdp_depositi as depositi
from web.services.penale_pdp_import import importa

api_v1_penale = Blueprint("api_v1_penale", __name__)
LIMITE_UPLOAD = 20 * 1024 * 1024


def _risposta(func: Callable[..., Any]) -> Callable[..., Any]:
    """Errori del dominio come JSON con il codice HTTP giusto, mai un 500 generico."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        try:
            return func(*args, **kwargs)
        except LookupError as exc:
            return jsonify(ok=False, message=str(exc).strip("'")), 404
        except ValueError as exc:
            return jsonify(ok=False, message=str(exc)), 400
        except Exception:
            current_app.logger.exception("Errore API deposito penale")
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
        raise ValueError("File troppo grande (massimo 20 MB).")
    return str(caricato.filename or ""), contenuto


@api_v1_penale.get("/fascicoli/<fid>")
@_richiedi_auth
@_risposta
def quadro(fid: str):
    return jsonify(contesto.quadro(fid))


@api_v1_penale.post("/fascicoli/<fid>/procedimento")
@_richiedi_auth
@_scrittura
@_risposta
def procedimento(fid: str):
    contesto.aggiorna_procedimento(fid, _json())
    _audit_event("penale_pdp_procedimento", "fascicolo", fid, str(sorted(_json())))
    return jsonify(contesto.quadro(fid))


@api_v1_penale.post("/fascicoli/<fid>/registri")
@_richiedi_auth
@_scrittura
@_risposta
def registro_nuovo(fid: str):
    return jsonify(ok=True, registro=contesto.salva_registro(fid, _json()))


@api_v1_penale.delete("/fascicoli/<fid>/registri/<rid>")
@_richiedi_auth
@_scrittura
@_risposta
def registro_elimina(fid: str, rid: str):
    contesto.archivio().elimina_registro(contesto.caso(fid)["id"], rid)
    return jsonify(ok=True)


@api_v1_penale.post("/fascicoli/<fid>/soggetti")
@_richiedi_auth
@_scrittura
@_risposta
def soggetto_nuovo(fid: str):
    return jsonify(ok=True, soggetto=contesto.salva_soggetto(fid, _json()))


@api_v1_penale.delete("/fascicoli/<fid>/soggetti/<sid>")
@_richiedi_auth
@_scrittura
@_risposta
def soggetto_elimina(fid: str, sid: str):
    contesto.archivio().elimina_soggetto(contesto.caso(fid)["id"], sid)
    return jsonify(ok=True)


@api_v1_penale.get("/fascicoli/<fid>/atti")
@_richiedi_auth
@_risposta
def atti(fid: str):
    caso = contesto.caso(fid)
    arch = contesto.archivio()
    ufficio = request.args.get("ufficio") or contesto.ufficio_corrente(caso, arch.registri(caso["id"]))
    scelti = set(filter(None, request.args.get("soggetti", "").split(",")))
    ruoli = [s["role_code"] for s in arch.soggetti(caso["id"]) if not scelti or s["id"] in scelti]
    principali = {"1": True, "0": False}.get(request.args.get("principali", ""))
    voci = catalogo.atti_ammessi(ufficio, ruoli, avocato_pg=bool(caso.get("avocato_pg")), principali=principali,
                                 fase=request.args.get("fase", ""), cerca=request.args.get("cerca", ""))
    return jsonify(ok=True, ufficio=ufficio, autorizzato=bool(caso.get("authorized")), atti=[
        {"codice": v.codice, "nome": v.nome, "principale": v.principale, "fase": v.fase, "norma": v.norma,
         "confermaRicezione": v.conferma_ricezione} for v in voci
    ])


@api_v1_penale.get("/panoramica")
@_richiedi_auth
@_risposta
def panoramica():
    from web.services.penale_pdp_panoramica import panoramica as costruisci

    return jsonify(**costruisci())


@api_v1_penale.get("/atti/<codice>")
@_richiedi_auth
@_risposta
def scheda_atto(codice: str):
    scheda = catalogo.scheda(codice)
    ruoli = list(filter(None, request.args.get("ruoli", "").split(",")))
    contestuali = catalogo.contestuali_per(codice, request.args.get("ufficio", ""), ruoli)
    return jsonify(ok=True, atto=scheda, contestuali=[{"codice": v.codice, "nome": v.nome} for v in contestuali])


@api_v1_penale.post("/fascicoli/<fid>/depositi")
@_richiedi_auth
@_scrittura
@_risposta
def deposito_nuovo(fid: str):
    esito = depositi.prepara(fid, _json())
    _audit_event("penale_pdp_deposito_preparato", "fascicolo", fid, esito["deposito"]["atto"])
    return jsonify(ok=True, **esito)


@api_v1_penale.get("/fascicoli/<fid>/depositi/<did>")
@_richiedi_auth
@_risposta
def deposito_dettaglio(fid: str, did: str):
    return jsonify(ok=True, **depositi.dettaglio(fid, did))


@api_v1_penale.post("/fascicoli/<fid>/depositi/<did>")
@_richiedi_auth
@_scrittura
@_risposta
def deposito_aggiorna(fid: str, did: str):
    return jsonify(ok=True, **depositi.prepara(fid, _json(), deposito_id=did))


@api_v1_penale.delete("/fascicoli/<fid>/depositi/<did>")
@_richiedi_auth
@_scrittura
@_risposta
def deposito_elimina(fid: str, did: str):
    depositi.elimina(fid, did)
    return jsonify(ok=True)


@api_v1_penale.post("/fascicoli/<fid>/depositi/<did>/ricevuta")
@_richiedi_auth
@_scrittura
@_risposta
def deposito_ricevuta(fid: str, did: str):
    nome, contenuto = _file("ricevuta")
    manuale = {k: request.form.get(k, "") for k in ("identificativo", "dataInvio", "stato", "motivazione")}
    esito = depositi.registra_ricevuta(fid, did, contenuto=contenuto, nome=nome, manuale=manuale)
    _audit_event("penale_pdp_ricevuta", "fascicolo", fid, esito["deposito"]["identificativo"])
    return jsonify(ok=True, **esito)


@api_v1_penale.post("/fascicoli/<fid>/depositi/<did>/stato")
@_richiedi_auth
@_scrittura
@_risposta
def deposito_stato(fid: str, did: str):
    esito = depositi.aggiorna_stato(fid, did, _json())
    _audit_event("penale_pdp_stato", "fascicolo", fid, esito["deposito"]["stato"])
    return jsonify(ok=True, **esito)


@api_v1_penale.post("/fascicoli/<fid>/import")
@_richiedi_auth
@_scrittura
@_risposta
def importa_export(fid: str):
    _nome, contenuto = _file("export")
    if not contenuto:
        raise ValueError("Scegli il file esportato dal PDP (.xlsx o .csv).")
    anteprima = request.form.get("anteprima", "1") != "0"
    esito = importa(fid, contenuto, anteprima=anteprima)
    if not anteprima:
        _audit_event("penale_pdp_import", "fascicolo", fid, f"{esito['tipo']}: {esito['importati']}")
    return jsonify(ok=True, **esito)


@api_v1_penale.get("/catalogo-apertura")
@_richiedi_auth
@_risposta
def catalogo_apertura():
    from web.services.penale_pdp_apertura import catalogo_apertura as costruisci

    return jsonify(costruisci(request.args.get("ufficio", "")[:200], request.args.get("codice", "PM-U")[:12]))


@api_v1_penale.get("/fascicoli/<fid>/accesso-atti")
@_richiedi_auth
@_risposta
def accesso_atti(fid: str):
    from web.services.penale_accesso_atti import quadro as quadro_accesso

    return jsonify(quadro_accesso(fid))


@api_v1_penale.post("/fascicoli/<fid>/accesso-atti/<azione>")
@_richiedi_auth
@_scrittura
@_risposta
def accesso_atti_azione(fid: str, azione: str):
    from web.services.penale_accesso_atti import esegui

    return jsonify(esegui(fid, azione, str(request.form.get("task_id") or "")))


@api_v1_penale.get("/casella-pec")
@_richiedi_auth
@_risposta
def casella_pec():
    from web.services.pec_capienza_runtime import stato_casella

    return jsonify(ok=True, **stato_casella(forza=request.args.get("forza") == "1"))
