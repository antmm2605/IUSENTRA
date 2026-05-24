from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from flask import Flask, g

from legal_document_ingestion import LegalDocumentIngestionService, LegalDocumentRepository
from legal_document_ingestion.archive_extractor import extract_zip_bytes
from legal_document_ingestion.zip_safety import ZipSafetyConfig
from web.blueprints.legal_documents_api import legal_documents_api


def _zip(entries: dict[str, bytes | str], *, compression: int = ZIP_DEFLATED) -> bytes:
    bio = BytesIO()
    with ZipFile(bio, "w", compression=compression) as archive:
        for name, value in entries.items():
            archive.writestr(name, value.encode("utf-8") if isinstance(value, str) else value)
    return bio.getvalue()


def _repo(tmp_path: Path) -> LegalDocumentRepository:
    return LegalDocumentRepository(tmp_path / "legal.sqlite", tmp_path / "evidence")


def _service(tmp_path: Path, cases: list[dict] | None = None) -> tuple[LegalDocumentIngestionService, LegalDocumentRepository]:
    repository = _repo(tmp_path)
    service = LegalDocumentIngestionService(
        repository,
        cases
        if cases is not None
        else [
            {
                "id": "F-1234",
                "numero_rg": "1234/2026",
                "ufficio": "Tribunale di Milano",
                "nome_cliente": "Mario Rossi",
                "controparte": "Alfa S.r.l.",
            }
        ],
    )
    return service, repository


def test_pec_zip_pdf_jpg_xml_nested_and_tree_are_processed(tmp_path: Path):
    nested = _zip({"verbale.txt": "Verbale udienza R.G. 1234/2026 udienza rinviata al 10/10/2026 Tribunale di Milano"})
    payload = _zip(
        {
            "atti/atto.txt": "Tribunale di Milano\nAtto di citazione R.G. 1234/2026\nattore: Mario Rossi\nPEC mario.rossi@pec.it",
            "documenti/scansione.jpg": b"\xff\xd8\xff\xe0" + b"immagine",
            "ricevute/dati.xml": "<?xml version='1.0'?><postacert>ricevuta di avvenuta consegna mario.rossi@pec.it</postacert>",
            "annidato.zip": nested,
        }
    )
    service, repository = _service(tmp_path)

    result = service.ingest_bytes(
        tenant_id="tenant-a",
        filename="messaggio.zip",
        content=payload,
        source_type="PEC",
        source_message_id="PEC-1",
        root_pec_id="PEC-1",
    )

    assert result["document"]["status"] in {"validated", "needs_review"}
    assert len(result["children"]) >= 4
    tree = repository.archive_tree("tenant-a", result["document"]["id"])
    names = str(tree)
    assert "atto.txt" in names
    assert "annidato.zip" in names
    processed = [item for item in result["processed"] if (item.get("classification") or {}).get("document_type") == "atto di citazione"]
    assert processed
    evidence = repository.evidence_payload("tenant-a", processed[0]["document"]["id"])
    assert evidence["validation"]["result"] == "valid"
    assert evidence["case_match"]["status"] == "auto_matched"
    assert evidence["lex_index"]["status"] == "completed"


def test_zip_security_negative_cases_are_blocked(tmp_path: Path):
    config = ZipSafetyConfig(max_single_file_bytes=32, max_total_uncompressed_bytes=64, max_files=4, max_depth=2)
    traversal = extract_zip_bytes(
        _zip({"../segreto.txt": "no"}),
        filename="bad.zip",
        parent_document_id="root",
        root_document_id="root",
        config=config,
    )
    assert traversal.blocked and traversal.blocked[0]["security_status"] == "unsafe_file"

    too_large = extract_zip_bytes(
        _zip({"grande.txt": "x" * 80}),
        filename="large.zip",
        parent_document_id="root",
        root_document_id="root",
        config=config,
    )
    assert too_large.blocked

    disallowed = extract_zip_bytes(
        _zip({"programma.exe": b"MZ"}),
        filename="exe.zip",
        parent_document_id="root",
        root_document_id="root",
        config=config,
    )
    assert disallowed.blocked and disallowed.blocked[0]["security_status"] == "quarantined"

    corrupt = extract_zip_bytes(b"non uno zip", filename="rotto.zip", parent_document_id="root", root_document_id="root", config=config)
    assert corrupt.blocked and corrupt.blocked[0]["security_status"] == "needs_review"


def test_zip_bomb_duplicate_and_magic_without_extension(tmp_path: Path):
    config = ZipSafetyConfig(max_single_file_bytes=4 * 1024 * 1024, max_compression_ratio=10.0)
    bomb = extract_zip_bytes(
        _zip({"bomb.txt": "0" * (2 * 1024 * 1024)}),
        filename="bomb.zip",
        parent_document_id="root",
        root_document_id="root",
        config=config,
    )
    assert bomb.blocked

    payload = _zip({"cartella/doc": b"%PDF-1.4\n% testo", "dup.txt": "uno", "DUP.txt": "due"})
    result = extract_zip_bytes(payload, filename="mix.zip", parent_document_id="root", root_document_id="root")
    names = [item.normalized_filename for item in result.files]
    assert any(item.mime.mime_type == "application/pdf" for item in result.files)
    assert len(names) == len(set(names))


@pytest.mark.parametrize(
    ("text", "expected", "area"),
    [
        ("Atto di citazione Tribunale di Milano R.G. 1234/2026", "atto di citazione", "civile"),
        ("Avviso di conclusione delle indagini 415 bis imputato", "avviso 415 bis", "penale"),
        ("Tribunale Amministrativo Regionale TAR ricorso istanza cautelare", "istanza cautelare", "amministrativo"),
        ("Ricorso tributario Corte di Giustizia Tributaria Agenzia delle Entrate", "ricorso tributario", "tributario"),
        ("Giudice di Pace opposizione sanzione verbale di accertamento", "opposizione sanzione", "giudice di pace"),
        ("Diffida e messa in mora per pagamento fattura", "diffida", "stragiudiziale"),
        ("Ricevuta di avvenuta consegna postacert", "ricevuta PEC consegna", "trasversale"),
        ("Esito controlli automatici positivo deposito accettato", "esito controlli automatici", "civile"),
    ],
)
def test_classification_engine_multi_rito(tmp_path: Path, text: str, expected: str, area: str):
    service, _repository = _service(tmp_path)
    result = service.ingest_bytes(tenant_id="tenant-a", filename="atto.txt", content=text.encode("utf-8"))
    processed = result["processed"][0]
    assert processed["classification"]["document_type"] == expected
    assert processed["classification"]["legal_area"] == area


def test_entity_extraction_validation_events_and_matching(tmp_path: Path):
    text = """
    Tribunale di Milano
    Atto di citazione R.G. 1234/2026
    attore: Mario Rossi
    convenuto: Alfa S.r.l.
    PEC mario.rossi@pec.it
    codice fiscale RSSMRA80A01H501U
    partita IVA 12345678903
    valore della causa: € 12.500,00
    art. 183 c.p.c.
    udienza rinviata al 10/10/2026
    termine di 30 giorni
    """
    service, _repository = _service(tmp_path)
    result = service.ingest_bytes(tenant_id="tenant-a", filename="citazione.txt", content=text.encode("utf-8"))
    processed = result["processed"][0]
    entity_types = {item["entity_type"] for item in processed["entities"]}
    assert {"NRG", "PEC", "codice_fiscale", "partita_iva", "data_udienza", "termine_processuale"}.issubset(entity_types)
    assert processed["validation"]["result"] == "valid"
    assert processed["case_match"]["status"] == "auto_matched"
    assert {event["event_type"] for event in processed["events"]} >= {"udienza", "scadenza"}


def test_validation_negative_cases_and_lex_gate(tmp_path: Path):
    text = "Atto di citazione Tribunale di Milano codice fiscale ABC123 PEC indirizzo@nonvalida data atto: 01/01/2999"
    service, repository = _service(tmp_path)
    result = service.ingest_bytes(tenant_id="tenant-a", filename="incoerente.txt", content=text.encode("utf-8"))
    document = result["document"]
    processed = result["processed"][0]
    assert processed["validation"]["result"] == "needs_review"
    assert processed["lex"]["status"] == "blocked"

    rejected = service.ingest_bytes(tenant_id="tenant-a", filename="file.exe", content=b"MZ unsafe")
    assert rejected["document"]["status"] == "needs_review"
    assert repository.latest_lex_job("tenant-a", document["id"])["status"] == "blocked"


def test_case_matching_ambiguous_none_and_conflicts(tmp_path: Path):
    cases = [
        {"id": "A", "numero_rg": "1234/2026", "ufficio": "Tribunale di Milano", "nome_cliente": "Mario Rossi"},
        {"id": "B", "numero_rg": "1234/2026", "ufficio": "Tribunale di Milano", "nome_cliente": "Mario Rossi"},
    ]
    service, _repository = _service(tmp_path, cases)
    ambiguous = service.ingest_bytes(tenant_id="tenant-a", filename="atto.txt", content=b"Tribunale di Milano Atto di citazione R.G. 1234/2026 Mario Rossi")
    assert ambiguous["processed"][0]["case_match"]["status"] == "suggested_match"

    service_none, _ = _service(tmp_path / "none", [])
    no_match = service_none.ingest_bytes(tenant_id="tenant-a", filename="atto.txt", content=b"Diffida stragiudiziale senza fascicolo")
    assert no_match["processed"][0]["case_match"]["status"] == "no_match"


def test_case_matching_non_auto_associa_se_cliente_non_coincide(tmp_path: Path):
    service, _repository = _service(
        tmp_path,
        [
            {
                "id": "F-1234",
                "numero_rg": "1234/2026",
                "ufficio": "Tribunale di Milano",
                "nome_cliente": "Mario Rossi",
                "codice_fiscale_cliente": "RSSMRA80A01H501U",
            }
        ],
    )

    result = service.ingest_bytes(
        tenant_id="tenant-a",
        filename="atto.txt",
        content=b"Tribunale di Milano Atto di citazione R.G. 1234/2026 attore: Luigi Bianchi PEC luigi.bianchi@pec.it",
        fascicolo_id="F-1234",
    )

    match = result["processed"][0]["case_match"]
    assert match["status"] == "needs_manual_match"
    assert any("cliente" in conflict.lower() for conflict in match["conflicts"])


def test_fascicolo_lex_index_include_solo_documenti_validati_e_identita_coerente(tmp_path: Path):
    service, _repository = _service(tmp_path)
    valid = service.ingest_bytes(
        tenant_id="tenant-a",
        filename="valido.txt",
        content=b"Tribunale di Milano Atto di citazione R.G. 1234/2026 attore: Mario Rossi PEC mario.rossi@pec.it",
        fascicolo_id="F-1234",
    )
    conflict = service.ingest_bytes(
        tenant_id="tenant-a",
        filename="conflitto.txt",
        content=b"Tribunale di Milano Atto di citazione R.G. 1234/2026 attore: Luigi Bianchi PEC luigi.bianchi@pec.it",
        fascicolo_id="F-1234",
    )

    result = service.request_fascicolo_lex_index("tenant-a", "F-1234", actor="tester")

    included_ids = {item["document_id"] for item in result["included"]}
    skipped_ids = {item["document_id"] for item in result["skipped"]}
    assert valid["document"]["id"] in included_ids
    assert conflict["document"]["id"] in skipped_ids


def test_multi_tenant_isolation_and_proof_bundle(tmp_path: Path):
    service, repository = _service(tmp_path)
    a = service.ingest_bytes(tenant_id="tenant-a", filename="a.txt", content=b"Diffida e messa in mora")
    b = service.ingest_bytes(tenant_id="tenant-b", filename="b.txt", content=b"Contratto tra le parti")
    assert repository.get_document("tenant-a", a["document"]["id"])
    assert repository.get_document("tenant-a", b["document"]["id"]) is None
    bundle = repository.create_proof_bundle("tenant-a", a["document"]["id"], actor="tester")
    assert bundle["sha256"]
    with pytest.raises(KeyError):
        repository.create_proof_bundle("tenant-b", a["document"]["id"], actor="tester")


def test_api_upload_evidence_tree_and_lex(monkeypatch, tmp_path: Path):
    service, repository = _service(tmp_path)
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["FEATURE_FLAGS"] = {
        "legal_document_understanding": True,
        "ocr_forensic": True,
        "pec_zip_ocr": True,
        "lex_validated_documents_only": True,
    }

    @app.before_request
    def _user():
        g.utente_corrente = SimpleNamespace(username="tester")

    app.register_blueprint(legal_documents_api)
    monkeypatch.setattr("web.blueprints.legal_documents_api._service", lambda: service)
    monkeypatch.setattr("web.blueprints.legal_documents_api._repo", lambda: repository)
    monkeypatch.setattr("web.blueprints.legal_documents_api.legal_document_tenant_id", lambda: "tenant-a")
    monkeypatch.setattr("web.blueprints.legal_documents_api.legal_document_actor", lambda: "tester")

    payload = _zip({"atto.txt": "Tribunale di Milano Atto di citazione R.G. 1234/2026 Mario Rossi"})
    with app.test_client() as client:
        upload = client.post("/api/documents/upload", data={"file": (BytesIO(payload), "pec.zip")}, content_type="multipart/form-data")
        assert upload.status_code == 201
        root_id = upload.get_json()["data"][0]["document"]["id"]
        tree = client.get(f"/api/documents/{root_id}/archive-tree")
        assert tree.status_code == 200
        child_id = tree.get_json()["data"]["children"][0]["document"]["id"]
        evidence = client.get(f"/api/documents/{child_id}/evidence")
        assert evidence.status_code == 200
        assert evidence.get_json()["data"]["lex_index"]["status"] == "completed"
