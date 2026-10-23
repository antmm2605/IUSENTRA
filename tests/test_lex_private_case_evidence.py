from io import BytesIO
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import FileStorage

from lex.dataset.models import StudioDatasetDocument
from lex.dataset.pipeline import build_studio_dataset_pipeline
from lex.retrieval.attachment_evidence import build_attachment_evidence
from lex.retrieval.documenti import search_document_sources
from pct.document_intelligence.repository import DocumentAIRepository
from pct.document_intelligence.service import DocumentAIService
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from tests.test_document_intelligence_service import FakeFascicoli, FakeUser, _context

_TEXT = (
    "Documento di prova inventato. La motivazione collega il fatto alla conclusione e indica il passaggio da valutare nel fascicolo. "
    * 12
)


def test_documento_fornito_rag_disponibile_qa_e_corpus_condiviso_esclusi(tmp_path):
    request = SimpleNamespace(tenant_id="studio-a", session_id="sessione-a", fascicolo_id="fas-1")
    evidence = build_attachment_evidence(
        [
            {
                "id": "doc-1",
                "name": "precedente.txt",
                "text": _TEXT,
                "tenant_id": "studio-b",
                "evidence_scope": "public",
                "training_eligible": True,
            }
        ],
        request,
    )[0]
    assert evidence.content == _TEXT.strip()
    assert evidence.metadata["tenant_id"] == "studio-a"
    assert evidence.metadata["fascicolo_id"] == "fas-1"
    assert evidence.metadata["training_eligible"] is False
    assert evidence.verified_reference is False
    private = StudioDatasetDocument(
        tenant_id="studio-a",
        document_id="privato",
        title="Precedente",
        text=evidence.content,
        metadata=evidence.metadata,
    )
    public = StudioDatasetDocument(tenant_id="studio-a", document_id="pubblico", title="Fonte autorizzata", text=_TEXT)
    result = build_studio_dataset_pipeline("studio-a", [private, public])
    assert {chunk.document_id for chunk in result.chunks} == {"privato", "pubblico"}
    assert result.qa_tasks and all(task.document_id == "pubblico" for task in result.qa_tasks)
    assert result.qa_pairs and all(pair.document_id == "pubblico" for pair in result.qa_pairs)
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "corpus.db"))
    with pytest.raises(ValueError, match="Documento privato"):
        corpus.salva_sentenza({"metadata": evidence.metadata, "numero_sentenza": "1", "anno_sentenza": 2026})
    with pytest.raises(ValueError, match="Documento privato"):
        corpus.salva_sentenze_blocco([{"metadata": evidence.metadata}])
    assert corpus.cerca_sentenze(limit=10) == []


def test_lettura_reale_indice_locale_rispetta_tenant_permessi_e_fascicolo(tmp_path, monkeypatch):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "documenti.db")
    service = DocumentAIService(repo, FakeFascicoli())
    upload = FileStorage(stream=BytesIO(_TEXT.encode()), filename="precedente.txt", content_type="text/plain")
    service.upload_document_for_fascicolo("studio-a", "fas-1", upload, _context())
    context = {
        "document_ai_service": service,
        "document_ai_tenant_id": "studio-a",
        "document_ai_user_context": _context(),
    }
    rows = search_document_sources("fas-1", "analizza il precedente", context)
    documents = [x for x in rows if x.source_type == "documento_indicizzato"]
    assert documents and "motivazione" in documents[0].content
    metadata = documents[0].metadata
    assert metadata["tenant_id"] == "studio-a" and metadata["fascicolo_id"] == "fas-1"
    assert metadata["evidence_scope"] == "private_fascicolo"
    assert metadata["href"].startswith("/fascicoli/fas-1/documenti/")
    assert search_document_sources("fas-1", "precedente", {**context, "document_ai_tenant_id": "studio-b"}) == []
    monkeypatch.setattr(
        "web.helpers.get_fascicoli", lambda: pytest.fail("Accesso negato non deve attivare il percorso precedente")
    )
    denied = {**context, "document_ai_user_context": _context(FakeUser(can_read=False))}
    assert search_document_sources("fas-1", "precedente", denied) == []
    repo.structured_db.close()


def test_cache_non_condivide_risposte_fra_studi_utenti_sessioni_o_fascicoli():
    from lex.retrieval.cache import LexRetrievalCache

    cache = LexRetrievalCache()
    fields = dict(tenant_id="studio-a", user_id="avvocato-a", session_id="sessione-a", fascicolo_id="fas-1", query="Analizza il documento", intent="analyze_document")
    original = cache.build_key(SimpleNamespace(**fields), {}, "analyze_document")
    cache.set(original, {"testo": "Motivazione privata del fascicolo"})
    for field in ["tenant_id", "user_id", "session_id", "fascicolo_id"]:
        key = cache.build_key(SimpleNamespace(**{**fields, field: "altro"}), {}, "analyze_document")
        assert key != original and cache.get(key) is None


def test_mapping_corpus_non_elimina_il_perimetro_privato():
    from pct.giurisprudenza import GestioneGiurisprudenza

    for record, payload in [
        ({"metadata": {"evidence_scope": "private_fascicolo"}}, None),
        ({}, {"shared_catalog_eligible": False}),
        ({"authority": "user_attachment"}, None),
    ]:
        with pytest.raises(ValueError, match="Documento privato"):
            GestioneGiurisprudenza._corpus_payload_from_record(None, record, payload)
