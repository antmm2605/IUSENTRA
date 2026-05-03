from __future__ import annotations

from types import SimpleNamespace

from lex.contracts import EvidenceItem
from lex.retrieval.chunking import chunk_structured_text, normalize_structured_chunks
from lex.retrieval.citations import build_citations
from lex.retrieval.document_parser_docling import (
    DocumentParseChunk,
    DocumentParseResult,
    is_docling_enabled,
    parse_document_with_docling,
)
from lex.retrieval.documenti import search_document_sources


class FakeTable:
    def export_to_markdown(self):
        return "| Voce | Importo |\n| --- | --- |\n| Contributo unificato | 98,00 |"

    def export_to_html(self):
        return "<table><tr><td>Contributo unificato</td><td>98,00</td></tr></table>"


class FakeDoc:
    tables = [FakeTable()]
    pages = {1: {"size": [595, 842]}, 2: {"size": [595, 842]}}

    def export_to_markdown(self):
        return "# Atto di citazione\n\n## Fatto\n\nIl fascicolo contiene una tabella spese."

    def export_to_dict(self):
        return {"name": "atto.pdf", "body": {"children": 2}}


class FakeConverter:
    def convert(self, source):
        return SimpleNamespace(document=FakeDoc(), status="success", source=source)


class FakeChunk:
    def __init__(self, text, meta):
        self.text = text
        self.meta = meta


class FakeChunker:
    def chunk(self, dl_doc):
        return [
            FakeChunk(
                "Il fascicolo contiene una tabella spese.",
                {
                    "headings": ["Atto di citazione", "Fatto"],
                    "doc_items": [{"prov": [{"page_no": 2, "bbox": {"l": 10, "t": 20, "r": 50, "b": 80}}]}],
                    "confidence": 0.91,
                },
            )
        ]

    def contextualize(self, chunk):
        return f"Atto di citazione > Fatto\n{chunk.text}"


def test_docling_parser_pdf_testuale_estrae_markdown_chunk_e_tabella(tmp_path):
    source = tmp_path / "atto.pdf"
    source.write_bytes(b"%PDF-1.4\natto testuale\n%%EOF")

    result = parse_document_with_docling(
        source,
        document_id="DOC-1",
        converter_factory=FakeConverter,
        chunker_factory=FakeChunker,
    )

    assert result.parser == "docling"
    assert result.document_id == "DOC-1"
    assert result.source_hash
    assert result.markdown.startswith("# Atto di citazione")
    assert result.json == {"name": "atto.pdf", "body": {"children": 2}}
    assert result.tables[0]["markdown"].startswith("| Voce")
    assert result.chunks[0].page_no == 2
    assert result.chunks[0].section_path == "Atto di citazione > Fatto"
    assert '"bbox"' in result.chunks[0].bbox_json
    assert result.chunks[0].confidence == 0.91


def test_docling_parser_pdf_scansionato_mockato_conserva_flag_ocr(tmp_path):
    source = tmp_path / "scansione.pdf"
    source.write_bytes(b"%PDF-1.4\nscansione\n%%EOF")

    class OcrChunker(FakeChunker):
        def chunk(self, dl_doc):
            return [
                FakeChunk(
                    "Testo OCR della procura alle liti.",
                    {
                        "headings": ["Procura"],
                        "page_no": 1,
                        "ocr_used": True,
                        "confidence": 0.74,
                    },
                )
            ]

    result = parse_document_with_docling(
        source,
        document_id="DOC-OCR",
        converter_factory=FakeConverter,
        chunker_factory=OcrChunker,
    )

    assert result.chunks[0].ocr_used is True
    assert result.chunks[0].confidence == 0.74
    assert "Procura" in result.chunks[0].section_path


def test_chunking_accetta_chunk_gia_strutturati():
    chunks = normalize_structured_chunks(
        [
            {
                "chunk_index": 3,
                "text": "Motivo di diritto",
                "page_no": 7,
                "section_path": "Diritto",
            }
        ]
    )

    assert chunks == [
        {
            "chunk_index": 3,
            "text": "Motivo di diritto",
            "page_no": 7,
            "section_path": "Diritto",
            "markdown": "Motivo di diritto",
        }
    ]
    fallback = chunk_structured_text("abc" * 500, max_chars=100)
    assert len(fallback) > 1
    assert fallback[0]["chunk_index"] == 1


def test_documenti_source_usa_docling_quando_abilitato_e_citazioni_citabili(tmp_path, monkeypatch):
    source = tmp_path / "atto.txt"
    source.write_text("Testo legacy", encoding="utf-8")
    doc = SimpleNamespace(
        id="DOC-7",
        nome="atto.txt",
        tipo=SimpleNamespace(value="ATTO_GIUDIZIARIO"),
        percorso="atto.txt",
        data_documento="2026-05-01",
        firmato_digitalmente=False,
        id_deposito_pct="DEP-1",
        note="",
        descrizione="",
    )
    store = SimpleNamespace(documents_dir=tmp_path, get=lambda pratica_id: SimpleNamespace(documenti=[doc]))

    import lex.retrieval.documenti as documenti_module
    import web.helpers

    result = DocumentParseResult(
        document_id="DOC-7",
        source_path=str(source),
        source_hash="abc123",
        parser="docling",
        parser_version="2.92.0",
        markdown="## Diritto\n\nLa domanda riguarda il pagamento.",
        chunks=[
            DocumentParseChunk(
                document_id="DOC-7",
                source_hash="abc123",
                chunk_index=1,
                text="La domanda riguarda il pagamento.",
                markdown="## Diritto\n\nLa domanda riguarda il pagamento.",
                page_no=4,
                section_path="Diritto",
                confidence=0.96,
            )
        ],
        tables=[],
        pages=[{"page_no": 4}],
        warnings=[],
    )

    monkeypatch.setenv("LEX_DOCLING_ENABLED", "1")
    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: store)
    monkeypatch.setattr(documenti_module, "parse_document_with_docling", lambda *args, **kwargs: result)

    items = search_document_sources("FASC-1", "pagamento", {})
    chunk_item = next(item for item in items if item.source_type == "documento_chunk")

    assert chunk_item.metadata["parser"] == "docling"
    assert chunk_item.metadata["page_no"] == 4
    assert chunk_item.metadata["section_path"] == "Diritto"
    assert chunk_item.metadata["chunk_index"] == 1

    citations = build_citations([chunk_item])
    assert citations[0].page_no == 4
    assert citations[0].section_path == "Diritto"
    assert citations[0].chunk_index == 1


def test_documenti_source_fallback_legacy_se_docling_fallisce(tmp_path, monkeypatch):
    source = tmp_path / "memo.txt"
    source.write_text("Testo estratto dal parser legacy.", encoding="utf-8")
    doc = SimpleNamespace(
        id="DOC-LEGACY",
        nome="memo.txt",
        tipo=SimpleNamespace(value="ALLEGATO"),
        percorso="memo.txt",
        data_documento="2026-05-02",
        firmato_digitalmente=False,
        id_deposito_pct="",
        note="",
        descrizione="",
    )
    store = SimpleNamespace(documents_dir=tmp_path, get=lambda pratica_id: SimpleNamespace(documenti=[doc]))

    import lex.retrieval.documenti as documenti_module
    import web.helpers

    monkeypatch.setenv("LEX_DOCLING_ENABLED", "1")
    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: store)
    monkeypatch.setattr(
        documenti_module,
        "parse_document_with_docling",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("docling non installato")),
    )

    items = search_document_sources("FASC-1", "legacy", {})
    document_item = next(item for item in items if item.source_type == "documento")

    assert "Testo estratto dal parser legacy" in document_item.content
    assert document_item.metadata["parser"] == "legacy"
    assert document_item.metadata["docling_fallback"] is True
    assert "docling non installato" in document_item.metadata["docling_error"]


def test_feature_flag_docling_disattivato_di_default(monkeypatch):
    monkeypatch.delenv("LEX_DOCLING_ENABLED", raising=False)
    assert is_docling_enabled() is False
    monkeypatch.setenv("LEX_DOCLING_ENABLED", "true")
    assert is_docling_enabled() is True


def test_citations_preservano_metadati_pagina_sezione_chunk():
    item = EvidenceItem(
        source_type="documento_chunk",
        source_id="DOC-1:docling:2",
        title="Comparsa - Diritto",
        content="Motivo di diritto citabile",
        score=0.9,
        metadata={"page_no": 5, "section_path": "Diritto", "chunk_index": 2},
    )

    citation = build_citations([item])[0]

    assert citation.page_no == 5
    assert citation.section_path == "Diritto"
    assert citation.chunk_index == 2
