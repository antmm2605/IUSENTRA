import io
import zipfile
from pathlib import Path
from email.message import EmailMessage

from pct.document_intelligence.extraction import ExtractionResult, extract_text_from_document
from pct.document_intelligence.indexer import build_lex_indexing_summary
from pct.document_intelligence.models import DocumentAIPageText, DocumentAIRecord, utc_now
from pct.document_intelligence.sources import source_from_uploaded_document
from pct.document_intelligence.security import DocumentAIPermissionDenied
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from tests.test_applicazioni import _cfg_web, _crea_operatore, _login
from web.app import create_app


def _app(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    cfg["STORAGE_MODE_DEFAULT"] = "JSON"
    app = create_app(cfg)
    _crea_operatore(app)
    return app


def _crea_fascicolo(app) -> str:
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    return fascicoli.nuovo("Fascicolo Documenti AI", TipoFascicolo.CIVILE, nome_cliente="Cliente Test").id


def _patch_extraction(monkeypatch, text: str = "Il documento contiene una clausola importante."):
    monkeypatch.setattr(
        "pct.document_intelligence.service.extract_text_from_document",
        lambda *_args: ExtractionResult(
            ok=True,
            text=text,
            pages=[DocumentAIPageText(page_number=1, text=text)],
            extraction_engine="test-engine",
        ),
    )


def _walk_strings(payload):
    if isinstance(payload, dict):
        for value in payload.values():
            yield from _walk_strings(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_strings(value)
    elif isinstance(payload, str):
        yield payload


def test_document_ai_api_lista_mock_fallback_false(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id = _crea_fascicolo(app)

    with app.test_client() as client:
        _login(client)
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mock_fallback"] is False
    assert payload["documents"] == []
    assert payload["capabilities"]["generate_docx"] is False


def test_document_ai_api_stato_indicizzazione_lex(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id = _crea_fascicolo(app)

    with app.test_client() as client:
        _login(client)
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/lex-indexing")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mock_fallback"] is False
    assert payload["lex_indexing"]["total_documents"] == 0
    assert payload["lex_indexing"]["status"] == "ready"
    assert payload["lex_indexing"]["warnings"] == []


def test_document_ai_api_indicizza_file_anomalo_gia_acquisito_con_best_effort(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id = _crea_fascicolo(app)
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicoli.aggiungi_documento(
        fascicolo_id,
        "allegato.exe",
        TipoDocumento.ALTRO,
        b"Documento gia acquisito nel fascicolo con termine udienza e scadenza da presidiare.",
    )

    with app.test_client() as client:
        _login(client)
        response = client.post(f"/api/v1/ui/fascicoli/{fascicolo_id}/lex-indexing/aggiorna")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["lex_indexing"]["status"] == "ready"
    assert payload["lex_indexing"]["ready"] == 1
    assert payload["lex_indexing"]["errors"] == 0
    assert not any("formato non supportato" in warning.lower() for warning in payload["lex_indexing"]["warnings"])


def test_document_ai_api_indicizza_pdf_p7m_automaticamente_e_una_sola_volta(tmp_path: Path, monkeypatch):
    _patch_extraction(monkeypatch, "Provvedimento leggibile da PDF firmato.")
    app = _app(tmp_path)
    fascicolo_id = _crea_fascicolo(app)
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicoli.aggiungi_documento(fascicolo_id, "Documento_33584995.pdf.p7m", TipoDocumento.ALTRO, b"%PDF-1.4\nprovvedimento")

    with app.test_client() as client:
        _login(client)
        first = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/lex-indexing")
        second = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/lex-indexing")
        documents = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai")

    assert first.status_code == 200
    assert first.get_json()["lex_indexing"]["ready"] == 1
    assert first.get_json()["lex_indexing"]["errors"] == 0
    assert second.get_json()["lex_indexing"]["ready"] == 1
    indexed = documents.get_json()["documents"]
    assert len(indexed) == 1
    assert indexed[0]["original_filename"] == "Documento_33584995.pdf.p7m"


def test_lex_summary_preferisce_record_ready_a_vecchi_errori_stesso_hash():
    content = b"%PDF-1.4\natto"
    source = source_from_uploaded_document(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        document_id="doc-fasc",
        filename="ScrittiDifensivi_29334341.pdf.p7m",
        content=content,
        source_type="documenti_fascicolo",
    )
    base = {
        "tenant_id": "tenant-a",
        "fascicolo_id": "fas-1",
        "original_filename": source.filename,
        "safe_filename": source.safe_filename,
        "file_type": source.file_type,
        "mime_type": source.mime_type or "application/pdf",
        "size_bytes": source.size_bytes,
        "sha256": source.sha256,
        "current_version_id": "ver-1",
        "page_count": 1,
        "created_by": "test",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    records = [
        DocumentAIRecord(id="old-error", status="error", **base),
        DocumentAIRecord(id="new-ready", status="ready", **base),
    ]

    summary = build_lex_indexing_summary(sources=[source], records=records)

    assert summary.ready == 1
    assert summary.errors == 0
    assert summary.warnings == []


def test_document_ai_api_upload_validazioni(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id = _crea_fascicolo(app)

    with app.test_client() as client:
        _login(client)
        missing = client.post(f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/upload")
        forbidden = client.post(
            f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/upload",
            data={"file": (io.BytesIO(b"bad"), "malware.exe")},
            content_type="multipart/form-data",
        )

    assert missing.status_code == 400
    assert missing.get_json()["code"] == "validation_error"
    assert forbidden.status_code == 400


def test_document_ai_api_upload_testo_e_ricerca(tmp_path: Path, monkeypatch):
    _patch_extraction(monkeypatch)
    app = _app(tmp_path)
    fascicolo_id = _crea_fascicolo(app)

    with app.test_client() as client:
        _login(client)
        upload = client.post(
            f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/upload",
            data={"file": (io.BytesIO(b"docx-content"), "atto.docx")},
            content_type="multipart/form-data",
        )
        upload_payload = upload.get_json()
        document_id = upload_payload["document"]["id"]
        detail = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/{document_id}")
        text = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/{document_id}/testo")
        search = client.post(
            f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/{document_id}/cerca",
            json={"query": "clausola", "max_results": 20},
        )

    assert upload.status_code == 201
    assert upload_payload["mock_fallback"] is False
    assert upload_payload["document"]["status"] == "ready"
    assert upload_payload["version"]["version_number"] == 1
    assert upload_payload["extraction"]["status"] == "completed"
    assert detail.status_code == 200
    assert detail.get_json()["versions"][0]["source"] == "upload"
    assert text.status_code == 200
    assert text.get_json()["status"] == "ready"
    assert search.status_code == 200
    assert search.get_json()["results"][0]["page_number"] == 1
    assert not any(str(tmp_path) in value for value in _walk_strings(upload_payload))


def test_document_ai_api_upload_txt_ed_eml_indicizzabili(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id = _crea_fascicolo(app)

    with app.test_client() as client:
        _login(client)
        txt_upload = client.post(
            f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/upload",
            data={"file": (io.BytesIO("Nota interna per Lex".encode("utf-8")), "nota.txt")},
            content_type="multipart/form-data",
        )
        eml_upload = client.post(
            f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/upload",
            data={
                "file": (
                    io.BytesIO(b"Subject: PEC prova\r\nFrom: cancelleria@example.test\r\n\r\nCorpo messaggio"),
                    "ricevuta.eml",
                )
            },
            content_type="multipart/form-data",
        )
        txt_text = client.get(
            f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/{txt_upload.get_json()['document']['id']}/testo"
        )
        eml_text = client.get(
            f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/{eml_upload.get_json()['document']['id']}/testo"
        )

    assert txt_upload.status_code == 201
    assert eml_upload.status_code == 201
    assert txt_upload.get_json()["document"]["file_type"] == "txt"
    assert eml_upload.get_json()["document"]["file_type"] == "eml"
    assert "Nota interna per Lex" in txt_text.get_json()["text"]
    assert "PEC prova" in eml_text.get_json()["text"]


def test_document_ai_extraction_legge_pm7_zip_e_allegati_pec():
    pm7 = extract_text_from_document(
        b"Atto di opposizione leggibile da file firmato anomalo.",
        "atto_opposizione.pdf.pm7",
        "pdf",
    )
    assert pm7.ok
    assert "opposizione leggibile" in pm7.text
    assert pm7.extraction_engine.startswith("cades:")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ricorso.txt", "Ricorso con termine processuale da presidiare.")
    zipped = extract_text_from_document(zip_buffer.getvalue(), "ricorso.pdf.zip", "zip")
    assert zipped.ok
    assert "termine processuale" in zipped.text

    message = EmailMessage()
    message["Subject"] = "PEC con allegato zip"
    message["From"] = "cancelleria@example.test"
    message["To"] = "studio@example.test"
    message.set_content("Comunicazione con allegato compresso.")
    message.add_attachment(
        zip_buffer.getvalue(),
        maintype="application",
        subtype="zip",
        filename="allegato.pdf.zip",
    )
    eml = extract_text_from_document(message.as_bytes(), "messaggio.eml", "eml")
    assert eml.ok
    assert "PEC con allegato zip" in eml.text
    assert "Ricorso con termine processuale" in eml.text


def test_document_ai_api_documento_inesistente_e_query_vuota(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id = _crea_fascicolo(app)

    with app.test_client() as client:
        _login(client)
        detail = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/missing")
        search = client.post(f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai/missing/cerca", json={"query": ""})

    assert detail.status_code == 404
    assert detail.get_json()["code"] == "not_found"
    assert search.status_code == 400
    assert search.get_json()["mock_fallback"] is False


def test_document_ai_api_permesso_negato_restituisce_403(tmp_path: Path, monkeypatch):
    app = _app(tmp_path)
    fascicolo_id = _crea_fascicolo(app)

    def denied(*_args, **_kwargs):
        raise DocumentAIPermissionDenied("Operazione non autorizzata")

    monkeypatch.setattr(
        "pct.document_intelligence.service.DocumentAIService.list_fascicolo_documents",
        denied,
    )

    with app.test_client() as client:
        _login(client)
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/documenti-ai")

    assert response.status_code == 403
    assert response.get_json()["code"] == "permission_denied"


def test_document_ai_blueprint_registrato(tmp_path: Path):
    app = _app(tmp_path)
    assert "api_v1_documenti_ai" in app.blueprints
