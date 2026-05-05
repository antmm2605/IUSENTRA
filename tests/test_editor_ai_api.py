from __future__ import annotations

from pathlib import Path

from pct.editor_ai.models import (
    AttoAIDraftRequest,
    AttoAIEditProposal,
    AttoAIExportResult,
    AttoAIGenerationResult,
    AttoAIRecord,
    AttoAISource,
    AttoAIVersion,
    AttoDraftPlan,
    AttoDraftSection,
    utc_now,
)
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_document_editor import _app


def _record() -> AttoAIRecord:
    now = utc_now()
    return AttoAIRecord(
        id="atto-ai-1",
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        tipo_atto="Comparsa di costituzione",
        template_id="comparsa",
        title="Comparsa di costituzione",
        status="draft",
        editor_document_id="doc-editor-1",
        current_version_id="ver-1",
        created_by="operatore",
        created_at=now,
        updated_at=now,
    )


def _version() -> AttoAIVersion:
    return AttoAIVersion(
        id="ver-1",
        atto_ai_id="atto-ai-1",
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        version_number=1,
        source="ai_generation",
        editor_document_snapshot={"text": "Bozza riletta"},
        docx_path=None,
        pdf_path=None,
        created_by="operatore",
        created_at=utc_now(),
    )


def _plan() -> AttoDraftPlan:
    return AttoDraftPlan(
        title="Comparsa di costituzione",
        tipo_atto="Comparsa di costituzione",
        template_id="comparsa",
        sections=[AttoDraftSection(id="premesse", heading="Premesse in fatto", level=1, purpose="Fatti")],
        missing_fields=["Numero RG"],
    )


def _proposal(status: str = "pending") -> AttoAIEditProposal:
    return AttoAIEditProposal(
        id="edit-1",
        atto_ai_id="atto-ai-1",
        version_id="ver-1",
        status=status,
        operation_type="add_section",
        target_block_id=None,
        find_text=None,
        replace_text=None,
        insert_text="<p>Integrazione</p>",
        reason="Integrazione richiesta.",
        created_by="operatore",
        created_at=utc_now(),
    )


class FakeEditorAIService:
    def __init__(self):
        self.last_request: AttoAIDraftRequest | None = None

    def bootstrap(self, **_kwargs):
        return {
            "mock_fallback": False,
            "fascicolo_id": "fas-1",
            "templates": [{"id": "comparsa", "titolo": "Comparsa di costituzione"}],
            "documents": [{"document_id": "doc-ready", "filename": "contratto.pdf", "status": "ready"}],
            "missing_fields": [],
            "capabilities": {"generate_draft": True},
        }

    def generate_editor_draft(self, request_model, _user_context):
        self.last_request = request_model
        return AttoAIGenerationResult(
            record=_record(),
            version=_version(),
            sources=[
                AttoAISource(
                    id="src-1",
                    atto_ai_id="atto-ai-1",
                    source_type="documento_fascicolo",
                    source_id="doc-ready",
                    document_id="doc-ready",
                    page_number=1,
                    quote="Clausola",
                    sha256="a" * 64,
                    reason="Fonte usata.",
                )
            ],
            plan=_plan(),
            open_url="/fascicoli/fas-1/documenti/doc-editor-1/editor",
            readback={"editor_document_id": "doc-editor-1", "filename": "atto.html"},
            missing_fields=["Numero RG"],
            warnings=[],
        )

    def get_atto_ai(self, **_kwargs):
        return {"record": _record(), "versions": [_version()], "sources": [], "edit_proposals": [_proposal()]}

    def propose_editor_edits(self, **_kwargs):
        return [_proposal()]

    def accept_edit(self, **_kwargs):
        return {"record": _record(), "version": _version(), "proposal": _proposal("accepted"), "warnings": []}

    def reject_edit(self, **_kwargs):
        return _proposal("rejected")

    def export_editor_document(self, **_kwargs):
        return AttoAIExportResult(
            atto_ai_id="atto-ai-1",
            editor_document_id="doc-editor-1",
            format="docx",
            download_url="/api/editor/fas-1/doc-editor-1/docx",
            version_id="ver-1",
        )


def _client(tmp_path: Path, monkeypatch):
    fake = FakeEditorAIService()
    monkeypatch.setattr("web.blueprints.api_v1_editor_ai.build_editor_ai_service", lambda: fake)
    app = _app(tmp_path)
    _crea_operatore(app)
    client = app.test_client()
    _login(client)
    return client, fake


def test_bootstrap_mock_fallback_false(tmp_path: Path, monkeypatch):
    client, _fake = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/ui/fascicoli/fas-1/editor-ai/bootstrap")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mock_fallback"] is False
    assert payload["templates"][0]["id"] == "comparsa"


def test_genera_ritorna_open_url_e_rispetta_payload(tmp_path: Path, monkeypatch):
    client, fake = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/ui/fascicoli/fas-1/editor-ai/genera",
        json={"template_id": "comparsa", "tipo_atto": "Comparsa", "document_ids": ["doc-ready"]},
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["mock_fallback"] is False
    assert payload["open_url"] == "/fascicoli/fas-1/documenti/doc-editor-1/editor"
    assert fake.last_request is not None
    assert fake.last_request.language == "it"


def test_modifiche_ed_export_non_espongono_path_assoluti(tmp_path: Path, monkeypatch):
    client, _fake = _client(tmp_path, monkeypatch)

    proposals = client.post(
        "/api/v1/ui/fascicoli/fas-1/editor-ai/atto-ai-1/modifiche/proponi",
        json={"istruzioni": "Aggiungi una sezione sulle prove"},
    )
    export = client.post("/api/v1/ui/fascicoli/fas-1/editor-ai/atto-ai-1/export", json={"format": "docx"})

    assert proposals.status_code == 200
    assert proposals.get_json()["proposals"][0]["status"] == "pending"
    assert export.status_code == 200
    payload = export.get_json()
    assert payload["export"]["download_url"].startswith("/api/editor/")
    assert ":\\" not in str(payload)
