from pathlib import Path
from types import SimpleNamespace

from pct.pec_pipeline import DOCUMENT_PRESIDIO_PARSER_VERSION
from scripts.audit_fascicolo_document_autonomy import _best_contributo_evidence, _failure, _source_availability_issue


def test_audit_contributo_preferisce_ricevuta_pagata_all_avviso():
    due = {
        "status": "da_registrare",
        "importo": 49.0,
        "filename": "Avviso contributo.pdf",
    }
    paid = {
        "status": "pagato",
        "importo": 49.0,
        "filename": "Ricevuta contributo.eml",
    }

    evidence, document = _best_contributo_evidence([(due, "avviso"), (paid, "ricevuta")])

    assert evidence == paid
    assert document == "ricevuta"


def test_audit_sorgente_documento_distingue_file_presente_mancante_e_vuoto(tmp_path: Path):
    present = tmp_path / "presente.pdf"
    present.write_bytes(b"%PDF-contenuto")
    empty = tmp_path / "vuoto.pdf"
    empty.touch()

    assert _source_availability_issue(SimpleNamespace(supported=True, content_bytes=None, content_path=present)) == ""
    assert _source_availability_issue(SimpleNamespace(supported=True, content_bytes=None, content_path=empty)) == "file vuoto"
    assert _source_availability_issue(SimpleNamespace(supported=True, content_bytes=None, content_path=tmp_path / "assente.pdf")) == "file fisico non disponibile"
    assert _source_availability_issue(SimpleNamespace(supported=False, content_bytes=None, content_path=None)) == "formato non supportato"


def test_audit_coda_diagnostica_espone_tutti_i_campi_governati():
    failures = []
    _failure(
        failures,
        code="testo_documento_non_indicizzato",
        fascicolo=SimpleNamespace(id="FASC-1", rg_completo="RG 12/2026"),
        document=SimpleNamespace(id="DOC-1", nome="Decreto.pdf"),
        source=SimpleNamespace(sha256="abc123"),
        text_available=False,
        expected="data udienza",
        actual="mancante",
    )

    assert failures == [
        {
            "code": "testo_documento_non_indicizzato",
            "reason": "testo_documento_non_indicizzato",
            "fascicolo_id": "FASC-1",
            "rg": "RG 12/2026",
            "document_id": "DOC-1",
            "documento": "Decreto.pdf",
            "fingerprint": "abc123",
            "text_available": False,
            "expected_field": "data udienza",
            "parser_version": DOCUMENT_PRESIDIO_PARSER_VERSION,
            "expected": "data udienza",
            "actual": "mancante",
        }
    ]
