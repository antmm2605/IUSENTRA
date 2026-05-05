import io
from pathlib import Path

from pct.document_intelligence.extraction import ExtractionResult
from pct.document_intelligence.models import DocumentAIPageText
from pct.document_intelligence.security import DocumentAIPermissionDenied
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
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
