from __future__ import annotations

from dataclasses import dataclass

from lex.tools import editor_ai
from pct.editor_ai.models import (
    AttoAIEditProposal,
    AttoAIGenerationResult,
    AttoAIRecord,
    AttoAIVersion,
    AttoDraftPlan,
    AttoDraftSection,
    FascicoloEditorAIContext,
    utc_now,
)


@dataclass
class FakeFascicolo:
    id: str = "fas-1"
    tipo: str = "civile"


class FakeFascicoli:
    def get(self, fascicolo_id):
        return FakeFascicolo(fascicolo_id)


class FakeTemplateRepository:
    def tutti(self):
        return [{"id": "comparsa", "titolo": "Comparsa di costituzione", "area": "civile"}]

    def get(self, template_id):
        return {"id": template_id, "titolo": "Comparsa di costituzione", "area": "civile"}


def _record() -> AttoAIRecord:
    now = utc_now()
    return AttoAIRecord(
        id="atto-ai-1",
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        tipo_atto="Comparsa",
        template_id="comparsa",
        title="Comparsa di costituzione",
        status="draft",
        editor_document_id="doc-editor-1",
        current_version_id="ver-1",
        created_by="lex",
        created_at=now,
        updated_at=now,
    )


class FakeEditorAIService:
    def __init__(self):
        self.template_repository = FakeTemplateRepository()
        self.fascicoli_repository = FakeFascicoli()
        self.calls: list[tuple] = []

    def collect_fascicolo_context(self, **kwargs):
        self.calls.append(("context", kwargs["fascicolo_id"]))
        return FascicoloEditorAIContext(
            tenant_id=kwargs["tenant_id"],
            fascicolo_id=kwargs["fascicolo_id"],
            facts={"cliente": "Cliente Rossi", "oggetto": "Opposizione"},
            documents=[{"document_id": "doc-ready", "filename": "contratto.pdf", "status": "ready"}],
            missing_fields=[],
        )

    def generate_editor_draft(self, request, user_context):
        self.calls.append(("generate", request.fascicolo_id, request.template_id, tuple(request.document_ids)))
        plan = AttoDraftPlan(
            title="Comparsa di costituzione",
            tipo_atto=request.tipo_atto,
            template_id=request.template_id,
            sections=[AttoDraftSection(id="premesse", heading="Premesse in fatto", level=1, purpose="Fatti")],
        )
        version = AttoAIVersion(
            id="ver-1",
            atto_ai_id="atto-ai-1",
            tenant_id=request.tenant_id,
            fascicolo_id=request.fascicolo_id,
            version_number=1,
            source="ai_generation",
            editor_document_snapshot={},
            docx_path=None,
            pdf_path=None,
            created_by="lex",
            created_at=utc_now(),
        )
        return AttoAIGenerationResult(
            record=_record(),
            version=version,
            sources=[],
            plan=plan,
            open_url="/fascicoli/fas-1/documenti/doc-editor-1/editor",
            readback={"text": "Bozza riletta"},
            missing_fields=[],
            warnings=[],
        )

    def read_editor_document_for_lex(self, **kwargs):
        self.calls.append(("read", kwargs["editor_document_id"]))
        return {"editor_document_id": kwargs["editor_document_id"], "text": "Documento riletto dall'editor"}

    def propose_editor_edits(self, **kwargs):
        self.calls.append(("propose", kwargs["atto_ai_id"], kwargs["instructions"]))
        return [
            AttoAIEditProposal(
                id="edit-1",
                atto_ai_id=kwargs["atto_ai_id"],
                version_id="ver-1",
                status="pending",
                operation_type="add_section",
                target_block_id=None,
                find_text=None,
                replace_text=None,
                insert_text="<p>Integrazione</p>",
                reason="Integrazione richiesta.",
                created_by="lex",
                created_at=utc_now(),
            )
        ]

    def export_editor_document(self, **kwargs):
        self.calls.append(("export", kwargs["export_format"]))
        return type(
            "Export",
            (),
            {
                "to_dict": lambda _self: {
                    "atto_ai_id": kwargs["atto_ai_id"],
                    "editor_document_id": "doc-editor-1",
                    "format": kwargs["export_format"],
                    "download_url": "/api/editor/fas-1/doc-editor-1/docx",
                }
            },
        )()


def test_lex_tools_generano_documento_editor_non_testo_chat():
    service = FakeEditorAIService()

    payload = editor_ai.generate_editor_draft(
        "fas-1",
        "Comparsa",
        template_id="comparsa",
        document_ids=["doc-ready"],
        service=service,
        tenant_id="tenant-a",
        user_context={"skip_permission_check": True},
    )

    assert payload["editor_document_id"] == "doc-editor-1"
    assert payload["open_url"].endswith("/editor")
    assert payload["messaggio"] == "Bozza creata nell'editor professionale IUSENTRA."
    assert ("generate", "fas-1", "comparsa", ("doc-ready",)) in service.calls


def test_lex_tools_rileggono_documento_e_propongono_modifiche_pending():
    service = FakeEditorAIService()

    readback = editor_ai.read_editor_document("fas-1", "doc-editor-1", service=service, tenant_id="tenant-a", user_context={})
    proposals = editor_ai.propose_editor_edits("fas-1", "atto-ai-1", "Aggiungi una sezione", service=service, tenant_id="tenant-a", user_context={})

    assert "Documento riletto" in readback["text"]
    assert proposals["proposals"][0]["status"] == "pending"


def test_lex_tools_template_context_ed_export():
    service = FakeEditorAIService()

    templates = editor_ai.list_template_atti(service=service, fascicolo_id="fas-1")
    context = editor_ai.collect_fascicolo_context("fas-1", service=service, tenant_id="tenant-a", user_context={})
    export = editor_ai.export_editor_document("fas-1", "atto-ai-1", "docx", service=service, tenant_id="tenant-a", user_context={})

    assert templates["templates"][0]["template_id"] == "comparsa"
    assert context["facts"]["cliente"] == "Cliente Rossi"
    assert export["download_url"].startswith("/api/editor/")


def test_prompt_registry_impone_editor_ai_per_richieste_atto():
    prompt_source = __import__("pathlib").Path("lex/prompts/prompt_builder.py").read_text(encoding="utf-8")
    registry_source = __import__("pathlib").Path("lex/tools/registry.py").read_text(encoding="utf-8")

    assert "generate_editor_draft" in prompt_source
    assert "propose_editor_edits" in prompt_source
    assert "non rispondere con una bozza lunga in chat" in prompt_source.lower()
    assert '"generate_editor_draft"' in registry_source
    assert '"propose_editor_edits"' in registry_source
