"""OCR di pagina e PDF A4 dell'acquisizione: guardrail tecnici, non prove hardware."""

from __future__ import annotations

import base64
import io
import shutil
import subprocess

import fitz
import pytest
from flask import Flask, g
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader

from web.blueprints import api_v1_document_tools as blueprint_module
from web.blueprints.api_v1_document_tools import api_v1_document_tools
from legal_ocr.page_layout import Blocco, analizza_pagina
from web.services import document_ocr
from web.services.document_ocr import OcrPageResult, page_dpi
from web.services.document_tools import DocumentToolError, UploadedDocument, images_to_pdf


def _app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _authenticate():
        g.utente_corrente = object()

    app.register_blueprint(api_v1_document_tools, url_prefix="/api/v1/ui/document-tools")
    return app


def _jpeg(width: int = 827, height: int = 1169, lines: tuple[str, ...] = ()) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    for index, line in enumerate(lines):
        draw.text((80, 120 + (index * 48)), line, fill="black", font=font)
    output = io.BytesIO()
    image.save(output, "JPEG", quality=92)
    return output.getvalue()


def _text_pdf(blocks: list[tuple[float, float, str]]) -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    for x, y, text in blocks:
        page.insert_text((x, y), text, fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def test_page_dpi_fa_rientrare_la_pagina_in_a4():
    assert page_dpi(1654, 2339) == 200
    assert page_dpi(2339, 1654) == 200
    assert page_dpi(2480, 3508) == 300
    assert page_dpi(100, 100) == 72
    assert page_dpi(20000, 28000) == 600


def _parola(testo: str, sinistra: int, alto: int, larghezza: int = 90, altezza: int = 20, riga: int = 1) -> dict:
    return {
        "text": testo, "left": sinistra, "top": alto, "width": larghezza, "height": altezza,
        "conf": 0.95, "block": 1, "par": 1, "line": riga,
    }


def test_i_paragrafi_nascono_dalla_struttura_riconosciuta_non_dal_pdf():
    """Capoversi, sillabazione e tabelle nel testo lineare offerto all'editor.

    I paragrafi si ricavano dalla posizione delle parole (`legal_ocr.page_layout`),
    non rileggendo il livello di testo del PDF: e' la stessa struttura che
    alimenta la revisione modificabile, quindi le due viste non possono divergere.
    """
    parole = [
        _parola("TRIBUNALE", 100, 100, 200, 26, riga=1),
        _parola("DI", 310, 100, 40, 26, riga=1),
        _parola("BARI", 360, 100, 110, 26, riga=1),
        _parola("Il", 100, 160, 20, 18, riga=2),
        _parola("sottoscritto", 130, 160, 130, 18, riga=2),
        _parola("chiede", 270, 160, 80, 18, riga=2),
        _parola("la", 360, 160, 20, 18, riga=2),
        _parola("fissa-", 390, 160, 60, 18, riga=2),
        _parola("zione", 100, 182, 60, 18, riga=3),
        _parola("dell'udienza.", 170, 182, 140, 18, riga=3),
    ]
    blocchi = analizza_pagina(parole)
    assert document_ocr._blocchi_in_paragrafi(blocchi) == [
        "TRIBUNALE DI BARI",
        "Il sottoscritto chiede la fissazione dell'udienza.",
    ]


def test_le_tabelle_entrano_nel_testo_lineare_riga_per_riga():
    tabella = Blocco(tipo="tabella", righe=[["Voce", "Importo"], ["Diritti", "150,00"]])
    assert document_ocr._blocchi_in_paragrafi([tabella]) == ["Voce | Importo", "Diritti | 150,00"]


@pytest.mark.parametrize(
    ("data", "message"),
    [(b"", "vuota"), (b"%PDF-1.7 non immagine", "leggibile")],
)
def test_pagina_non_valida_viene_respinta_con_messaggio_italiano(monkeypatch, data, message):
    monkeypatch.setattr(document_ocr, "_tesseract", lambda: object())
    with pytest.raises(DocumentToolError, match=message):
        document_ocr.recognize_page(data)


def test_dizionario_italiano_mancante_blocca_senza_ripiegare_su_altre_lingue(monkeypatch):
    class FakeTesseract:
        @staticmethod
        def get_languages(config=""):
            return ["eng", "osd"]

    monkeypatch.setattr(document_ocr, "_LANGUAGE_READY", False)
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", FakeTesseract)
    with pytest.raises(DocumentToolError, match="dizionario italiano"):
        document_ocr.recognize_page(_jpeg())


def _dati_motore(parole: list[dict]) -> dict:
    """Risposta di `image_to_data` nella forma che Tesseract restituisce."""
    return {
        "text": [parola["text"] for parola in parole],
        "conf": [str(round(parola["conf"] * 100)) for parola in parole],
        "left": [parola["left"] for parola in parole],
        "top": [parola["top"] for parola in parole],
        "width": [parola["width"] for parola in parole],
        "height": [parola["height"] for parola in parole],
        "block_num": [parola["block"] for parola in parole],
        "par_num": [parola["par"] for parola in parole],
        "line_num": [parola["line"] for parola in parole],
    }


def test_rotazione_oraria_e_configurazione_migliore_passate_al_motore(monkeypatch):
    """La rotazione arriva al motore e il PDF si genera con la stessa lettura scelta.

    Le configurazioni vengono provate tutte e vince quella con piu' testo sicuro:
    qui la lettura «colonne» riconosce due parole certe contro una, quindi e' la
    sua configurazione a dover generare anche il PDF, non un'altra.
    """
    letture = {}
    pdf_richiesto = {}

    class FakeTesseract:
        @staticmethod
        def image_to_data(image, lang, config, output_type, timeout):
            letture[config] = letture.get(config, 0) + 1
            if "--psm 4" in config:
                return _dati_motore([_parola("Pagina", 100, 100), _parola("riconosciuta", 200, 100)])
            return _dati_motore([_parola("Pagina", 100, 100)])

        @staticmethod
        def image_to_pdf_or_hocr(image, lang, extension, config, timeout):
            pdf_richiesto.update(size=image.size, lang=lang, extension=extension, config=config)
            return _text_pdf([(72, 100, "Pagina riconosciuta")])

    monkeypatch.setattr(document_ocr, "_tesseract", lambda: FakeTesseract)
    result = document_ocr.recognize_page(_jpeg(827, 1169), rotation=90, raddrizza=False)
    assert len(letture) == len(document_ocr.CONFIGURAZIONI)
    assert pdf_richiesto["lang"] == "ita" and pdf_richiesto["extension"] == "pdf"
    assert "--psm 4" in pdf_richiesto["config"] and f"--dpi {result.dpi}" in pdf_richiesto["config"]
    # La rotazione oraria arriva al motore: la pagina verticale diventa orizzontale.
    assert pdf_richiesto["size"][0] > pdf_richiesto["size"][1]
    # La pagina viene portata alla densita' minima leggibile prima della lettura.
    assert result.dpi >= 300
    assert result.paragraphs == ["Pagina riconosciuta"]
    assert result.characters == len("Paginariconosciuta")
    assert result.engine.endswith("colonne")


def test_api_ocr_pagina_restituisce_pdf_e_paragrafi_senza_salvare(monkeypatch):
    pdf = _text_pdf([(72, 100, "Atto acquisito")])
    calls = []

    def fake_recognize(data, rotation, *, raddrizza=True):
        calls.append((len(data), rotation, raddrizza))
        return OcrPageResult(pdf=pdf, paragraphs=["Atto acquisito"], dpi=200)

    monkeypatch.setattr(blueprint_module, "recognize_page", fake_recognize)
    response = _app().test_client().post(
        "/api/v1/ui/document-tools/ocr-page",
        data={"file": (io.BytesIO(_jpeg()), "pagina.jpg"), "rotation": "450"},
        content_type="multipart/form-data",
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert payload["ok"] is True and payload["paragraphs"] == ["Atto acquisito"]
    assert base64.b64decode(payload["pdf_base64"]).startswith(b"%PDF-")
    assert calls == [(len(_jpeg()), 90, True)]


def test_api_ocr_pagina_senza_file_risponde_errore_leggibile():
    response = _app().test_client().post("/api/v1/ui/document-tools/ocr-page", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "message": "Nessuna pagina ricevuta."}


def test_pdf_multipagina_a4_mantiene_immagine_intera_e_orientamento():
    data, pages = images_to_pdf(
        [UploadedDocument("verticale.jpg", _jpeg(827, 1169)), UploadedDocument("orizzontale.jpg", _jpeg(1169, 827))],
        [0, 90],
        page_format="a4",
    )
    reader = PdfReader(io.BytesIO(data))
    assert pages == 2
    first, second = reader.pages
    assert (round(float(first.mediabox.width)), round(float(first.mediabox.height))) == (595, 842)
    assert (round(float(second.mediabox.width)), round(float(second.mediabox.height))) == (842, 595)
    assert second.rotation == 90


def test_formato_pagina_sconosciuto_respinto():
    with pytest.raises(DocumentToolError, match="Formato di pagina"):
        images_to_pdf([UploadedDocument("pagina.jpg", _jpeg())], page_format="lettera")


def _italian_tesseract_available() -> bool:
    if not shutil.which("tesseract"):
        return False
    try:
        output = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=20, check=False)
    except Exception:
        return False
    return "ita" in output.stdout.split()


@pytest.mark.skipif(not _italian_tesseract_available(), reason="Tesseract con dizionario italiano non installato")
def test_ocr_reale_in_italiano_produce_pdf_a4_ricercabile(monkeypatch):
    monkeypatch.setattr(document_ocr, "_LANGUAGE_READY", False)
    result = document_ocr.recognize_page(_jpeg(1654, 2339, ("TRIBUNALE ORDINARIO DI BARI", "Procura alle liti conferita all'avvocato.")))
    text = " ".join(result.paragraphs)
    assert "TRIBUNALE" in text and "Procura" in text
    with fitz.open(stream=result.pdf, filetype="pdf") as document:
        assert round(document[0].rect.width) == 595
        assert "BARI" in document[0].get_text()
