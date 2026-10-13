"""Compilazione nativa nel lettore: campi, geometria e integrità della fonte."""

from types import SimpleNamespace

import fitz
import pytest

from pct.mediazione_documenti import campi_pdf, contiene_modulo_pdf
from web.services.pdf_overlay_editor import PdfOverlayError, apply_pdf_overlays


def modulo(*, rotation=0, readonly=False):
    with fitz.open() as doc:
        page = doc.new_page(width=400, height=600)
        page.insert_text((30, 60), "Fonte originale da preservare")
        widget = fitz.Widget()
        widget.field_name = "cliente"
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(40, 300, 280, 330)
        widget.field_value = ""
        widget.field_flags = 1 if readonly else 0
        page.add_widget(widget)
        page.set_rotation(rotation)
        return doc.tobytes()


def test_compilazione_conserva_fonte_e_pixel_fuori_dal_campo():
    source = modulo()
    modified, count = apply_pdf_overlays(source, [{"type": "form", "values": {"cliente": "Attività à è ì ò ù"}}])
    assert count == 1
    with fitz.open(stream=source, filetype="pdf") as original, fitz.open(stream=modified, filetype="pdf") as result:
        assert next(original[0].widgets()).field_value == ""
        assert next(result[0].widgets()).field_value == "Attività à è ì ò ù"
        area = fitz.Rect(0, 0, 400, 290)
        assert original[0].get_pixmap(clip=area).samples == result[0].get_pixmap(clip=area).samples


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_anteprima_pdfium_mostra_valori_salvati_senza_modificare_la_fonte(rotation):
    import io

    from PIL import Image, ImageChops

    from pct.rendering_pdf import pagina_png

    source = modulo(rotation=rotation)
    modified, _ = apply_pdf_overlays(source, [{"type": "form", "values": {"cliente": "Attività verificata"}}])
    before = Image.open(io.BytesIO(pagina_png(source, numero_pagina=1, scala=1))).convert("RGB")
    after = Image.open(io.BytesIO(pagina_png(modified, numero_pagina=1, scala=1))).convert("RGB")
    field = campi_pdf(modified)[0]
    x, y, width, height = field["rettangolo"]
    rect = (int(x * after.width), int(y * after.height), int((x + width) * after.width), int((y + height) * after.height))
    assert ImageChops.difference(before.crop(rect), after.crop(rect)).getbbox() is not None
    before.paste((255, 255, 255), rect)
    after.paste((255, 255, 255), rect)
    assert ImageChops.difference(before, after).getbbox() is None
    assert campi_pdf(source)[0]["valore"] == ""
    assert campi_pdf(modified)[0]["valore"] == "Attività verificata"


def test_acquisizione_riconosce_modulo_senza_confonderlo_con_pdf_statico():
    assert contiene_modulo_pdf(modulo())
    with fitz.open() as doc:
        doc.new_page().insert_text((30, 60), "Documento statico")
        assert not contiene_modulo_pdf(doc.tobytes())
    assert not contiene_modulo_pdf(b"%PDF- documento danneggiato")
    assert not contiene_modulo_pdf(b"testo senza PDF")


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_coordinate_campi_seguono_rotazione_pagina(rotation):
    source = modulo(rotation=rotation)
    field = campi_pdf(source)[0]
    with fitz.open(stream=source, filetype="pdf") as doc:
        page = doc[0]
        rect = fitz.Rect(40, 300, 280, 330) * page.rotation_matrix
        expected = [rect.x0 / page.rect.width, rect.y0 / page.rect.height, rect.width / page.rect.width, rect.height / page.rect.height]
    assert field["rettangolo"] == pytest.approx(expected)


@pytest.mark.parametrize("values", [{}, {"assente": "testo"}, {"cliente": 42}, {"cliente": "a" * 10001}])
def test_valori_non_ammessi_non_producono_un_pdf(values):
    with pytest.raises(PdfOverlayError):
        apply_pdf_overlays(modulo(), [{"type": "form", "values": values}])


def test_campo_bloccato_non_si_modifica():
    with pytest.raises(PdfOverlayError):
        apply_pdf_overlays(modulo(readonly=True), [{"type": "form", "values": {"cliente": "Test"}}])


def test_non_mescola_compilazione_e_interventi_grafici():
    with pytest.raises(PdfOverlayError, match="prima degli altri"):
        apply_pdf_overlays(modulo(), [{"type": "form", "values": {"cliente": "Test"}}, {"type": "highlight"}])


def test_api_rispetta_permessi_fascicolo_e_versione(monkeypatch, tmp_path):
    from flask import Flask, g

    import web.helpers
    from web.bootstrap.viewer_editor_routes import register_viewer_editor_routes

    path = tmp_path / "modulo.pdf"
    path.write_bytes(modulo(rotation=90))
    document = SimpleNamespace(id="documento", nome="Modulo.pdf", hash_sha256="impronta", versioni=[], eliminato_il="")
    case = SimpleNamespace(documenti=[document])
    manager = SimpleNamespace(get=lambda fid: case if fid == "autorizzato" else None,
                              percorso_documento_lettura=lambda fid, did: path)
    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: manager)
    app = Flask(__name__)
    allowed = {"fascicoli.leggi", "fascicoli.scrivi"}

    @app.before_request
    def user():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda p: p in allowed)

    register_viewer_editor_routes(app)
    client = app.test_client()
    url = "/api/v1/ui/fascicoli/autorizzato/documenti/documento/editor-visualizzatore/modulo"
    response = client.get(url + "?expectedHash=impronta")
    assert response.status_code == 200
    assert response.json["campi"][0]["nome"] == "cliente"
    assert response.json["pagine"][0]["larghezza"] == 600
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get(url + "?expectedHash=vecchia").status_code == 409
    assert client.get(url.replace("autorizzato", "altro") + "?expectedHash=impronta").status_code == 404
    allowed.remove("fascicoli.scrivi")
    assert client.get(url + "?expectedHash=impronta").status_code == 403


def test_caricamento_normale_conserva_byte_campi_rotazione_e_deduplica(tmp_path, monkeypatch):
    import io

    from pct.document_crypto import decrypt_doc
    from pct.fascicoli import TipoFascicolo
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login
    from web.helpers import get_fascicoli

    monkeypatch.setattr("web.bootstrap.fascicoli_document_routes.indicizza_documento_lex", lambda *a, **k: None)
    app = _app(tmp_path)
    source = modulo(rotation=90)
    with app.test_request_context("/"):
        case = get_fascicoli().nuovo("Collaudo modulo", TipoFascicolo.CIVILE)
    with app.test_client() as client:
        _login(client)
        responses = [client.post(
            f"/fascicoli/{case.id}/documenti/carica",
            data={"files": (io.BytesIO(source), "Modulo.pdf"), "classificazione_modalita": "auto"},
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
            content_type="multipart/form-data",
        ) for _ in range(2)]
        assert all(r.status_code == 200 and r.json["ok"] for r in responses)
        assert responses[0].json["documenti_id"] == responses[1].json["documenti_id"]
        document_id = responses[0].json["documenti_id"][0]
        with app.test_request_context("/"):
            manager = get_fascicoli()
            from pathlib import Path
            persisted = decrypt_doc(Path(manager.percorso_documento_lettura(case.id, document_id)).read_bytes())
            assert persisted == source
            assert len(manager.get(case.id).documenti) == 1
            assert campi_pdf(persisted)[0]["nome"] == "cliente"
