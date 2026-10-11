"""Contratto HTTP dei comandi persistenti della preparazione."""
from functools import wraps

from flask import g, jsonify, make_response

from pct.udienze.repository import PreparazioneConflict, PreparazioneRejected


class PreconditionRequired(ValueError):
    pass


def governed_write(app):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            g._preparazioni_confirmed_command = None
            try:
                response = make_response(function(*args, **kwargs))
                receipt = g.get("_preparazioni_confirmed_command")
                if receipt and response.is_json and 200 <= response.status_code < 300:
                    body = response.get_json()
                    if isinstance(body, dict) and body.get("ok") is True:
                        response.set_data(app.json.dumps({**body, "confirmedCommand": receipt}))
                return response
            except PreconditionRequired as exc:
                return jsonify(ok=False, code="precondition_required", message=str(exc)), 428
            except PreparazioneRejected as exc:
                context = g.get("_preparazioni_command_context") or {}
                return jsonify(ok=False, code=exc.result["code"], message=str(exc),
                               rejectedCommand={**exc.result, **context}), 409 if exc.result["code"] == "conflict" else 400
            except PreparazioneConflict as exc:
                return jsonify(ok=False, code="conflict", message=str(exc)), 409
            except ValueError as exc:
                return jsonify(ok=False, code="validation", message=str(exc)), 400
            except Exception:
                app.logger.exception("Comando preparazione non confermato: %s", function.__name__)
                return jsonify(ok=False, code="outcome_not_confirmed", message=
                    "Salvataggio non confermato. La bozza è conservata: verifica l'esito prima di riprovare."), 503
        return wrapped
    return decorate


def persistent(manager):
    return bool(getattr(manager, "write_protocol", {}).get("persistentCommands"))


def command_input(body, *, start=False):
    if not isinstance(body, dict):
        raise ValueError("Richiesta di preparazione non valida.")
    command, revision = body.get("commandKey"), body.get("expectedRevision")
    if not command or type(revision) is not int or revision < 0 or (start and revision != 0):
        raise PreconditionRequired("Il salvataggio richiede il comando e la versione della bozza. Nessuna modifica registrata.")
    return command, revision, {key: value for key, value in body.items() if key not in {"commandKey", "expectedRevision"}}


def confirm(manager, result, command):
    from pct.wizard_pro import SessioneWizardPro
    session = SessioneWizardPro.from_dict(result["record"])
    session.sql_revision = result["revision"]
    g._preparazioni_confirmed_command = {"scope": manager.write_protocol["scope"], "commandKey": command,
        "sessionId": session.id, "committedRevision": result["revision"]}
    return session


def command_context(manager, key, command, revision):
    g._preparazioni_command_context = {"scope": manager.write_protocol["scope"], "sessionId": key,
        "commandKey": command, "expectedRevision": revision}
