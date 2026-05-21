"""Tool mutanti controllati per Lex Workflow Agents."""

from __future__ import annotations

from datetime import date
from typing import Any

from flask import g, has_request_context

from lex.agents.audit import record_agent_audit
from lex.agents.policies import validate_client_payload
from lex.agents.serialization import redact_value
from lex.agents.storage import WorkflowAgentActionStore


def _actor() -> str:
    if has_request_context():
        utente = g.get("utente_corrente")
        username = str(getattr(utente, "username", "") or "").strip()
        if username:
            return username
    return "workflow-agent"


def _safe_payload(kwargs: dict[str, Any]) -> dict[str, Any]:
    validate_client_payload(kwargs)
    return {str(key): value for key, value in kwargs.items() if value not in (None, "")}


def _stored_action(action_type: str, payload: dict[str, Any], *, message: str) -> dict[str, Any]:
    item = WorkflowAgentActionStore().append(action_type, payload)
    record_agent_audit(f"workflow.tool.{action_type}", actor=_actor(), details=item)
    return {
        "ok": True,
        "action_id": item["id"],
        "action_type": action_type,
        "message": message,
        "payload": redact_value(payload),
    }


class CreateTaskTool:
    tool_name = "create_task"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        payload = _safe_payload(kwargs)
        return _stored_action("task", payload, message="Attività operativa registrata nella coda agentica approvata.")


class CreateDeadlineTool:
    tool_name = "create_deadline"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        payload = _safe_payload(kwargs)
        titolo = str(payload.get("titolo") or payload.get("title") or "").strip()
        data_scadenza = str(payload.get("data_scadenza") or payload.get("due_date") or "").strip()
        if titolo and data_scadenza:
            try:
                from pct.scadenziario import TipoTermine
                from web.helpers import get_scadenziario

                scadenza = get_scadenziario().nuova(
                    titolo=titolo,
                    tipo=TipoTermine.ALTRO,
                    data_scadenza=data_scadenza,
                    id_fascicolo=str(payload.get("fascicolo_id") or ""),
                    descrizione=str(payload.get("descrizione") or ""),
                    giorni_preavviso=list(payload.get("giorni_preavviso") or [7, 3, 1]),
                    note=str(payload.get("note") or "Creata da Regia Agentica Studio dopo approvazione."),
                    perentorio=bool(payload.get("perentorio", False)),
                )
                result = {"ok": True, "id": scadenza.id, "titolo": scadenza.titolo, "data_scadenza": scadenza.data_scadenza}
                record_agent_audit("workflow.tool.create_deadline", actor=_actor(), details=result)
                return result
            except Exception as exc:
                payload["errore_repository"] = str(exc)
        return _stored_action("deadline", payload, message="Promemoria registrato nella coda agentica: dati da completare prima della creazione scadenza.")


class CreateDocumentDraftTool:
    tool_name = "create_document_draft"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        payload = _safe_payload(kwargs)
        fascicolo_id = str(payload.get("fascicolo_id") or "").strip()
        tipo_atto = str(payload.get("tipo_atto") or payload.get("tipo") or "bozza").strip()
        if fascicolo_id:
            try:
                from lex.tools.editor_ai import GenerateEditorDraftTool

                result = GenerateEditorDraftTool().run(
                    fascicolo_id=fascicolo_id,
                    tipo_atto=tipo_atto,
                    template_id=str(payload.get("template_id") or ""),
                    istruzioni_utente=str(payload.get("istruzioni") or payload.get("query") or ""),
                    document_ids=list(payload.get("document_ids") or []),
                )
                record_agent_audit("workflow.tool.create_document_draft", actor=_actor(), details=result)
                return redact_value(result)
            except Exception as exc:
                payload["errore_editor"] = str(exc)
        return _stored_action("document_draft", payload, message="Bozza documento registrata nella coda agentica per completamento nell'editor.")


class CreateTimesheetEntryTool:
    tool_name = "create_timesheet_entry"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        payload = _safe_payload(kwargs)
        try:
            from pct.timesheet import StatoTimesheet
            from web.helpers import get_timesheet

            voce = get_timesheet().crea(
                descrizione=str(payload.get("descrizione") or "Attività proposta dalla regia agentica"),
                minuti=int(payload.get("minuti") or 30),
                id_fascicolo=str(payload.get("fascicolo_id") or ""),
                id_cliente=str(payload.get("cliente_id") or payload.get("id_cliente") or ""),
                username=_actor(),
                data_attivita=str(payload.get("data_attivita") or date.today().isoformat()),
                valore_unitario=float(payload.get("valore_unitario") or 0.0),
                fatturabile=bool(payload.get("fatturabile", True)),
                stato=StatoTimesheet.APERTO,
                origine="Regia Agentica Studio",
                note=str(payload.get("note") or ""),
                dati_json={"workflow_agents": True},
            )
            result = {"ok": True, "id": voce.id, "descrizione": voce.descrizione, "minuti": voce.minuti, "stato": voce.stato.value}
            record_agent_audit("workflow.tool.create_timesheet_entry", actor=_actor(), details=result)
            return result
        except Exception as exc:
            payload["errore_repository"] = str(exc)
            return _stored_action("timesheet_entry", payload, message="Voce timesheet registrata nella coda agentica per completamento dati.")


class CreateInvoiceDraftTool:
    tool_name = "create_invoice_draft"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        payload = _safe_payload(kwargs)
        cliente_id = str(payload.get("cliente_id") or payload.get("id_cliente") or "").strip()
        try:
            from pct.fatturazione import VoceParcella
            from web.helpers import get_fatturazione

            importo = float(payload.get("importo") or payload.get("prezzo_unitario") or 0.0)
            if not cliente_id:
                raise ValueError("Cliente richiesto per creare una parcella in bozza.")
            parcella = get_fatturazione().crea(
                id_cliente=cliente_id,
                id_fascicolo=str(payload.get("fascicolo_id") or ""),
                creato_da=_actor(),
                origine="Regia Agentica Studio",
                note=str(payload.get("descrizione") or payload.get("note") or ""),
                voci=[VoceParcella(descrizione=str(payload.get("descrizione") or "Attività professionale"), prezzo_unitario=importo)],
                dati_personalizzati={"workflow_agents": True},
            )
            result = {"ok": True, "id": parcella.id, "numero": parcella.numero, "stato": parcella.stato.value, "totale": parcella.totale}
            record_agent_audit("workflow.tool.create_invoice_draft", actor=_actor(), details=result)
            return result
        except Exception as exc:
            payload["errore_repository"] = str(exc)
            return _stored_action("invoice_draft", payload, message="Parcella in bozza registrata nella coda agentica per completamento dati.")


class CreateClientDraftTool:
    tool_name = "create_client_draft"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        payload = _safe_payload(kwargs)
        try:
            from pct.clienti import TipoCliente
            from web.helpers import get_clienti

            tipo = TipoCliente(str(payload.get("tipo") or "PERSONA_FISICA"))
            cliente, creato = get_clienti().crea_o_recupera_potenziale(
                tipo=tipo,
                nome=str(payload.get("nome") or ""),
                cognome=str(payload.get("cognome") or ""),
                ragione_sociale=str(payload.get("ragione_sociale") or ""),
                codice_fiscale=str(payload.get("codice_fiscale") or ""),
                partita_iva=str(payload.get("partita_iva") or ""),
                provenienza="Regia Agentica Studio",
                avvocato_referente=_actor(),
                note=str(payload.get("note") or ""),
            )
            result = {"ok": True, "id": cliente.id, "nome": cliente.nome_completo, "creato": creato, "stato": cliente.stato.value}
            record_agent_audit("workflow.tool.create_client_draft", actor=_actor(), details=result)
            return redact_value(result)
        except Exception as exc:
            payload["errore_repository"] = str(exc)
            return _stored_action("client_draft", payload, message="Cliente potenziale registrato nella coda agentica per completamento dati.")


class CreateFascicoloDraftTool:
    tool_name = "create_fascicolo_draft"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        payload = _safe_payload(kwargs)
        try:
            from pct.fascicoli import TipoFascicolo
            from web.helpers import get_fascicoli

            tipo = TipoFascicolo(str(payload.get("tipo") or "ALTRO"))
            fascicolo = get_fascicoli().nuovo(
                titolo=str(payload.get("titolo") or payload.get("oggetto") or "Nuovo fascicolo"),
                tipo=tipo,
                id_cliente=str(payload.get("cliente_id") or payload.get("id_cliente") or ""),
                nome_cliente=str(payload.get("nome_cliente") or ""),
                oggetto=str(payload.get("oggetto") or ""),
                note=str(payload.get("note") or "Creato da Regia Agentica Studio dopo approvazione."),
                avvocato_referente=_actor(),
            )
            result = {"ok": True, "id": fascicolo.id, "numero": fascicolo.numero, "titolo": fascicolo.titolo, "stato": fascicolo.stato.value}
            record_agent_audit("workflow.tool.create_fascicolo_draft", actor=_actor(), details=result)
            return result
        except Exception as exc:
            payload["errore_repository"] = str(exc)
            return _stored_action("fascicolo_draft", payload, message="Fascicolo in bozza registrato nella coda agentica per completamento dati.")


class CreatePecDraftTool:
    tool_name = "create_pec_draft"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        payload = _safe_payload(kwargs)
        payload["send_blocked"] = True
        return _stored_action("pec_draft", payload, message="Bozza PEC salvata senza invio automatico.")


class UpdateChecklistTool:
    tool_name = "update_checklist"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        payload = _safe_payload(kwargs)
        return _stored_action("checklist_update", payload, message="Aggiornamento checklist registrato dopo approvazione.")

