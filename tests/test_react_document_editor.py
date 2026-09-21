from __future__ import annotations

import io
from pathlib import Path

from pct.fascicoli import TipoDocumento, TipoFascicolo
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


def _seed_documento_pdf(app):
    with app.test_request_context("/"):
        core_loader = (app.extensions.get("core_runtime") or {}).get("get_fascicoli")
        fascicoli = core_loader() if callable(core_loader) else get_fascicoli()
        fascicolo = fascicoli.nuovo(
            "Ricorso per cassazione",
            TipoFascicolo.CIVILE,
            nome_cliente="Cliente Reale",
            tribunale="Corte Suprema di Cassazione",
            numero_rg="14732/2025",
        )
        documento = fascicoli.aggiungi_documento(
            fascicolo.id,
            "sentenza_cassazione.pdf",
            TipoDocumento.SENTENZA,
            b"%PDF-1.4\n% test\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            note="Documento PDF originale",
            tags=["sentenza"],
            caricato_da="operatore",
        )
    return fascicolo, documento


def _pdf_valido_testo(testo: str = "Documento PDF originale") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.drawString(72, 760, testo)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _seed_documento_pdf_valido(app):
    with app.test_request_context("/"):
        core_loader = (app.extensions.get("core_runtime") or {}).get("get_fascicoli")
        fascicoli = core_loader() if callable(core_loader) else get_fascicoli()
        fascicolo = fascicoli.nuovo(
            "Ricorso PDF modificabile",
            TipoFascicolo.CIVILE,
            nome_cliente="Cliente Reale",
            tribunale="Tribunale di Palmi",
            numero_rg="811/2026",
        )
        documento = fascicoli.aggiungi_documento(
            fascicolo.id,
            "ricorso_originale.pdf",
            TipoDocumento.ATTO_GIUDIZIARIO,
            _pdf_valido_testo(),
            note="PDF originale valido",
            tags=["atto"],
            caricato_da="operatore",
        )
    return fascicolo, documento


def _seed_documento_eml(app):
    raw = (
        b"From: Cancelleria <cancelleria@example.test>\r\n"
        b"To: Studio <studio@example.test>\r\n"
        b"Subject: Comunicazione fascicolo\r\n"
        b"Date: Mon, 25 May 2026 16:12:00 +0200\r\n"
        b"Message-ID: <pec-test@example.test>\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=\"iusentra\"\r\n"
        b"\r\n--iusentra\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\nTesto della comunicazione PEC.\r\n"
        b"--iusentra\r\n"
        b"Content-Type: text/plain; name=\"allegato.txt\"\r\n"
        b"Content-Disposition: attachment; filename=\"allegato.txt\"\r\n"
        b"\r\nAllegato testuale.\r\n"
        b"--iusentra--\r\n"
    )
    with app.test_request_context("/"):
        core_loader = (app.extensions.get("core_runtime") or {}).get("get_fascicoli")
        fascicoli = core_loader() if callable(core_loader) else get_fascicoli()
        fascicolo = fascicoli.nuovo(
            "Comunicazione PEC",
            TipoFascicolo.CIVILE,
            nome_cliente="Cliente Reale",
            tribunale="Tribunale di Palmi",
            numero_rg="3441/2025",
        )
        documento = fascicoli.aggiungi_documento(
            fascicolo.id,
            "pec_comunicazione.eml",
            TipoDocumento.COMUNICAZIONE,
            raw,
            note="Messaggio PEC",
            tags=["pec"],
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
    assert payload["endpoints"]["importFile"] == f"/api/editor/{fascicolo.id}/{documento.id}/importa"
    assert ".docx" in payload["capabilities"]["formats"]
    assert ".pdf" in payload["capabilities"]["formats"]
    assert payload["editorAI"]["enabled"] is True
    assert payload["editorAI"]["bootstrap"] == f"/api/v1/ui/fascicoli/{fascicolo.id}/editor-ai/bootstrap"
    assert payload["editorAI"]["generate"] == f"/api/v1/ui/fascicoli/{fascicolo.id}/editor-ai/genera"


def test_editor_documento_payload_pdf_usa_anteprima_nativa(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo, documento = _seed_documento_pdf(app)

    with app.test_client() as client:
        _login(client)
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti/{documento.id}/editor")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["document"]["name"] == "sentenza_cassazione.pdf"
    assert payload["document"]["editable"] is False
    assert "anteprima originale" in payload["document"]["lockedReason"]
    assert payload["document"]["actions"]["preview"] == f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/visualizza"
    assert any("Anteprima PDF nativa" in warning for warning in payload["warnings"])


def test_editor_pdf_non_viene_salvato_ricostruendolo_da_html(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo, documento = _seed_documento_pdf(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/api/editor/{fascicolo.id}/{documento.id}/salva",
            json={"html": "<h1>Testo riscritto dall'editor</h1>"},
        )

    payload = response.get_json()
    assert response.status_code == 409
    assert payload["ok"] is False
    assert "non lo ricostruisce" in payload["errore"]


def test_editor_pdf_endpoint_restituisce_il_pdf_originale(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo, documento = _seed_documento_pdf(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/api/editor/{fascicolo.id}/{documento.id}/pdf",
            json={"html": "<h1>Contenuto che non deve entrare nel PDF</h1>"},
        )

    assert response.status_code == 200
    assert response.data == b"%PDF-1.4\n% test\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    assert b"Contenuto che non deve entrare nel PDF" not in response.data


def test_editor_pdf_overlay_versiona_e_preserva_pdf_originale(tmp_path: Path):
    import fitz

    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo, documento = _seed_documento_pdf_valido(app)

    with app.test_client() as client:
        _login(client)
        meta_response = client.get(f"/api/editor/{fascicolo.id}/{documento.id}/pdf-meta")
        page_response = client.get(f"/api/editor/{fascicolo.id}/{documento.id}/pdf-pagina/1.png")
        overlay_response = client.post(
            f"/api/editor/{fascicolo.id}/{documento.id}/pdf-overlay",
            json={
                "annotations": [
                    {
                        "type": "text",
                        "page": 1,
                        "x": 0.12,
                        "y": 0.18,
                        "text": "Nota studio verificata",
                        "fontSizePt": 13,
                        "color": "#111827",
                    },
                    {
                        "type": "highlight",
                        "page": 1,
                        "x": 0.1,
                        "y": 0.2,
                        "width": 0.35,
                        "height": 0.04,
                        "fillColor": "#fef3c7",
                    },
                ]
            },
        )
        exported = client.post(f"/api/editor/{fascicolo.id}/{documento.id}/pdf", json={"html": "<p>ignorato</p>"})

    assert meta_response.status_code == 200
    assert meta_response.get_json()["pageCount"] == 1
    assert page_response.status_code == 200
    assert page_response.data.startswith(b"\x89PNG")
    payload = overlay_response.get_json()
    assert overlay_response.status_code == 200, payload
    assert payload["ok"] is True
    assert payload["annotations"] == 2
    assert payload["documento"]["versioni"] == 1
    assert exported.status_code == 200
    with fitz.open(stream=exported.data, filetype="pdf") as pdf:
        assert "Nota studio verificata" in pdf[0].get_text()


def test_editor_pdf_importa_nuova_versione_senza_conversione_html(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo, documento = _seed_documento_pdf_valido(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/api/editor/{fascicolo.id}/{documento.id}/importa",
            data={"documento": (io.BytesIO(_pdf_valido_testo("Nuova versione PDF")), "nuova_versione.pdf")},
            content_type="multipart/form-data",
        )

    payload = response.get_json()
    with app.test_request_context("/"):
        updated = get_fascicoli().get(fascicolo.id)
        updated_doc = next(doc for doc in updated.documenti if doc.id == documento.id)

    assert response.status_code == 200, payload
    assert payload["ok"] is True
    assert payload["documento"]["nome"] == "nuova_versione.pdf"
    assert payload["documento"]["editable"] is False
    assert updated_doc.nome == "nuova_versione.pdf"
    assert len(updated_doc.versioni) == 1


def test_editor_documento_payload_eml_usa_anteprima_email_originale(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo, documento = _seed_documento_eml(app)

    with app.test_client() as client:
        _login(client)
        payload_response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti/{documento.id}/editor")
        html_response = client.get(f"/api/editor/{fascicolo.id}/{documento.id}/html")
        preview_response = client.get(f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/visualizza")

    payload = payload_response.get_json()
    html_payload = html_response.get_json()
    preview_html = preview_response.get_data(as_text=True)
    assert payload_response.status_code == 200
    assert payload["document"]["extension"] == "eml"
    assert payload["document"]["editable"] is False
    assert "email originale" in payload["document"]["lockedReason"].lower()
    assert any("Formato EML" in warning for warning in payload["warnings"])
    assert html_response.status_code == 200
    assert html_payload["ok"] is True
    assert "Comunicazione fascicolo" in html_payload["html"]
    assert "Testo della comunicazione PEC" in html_payload["html"]
    assert html_payload["meta"]["tipo_originale"] == "eml"
    assert preview_response.status_code == 200
    assert "Email PEC / EML" in preview_html
    assert "allegato.txt" in preview_html


def test_editor_documento_importa_pdf_word_versiona_documento(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo, documento = _seed_documento_editabile(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/api/editor/{fascicolo.id}/{documento.id}/importa",
            data={"documento": (io.BytesIO(b"documento word importato"), "ricorso_importato.docx")},
            content_type="multipart/form-data",
        )

    payload = response.get_json()
    with app.test_request_context("/"):
        fascicoli = get_fascicoli()
        updated = fascicoli.get(fascicolo.id)
        updated_doc = next(doc for doc in updated.documenti if doc.id == documento.id)

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["documento"]["nome"] == "ricorso_importato.docx"
    assert payload["documento"]["editable"] is True
    assert updated_doc.nome == "ricorso_importato.docx"
    assert updated_doc.versioni


def test_editor_documento_react_contract_statico():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/DocumentEditorPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/documentEditorData.ts").read_text(encoding="utf-8")
    bridge_source = Path("web/services/react_document_editor_bridge.py").read_text(encoding="utf-8")
    route_source = Path("web/bootstrap/fascicoli_editor_routes.py").read_text(encoding="utf-8")

    assert "DocumentEditorPage" in app_source
    assert "isDocumentEditorPage?<DocumentEditorPage/>" in app_source
    assert "Editor professionale" in page_source
    assert "Font testo" in page_source
    assert "Dimensione testo" in page_source
    assert "Interlinea" in page_source
    assert "Anteprima PDF fedele all\\'originale" in page_source
    assert "Modifica PDF sicura" in page_source
    assert "Salva versione PDF" in page_source
    assert "Messaggio EML consultabile" in page_source
    assert "EML originale" in page_source
    assert "PDF nativo" in page_source
    assert "Dati reali" in page_source
    assert "Nuovo atto con Lex" in page_source
    assert "Fonti usate" in page_source
    assert "Dati da completare" in page_source
    assert "Modifiche proposte da Lex" in page_source
    assert "href=\"#\"" not in page_source
    assert "#lex" not in page_source
    assert "contentEditable={editorEnabled}" in page_source
    assert "Payload reale" not in page_source
    assert "https://esm.sh" not in page_source
    assert "editorAI" in data_source
    assert "importFile" in data_source
    assert "pdfOverlay" in data_source
    assert "/api/v1/ui/fascicoli/${encodeURIComponent(idFascicolo)}/documenti/${encodeURIComponent(idDocumento)}/editor" in data_source
    assert "build_react_document_editor_payload" in bridge_source
    assert "editorAI" in bridge_source
    assert "/importa" in bridge_source
    assert "/pdf-overlay" in bridge_source
    assert 'render_react_shell_response(f"fascicoli/{id_fasc}/documenti/{id_doc}/editor")' in route_source
