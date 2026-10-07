"""API reali su cache tecnica temporanea: guardrail, non accettazione utente."""
import io
from urllib.parse import urlsplit

import pytest
from flask import Flask, g
from pypdf import PdfWriter

from web.blueprints import api_v1_document_tools as api
from web.blueprints import api_v1_react as react
from web.services import document_tools_cache as cache


@pytest.fixture
def client(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.secret_key = 'chiave-solo-per-guardrail'
    app.config['DOCUMENT_TOOLS_CACHE_ROOT'] = str(tmp_path)
    app.register_blueprint(api.api_v1_document_tools, url_prefix='/api/v1/ui/document-tools')

    @app.before_request
    def authenticate():
        g.utente_corrente = object()

    monkeypatch.setattr(react, '_session_user_can', lambda permission: permission == 'fascicoli.leggi')
    monkeypatch.setattr(cache, 'tenant_corrente', lambda: 'studio-qa')
    monkeypatch.setattr(cache, 'utente_corrente_id', lambda: 'utente-qa')
    monkeypatch.setattr(api, '_audit_event', lambda *args: None)
    return app.test_client()


def pdf_bytes():
    pdf = PdfWriter()
    pdf.add_blank_page(width=595, height=842)
    output = io.BytesIO()
    pdf.write(output)
    return output.getvalue()


def test_preview_conserva_byte_e_download_autenticato(client):
    original = pdf_bytes()
    response = client.post('/api/v1/ui/document-tools/preview', data={'files': (io.BytesIO(original), 'fonte.pdf')})
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    payload = response.get_json()
    path = urlsplit(payload['previewHref']).path
    download = client.get(path.replace('/visualizza', '/scarica'))
    assert download.status_code == 200 and download.data == original
    assert download.mimetype == 'application/pdf'


def test_preview_rispetta_permessi_prima_di_leggere_il_file(client, monkeypatch):
    monkeypatch.setattr(react, '_session_user_can', lambda permission: False)
    response = client.post('/api/v1/ui/document-tools/preview', data={'files': (io.BytesIO(pdf_bytes()), 'fonte.pdf')})
    assert response.status_code == 403 and not response.get_json()['ok']


@pytest.mark.parametrize('filename,data', [('prova.txt', b'testo'), ('prova.pdf', b'non PDF')])
def test_preview_rifiuta_formato_non_pdf(client, filename, data):
    response = client.post('/api/v1/ui/document-tools/preview', data={'files': (io.BytesIO(data), filename)})
    assert response.status_code == 400 and not response.get_json()['ok']


def test_preview_richiede_un_solo_documento(client):
    assert client.post('/api/v1/ui/document-tools/preview').status_code == 400
    assert client.post('/api/v1/ui/document-tools/preview', data={'files': [
        (io.BytesIO(pdf_bytes()), 'a.pdf'), (io.BytesIO(pdf_bytes()), 'b.pdf'),
    ]}).status_code == 400


def test_word_con_link_restituisce_stessi_byte_del_download(client):
    response = client.post('/api/v1/ui/document-tools/documento-testo-riconosciuto',
                           data={'html': '<p>Testo controllato: attività, € 1.234,56.</p>', 'nome': 'prova.pdf', 'formato': 'docx'},
                           headers={'X-Iusentra-Result-Links': '1'})
    assert response.status_code == 200
    download = client.get(response.headers['X-Iusentra-Download'])
    assert download.status_code == 200 and download.data == response.data
    assert download.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


@pytest.mark.parametrize('function,value', [('tenant_corrente', 'altro-studio'), ('utente_corrente_id', 'altro-utente')])
def test_download_non_esce_dal_tenant_o_utente(client, monkeypatch, function, value):
    response = client.post('/api/v1/ui/document-tools/preview', data={'files': (io.BytesIO(pdf_bytes()), 'fonte.pdf')})
    path = urlsplit(response.get_json()['previewHref']).path.replace('/visualizza', '/scarica')
    monkeypatch.setattr(cache, function, lambda: value)
    download = client.get(path)
    assert download.status_code == 400 and download.mimetype == 'text/html'
    assert 'Copia temporanea non disponibile' in download.get_data(as_text=True)
    assert download.headers['Cache-Control'] == 'no-store'
