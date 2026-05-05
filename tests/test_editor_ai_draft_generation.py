from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pct.document_intelligence.models import DocumentAIPageText, DocumentAIRecord, DocumentAIText
from pct.editor_ai import AttoAIDraftRequest, EditorAIRepository, EditorAIService
from pct.editor_ai.models import utc_now
from pct.fascicoli import GestioneFascicoli, TipoFascicolo


@dataclass
class FakeUser:
    id: str = "user-editor-ai"

    def ha_permesso(self, permission: str) -> bool:
        return permission in {"fascicoli.leggi", "fascicoli.scrivi"}


class FakeTemplateRepository:
    template = {
        "id": "comparsa_costituzione",
        "titolo": "Comparsa di costituzione",
        "area": "civile",
        "campi_guidati": [
            {"name": "cliente", "label": "Cliente", "required": True},
            {"name": "oggetto", "label": "Oggetto", "required": True},
        ],
        "link_compilatore_code": "comparsa_costituzione",
    }

    def tutti(self):
        return [dict(self.template)]

    def get(self, template_id: str):
        return dict(self.template) if template_id == self.template["id"] else None


class FakeDocumentAIService:
    def list_fascicolo_documents(self, tenant_id, fascicolo_id, user_context):
        return [
            DocumentAIRecord(
                id="doc-ready",
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                original_filename="contratto.pdf",
                safe_filename="contratto.pdf",
                file_type="pdf",
                mime_type="application/pdf",
                size_bytes=42,
                sha256="a" * 64,
                status="ready",
                current_version_id="ver-doc-1",
                page_count=1,
                created_by="operatore",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        ]

    def get_fascicolo_document_text(self, tenant_id, fascicolo_id, document_id, user_context):
        return DocumentAIText(
            document_id=document_id,
            version_id="ver-doc-1",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            text="Il contratto contiene una clausola risolutiva espressa.",
            pages=[DocumentAIPageText(page_number=1, text="Clausola risolutiva espressa nel contratto.")],
            extraction_engine="test",
            warnings=[],
            created_at=utc_now(),
        )


def _context():
    return {"user": FakeUser(), "user_id": "user-editor-ai"}


def _service(tmp_path: Path):
    fascicoli = GestioneFascicoli(
        str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = fascicoli.nuovo(
        "Opposizione a decreto ingiuntivo",
        TipoFascicolo.CIVILE,
        nome_cliente="Cliente Rossi",
        tribunale="Tribunale di Palmi",
        numero_rg="123/2026",
    )
    repository = EditorAIRepository(tmp_path / "editor_ai.json")
    service = EditorAIService(
        repository,
        fascicoli,
        template_repository=FakeTemplateRepository(),
        document_ai_service=FakeDocumentAIService(),
        ai_generator=lambda **_kwargs: (
            "<h1>Comparsa di costituzione</h1>"
            "<h2>Premesse in fatto</h2>"
            "<p>Il fascicolo riguarda Cliente Rossi e la clausola risolutiva espressa.</p>"
            "<h2>Conclusioni</h2><p>Si chiede l'accoglimento delle conclusioni.</p>"
        ),
    )
    return service, repository, fascicoli, fascicolo


def test_generazione_crea_documento_editor_versione_fonti_e_audit(tmp_path: Path):
    service, repository, fascicoli, fascicolo = _service(tmp_path)

    result = service.generate_editor_draft(
        AttoAIDraftRequest(
            tenant_id="tenant-a",
            fascicolo_id=fascicolo.id,
            tipo_atto="Comparsa di costituzione",
            template_id="comparsa_costituzione",
            istruzioni_utente="Prepara una bozza sintetica con riferimento alla clausola.",
            document_ids=["doc-ready"],
        ),
        _context(),
    )

    assert result.record.editor_document_id
    assert result.version.version_number == 1
    assert result.version.source == "ai_generation"
    assert result.open_url.endswith(f"/documenti/{result.record.editor_document_id}/editor")
    assert "clausola risolutiva" in result.readback["text"].lower()
    assert repository.get_record("tenant-a", fascicolo.id, result.record.id) is not None
    assert len(repository.list_versions("tenant-a", fascicolo.id, result.record.id)) == 1
    assert [source.document_id for source in result.sources] == ["doc-ready"]
    assert fascicoli.percorso_documento(fascicolo.id, result.record.editor_document_id).exists()
    assert any(event["event_type"] == "editor_ai.generation.completed" for event in repository._data["audit_events"])


def test_generazione_non_inventa_campi_mancanti(tmp_path: Path):
    service, _repository, _fascicoli, fascicolo = _service(tmp_path)
    service.fascicoli_repository.aggiorna(fascicolo.id, nome_cliente="", titolo="")

    result = service.generate_editor_draft(
        AttoAIDraftRequest(
            tenant_id="tenant-a",
            fascicolo_id=fascicolo.id,
            tipo_atto="Comparsa di costituzione",
            template_id="comparsa_costituzione",
            istruzioni_utente="Usa solo dati disponibili.",
            document_ids=["doc-ready"],
        ),
        _context(),
    )

    assert any(field in result.missing_fields for field in ("Cliente", "Oggetto", "Oggetto del fascicolo"))


def test_bootstrap_espone_template_documenti_e_mock_false(tmp_path: Path):
    service, _repository, _fascicoli, fascicolo = _service(tmp_path)

    payload = service.bootstrap(tenant_id="tenant-a", fascicolo_id=fascicolo.id, user_context=_context())

    assert payload["mock_fallback"] is False
    assert payload["templates"][0]["id"] == "comparsa_costituzione"
    assert payload["documents"][0]["document_id"] == "doc-ready"
    assert payload["capabilities"]["generate_draft"] is True
