from types import SimpleNamespace

from PIL import Image, ImageDraw

from legal_ocr.motore import geometria_identita, identita, immagine
from legal_ocr.motore.preparazione_identita import prepara_riquadro_identita


def test_geometry_orientation_light_and_zoom_precede_ocr(monkeypatch):
    events = []
    def geometry(image):
        events.append('geometria')
        return SimpleNamespace(immagine=image.copy(), passaggi=('geometria misurata',))
    def orientation(image):
        events.append('orientamento')
        return 90
    monkeypatch.setattr(geometria_identita, 'prepara_geometria_identita', geometry)
    monkeypatch.setattr(identita, '_orientamento_riscontrato', orientation)
    monkeypatch.setattr(immagine, 'scala_caratteri_zona', lambda image: 2)
    real_phase = immagine.prepara_zona_testo
    def phase(image, diagnosis):
        events.append('luce')
        return real_phase(image, diagnosis)
    monkeypatch.setattr(immagine, 'prepara_zona_testo', phase)
    with Image.new('L', (256, 96), 120) as source:
        draw = ImageDraw.Draw(source)
        for x in range(16, 240, 20):
            draw.rectangle((x, 16, x + 5, 76), fill=20)
        before = source.tobytes()
        prepared = prepara_riquadro_identita(source)
        try:
            assert events == ['geometria', 'orientamento', 'luce']
            assert prepared.immagine.size == (192, 512)
            assert prepared.orientamento == 90 and prepared.scala == 2
            assert source.tobytes() == before
            light = next(i for i, step in enumerate(prepared.passaggi) if 'illuminazione normalizzata' in step)
            zoom = next(i for i, step in enumerate(prepared.passaggi) if 'Ingrandimento misurato' in step)
            assert light < zoom < len(prepared.passaggi) - 1
        finally:
            prepared.immagine.close()


def test_preparation_rejects_worsening_and_stops(monkeypatch):
    monkeypatch.setattr(geometria_identita, 'prepara_geometria_identita', lambda image:
                        SimpleNamespace(immagine=image.copy(), passaggi=()))
    monkeypatch.setattr(identita, '_orientamento_riscontrato', lambda image: 0)
    monkeypatch.setattr(immagine, 'scala_caratteri_zona', lambda image: 1)
    monkeypatch.setattr(immagine, 'prepara_zona_testo', lambda image, diagnosis:
                        immagine.PaginaPreparata(Image.new('L', image.size, 255), 216, 1, 0, ('perdita testo',)))
    with Image.new('L', (256, 96), 120) as source:
        for x in range(16, 240, 20):
            ImageDraw.Draw(source).rectangle((x, 16, x + 5, 76), fill=20)
        prepared = prepara_riquadro_identita(source)
        try:
            assert prepared.immagine.tobytes() == source.tobytes()
            assert any('scartata' in step for step in prepared.passaggi)
            assert not any('perdita testo' in step for step in prepared.passaggi)
        finally:
            prepared.immagine.close()
