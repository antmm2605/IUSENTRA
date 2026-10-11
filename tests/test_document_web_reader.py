from flask import Flask

from web.services import document_web_reader


def test_public_reader_keeps_visible_image_labels_without_hidden_preload(monkeypatch):
    app = Flask(__name__)
    source = b'''<html><title>Organismo</title><body>
        <img alt="preload" style="display: none;" src="https://example.org/tracker.png">
        <img alt="decorazione" hidden src="https://example.org/hidden.png">
        <img alt="invisibile" style="visibility:hidden" src="https://example.org/hidden2.png">
        <img alt="Organismo di mediazione" src="https://example.org/logo.png">
        <a href="/domanda.pdf">Domanda di mediazione</a>
        </body></html>'''
    monkeypatch.setattr(document_web_reader, "_public_snapshot", lambda *_: {
        "url": "https://example.org/", "status": 200, "content_type": "text/html", "body": source,
    })
    with app.test_request_context("/api/v1/ui/document-reader/web?url=https://example.org/"):
        response = document_web_reader.web_preview()
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "preload" not in html and "decorazione" not in html and "invisibile" not in html
    assert "Organismo di mediazione" in html
    assert 'href="https://example.org/domanda.pdf"' in html
    assert "tracker.png" not in html and "<img" not in html
    assert "form-action 'none'" in response.headers["Content-Security-Policy"]
