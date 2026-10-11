"""Un solo protocollo di comando per UI React e scrittori classici."""
from __future__ import annotations

from web.services import preparazione_udienza_runtime as native
from pct.udienze.delivery import deliver_outcome
from pct.udienze.repository import PreparazioneConflict, PreparazioneRejected

OPERATIONS = {"passo", "documento", "documento-extra", "verifica", "esito", "archivia", "elimina"}


def _shape(values, allowed):
    if not isinstance(values, dict) or set(values) - set(allowed):
        raise ValueError("Campi del comando non previsti.")


def _boolean(value):
    if type(value) is not bool:
        raise ValueError("Conferma del comando non valida.")
    return value


def _text(value, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("Testo del comando non valido o troppo lungo.")
    return value


def apply_command(conn, session, operation, intent, *, tenant, actor, today):
    """Il repository mantiene versione, audit e commit; qui le regole native."""
    if operation == "esito":
        return deliver_outcome(conn, session, intent, tenant=tenant, actor=actor, today=today)
    if operation == "passo":
        _shape(intent, {"passo", "campi", "conferma", "documenti", "extra"})
        step = intent.get("passo")
        if type(step) is not int or not 1 <= step <= 4:
            raise ValueError("Passo non valido: l'esito ha un comando dedicato.")
        fields = intent.get("campi", {})
        _shape(fields, set(native.CAMPI_PASSO.get(step, ())) | ({"tipo_udienza"} if step == 1 else set()))
        for key, value in fields.items():
            if key.startswith("precheck_") and key != "precheck_note":
                _boolean(value)
            else:
                _text(value, 4000)
        if "documenti" in intent or "extra" in intent:
            if step != 2:
                raise ValueError("La checklist appartiene al passo documenti.")
            rows = intent.get("documenti", [])
            if not isinstance(rows, list) or len(rows) != len(session.checklist_documenti):
                raise PreparazioneConflict("Checklist cambiata: bozza conservata, nessuna riga scartata.")
            for index, row in enumerate(rows):
                _shape(row, {"id_documento", "label", "stato", "note"})
                original = session.checklist_documenti[index]
                if (row.get("id_documento"), row.get("label")) != (original.get("id_documento"), original.get("label")):
                    raise PreparazioneConflict("Identità del documento cambiata nella checklist.")
                native.imposta_documento(session, index, _text(row.get("stato"), 40))
                original["note"] = _text(row.get("note", ""), 4000)
            if intent.get("extra"):
                native.aggiungi_documento(session, _text(intent["extra"], 200))
        native.salva_passo(session, step, fields, conferma=_boolean(intent.get("conferma", False)))
    elif operation == "documento":
        _shape(intent, {"indice", "stato"})
        index = intent.get("indice")
        if type(index) is not int:
            raise ValueError("Indice del documento non valido.")
        native.imposta_documento(session, index, _text(intent.get("stato"), 40))
    elif operation == "documento-extra":
        _shape(intent, {"etichetta"})
        label = " ".join(_text(intent.get("etichetta"), 200).split())
        if label and any(not row.get("id_documento") and row.get("label") == label for row in session.checklist_documenti):
            return {"kind": operation, "status": "already_present"}
        native.aggiungi_documento(session, label)
    elif operation == "verifica":
        _shape(intent, {"id", "fatta"})
        native.imposta_verifica(session, _text(intent.get("id"), 200), _boolean(intent.get("fatta")))
    elif operation in {"archivia", "elimina"}:
        _shape(intent, set())
        if operation == "archivia":
            session.stato = "archiviato"
        # Eliminare la preparazione non annulla eventi, termini o attività già
        # consegnati. Restano i riscontri del comando e le fonti nei presìdi.
    else:
        raise ValueError("Azione della preparazione non prevista.")
    return {"kind": operation, "status": "confirmed"}


def execute_command(repository, key, operation, intent, *, command_key, expected_revision, today):
    if operation not in OPERATIONS:
        raise ValueError("Azione della preparazione non prevista.")
    try:
        return repository.execute(key, operation, intent, command_key=command_key, expected_revision=expected_revision,
            apply=lambda conn, session, values: apply_command(conn, session, operation, values,
                tenant=repository.tenant, actor=repository.actor, today=today))
    except PreparazioneRejected:
        raise
    except (PreparazioneConflict, ValueError) as exc:
        # Il rifiuto è definitivo per l'intento: un retry non riattiva il comando
        # quando la fonte cambia. Guasti del database non diventano rifiuti.
        receipt = repository.reject(key, operation, intent, command_key=command_key, expected_revision=expected_revision,
            code="conflict" if isinstance(exc, PreparazioneConflict) else "validation", message=str(exc))
        if receipt.get("status") != "rejected":
            return receipt
        raise PreparazioneRejected(receipt) from exc
