import json
from pathlib import Path

from lex.dataset.models import DocumentPage, StudioDatasetDocument
from lex.memory_tree import (
    build_and_write_lex_memory_tree,
    build_lex_memory_tree,
    load_lex_memory_chunks,
    search_lex_memory_chunks,
)


def _document(text: str, *, title: str = "Questione Penale Pendente R.G. 9926/2026") -> StudioDatasetDocument:
    return StudioDatasetDocument(
        tenant_id="tenant-fonti",
        document_id="doc-qsp50194",
        title=title,
        text=text,
        source_name="Cassazione",
        mime_type="application/pdf",
        source_kind="legal_web_evidence",
        fascicolo_id="cassazione_massimario",
        sha256="a" * 64,
        pages=(DocumentPage(page_number=1, text=text),),
        metadata={
            "source_code": "cassazione_massimario",
            "source_url": "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
            "attachment_url": "https://www.cortedicassazione.it/resources/cms/documents/ordinanza.pdf",
            "attachment_type": "pdf",
            "is_official": True,
            "verification_status": "verified",
            "review_id": 390,
            "evidence_id": 1,
        },
    )


def test_memory_tree_crea_chunk_deterministici_con_provenienza_qualita_norme_e_rg():
    text = (
        "Questione su concordato in appello ex art. 599-bis c.p.p. e ricorso "
        "per cassazione ex art. 606 c.p.p. R.G. 9926/2026. "
        "Il PDF collegato richiama anche R.G. 9966/2026."
    )

    first = build_lex_memory_tree([_document(text)])
    second = build_lex_memory_tree([_document(text)])

    assert first.schema == "iusentra.lex_memory_tree.v1"
    assert first.documents_count == 1
    assert first.ready_documents_count == 1
    assert first.chunks_count == 1
    assert first.chunks[0].chunk_id == second.chunks[0].chunk_id
    assert first.chunks[0].provenance.source_code == "cassazione_massimario"
    assert first.chunks[0].quality.status == "pronto_con_note"
    assert first.chunks[0].metadata["tokenjuice"]["schema"] == "iusentra.lex_tokenjuice.v1"
    assert first.chunks[0].metadata["tokenjuice"]["metadata"]["llm_used"] is False
    assert "R.G. 9926/2026" in first.chunks[0].rg_refs
    assert "R.G. 9966/2026" in first.chunks[0].rg_refs
    assert any("599" in norm for norm in first.chunks[0].norms)
    assert any("606" in norm for norm in first.chunks[0].norms)


def test_memory_tree_scrive_indice_e_permette_ricerca_per_rg_norma_e_fonte(tmp_path: Path):
    text = (
        "La questione riguarda i limiti del ricorso per cassazione dopo "
        "concordato in appello. Art. 599-bis c.p.p., art. 606 c.p.p. "
        "R.G. 9926/2026."
    )

    report = build_and_write_lex_memory_tree([_document(text)], tmp_path)
    chunks = load_lex_memory_chunks(tmp_path / "memory_tree" / "chunks.jsonl")
    hits = search_lex_memory_chunks(chunks, "Cassazione art. 599-bis c.p.p. R.G. 9926/2026")

    assert Path(report["memory_tree_index"]).exists()
    assert Path(report["memory_tree_chunks"]).exists()
    assert report["documents_count"] == 1
    assert report["chunks_count"] == 1
    assert hits
    assert hits[0]["provenance"]["source_name"] == "Cassazione"
    assert "599" in " ".join(hits[0]["norms"])
    assert "R.G. 9926/2026" in hits[0]["rg_refs"]

    index = json.loads((tmp_path / "memory_tree" / "index.json").read_text(encoding="utf-8"))
    assert index["schema"] == "iusentra.lex_memory_tree.v1"
    assert "cassazione_massimario" in index["sources"]


def test_memory_tree_marca_ocr_sporco_senza_portarlo_come_pronto_pulito():
    dirty = "CORTE SUPREMA | d anni due e mesi o edi " * 20
    tree = build_lex_memory_tree([_document(dirty, title="Ordinanza OCR")])

    assert tree.chunks[0].quality.status == "da_ocr"
    assert tree.chunks[0].quality.ocr_dirty is True
    assert tree.chunks[0].quality.ready is True


def test_memory_tree_aggiunge_contesto_tokenjuice_compattato_per_chunk_lunghi():
    long_text = (
        ("Riga ripetitiva senza valore decisivo. " * 80)
        + "Questione penale pendente: art. 599-bis c.p.p., art. 606 c.p.p., R.G. 9926/2026. "
        + ("Altro testo OCR lungo. " * 80)
    )

    tree = build_lex_memory_tree([_document(long_text)], max_chars=8000, overlap_chars=100)
    tokenjuice = tree.chunks[0].metadata["tokenjuice"]

    assert tokenjuice["schema"] == "iusentra.lex_tokenjuice.v1"
    assert tokenjuice["compressed_chars"] < tokenjuice["original_chars"]
    assert "compressed_text" in tokenjuice
    assert "R.G. 9926/2026" in tokenjuice["compressed_text"]
