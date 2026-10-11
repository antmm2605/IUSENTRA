"""Traduzione dei moduli classici nel medesimo comando SQL della UI React."""
from datetime import datetime
from zoneinfo import ZoneInfo
import json

from web.services.preparazione_udienza_http_commands import command_input
from web.services.preparazione_udienza_runtime import CAMPI_PASSO


def form_command(form, *, start=False):
    revision = form.get("expectedRevision", "")
    if not revision.isdecimal():
        revision = None
    else:
        revision = int(revision)
    command, revision, _ = command_input({"commandKey": form.get("commandKey"), "expectedRevision": revision}, start=start)
    return command, revision


def save_form(manager, session, step, form):
    command, revision = form_command(form)
    if step == 5:
        operation = "esito"
        intent = {"esito": form.get("esito", ""), "rinvioData": form.get("esito_rinvio_data", ""),
                  "rinvioOra": form.get("esito_rinvio_ora", "09:00"), "noteVerbale": form.get("esito_note_verbale", ""),
                  "azioni": form.get("esito_azioni", ""), "termini": json.loads(form.get("terminiIntent", "[]"))}
    else:
        operation = "passo"
        fields = {key: bool(form.get(key)) if key.startswith("precheck_") and key != "precheck_note"
                  else form.get(key, "") for key in CAMPI_PASSO.get(step, ())}
        intent = {"passo": step, "campi": fields, "conferma": True}
        if step == 2:
            count = form.get("documentCount", "")
            if not count.isdecimal() or int(count) > 10000:
                raise ValueError("Identità del modulo documenti incompleta: nessuna riga salvata.")
            intent.update(documenti=[{"id_documento": form.get(f"doc_id_{index}", ""), "label": form.get(f"doc_label_{index}", ""),
                "stato": form.get(f"doc_stato_{index}", "da_portare"), "note": form.get(f"doc_note_{index}", "")}
                for index in range(int(count))], extra=form.get("doc_extra_label", ""))
    return manager.execute(session.id, operation, intent, command_key=command, expected_revision=revision,
                           today=datetime.now(ZoneInfo("Europe/Rome")).date())
