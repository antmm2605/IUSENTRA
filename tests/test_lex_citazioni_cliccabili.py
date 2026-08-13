"""Fase A: citazioni cliccabili nella chat sul fascicolo.

Le fonti documentali del retrieval Lex portano un href interno al viewer del
documento (/fascicoli/<id>/documenti/<id_doc>/visualizza?page=N): il widget lo
rende come link. Coerente col principio delle fonti certe: la citazione apre
il punto esatto del documento che la supporta.
"""

from __future__ import annotations

from lex.contracts import Citation, EvidenceItem, LexResponse
from lex.http_bounded_bridge import _document_citation_href, _source_rows
from lex.research.evidence_pack import _to_dict
from lex.retrieval.documenti import _document_href


# --- Costruzione href ------------------------------------------------------------


def test_href_documento_con_pagina():
    assert _document_href("F1", "DOC9", 3) == "/fascicoli/F1/documenti/DOC9/visualizza?page=3"
    assert _document_href("F1", "DOC9") == "/fascicoli/F1/documenti/DOC9/visualizza"
    assert _document_href("", "DOC9") == ""
    assert _document_href("F1", "") == ""


def test_href_citation_quota_id_con_caratteri_speciali():
    href = _document_citation_href("fasc/1", "doc 2", None)
    assert href == "/fascicoli/fasc%2F1/documenti/doc%202/visualizza"


# --- Propagazione nel pack evidenze ----------------------------------------------


def test_evidence_pack_propaga_href_e_fascicolo():
    item = EvidenceItem(
        source_type="documento_chunk",
        source_id="DOC9:docling:0",
        title="Atto di citazione - p. 3",
        content="testo",
        score=0.9,
        metadata={
            "document_id": "DOC9",
            "page_no": 3,
            "href": "/fascicoli/F1/documenti/DOC9/visualizza?page=3",
            "fascicolo_id": "F1",
        },
    )
    row = _to_dict(item)
    assert row["href"] == "/fascicoli/F1/documenti/DOC9/visualizza?page=3"
    assert row["fascicolo_id"] == "F1"


# --- Sources del payload chat -----------------------------------------------------


def _response(citations, compared=None):
    return LexResponse(answer="ok", citations=citations, compared_sources=compared or [], metadata={"workflow": "case"})


def test_source_rows_usa_href_dalle_compared():
    citation = Citation(
        source_type="documento_chunk",
        source_id="DOC9:docling:0",
        title="Atto di citazione - p. 3",
        excerpt="Il convenuto...",
        page_no=3,
    )
    compared = [{
        "source_id": "DOC9:docling:0",
        "title": "Atto di citazione - p. 3",
        "href": "/fascicoli/F1/documenti/DOC9/visualizza?page=3",
    }]
    rows = _source_rows(_response([citation], compared))
    assert rows[0]["href"] == "/fascicoli/F1/documenti/DOC9/visualizza?page=3"


def test_source_rows_ricostruisce_href_da_source_id_docling():
    citation = Citation(
        source_type="documento_chunk",
        source_id="DOC9:docling:2",
        title="Comparsa - p. 5",
        excerpt="...",
        page_no=5,
    )
    rows = _source_rows(_response([citation]), fascicolo_id="F1")
    assert rows[0]["href"] == "/fascicoli/F1/documenti/DOC9/visualizza?page=5"


def test_source_rows_senza_fascicolo_non_inventa_link():
    citation = Citation(
        source_type="documento_chunk",
        source_id="DOC9:docling:2",
        title="Comparsa",
        excerpt="...",
    )
    rows = _source_rows(_response([citation]))
    assert rows[0]["href"] == ""


def test_fonte_normativa_esterna_senza_href_interno():
    citation = Citation(
        source_type="normativa",
        source_id="art-2043-cc",
        title="Art. 2043 c.c.",
        excerpt="Risarcimento per fatto illecito",
        url="https://www.normattiva.it/...",
    )
    rows = _source_rows(_response([citation]), fascicolo_id="F1")
    assert rows[0]["href"] == ""  # nessun link interno per fonti non documentali
