"""Misure e trattamenti condizionati; guardrail, non accettazione OCR reale."""
from PIL import Image, ImageDraw, ImageFilter

from legal_ocr.motore.immagine import diagnostica_zona_testo, prepara_zona_testo


def zone(background=255, ink=0):
    image = Image.new('L', (256, 96), background)
    draw = ImageDraw.Draw(image)
    for x in range(16, 240, 20):
        draw.rectangle((x, 16, x + 5, 76), fill=ink)
        draw.rectangle((x, 16, x + 13, 21), fill=ink)
    return image


def test_clear_zone_is_not_treated_and_original_is_preserved():
    image = zone()
    original = image.tobytes()
    diagnosis = diagnostica_zona_testo(image)
    assert not diagnosis.richiede_intervento
    prepared = prepara_zona_testo(image, diagnosis)
    assert prepared.passaggi == ()
    assert prepared.immagine.tobytes() == original
    assert image.tobytes() == original
    prepared.immagine.close()


def test_dark_zone_only_activates_relevant_light_treatment():
    image = zone(120, 20)
    diagnosis = diagnostica_zona_testo(image)
    assert diagnosis.scura and not diagnosis.chiara and not diagnosis.sfocata
    prepared = prepara_zona_testo(image, diagnosis)
    assert len(prepared.passaggi) == 1 and 'zona scura' in prepared.passaggi[0]
    assert prepared.rotazione_gradi == 0 and prepared.scala == 1
    prepared.immagine.close()


def test_washed_out_zone_detects_low_contrast():
    image = zone(250, 225)
    diagnosis = diagnostica_zona_testo(image)
    assert diagnosis.chiara and diagnosis.basso_contrasto and not diagnosis.scura
    prepared = prepara_zona_testo(image, diagnosis)
    assert any('contrasto' in step for step in prepared.passaggi)
    assert not any('illuminazione' in step for step in prepared.passaggi)
    prepared.immagine.close()


def test_blurred_zone_detects_attenuated_edges():
    blurred = zone().filter(ImageFilter.GaussianBlur(3))
    assert diagnostica_zona_testo(blurred).sfocata


def test_uniform_zone_does_not_invent_a_recoverable_signal():
    assert not diagnostica_zona_testo(Image.new('L', (100, 100), 250)).richiede_intervento


def test_each_diagnosed_treatment_is_a_separate_bounded_phase():
    from legal_ocr.motore.immagine import DiagnosiZonaTesto, passaggi_diagnosi_zona
    diagnosis = DiagnosiZonaTesto(True, True, True, True, 150, 40, .08, True)
    phases = list(passaggi_diagnosi_zona(diagnosis))
    assert len(phases) == 3
    assert phases[0].scura and phases[0].illuminazione_irregolare
    assert not phases[0].chiara and not phases[0].basso_contrasto and not phases[0].sfocata
    assert phases[1].chiara and phases[1].basso_contrasto
    assert not phases[1].scura and not phases[1].sfocata and not phases[1].illuminazione_irregolare
    assert phases[2].sfocata
    assert not phases[2].scura and not phases[2].chiara and not phases[2].basso_contrasto
    assert list(passaggi_diagnosi_zona(DiagnosiZonaTesto(False, False, False, False, 255, 80, .4))) == []


def test_cycle_stops_and_failed_phases_do_not_accumulate(monkeypatch):
    from types import SimpleNamespace
    from legal_ocr.motore import identita, immagine
    monkeypatch.setattr(immagine, 'scala_caratteri_zona', lambda image: 1)
    monkeypatch.setattr(immagine, 'inclinazione_stimata', lambda image: 0)
    monkeypatch.setattr(immagine, 'diagnostica_zona_testo', lambda image:
                        immagine.DiagnosiZonaTesto(True, True, True, True, 150, 40, .08))
    monkeypatch.setattr(immagine, 'separa_sfondo_zona_testo', lambda *args, **kwargs: None)
    bases, calls = [], []
    def phase(image, diagnosis):
        bases.append(image.getpixel((0, 0)))
        candidate = image.copy()
        candidate.putpixel((0, 0), 30 + len(bases))
        return immagine.PaginaPreparata(candidate, 216, 1, 0, ('fase singola',))
    monkeypatch.setattr(immagine, 'prepara_zona_testo', phase)
    source = SimpleNamespace(testo='testo insufficiente', confidenza=.6)
    def reader(image, **kwargs):
        calls.append(image.getpixel((0, 0)))
        return source
    monkeypatch.setattr(identita, 'leggi_con_secondo_lettore', reader)
    with Image.new('L', (160, 80), 220) as image:
        result, steps = identita._leggi_con_diagnosi(image, Image)
        assert image.getpixel((0, 0)) == 220
    assert bases == [220, 220, 220]
    assert calls == [220, 31, 32, 33]
    assert result is source and 'Nessun miglioramento accettato' in steps[-1]


def test_partial_shadow_is_detected_even_with_bright_background():
    image = zone()
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 127, 95), fill=120)
    for x in range(16, 120, 20):
        draw.rectangle((x, 16, x + 5, 76), fill=20)
    original = image.tobytes()
    diagnosis = diagnostica_zona_testo(image)
    assert diagnosis.illuminazione_irregolare and not diagnosis.scura
    prepared = prepara_zona_testo(image, diagnosis)
    assert any('sfondo disomogeneo' in step for step in prepared.passaggi)
    assert image.tobytes() == original
    prepared.immagine.close()


def test_glyph_size_controls_zoom_without_a4_assumptions():
    import pytest
    pytest.importorskip('cv2')
    from legal_ocr.motore.immagine import scala_caratteri_zona
    small = Image.new('L', (240, 50), 255)
    draw = ImageDraw.Draw(small)
    for x in range(10, 210, 20):
        draw.rectangle((x, 10, x + 2, 18), fill=0)
        draw.rectangle((x, 10, x + 6, 12), fill=0)
    assert 2 < scala_caratteri_zona(small) <= 4
    large = small.resize((960, 200), Image.Resampling.NEAREST)
    assert scala_caratteri_zona(large) == 1
    assert scala_caratteri_zona(Image.new('L', (240, 50), 255)) == 1


def test_pixel_background_selection_preserves_dark_strokes_and_original():
    from legal_ocr.motore.immagine import separa_sfondo_zona_testo
    image = Image.new('L', (160, 80), 220)
    draw = ImageDraw.Draw(image)
    for x in range(160):
        draw.line((x, 0, x, 79), fill=180 + x // 4)
    draw.text((20, 25), 'ROSSI 123', fill=25)
    original = image.tobytes()
    for mode in ('rimuovi', 'schiarisci', 'scurisci'):
        variant = separa_sfondo_zona_testo(image, modalita=mode)
        assert variant is not None
        changed = variant.immagine.tobytes()
        assert image.tobytes() == original
        assert all(after == before for before, after in zip(original, changed) if before <= 96)
        if mode == 'scurisci':
            assert any(after < before for before, after in zip(original, changed))
        else:
            assert any(after > before for before, after in zip(original, changed))
        variant.immagine.close()


def test_pixel_background_selection_is_skipped_for_clear_and_uniform_images():
    from legal_ocr.motore.immagine import separa_sfondo_zona_testo
    assert separa_sfondo_zona_testo(zone()) is None
    assert separa_sfondo_zona_testo(Image.new('L', (100, 100), 180)) is None


def test_common_reader_tries_all_background_modes_only_after_failed_reading(monkeypatch):
    from types import SimpleNamespace
    from legal_ocr.motore import identita, immagine
    monkeypatch.setattr(immagine, 'scala_caratteri_zona', lambda image: 1)
    monkeypatch.setattr(immagine, 'inclinazione_stimata', lambda image: 0)
    monkeypatch.setattr(immagine, 'diagnostica_zona_testo', lambda image: immagine.DiagnosiZonaTesto(False, False, False, False, 220, 80, .4))
    modes = []
    def variant(image, *, modalita):
        modes.append(modalita)
        return immagine.PaginaPreparata(image.copy(), 216, 1, 0, (modalita,))
    monkeypatch.setattr(immagine, 'separa_sfondo_zona_testo', variant)
    source = SimpleNamespace(testo="CARTA D'IDENTITÀ N. AB1234567", confidenza=.6)
    monkeypatch.setattr(identita, 'leggi_con_secondo_lettore', lambda *args, **kwargs: source)
    with Image.new('L', (160, 80), 220) as image:
        read, steps = identita._leggi_con_diagnosi(image, Image)
    assert modes == ['rimuovi', 'schiarisci', 'scurisci']
    assert read is source and 'Nessun miglioramento accettato' in steps[-1]
