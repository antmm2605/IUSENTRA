"""Policy fail-closed per Lex Workflow Agents."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .models import AgentStep


class WorkflowAgentPolicyError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 403):
        super().__init__(message)
        self.code = code
        self.public_message = message
        self.status_code = status_code


CLIENT_CONTROL_KEYS = {"tenant_id", "studio_id", "user_id", "token", "api_key", "path", "percorso", "filesystem_path", "root"}
FORBIDDEN_TOOL_NAMES = {
    "send_pec",
    "invia_pec",
    "deposito_telematico",
    "deposit_atto",
    "firma_digitale",
    "sign_document",
    "delete_client",
    "delete_fascicolo",
    "delete_document",
    "update_roles",
    "export_sensitive_external",
}
FORBIDDEN_ACTION_WORDS = re.compile(r"(invia.*pec|deposit|firma|cancell|elimina|ruol|utente|provider estern)", re.IGNORECASE)

READ_PERMISSION_MAP = {
    "fascicolo": ("fascicoli.leggi",),
    "agenda": ("agenda.leggi",),
    "scadenziario": ("scadenziario.leggi",),
    "telematico": ("telematico.leggi",),
    "giurisprudenza": ("ai.usa",),
    "legal_intelligence": ("ai.usa",),
    "operational_knowledge": ("ai.usa",),
    "template_atti": ("ai.usa",),
    "preventivi": ("fatturazione.leggi",),
    "list_template_atti": ("ai.usa",),
    "read_template_atto": ("ai.usa",),
    "collect_fascicolo_context": ("fascicoli.leggi", "ai.usa"),
}

WRITE_PERMISSION_MAP = {
    "create_task": ("agenda.scrivi",),
    "create_deadline": ("scadenziario.scrivi",),
    "create_document_draft": ("ai.usa", "fascicoli.scrivi"),
    "create_timesheet_entry": ("agenda.scrivi",),
    "create_invoice_draft": ("fatturazione.scrivi",),
    "create_client_draft": ("clienti.scrivi",),
    "create_fascicolo_draft": ("fascicoli.scrivi",),
    "create_pec_draft": ("messaggi.scrivi",),
    "update_checklist": ("telematico.valida",),
}


def required_permissions_for_tool(tool_name: str, *, mutates_state: bool = False) -> tuple[str, ...]:
    name = str(tool_name or "").strip()
    if mutates_state or name in WRITE_PERMISSION_MAP:
        return WRITE_PERMISSION_MAP.get(name, ())
    return READ_PERMISSION_MAP.get(name, ())


def _walk_control_keys(payload: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            clean = str(key or "").strip().lower()
            next_path = f"{path}.{clean}" if path else clean
            if clean in CLIENT_CONTROL_KEYS:
                found.append(next_path)
            found.extend(_walk_control_keys(value, next_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_walk_control_keys(value, f"{path}[{index}]"))
    return found


def validate_client_payload(payload: dict[str, Any]) -> None:
    violations = _walk_control_keys(payload)
    if violations:
        raise WorkflowAgentPolicyError(
            "client_control_param",
            "La richiesta contiene parametri di controllo non accettati.",
            status_code=400,
        )


def assert_tenant_context(tenant_scope: str) -> None:
    if not str(tenant_scope or "").strip():
        raise WorkflowAgentPolicyError("tenant_context_required", "Contesto studio non disponibile.", status_code=409)


def assert_no_forbidden_tool(tool_name: str, payload: dict[str, Any] | None = None) -> None:
    name = str(tool_name or "").strip().lower()
    text = " ".join([name, str(payload or {})])
    if name in FORBIDDEN_TOOL_NAMES or FORBIDDEN_ACTION_WORDS.search(text):
        raise WorkflowAgentPolicyError("forbidden_agent_action", "Azione agentica vietata dalle policy di studio.")


def assert_permissions(required: Iterable[str], granted: Iterable[str] | None) -> None:
    requested = {str(item).strip() for item in required if str(item).strip()}
    if not requested:
        return
    granted_set = {str(item).strip() for item in granted or () if str(item).strip()}
    if not requested.issubset(granted_set):
        missing = ", ".join(sorted(requested - granted_set))
        raise WorkflowAgentPolicyError("insufficient_permissions", f"Permessi insufficienti: {missing}.")


def assert_step_executable(
    step: AgentStep,
    *,
    tenant_scope: str,
    allow_writes: bool,
    write_feature_enabled: bool,
    approved: bool,
    user_permissions: Iterable[str] | None,
) -> None:
    assert_tenant_context(tenant_scope)
    assert_no_forbidden_tool(step.tool_name, step.input_json)
    validate_client_payload(step.input_json)
    required = step.required_permissions or required_permissions_for_tool(step.tool_name, mutates_state=step.mutates_state)
    assert_permissions(required, user_permissions)
    if not step.mutates_state:
        return
    if not allow_writes:
        raise WorkflowAgentPolicyError("write_requires_approval_queue", "La scrittura richiede revisione e approvazione.")
    if not approved:
        raise WorkflowAgentPolicyError("approval_required", "Approvazione umana richiesta prima della scrittura.")
    if not write_feature_enabled:
        raise WorkflowAgentPolicyError("agent_write_feature_disabled", "Scritture agentiche non attive per questo studio.")
