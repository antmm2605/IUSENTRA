from types import SimpleNamespace

import pytest

from pct.document_intelligence.security import DocumentAIValidationError
from web.services import document_intelligence_runtime as runtime


def _runtime_with_catalog_evidence(monkeypatch, evidence):
    audit: list[dict[str, object]] = []
    current = SimpleNamespace(id="catalog-current")
    resolved = SimpleNamespace(
        id="catalog-resolved",
        document_version_id="version-1",
        document_sha256="a" * 64,
        metadata={"filename": "atto.pdf"},
        updated_at="2026-08-25T14:30:00+02:00",
    )

    class Repository:
        def get_catalog_assignment(self, tenant_id, fascicolo_id, document_id):
            assert (tenant_id, fascicolo_id, document_id) == ("studio-test", "FASC-1", "DOC-1")
            return current

        def list_catalog_evidence(self, assignment_id):
            assert assignment_id == current.id
            return evidence

        def resolve_catalog_assignment(self, **kwargs):
            assert kwargs["status"] == "confirmed"
            return resolved

        def append_audit_event(self, event):
            audit.append(event)

    repository = Repository()
    monkeypatch.setattr(runtime, "assert_document_ai_fascicolo_current_tenant", lambda fascicolo_id: None)
    monkeypatch.setattr(runtime, "document_ai_tenant_id", lambda: "studio-test")
    monkeypatch.setattr(runtime, "document_ai_user_context", lambda: {"user_id": "avvocato-test"})
    monkeypatch.setattr(runtime, "build_document_ai_service", lambda: SimpleNamespace(repository=repository))
    monkeypatch.setattr(runtime, "_catalog_assignment_payload", lambda repository, assignment: {"id": assignment.id})
    return audit


def test_conferma_catalogo_rifiuta_l_esito_senza_prova_del_contenuto(monkeypatch):
    _runtime_with_catalog_evidence(monkeypatch, [])

    with pytest.raises(DocumentAIValidationError, match="manca una prova letta dal contenuto"):
        runtime.resolve_document_catalog_assignment("FASC-1", "DOC-1", status="confirmed", evidence_acknowledged=True)


def test_conferma_catalogo_traccia_lettura_e_tipologie_delle_evidenze(monkeypatch):
    evidence = [
        SimpleNamespace(evidence_type="document_identity"),
        SimpleNamespace(evidence_type="legal_source"),
    ]
    audit = _runtime_with_catalog_evidence(monkeypatch, evidence)

    result = runtime.resolve_document_catalog_assignment(
        "FASC-1",
        "DOC-1",
        status="confirmed",
        evidence_acknowledged=True,
    )

    assert result == {"id": "catalog-resolved"}
    assert audit[0]["event_type"] == "document_catalog.reviewed"
    assert audit[0]["payload"] == {
        "note_length": 0,
        "evidence_acknowledged": True,
        "evidence_count": 2,
        "evidence_types": ["document_identity", "legal_source"],
    }
