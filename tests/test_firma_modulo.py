"""La firma del cliente nel campo firma del modulo, non in un angolo della pagina.

Su un modulo con i campi firma — un'autocertificazione, una procura alle liti,
un ricorso — la firma timbrata a coordinate fisse finisce lontano dal rigo
«Firma», e il modulo sembra non firmato.

I test girano su moduli PDF veri, con widget AcroForm veri.
"""

from __future__ import annotations

import io

import pytest

fitz = pytest.importorskip("pymupdf", reason="PyMuPDF non installato")
Image = pytest.importorskip("PIL.Image", reason="Pillow non installato")

from PIL import ImageDraw  # noqa: E402

from pct.firma_modulo import (  # noqa: E402
    campi_firma_del_documento,
    campi_firmabili,
    firma_nei_campi,
    tratto_trasparente,
)

CAMPO = (60.0, 310.0, 300.0, 344.0)


def _modulo(*, campi=(("firma", 310.0),), nascosti=()) -> bytes:
    documento = fitz.open()
    pagina = documento.new_page(width=595, height=842)
    pagina.insert_text((60, 120), "PROCURA ALLE LITI", fontsize=14)
    pagina.insert_text((60, 300), "Firma del conferente", fontsize=10)
    for nome, alto in campi:
        widget = fitz.Widget()
        widget.field_name = nome
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(60, alto, 300, alto + 34)
        widget.field_value = ""
        pagina.add_widget(widget)
    dati = documento.tobytes()
    documento.close()
    return dati


def _senza_campi() -> bytes:
    documento = fitz.open()
    documento.new_page(width=595, height=842).insert_text((60, 120), "Parere legale", fontsize=14)
    dati = documento.tobytes()
    documento.close()
    return dati


def _tratto_jpeg() -> bytes:
    """Il tratto come lo manda il portale: JPEG, quindi con lo sfondo bianco."""
    immagine = Image.new("RGB", (700, 300), (255, 255, 255))
    ImageDraw.Draw(immagine).line(
        [(120, 200), (180, 90), (250, 210), (330, 80), (420, 205), (520, 120)],
        fill=(12, 24, 92), width=8,
    )
    buffer = io.BytesIO()
    immagine.save(buffer, "JPEG", quality=92)
    return buffer.getvalue()


def _immagini(pdf: bytes) -> list[tuple[float, float, float, float]]:
    documento = fitz.open(stream=pdf, filetype="pdf")
    try:
        return [tuple(voce["bbox"]) for pagina in documento for voce in pagina.get_image_info()]
    finally:
        documento.close()


def _testo(pdf: bytes) -> str:
    documento = fitz.open(stream=pdf, filetype="pdf")
    try:
        return "".join(pagina.get_text() for pagina in documento)
    finally:
        documento.close()


def _widget(pdf: bytes) -> int:
    documento = fitz.open(stream=pdf, filetype="pdf")
    try:
        return sum(1 for pagina in documento for _ in pagina.widgets())
    finally:
        documento.close()


def test_la_firma_finisce_dentro_il_campo_firma():
    firmato = firma_nei_campi(_modulo(), _tratto_jpeg())
    assert firmato, "il modulo ha un campo firma e non e' stato firmato"
    riquadri = _immagini(firmato)
    assert len(riquadri) == 1, f"attesa una firma, trovate {len(riquadri)}"
    x0, alto, _, basso = riquadri[0]
    assert CAMPO[0] <= x0 <= CAMPO[2], "la firma e' fuori dal campo in orizzontale"
    assert CAMPO[1] - 6 <= alto <= CAMPO[3], f"la firma e' fuori dal rigo: y={alto}"
    assert 8 <= basso - alto <= 45, "la firma non ha la misura di una firma a penna"


def test_il_modulo_firmato_non_e_piu_compilabile():
    """Un modulo che resta compilabile puo' essere cambiato dopo la firma.

    Un documento del genere non prova nulla: art. 20 D.Lgs. 82/2005, integrita'
    del documento informatico.
    """
    assert _widget(_modulo()) == 1, "il modulo di prova non ha il campo"
    assert _widget(firma_nei_campi(_modulo(), _tratto_jpeg())) == 0


def test_un_documento_senza_campi_firma_non_viene_toccato():
    """Una lettera o un parere non sono moduli: li firma il timbro di sempre."""
    assert firma_nei_campi(_senza_campi(), _tratto_jpeg()) is None


def test_senza_tratto_non_si_firma_niente():
    assert firma_nei_campi(_modulo(), b"") is None
    assert firma_nei_campi(b"", _tratto_jpeg()) is None


def test_ogni_campo_firma_del_modulo_riceve_la_sua_firma():
    modulo = _modulo(campi=(("firma_dichiarazione", 310.0), ("firma_privacy", 430.0)))
    assert len(campi_firmabili_da(modulo)) == 2
    assert len(_immagini(firma_nei_campi(modulo, _tratto_jpeg()))) == 2


def campi_firmabili_da(pdf: bytes):
    return campi_firma_del_documento(pdf)


def test_lo_sfondo_bianco_del_tratto_diventa_trasparente():
    """Il JPEG non ha trasparenza: incollato cosi' coprirebbe il rigo del modulo."""
    png = tratto_trasparente(_tratto_jpeg())
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "il tratto non e' stato convertito in PNG"
    with Image.open(io.BytesIO(png)) as immagine:
        assert immagine.mode == "RGBA"
        assert immagine.getpixel((5, 5))[3] == 0, "l'angolo bianco non e' trasparente"
        alfa = immagine.getchannel("A")
        trasparenti = sum(conteggio for valore, conteggio in enumerate(alfa.histogram()) if valore == 0)
        opachi = immagine.size[0] * immagine.size[1] - trasparenti
        assert opachi > 0, "il tratto e' sparito del tutto"
        assert trasparenti > opachi, "lo sfondo non e' stato reso trasparente"


def test_il_documento_dice_chi_ha_firmato_e_quando():
    """Chi legge il documento fuori dallo studio non ha accesso al registro delle prove."""
    firmato = firma_nei_campi(_modulo(), _tratto_jpeg(),
                              nota="Firmato elettronicamente da Mario Rossi · 18/09/2026 14:32 · Rif. a1b2c3d4")
    testo = _testo(firmato)
    assert "Mario Rossi" in testo
    assert "18/09/2026 14:32" in testo
    assert "a1b2c3d4" in testo
    assert "PROCURA ALLE LITI" in testo, "la nota ha coperto il modulo"


def test_il_portale_usa_il_campo_sul_modulo_e_il_timbro_sulla_lettera():
    """Il ponte con il portale clienti: stessa chiamata, due comportamenti giusti."""
    from web.services.client_signature_providers import apply_visible_signature_stamp

    tratto = _tratto_jpeg()
    su_modulo = apply_visible_signature_stamp(
        _modulo(), signer_name="Mario Rossi", when_label="18/09/2026 14:32",
        reference="a1b2c3d4", signature_image=tratto,
    )
    assert _widget(su_modulo) == 0, "il modulo firmato e' rimasto compilabile"
    assert "Firma elettronica del cliente" not in _testo(su_modulo), \
        "sul modulo non ci va il riquadro del timbro"
    assert "Mario Rossi" in _testo(su_modulo)

    su_lettera = apply_visible_signature_stamp(
        _senza_campi(), signer_name="Mario Rossi", signature_image=tratto,
    )
    assert "Firma elettronica del cliente" in _testo(su_lettera), \
        "senza campi firma deve restare il timbro di sempre"


def test_un_guasto_nella_firma_del_modulo_non_ferma_la_firma_del_cliente(monkeypatch):
    """Il timbro di sempre e' il ripiego: la firma non deve mai fallire per questo."""
    from web.services import client_signature_providers as provider

    def esplode(*args, **kwargs):
        raise RuntimeError("PyMuPDF rotto")

    monkeypatch.setattr("pct.firma_modulo.firma_nei_campi", esplode)
    firmato = provider.apply_visible_signature_stamp(
        _modulo(), signer_name="Mario Rossi", signature_image=_tratto_jpeg(),
    )
    assert "Firma elettronica del cliente" in _testo(firmato)
