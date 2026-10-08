"""Guardrail dei margini dopo la prova della scansione nella copia reale."""
from PIL import Image, ImageDraw

from legal_ocr.motore.immagine import ritaglia_bordo


def test_white_page_margins_are_not_cropped_as_external_background():
    image = Image.new('RGB', (1000, 1400), 'white')
    ImageDraw.Draw(image).rectangle((100, 120, 800, 750), fill='black')
    result, cropped = ritaglia_bordo(image)
    assert result is image and cropped is False
    assert result.size == (1000, 1400)


def test_empty_white_page_remains_intact():
    image = Image.new('RGB', (500, 700), 'white')
    result, cropped = ritaglia_bordo(image)
    assert result is image and cropped is False
