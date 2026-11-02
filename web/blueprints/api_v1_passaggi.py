"""API v1 UI dei passaggi spiegabili e delle regole dello studio — /api/v1/ui/...

- ``GET  /fascicoli/<id>/passaggi``: i passaggi del software sul fascicolo, già
  corretti dalle regole dello studio (permesso ``fascicoli.leggi``);
- ``POST /fascicoli/<id>/passaggi/correzioni``: «Correggi la regola» — la
  correzione diventa regola dello studio o torna rifiutata con la norma
  (permesso ``fascicoli.scrivi``);
- ``GET  /regole-studio`` e ``GET /regole-studio/<id>/diario``: elenco e diario;
- ``POST /regole-studio/<id>``: modifica del valore o del motivo, disattivazione
  e riattivazione (permesso ``fascicoli.scrivi``).

Il tenant è sempre quello della richiesta (mai dal corpo); i fascicoli si
leggono con i gestori dello studio corrente, quindi un fascicolo di un altro
studio risulta inesistente. Ogni scrittura va anche nel registro di audit.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, current_app, g, jsonify, request

from web.services.tenant_api_auth import api_key_valid_for_request

api_v1_passaggi = Blueprint("api_v1_passaggi", __name__, url_prefix="/api/v1/ui")

PERMESSO_LETTURA = "fascicoli.leggi"
PERMESSO_SCRITTURA = "fascicoli.scrivi"
_CHIAVI_VIETATE = {"tenant", "tenant_id", "studio_id", "tenant_slug", "autore_id", "ufficio", "giudice", "fascicolo_id"}


def _audit(azione: str, risorsa: str, identificativo: str, dettagli: str) -> None:
    audit = (current_app.extensions.get("core_runtime", {}) or {}).get("audit")
    if callable(audit):
        audit(azione, risorsa, identificativo, dettagli)


def _richiedi(permesso: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decoratore(funzione: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(funzione)
        def wrapper(*args: Any, **kwargs: Any):
            if api_key_valid_for_request():
                return funzione(*args, **kwargs)
            utente = g.get("utente_corrente")
            if not utente:
                return jsonify({"ok": False, "code": "unauthorized", "errore": "Autenticazione richiesta."}), 401
            if not getattr(utente, "ha_permesso", lambda _p: False)(permesso):
                return jsonify({"ok": False, "code": "forbidden", "errore": "Permessi insufficienti."}), 403
            return funzione(*args, **kwargs)

        return wrapper

    return decoratore


def _corpo() -> dict[str, Any]:
    dati = request.get_json(silent=True)
    return {chiave: valore for chiave, valore in dict(dati if isinstance(dati, dict) else {}).items() if chiave not in _CHIAVI_VIETATE}


@api_v1_passaggi.get("/fascicoli/<id_fasc>/passaggi")
@_richiedi(PERMESSO_LETTURA)
def fascicolo_passaggi(id_fasc: str):
    """I passaggi con regola, norma, prove e dati, e le regole dello studio applicate o rifiutate."""
    try:
        from web.services.passaggi_runtime import payload_passaggi

        payload = payload_passaggi(id_fasc)
        if payload is None:
            return jsonify({"ok": False, "notFound": True, "errore": "Fascicolo non trovato."}), 404
        return jsonify({"ok": True, **payload})
    except Exception as exc:
        current_app.logger.exception("Passaggi del fascicolo %s non disponibili: %s", id_fasc, exc)
        return jsonify({"ok": False, "errore": "Passaggi del software non disponibili in questo momento."}), 200


@api_v1_passaggi.post("/fascicoli/<id_fasc>/passaggi/correzioni")
@_richiedi(PERMESSO_SCRITTURA)
def fascicolo_passaggi_correzione(id_fasc: str):
    """L'avvocato corregge un passaggio: nasce una regola dello studio, salvo vincoli di legge."""
    try:
        from pct.passaggi import CorrezioneRifiutata
        from pct.passaggi.repository import RegoleStudioError
        from web.services.passaggi_runtime import correggi_passaggio

        corpo = _corpo()
        chiave = str(corpo.get("chiave") or "").strip()
        try:
            regola = correggi_passaggio(id_fasc, chiave, corpo)
        except LookupError:
            return jsonify({"ok": False, "notFound": True, "errore": "Fascicolo non trovato."}), 404
        except CorrezioneRifiutata as rifiuto:
            _audit("passaggi.regola_studio.rifiutata", "fascicolo", id_fasc, f"{chiave}: {rifiuto.rifiuto.motivo}")
            return jsonify({"ok": False, "rifiutata": True, "errore": rifiuto.rifiuto.motivo, "rifiuto": rifiuto.rifiuto.come_dizionario()}), 200
        except RegoleStudioError as errore:
            return jsonify({"ok": False, "errore": str(errore)}), 200
        _audit("passaggi.regola_studio.creata", "regola_studio", regola["id"], f"{regola['regolaId']}: {regola['descrizione']}")
        return jsonify({"ok": True, "regola": regola})
    except Exception as exc:
        current_app.logger.exception("Correzione del passaggio nel fascicolo %s non registrata: %s", id_fasc, exc)
        return jsonify({"ok": False, "errore": "Correzione non registrata."}), 200


@api_v1_passaggi.get("/regole-studio")
@_richiedi(PERMESSO_LETTURA)
def regole_studio_elenco():
    try:
        from web.services.passaggi_runtime import elenco_regole

        return jsonify({"ok": True, "regole": elenco_regole()})
    except Exception as exc:
        current_app.logger.exception("Regole dello studio non disponibili: %s", exc)
        return jsonify({"ok": False, "errore": "Regole dello studio non disponibili.", "regole": []}), 200


@api_v1_passaggi.get("/regole-studio/<regola_id>/diario")
@_richiedi(PERMESSO_LETTURA)
def regole_studio_diario(regola_id: str):
    try:
        from pct.passaggi.repository import RegoleStudioError
        from web.services.passaggi_runtime import diario_regola

        try:
            return jsonify({"ok": True, **diario_regola(regola_id)})
        except RegoleStudioError as errore:
            return jsonify({"ok": False, "notFound": True, "errore": str(errore)}), 404
    except Exception as exc:
        current_app.logger.exception("Diario della regola %s non disponibile: %s", regola_id, exc)
        return jsonify({"ok": False, "errore": "Diario della regola non disponibile."}), 200


@api_v1_passaggi.post("/regole-studio/<regola_id>")
@_richiedi(PERMESSO_SCRITTURA)
def regole_studio_aggiorna(regola_id: str):
    """Modifica valore o motivo, disattiva o riattiva una regola dello studio."""
    try:
        from pct.passaggi.repository import RegoleStudioError
        from web.services.passaggi_runtime import aggiorna_regola

        corpo = {chiave: corpo for chiave, corpo in _corpo().items() if chiave in {"valore", "motivo", "attiva"}}
        try:
            regola = aggiorna_regola(regola_id, corpo)
        except RegoleStudioError as errore:
            return jsonify({"ok": False, "errore": str(errore)}), 200
        _audit("passaggi.regola_studio.aggiornata", "regola_studio", regola_id, ", ".join(f"{k}={v}" for k, v in corpo.items()))
        return jsonify({"ok": True, "regola": regola})
    except Exception as exc:
        current_app.logger.exception("Regola dello studio %s non aggiornata: %s", regola_id, exc)
        return jsonify({"ok": False, "errore": "Regola non aggiornata."}), 200
