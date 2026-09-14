"""Riconoscimento del testo di un documento del fascicolo o di un file caricato.

Le prove non verificano la qualita' dell'OCR (dipende dal motore installato) ma
le decisioni che rendono la funzione utilizzabile su atti veri: una pagina che
ha gia' il testo non va riconosciuta di nuovo, una busta firmata `.p7m` deve
essere aperta, un PDF protetto deve dirlo in italiano invece di rompersi, e il
testo corretto dall'avvocato deve arrivare all'editor senza portarsi dietro
codice arrivato dal browser.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import fitz
import pytest
from flask import Flask, g
from PIL import Image

from web.blueprints import api_v1_document_tools as blueprint_module
from web.blueprints.api_v1_document_tools import api_v1_document_tools
from web.services import document_ocr_documento as riconoscimento
from web.services import fascicolo_documento_ocr as sorgente_fascicolo
from web.services.document_ocr import OcrPageResult
from web.services.document_tools import DocumentToolError
from web.services.documento_testo_riconosciuto import (
    docx_da_testo,
    html_consentito,
    nome_file_documento,
)


def _pdf_con_testo(pagine: int = 1, testo: str = "") -> bytes:
    documento = fitz.open()
    corpo = testo or (
        "TRIBUNALE ORDINARIO DI BARI\n"
        "Il sottoscritto avvocato chiede la fissazione dell'udienza di comparizione\n"
        "delle parti ai sensi dell'articolo 183 del codice di procedura civile."
    )
    for indice in range(pagine):
        pagina = documento.new_page(width=595, height=842)
        pagina.insert_textbox(fitz.Rect(60, 60, 535, 500), f"{corpo}\nPagina {indice + 1}", fontsize=12)
    dati = documento.tobytes()
    documento.close()
    return dati


def _pdf_senza_testo(pagine: int = 1) -> bytes:
    documento = fitz.open()
    for _ in range(pagine):
        documento.new_page(width=595, height=842)
    dati = documento.tobytes()
    documento.close()
    return dati


def _immagine() -> bytes:
    uscita = io.BytesIO()
    Image.new("RGB", (827, 1169), "white").save(uscita, "JPEG")
    return uscita.getvalue()


@pytest.fixture()
def niente_ocr(monkeypatch):
    """Sostituisce il motore OCR: qui si prova la regia, non il riconoscimento."""
    chiamate: list[int] = []

    def _finto(data: bytes, rotation: int = 0, *, raddrizza: bool = True) -> OcrPageResult:
        chiamate.append(len(data))
        return OcrPageResult(
            pdf=b"%PDF-1.4 finto",
            paragraphs=["Testo letto dalla scansione"],
            dpi=300,
            blocks=[{"tipo": "paragrafo", "testo": "Testo letto dalla scansione", "confidenza": 0.9, "pagina": 1}],
            figures=[],
            confidence=0.9,
            engine="tesseract · prova",
        )

    monkeypatch.setattr(riconoscimento, "recognize_page", _finto)
    return chiamate


# ── Quante pagine ha il documento ──────────────────────────────────────────


def test_le_pagine_del_pdf_sono_quelle_del_documento():
    assert riconoscimento.conta_pagine(_pdf_con_testo(pagine=4), "atto.pdf") == 4


def test_una_immagine_vale_una_pagina():
    assert riconoscimento.conta_pagine(_immagine(), "scansione.jpg") == 1


def test_un_documento_vuoto_lo_dice_in_italiano():
    with pytest.raises(DocumentToolError, match="vuoto"):
        riconoscimento.conta_pagine(b"", "atto.pdf")


def test_un_pdf_protetto_da_password_non_si_apre_di_nascosto():
    documento = fitz.open()
    documento.new_page()
    protetto = documento.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="x", user_pw="y")
    documento.close()
    with pytest.raises(DocumentToolError, match="password"):
        riconoscimento.conta_pagine(protetto, "atto.pdf")


def test_un_formato_non_leggibile_spiega_cosa_si_puo_riconoscere():
    with pytest.raises(DocumentToolError, match="PDF, immagini e atti firmati"):
        riconoscimento.conta_pagine(b"PK\x03\x04 foglio di calcolo", "tabella.xlsx")


# ── Testo gia' presente contro riconoscimento ottico ───────────────────────


def test_una_pagina_con_testo_non_viene_riconosciuta_di_nuovo(niente_ocr):
    """Il testo dell'autore e' esatto: passarlo all'OCR peggiorerebbe il risultato."""
    esito = riconoscimento.riconosci_pagina(_pdf_con_testo(), "atto.pdf", 1)
    assert esito.origine == riconoscimento.ORIGINE_TESTO
    assert esito.confidence == 1.0
    assert niente_ocr == [], "l'OCR e' stato chiamato su una pagina che aveva gia' il testo"
    assert any("TRIBUNALE" in paragrafo for paragrafo in esito.paragraphs)
    assert esito.blocks and esito.characters > 50
    assert esito.pdf.startswith(b"%PDF-")


def test_una_pagina_senza_testo_passa_al_riconoscimento_ottico(niente_ocr):
    esito = riconoscimento.riconosci_pagina(_pdf_senza_testo(), "scansione.pdf", 1)
    assert esito.origine == riconoscimento.ORIGINE_OCR
    assert niente_ocr, "la pagina immagine doveva essere riconosciuta con l'OCR"
    assert esito.paragraphs == ["Testo letto dalla scansione"]


def test_una_filigrana_non_basta_a_considerare_la_pagina_gia_leggibile(niente_ocr):
    """Poche parole (numero di pagina, timbro) non sono il contenuto dell'atto."""
    documento = fitz.open()
    pagina = documento.new_page(width=595, height=842)
    pagina.insert_text((60, 800), "pag. 1", fontsize=9)
    scarno = documento.tobytes()
    documento.close()
    esito = riconoscimento.riconosci_pagina(scarno, "scansione.pdf", 1)
    assert esito.origine == riconoscimento.ORIGINE_OCR
    assert niente_ocr


def test_ogni_pagina_richiesta_e_quella_che_torna(niente_ocr):
    dati = _pdf_con_testo(pagine=3)
    for numero in (1, 2, 3):
        esito = riconoscimento.riconosci_pagina(dati, "atto.pdf", numero)
        assert esito.numero == numero
        assert any(f"Pagina {numero}" in paragrafo for paragrafo in esito.paragraphs)


def test_una_pagina_oltre_la_fine_dice_quante_ne_ha_il_documento(niente_ocr):
    with pytest.raises(DocumentToolError, match="2 pagine"):
        riconoscimento.riconosci_pagina(_pdf_con_testo(pagine=2), "atto.pdf", 5)


def test_un_atto_firmato_p7m_viene_aperto_per_leggerne_il_pdf(niente_ocr):
    """Gli atti depositati arrivano come `.pdf.p7m`: dentro c'e' il PDF."""
    busta = b"\x30\x82\x01\x00 firma CAdES " + _pdf_con_testo() + b" coda della busta"
    esito = riconoscimento.riconosci_pagina(busta, "ricorso.pdf.p7m", 1)
    assert esito.origine == riconoscimento.ORIGINE_TESTO
    assert any("TRIBUNALE" in paragrafo for paragrafo in esito.paragraphs)


def test_una_busta_senza_pdf_lo_dice_invece_di_rompersi(niente_ocr):
    with pytest.raises(DocumentToolError, match="non contiene un PDF"):
        riconoscimento.riconosci_pagina(b"\x30\x82 solo firma", "atto.pdf.p7m", 1)


def test_una_immagine_ha_una_pagina_sola(niente_ocr):
    with pytest.raises(DocumentToolError, match="una sola pagina"):
        riconoscimento.riconosci_pagina(_immagine(), "foto.jpg", 2)


def test_il_payload_per_la_pagina_react_porta_struttura_e_pdf(niente_ocr):
    payload = riconoscimento.come_payload(riconoscimento.riconosci_pagina(_pdf_con_testo(), "atto.pdf", 1))
    assert payload["origine"] == "testo"
    assert payload["origine_etichetta"]
    assert payload["pdf_base64"] and payload["blocks"] and payload["characters"] > 0


# ── Il fascicolo come sorgente ─────────────────────────────────────────────


@dataclass
class _Documento:
    id: str
    nome: str
    dimensione_bytes: int = 2048
    sezione: str = "atti"
    tipo: str = "RICORSO"
    firmato_digitalmente: bool = False


class _Fascicolo:
    def __init__(self, documenti):
        self.documenti = documenti


class _Gestore:
    def __init__(self, documenti, percorsi=None):
        self._fascicolo = _Fascicolo(documenti)
        self._percorsi = percorsi or {}

    def get(self, identificativo):
        return self._fascicolo if identificativo == "F1" else None

    def percorso_documento_lettura(self, id_fasc, id_doc):
        return self._percorsi[id_doc]


def test_nell_elenco_entrano_solo_i_documenti_leggibili():
    """Offrire un foglio di calcolo significa mandare l'avvocato in un errore."""
    gestore = _Gestore([
        _Documento("d1", "Ricorso.pdf"),
        _Documento("d2", "Scansione.jpg"),
        _Documento("d3", "Comparsa.pdf.p7m"),
        _Documento("d4", "Conteggio.xlsx"),
        _Documento("d5", "DatiAtto.xml"),
    ])
    elencati = [voce["id"] for voce in sorgente_fascicolo.documenti_riconoscibili(gestore, "F1")]
    assert elencati == ["d1", "d2", "d3"]


def test_l_elenco_dice_formato_dimensione_e_sezione():
    voce = sorgente_fascicolo.documenti_riconoscibili(_Gestore([_Documento("d1", "Ricorso.pdf")]), "F1")[0]
    assert voce["formato"] == "pdf"
    assert voce["dimensione"] == "2 KB"
    assert voce["sezione"] == "atti"


def test_un_fascicolo_inesistente_non_apre_un_errore_interno():
    with pytest.raises(DocumentToolError, match="Fascicolo non trovato"):
        sorgente_fascicolo.documenti_riconoscibili(_Gestore([]), "ALTRO")


def test_il_documento_del_fascicolo_arriva_in_chiaro(tmp_path):
    percorso = tmp_path / "ricorso.pdf"
    percorso.write_bytes(_pdf_con_testo())
    gestore = _Gestore([_Documento("d1", "Ricorso.pdf")], {"d1": percorso})
    nome, contenuto = sorgente_fascicolo.leggi_documento(gestore, "F1", "d1")
    assert nome == "Ricorso.pdf"
    assert contenuto.startswith(b"%PDF-")


def test_un_documento_di_un_altro_fascicolo_non_si_legge(tmp_path):
    gestore = _Gestore([_Documento("d1", "Ricorso.pdf")], {"d1": tmp_path / "x.pdf"})
    with pytest.raises(DocumentToolError, match="non presente in questo fascicolo"):
        sorgente_fascicolo.leggi_documento(gestore, "F1", "d9")


def test_un_file_sparito_dal_server_lo_dice_all_avvocato(tmp_path):
    gestore = _Gestore([_Documento("d1", "Ricorso.pdf")], {"d1": tmp_path / "mancante.pdf"})
    with pytest.raises(DocumentToolError, match="non è più presente"):
        sorgente_fascicolo.leggi_documento(gestore, "F1", "d1")


# ── Dal testo corretto al documento dell'editor ────────────────────────────


def test_il_testo_corretto_perde_codice_stili_e_collegamenti():
    pulito = html_consentito(
        '<p onclick="x">Comparsa <strong>conclusionale</strong></p>'
        '<script>fetch("/rubare")</script><style>p{display:none}</style>'
        '<a href="http://esterno">link</a><img src="http://esterno/x.png">'
    )
    assert "<p>Comparsa <strong>conclusionale</strong></p>" in pulito
    assert "script" not in pulito and "onclick" not in pulito and "href" not in pulito
    assert "fetch" not in pulito, "il contenuto dello script non deve finire nel documento"


def test_la_tabella_riconosciuta_resta_una_tabella():
    pulito = html_consentito('<table border="1"><tr><th>Voce</th><td>Importo</td></tr></table>')
    assert pulito.startswith("<table") and "<th>Voce</th>" in pulito and 'border="1"' in pulito


def test_un_testo_senza_contenuto_non_diventa_un_documento_vuoto():
    with pytest.raises(DocumentToolError, match="Non c'è testo"):
        html_consentito("<p></p><p>   </p>")


def test_il_nome_dice_che_e_una_trascrizione_e_non_l_originale():
    assert nome_file_documento("Ricorso Rossi.pdf") == "Ricorso Rossi - testo riconosciuto.docx"
    assert "/" not in nome_file_documento("cartella/atto:2026.pdf")


def test_il_documento_per_l_editor_e_un_docx_apribile():
    from pct.editor import estensione_editabile

    dati, nome = docx_da_testo("<p>TRIBUNALE DI BARI</p><ul><li>prima voce</li></ul>", "Verbale udienza.pdf")
    assert dati[:2] == b"PK", "il documento non e' un .docx"
    assert estensione_editabile(nome), "l'editor del fascicolo non aprirebbe questo formato"


# ── Gli endpoint che la pagina chiama davvero ──────────────────────────────


def _app(monkeypatch, gestore) -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _autentica():
        g.utente_corrente = object()

    monkeypatch.setattr(blueprint_module, "get_fascicoli", lambda: gestore)
    monkeypatch.setattr(blueprint_module, "_audit_event", lambda *a, **k: None)
    app.register_blueprint(api_v1_document_tools, url_prefix="/api/v1/ui/document-tools")
    return app


def test_l_elenco_dei_documenti_riconoscibili_risponde_alla_pagina(monkeypatch):
    gestore = _Gestore([_Documento("d1", "Ricorso.pdf"), _Documento("d2", "Conteggio.xlsx")])
    client = _app(monkeypatch, gestore).test_client()
    payload = client.get("/api/v1/ui/document-tools/fascicoli/F1/documenti-riconoscibili").get_json()
    assert payload["ok"] is True
    assert [voce["id"] for voce in payload["documents"]] == ["d1"]


def test_la_pagina_riconosce_un_documento_del_fascicolo(monkeypatch, tmp_path, niente_ocr):
    percorso = tmp_path / "ricorso.pdf"
    percorso.write_bytes(_pdf_con_testo(pagine=2))
    gestore = _Gestore([_Documento("d1", "Ricorso.pdf")], {"d1": percorso})
    client = _app(monkeypatch, gestore).test_client()
    risposta = client.post(
        "/api/v1/ui/document-tools/ocr-documento",
        data={"fascicolo_id": "F1", "documento_id": "d1", "pagina": "2"},
    )
    payload = risposta.get_json()
    assert risposta.status_code == 200 and payload["ok"] is True
    assert payload["pagine_totali"] == 2
    assert payload["pagina"]["numero"] == 2
    assert payload["pagina"]["origine"] == "testo"
    assert payload["pagina"]["pdf_base64"]


def test_la_pagina_riconosce_anche_un_file_caricato(monkeypatch, niente_ocr):
    client = _app(monkeypatch, _Gestore([])).test_client()
    risposta = client.post(
        "/api/v1/ui/document-tools/ocr-documento",
        data={"pagina": "1", "file": (io.BytesIO(_pdf_con_testo()), "memoria.pdf")},
        content_type="multipart/form-data",
    )
    payload = risposta.get_json()
    assert payload["ok"] is True and payload["nome"] == "memoria.pdf"


def test_senza_sorgente_l_endpoint_dice_cosa_scegliere(monkeypatch):
    client = _app(monkeypatch, _Gestore([])).test_client()
    risposta = client.post("/api/v1/ui/document-tools/ocr-documento", data={"pagina": "1"})
    assert risposta.status_code == 400
    assert "documento del fascicolo" in risposta.get_json()["message"]


def test_l_endpoint_del_documento_per_l_editor_restituisce_un_docx(monkeypatch):
    client = _app(monkeypatch, _Gestore([])).test_client()
    risposta = client.post(
        "/api/v1/ui/document-tools/documento-testo-riconosciuto",
        data={"html": "<p>Testo riletto dall'avvocato</p>", "nome": "Verbale.pdf"},
    )
    assert risposta.status_code == 200
    assert risposta.data[:2] == b"PK"
    assert "testo riconosciuto.docx" in risposta.headers["Content-Disposition"]


def test_un_testo_vuoto_non_crea_un_documento_nell_editor(monkeypatch):
    client = _app(monkeypatch, _Gestore([])).test_client()
    risposta = client.post(
        "/api/v1/ui/document-tools/documento-testo-riconosciuto", data={"html": "", "nome": "x.pdf"}
    )
    assert risposta.status_code == 400
    assert "Non c'è testo" in risposta.get_json()["message"]


# ── Contratto con la pagina React ──────────────────────────────────────────


def test_la_sezione_acquisisci_del_fascicolo_espone_il_riconoscimento():
    from pathlib import Path

    radice = Path(__file__).resolve().parents[1] / "frontend" / "src"
    pagina = (radice / "components/FascicoliPage.tsx").read_text(encoding="utf-8")
    componente = (radice / "components/documentCapture/FascicoloOcr.tsx").read_text(encoding="utf-8")
    servizio = (radice / "services/documentoOcr.ts").read_text(encoding="utf-8")

    assert "FascicoloOcr" in pagina, "il riconoscimento non e' montato nella sezione documenti del fascicolo"
    # Le due sorgenti chieste: il documento gia' nel fascicolo e il file da caricare.
    assert "Documento già nel fascicolo" in componente and "File dal computer" in componente
    # La revisione modificabile precede qualunque uso del testo.
    assert "OcrReview" in componente
    # Il passaggio all'editor gia' esistente del fascicolo.
    assert "Apri nell’editor del fascicolo" in componente
    assert "/documenti/${encodeURIComponent(documentoId)}/editor" in servizio
    assert "/api/v1/ui/document-tools/ocr-documento" in servizio
    assert "/api/v1/ui/document-tools/documento-testo-riconosciuto" in servizio
    assert "style={{" not in componente, "gli stili in linea sono vietati dal gate design system"
