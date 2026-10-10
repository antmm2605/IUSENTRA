"""Adattatore dei comandi CTU; riusa mutazioni native e audit SQL atomico."""
from functools import wraps

from flask import g, jsonify, make_response, request

from pct.ctu import IncaricoCtu
from pct.ctu_repository import CtuConflict, CtuRejected


class CtuPreconditionRequired(ValueError):
    """La bozza deve identificare la revisione e il comando da confermare."""


def read_ctu_body():
    if request.is_json:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ValueError("Richiesta CTU non valida: i dati devono essere un oggetto JSON.")
        return body
    return request.form.to_dict()


def governed_ctu_write(app):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            g._ctu_command_receipt = None
            g._ctu_rejected_receipt = None
            try:
                response = make_response(function(*args, **kwargs))
                receipt = g.get("_ctu_command_receipt")
                if receipt and response.is_json and 200 <= response.status_code < 300:
                    payload = response.get_json()
                    if isinstance(payload, dict) and payload.get("ok") is True:
                        response.set_data(app.json.dumps({**payload, "confirmedCommand": receipt}))
                return response
            except CtuPreconditionRequired as exc:
                return jsonify({"ok": False, "code": "precondition_required", "message": str(exc)}), 428
            except CtuRejected as exc:
                return jsonify({"ok": False, "code": exc.result["code"], "message": str(exc),
                                "rejectedCommand": g.get("_ctu_rejected_receipt")}), 409 if exc.result["code"] == "conflict" else 400
            except CtuConflict as exc:
                return jsonify({"ok": False, "code": "conflict", "message": str(exc)}), 409
            except ValueError as exc:
                return jsonify({"ok": False, "code": "validation", "message": str(exc)}), 400
            except KeyError:
                return jsonify({"ok": False, "message": "Incarico CTU non trovato."}), 404
            except Exception:
                app.logger.exception("Esito CTU non confermato: %s", function.__name__)
                return jsonify({"ok": False, "code": "outcome_not_confirmed", "message":
                    "Esito del comando CTU non confermato. La bozza è conservata: verifica il salvataggio prima di riprovare."}), 503
        return wrapped
    return decorate


def apply_ctu_change(manager, operation, body, *, fascicolo_id, incarico_id="", mutate, delivery=None):
    if not manager.write_protocol["persistentCommands"]:
        return mutate()
    if not body.get("commandKey") or body.get("expectedRevision") is None:
        raise CtuPreconditionRequired("Il salvataggio richiede il comando e la revisione della bozza CTU. Nessuna modifica registrata.")
    intent = {"fascicolo_id": fascicolo_id, "incarico_id": incarico_id,
              "body": {key: value for key, value in body.items() if key not in {"commandKey", "expectedRevision"}}}
    try:
        result = manager.execute_command(operation, intent, command_key=body.get("commandKey", ""),
                                         expected_revision=body.get("expectedRevision"), mutate=mutate, delivery=delivery)
    except CtuRejected as exc:
        g._ctu_rejected_receipt = {
            "scope": manager.write_protocol["scope"], "commandKey": body["commandKey"],
            "fascicoloId": fascicolo_id, "incaricoId": incarico_id,
            "expectedRevision": exc.result["expected_revision"],
            "rejectedAtRevision": exc.result["rejected_at_revision"], "status": "rejected",
        }
        raise
    record = IncaricoCtu.from_dict(result["record"])
    if record.fascicolo_id != fascicolo_id or (incarico_id and record.id != incarico_id):
        raise RuntimeError("Esito CTU riferito a un incarico differente.")
    g._ctu_command_receipt = {
        "scope": manager.write_protocol["scope"], "commandKey": body["commandKey"],
        "fascicoloId": fascicolo_id, "incaricoId": record.id, "committedRevision": result["revision"],
    }
    g._ctu_delivery_result = result.get("delivery")
    return record


def legacy_ctu_audit(manager, audit, *args, **kwargs):
    if not manager.write_protocol["persistentCommands"]:
        audit(*args, **kwargs)
