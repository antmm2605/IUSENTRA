from __future__ import annotations

from pathlib import Path

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.helpers import get_fascicoli


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-editor-test-key"
    return app


def _seed_documento_editabile(app):
    with app.test_request_context("/"):
        core_loader = (app.extensions.get("core_runtime") or {}).get("get_fascicoli")
        fascicoli = core_loader() if callable(core_loader) else get_fascicoli()
        fascicolo = fascicoli.nuovo(
            "Opposizione a decreto ingiuntivo",
            TipoFascicolo.CIVILE,
            nome_cliente="Cliente Reale",
            tribunale="Tribunale di Palmi",
            numero_rg="1025/2026",
        )
        documento = fascicoli.aggiungi_documento(
            fascicolo.id,
            "bozza_comparsa.txt",
            TipoDocumento.ATTO_GIUDIZIARIO,
            b"Comparsa di costituzione\nConclusioni",
            note="Bozza redazionale",
            tags=["bozza", "atto"],
            caricato_da="operatore",
        )
    return fascicolo, documento


def test_editor_documento_route_profonda_serve_shell_react(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo, documento = _seed_documento_editabile(app)

    with app.test_client() as client:
        _login(client)
        response = client.get(f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/editor")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="iusentra-react-bootstrap"' in html
    assert "/static/react/" in html
    assert "https://esm.sh/@tiptap" not in html


def test_editor_documento_payload_react_usa_dati_reali(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo, documento = _seed_documento_editabile(app)

    with app.test_client() as client:
        _login(client)
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti/{documento.id}/editor")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["fascicolo"]["id"] == fascicolo.id
    assert payload["fascicolo"]["client"] == "Cliente Reale"
    assert payload["document"]["id"] == documento.id
    assert payload["document"]["name"] == "bozza_comparsa.txt"
    assert payload["document"]["editable"] is True
    assert payload["endpoints"]["loadHtml"] == f"/api/editor/{fascicolo.id}/{documento.id}/html"
    assert payload["endpoints"]["save"] == f"/api/editor/{fascicolo.id}/{documento.id}/salva"


def test_editor_documento_react_contract_statico():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/DocumentEditorPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/documentEditorData.ts").read_text(encoding="utf-8")
    bridge_source = Path("web/services/react_document_editor_bridge.py").read_text(encoding="utf-8")
    route_source = Path("web/bootstrap/fascicoli_editor_routes.py").read_text(encoding="utf-8")

    assert "DocumentEditorPage" in app_source
    assert "isDocumentEditorPage?<DocumentEditorPage/>" in app_source
    assert "Editor professionale" in page_source
    assert "contentEditable" in page_source
    assert "https://esm.sh" not in page_source
    assert "/api/v1/ui/fascicoli/${encodeURIComponent(idFascicolo)}/documenti/${encodeURIComponent(idDocumento)}/editor" in data_source
    assert "build_react_document_editor_payload" in bridge_source
    assert 'render_react_shell_response(f"fascicoli/{id_fasc}/documenti/{id_doc}/editor")' in route_source
