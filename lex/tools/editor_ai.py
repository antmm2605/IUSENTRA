"""Tool Lex per generazione atti nell'editor professionale IUSENTRA."""

from __future__ import annotations

from typing import Any

from pct.editor_ai import AttoAIDraftRequest
from pct.editor_ai.template_resolver import EditorAITemplateResolver

from .base import BaseLexTool


def _runtime_service():
    from web.services.editor_ai_runtime import build_editor_ai_service

    return build_editor_ai_service()


def _runtime_tenant_id() -> str:
    from web.services.editor_ai_runtime import editor_ai_tenant_id

    return editor_ai_tenant_id()


def _runtime_user_context() -> dict[str, Any]:
    from web.services.editor_ai_runtime import editor_ai_user_context

    return editor_ai_user_context()


def list_template_atti(*, service: Any = None, fascicolo_id: str = "") -> dict[str, Any]:
    svc = service or _runtime_service()
    fascicolo = None
    if fascicolo_id:
        getter = getattr(svc.fascicoli_repository, "get", None)
        fascicolo = getter(fascicolo_id) if callable(getter) else None
    templates = EditorAITemplateResolver(svc.template_repository).list_available_templates_for_fascicolo(fascicolo)
    return {
        "templates": [
            {
                "template_id": str(item.get("id") or item.get("codice") or ""),
                "titolo": str(item.get("titolo") or item.get("name") or ""),
                "area": str(item.get("area") or item.get("materia") or ""),
                "canale_telematico": str(item.get("canale_telematico") or item.get("canale_deposito") or ""),
            }
            for item in templates
            if str(item.get("id") or item.get("codice") or "").strip()
        ]
    }


def read_template_atto(template_id: str, *, service: Any = None) -> dict[str, Any]:
    svc = service or _runtime_service()
    schema = EditorAITemplateResolver(svc.template_repository).read_template_schema(template_id)
    return {"template": schema}


def collect_fascicolo_context(fascicolo_id: str, *, service: Any = None, tenant_id: str | None = None, user_context: object | None = None) -> dict[str, Any]:
    svc = service or _runtime_service()
    context = svc.collect_fascicolo_context(
        tenant_id=tenant_id or _runtime_tenant_id(),
        fascicolo_id=fascicolo_id,
        user_context=user_context if user_context is not None else _runtime_user_context(),
        include_document_text=False,
    )
    return context.to_dict()


def generate_editor_draft(
    fascicolo_id: str,
    tipo_atto: str,
    template_id: str = "",
    istruzioni_utente: str = "",
    document_ids: list[str] | None = None,
    *,
    service: Any = None,
    tenant_id: str | None = None,
    user_context: object | None = None,
) -> dict[str, Any]:
    svc = service or _runtime_service()
    tenant = tenant_id or _runtime_tenant_id()
    request = AttoAIDraftRequest(
        tenant_id=tenant,
        fascicolo_id=fascicolo_id,
        tipo_atto=tipo_atto,
        template_id=template_id,
        istruzioni_utente=istruzioni_utente,
        document_ids=list(document_ids or []),
        use_fascicolo_context=True,
        language="it",
    )
    result = svc.generate_editor_draft(request, user_context if user_context is not None else _runtime_user_context())
    return {
        "atto_ai_id": result.record.id,
        "editor_document_id": result.record.editor_document_id,
        "open_url": result.open_url,
        "tipo_atto": result.record.tipo_atto,
        "sezioni": [section.heading for section in result.plan.sections],
        "fonti_usate": [source.to_dict() for source in result.sources],
        "dati_da_completare": result.missing_fields,
        "warnings": result.warnings,
        "messaggio": "Bozza creata nell'editor professionale IUSENTRA.",
    }


def read_editor_document(
    fascicolo_id: str,
    editor_document_id: str,
    *,
    service: Any = None,
    tenant_id: str | None = None,
    user_context: object | None = None,
) -> dict[str, Any]:
    svc = service or _runtime_service()
    return svc.read_editor_document_for_lex(
        tenant_id=tenant_id or _runtime_tenant_id(),
        fascicolo_id=fascicolo_id,
        editor_document_id=editor_document_id,
        user_context=user_context if user_context is not None else _runtime_user_context(),
    )


def propose_editor_edits(
    fascicolo_id: str,
    atto_ai_id: str,
    instructions: str,
    *,
    service: Any = None,
    tenant_id: str | None = None,
    user_context: object | None = None,
) -> dict[str, Any]:
    svc = service or _runtime_service()
    proposals = svc.propose_editor_edits(
        tenant_id=tenant_id or _runtime_tenant_id(),
        fascicolo_id=fascicolo_id,
        atto_ai_id=atto_ai_id,
        instructions=instructions,
        user_context=user_context if user_context is not None else _runtime_user_context(),
    )
    return {"proposals": [proposal.to_dict() for proposal in proposals], "messaggio": "Modifiche proposte in attesa di accettazione."}


def export_editor_document(
    fascicolo_id: str,
    atto_ai_id: str,
    export_format: str = "docx",
    *,
    service: Any = None,
    tenant_id: str | None = None,
    user_context: object | None = None,
) -> dict[str, Any]:
    svc = service or _runtime_service()
    result = svc.export_editor_document(
        tenant_id=tenant_id or _runtime_tenant_id(),
        fascicolo_id=fascicolo_id,
        atto_ai_id=atto_ai_id,
        export_format=export_format,
        user_context=user_context if user_context is not None else _runtime_user_context(),
    )
    return result.to_dict()


class ListTemplateAttiTool(BaseLexTool):
    tool_name = "list_template_atti"

    def run(self, **kwargs):
        return list_template_atti(fascicolo_id=str(kwargs.get("fascicolo_id") or ""))


class ReadTemplateAttoTool(BaseLexTool):
    tool_name = "read_template_atto"

    def run(self, **kwargs):
        return read_template_atto(str(kwargs.get("template_id") or ""))


class CollectFascicoloContextTool(BaseLexTool):
    tool_name = "collect_fascicolo_context"

    def run(self, **kwargs):
        return collect_fascicolo_context(str(kwargs.get("fascicolo_id") or ""))


class GenerateEditorDraftTool(BaseLexTool):
    tool_name = "generate_editor_draft"

    def run(self, **kwargs):
        return generate_editor_draft(
            str(kwargs.get("fascicolo_id") or ""),
            str(kwargs.get("tipo_atto") or ""),
            str(kwargs.get("template_id") or ""),
            str(kwargs.get("istruzioni_utente") or kwargs.get("instructions") or ""),
            list(kwargs.get("document_ids") or []),
        )


class ReadEditorDocumentTool(BaseLexTool):
    tool_name = "read_editor_document"

    def run(self, **kwargs):
        return read_editor_document(
            str(kwargs.get("fascicolo_id") or ""),
            str(kwargs.get("editor_document_id") or kwargs.get("document_id") or ""),
        )


class ProposeEditorEditsTool(BaseLexTool):
    tool_name = "propose_editor_edits"

    def run(self, **kwargs):
        return propose_editor_edits(
            str(kwargs.get("fascicolo_id") or ""),
            str(kwargs.get("atto_ai_id") or ""),
            str(kwargs.get("instructions") or kwargs.get("istruzioni") or ""),
        )


class ExportEditorDocumentTool(BaseLexTool):
    tool_name = "export_editor_document"

    def run(self, **kwargs):
        return export_editor_document(
            str(kwargs.get("fascicolo_id") or ""),
            str(kwargs.get("atto_ai_id") or ""),
            str(kwargs.get("format") or kwargs.get("formato") or "docx"),
        )
