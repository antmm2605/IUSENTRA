"""API React della pagina «Norme dei modelli d'atto» (presidio delle schede).

Montato sotto ``/api/v1/ui/schede-fonti``. Lettura con i permessi di consultazione delle fonti; decisioni sulle
proposte e approvazione delle norme di una scheda riservate a chi configura lo studio (``admin.configura``),
registrate con il nome dell'utente e nel registro attivita'. Nessuna scheda viene modificata da qui.
"""
from __future__ import annotations

import sqlite3

from flask import Blueprint, current_app, g, jsonify, request

from web.blueprints.api_v1_react import _audit_event, _request_json_object, _richiedi_auth
from web.services import schede_fonti_runtime as runtime

api_v1_schede_fonti = Blueprint("api_v1_schede_fonti", __name__)


def _biblioteca():
    from web.blueprints.api_v1_ricerca_legale import _normativa_db

    return _normativa_db()


def _studio_db(scrittura=False):
    from web.services.tenant_paths import tenant_data_path
    from web.services.storage_runtime import get_request_studio_db
    anchor = tenant_data_path("CONFIG_STUDIO_DB", "./config/studio.json", "STUDIO_CONFIG", require_tenant=True)
    backend = get_request_studio_db(anchor)
    if backend is None:
        # Anche gli studi con mirror storici JSON registrano queste nuove
        # decisioni nel proprio SQL canonico, mai nel registro pubblico.
        from pathlib import Path
        from pct.storage import StudioDB
        from web.services.storage_runtime import get_request_storage_runtime
        profile = get_request_storage_runtime(anchor)
        if scrittura or Path(profile.studio_db_path).is_file():
            backend = StudioDB.get(profile.studio_db_path)
    return backend


def _utente():
    return g.get("utente_corrente")


def _ha(permesso: str) -> bool:
    return bool(getattr(_utente(), "ha_permesso", lambda _p: False)(permesso))


def _lettura_negata():
    if not (_ha("ai.usa") or _ha("fascicoli.leggi")):
        return jsonify(ok=False, message="Non hai il permesso per consultare le norme dei modelli d'atto."), 403
    return None


def _decisione_negata():
    if not _ha("admin.configura"):
        return jsonify(ok=False, message="Solo chi configura lo studio puo' decidere sulle norme dei modelli d'atto."), 403
    return None


def _nome_utente() -> str:
    u = _utente()
    return str(getattr(u, "nome_completo", "") or getattr(u, "nome", "") or getattr(u, "username", "") or "").strip()


def _non_disponibile():
    current_app.logger.exception("Presidio norme dei modelli d'atto non disponibile")
    return jsonify(ok=False, message="Il presidio delle norme non e' ancora disponibile: riprova dopo l'aggiornamento notturno."), 503


@api_v1_schede_fonti.get("")
@_richiedi_auth
def riepilogo():
    negato = _lettura_negata()
    if negato is not None:
        return negato
    try:
        filtri = {k: str(request.args.get(k, "") or "") for k in ("tipo", "scheda")}
        stato = request.args.get("stato", "aperta")
        if stato not in ("aperta", "approvata", "respinta"):
            stato = "aperta"
        biblioteca, studio = _biblioteca(), _studio_db()
        righe = runtime._elenco(biblioteca, studio)
        proposte = runtime.proposte(biblioteca, stato=stato, studio_db=studio, righe=righe, **filtri)
        try:
            pagina = max(1, int(request.args.get("pagina", 1)))
        except (TypeError, ValueError):
            pagina = 1
        pagine = max(1, (len(proposte) + 49) // 50)
        pagina = min(pagina, pagine)
        return jsonify(ok=True, riepilogo=runtime.riepilogo(biblioteca, studio_db=studio, righe=righe),
                       proposte=proposte[(pagina - 1) * 50:pagina * 50], puo_decidere=_ha("admin.configura"),
                       modelli=runtime._modelli(), paginazione={"pagina": pagina, "pagine": pagine, "totale": len(proposte)})
    except (OSError, sqlite3.Error, ValueError, RuntimeError):
        return _non_disponibile()


@api_v1_schede_fonti.get("/schede/<scheda_id>")
@_richiedi_auth
def scheda(scheda_id: str):
    negato = _lettura_negata()
    if negato is not None:
        return negato
    try:
        dati = runtime.scheda(_biblioteca(), scheda_id, studio_db=_studio_db())
    except (OSError, sqlite3.Error, ValueError, RuntimeError):
        return _non_disponibile()
    if dati is None:
        return jsonify(ok=False, message="Modello d'atto non trovato."), 404
    return jsonify(ok=True, scheda=dati, puo_decidere=_ha("admin.configura"))


@api_v1_schede_fonti.post("/proposte/<proposta_id>/decisione")
@_richiedi_auth
def decisione(proposta_id: str):
    negato = _decisione_negata()
    if negato is not None:
        return negato
    corpo, errore = _request_json_object()
    if errore is not None:
        return errore
    esito, nota = str(corpo.get("esito") or ""), str(corpo.get("nota") or "")[:2000]
    try:
        nuova = runtime.decidi(_biblioteca(), proposta_id, esito, _nome_utente(), nota, str(corpo.get("impronta") or ""), studio_db=_studio_db(scrittura=True))
    except runtime.RevisioneCambiata as exc:
        return jsonify(ok=False, message=str(exc)), 409
    except KeyError:
        return jsonify(ok=False, message="Elemento non trovato."), 404
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400
    except (OSError, sqlite3.Error, RuntimeError):
        return _non_disponibile()
    if not nuova:
        return jsonify(ok=True, message="Decisione già registrata.")
    _audit_event("schede_fonti.decisione", "schede_fonti", str(proposta_id), f"Proposta {esito}.")
    return jsonify(ok=True, message="Decisione registrata.")


@api_v1_schede_fonti.post("/schede/<scheda_id>/approva")
@_richiedi_auth
def approva(scheda_id: str):
    negato = _decisione_negata()
    if negato is not None:
        return negato
    corpo, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        n = runtime.approva(_biblioteca(), scheda_id, _nome_utente(), str(corpo.get("impronta") or ""), studio_db=_studio_db(scrittura=True))
    except runtime.RevisioneCambiata as exc:
        return jsonify(ok=False, message=str(exc)), 409
    except KeyError:
        return jsonify(ok=False, message="Elemento non trovato."), 404
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400
    except (OSError, sqlite3.Error, RuntimeError):
        return _non_disponibile()
    _audit_event("schede_fonti.approvazione", "schede_fonti", scheda_id, f"{n} norme approvate.")
    return jsonify(ok=True, message=f"{n} norme approvate per questo modello.", approvate=n)
