"""Geometria e rappresentazione devono coincidere prima di usare pixel nativi."""
from io import BytesIO

from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import (ArrayObject, BooleanObject, DecodedStreamObject, DictionaryObject,
                           EncodedStreamObject, FloatObject, NameObject, NumberObject)
import pytest

from legal_ocr.motore.fonte_identita import immagine_nativa_copertina


def pdf_image(*, matrix=(160, 0, 0, 100, 25, 40), operations=None, image_fields=None,
              page_fields=None, extra_unused=False, crop=None):
    jpeg = BytesIO()
    with Image.new('RGB', (160, 100), '#123456') as image:
        image.save(jpeg, format='JPEG')
    writer = PdfWriter()
    page = writer.add_blank_page(300, 400)
    obj = EncodedStreamObject()
    obj._data = jpeg.getvalue()
    obj.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                NameObject('/Width'): NumberObject(160), NameObject('/Height'): NumberObject(100),
                NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8),
                NameObject('/Filter'): NameObject('/DCTDecode')})
    obj.update(image_fields or {})
    objects = DictionaryObject({NameObject('/I1'): writer._add_object(obj)})
    if extra_unused:
        objects[NameObject('/Unused')] = writer._add_object(obj)
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'): objects})
    content = DecodedStreamObject()
    data = operations if operations is not None else f"0.57 w 0 G q {' '.join(map(str, matrix))} cm /I1 Do Q"
    content.set_data(data.encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(content)
    page.update(page_fields or {})
    if crop:
        page[NameObject('/CropBox')] = ArrayObject([FloatObject(v) for v in crop])
    output = BytesIO()
    writer.write(output)
    return output.getvalue(), jpeg.getvalue()


@pytest.mark.parametrize('unused', [False, True])
def test_native_pixels_preserved_for_single_painted_image(unused):
    pdf, jpeg = pdf_image(extra_unused=unused)
    image, audit = immagine_nativa_copertina(pdf, 0)
    assert image is not None and image.size == (160, 100)
    with Image.open(BytesIO(jpeg)).convert('RGB') as original:
        assert image.tobytes() == original.tobytes()
    image.close()
    assert 'senza ricampionamento' in audit[0]


@pytest.mark.parametrize('matrix', [
    (0, 160, -100, 0, 25, 40), (-160, 0, 0, 100, 185, 40),
    (160, 1, 0, 100, 25, 40), (160, 0, 0, 120, 25, 40),
    (160, 0, 0, 100, -1, 40), (160, 0, 0, 100, 150, 40),
])
def test_rotation_mirroring_shear_distortion_and_clipping_are_rejected(matrix):
    pdf, _ = pdf_image(matrix=matrix)
    image, audit = immagine_nativa_copertina(pdf, 0)
    assert image is None and audit


@pytest.mark.parametrize('operations', [
    'q 160 0 0 100 25 40 cm /I1 Do /I1 Do Q',
    'q 0 0 200 200 re W n 160 0 0 100 25 40 cm /I1 Do Q',
    'q 160 0 0 100 25 40 cm /I1 Do Q BT ET',
    'q 160 0 0 100 25 40 cm /I1 Do Q 0 0 20 20 re f',
    'q /Gs1 gs 160 0 0 100 25 40 cm /I1 Do Q',
    'q 160 0 0 100 25 40 cm /I1 Do',
])
def test_additional_painting_clip_text_transparency_or_unbalanced_state_rejected(operations):
    pdf, _ = pdf_image(operations=operations)
    image, audit = immagine_nativa_copertina(pdf, 0)
    assert image is None and audit


@pytest.mark.parametrize('field,value', [
    ('/Mask', ArrayObject([NumberObject(0), NumberObject(255)])),
    ('/SMask', NameObject('/None')), ('/ImageMask', BooleanObject(True)),
    ('/SMaskInData', NumberObject(1)), ('/Decode', ArrayObject([NumberObject(1), NumberObject(0)])),
    ('/DecodeParms', DictionaryObject()), ('/Subtype', NameObject('/Form')),
    ('/ColorSpace', NameObject('/DeviceCMYK')),
])
def test_masks_or_nontrivial_pixel_representation_are_rejected(field, value):
    pdf, _ = pdf_image(image_fields={NameObject(field): value})
    assert immagine_nativa_copertina(pdf, 0)[0] is None


@pytest.mark.parametrize('page_fields', [
    {NameObject('/Rotate'): NumberObject(90)},
    {NameObject('/UserUnit'): NumberObject(2)},
    {NameObject('/Annots'): ArrayObject([DictionaryObject({NameObject('/Subtype'): NameObject('/Square')})])},
    {NameObject('/Group'): DictionaryObject()},
])
def test_page_rotation_units_annotations_and_group_are_rejected(page_fields):
    pdf, _ = pdf_image(page_fields=page_fields)
    assert immagine_nativa_copertina(pdf, 0)[0] is None


def test_cropbox_clipping_is_rejected():
    pdf, _ = pdf_image(crop=(30, 0, 300, 400))
    assert immagine_nativa_copertina(pdf, 0)[0] is None


@pytest.mark.parametrize('appearance', ['invisible', 'border', 'appearance'])
def test_only_link_with_no_possible_visible_appearance_is_allowed(appearance):
    link = DictionaryObject({NameObject('/Subtype'): NameObject('/Link'),
                             NameObject('/Border'): ArrayObject([NumberObject(0)] * 3)})
    if appearance == 'border':
        link[NameObject('/Border')][2] = NumberObject(1)
    elif appearance == 'appearance':
        link[NameObject('/AP')] = DictionaryObject()
    pdf, _ = pdf_image(page_fields={NameObject('/Annots'): ArrayObject([link])})
    image, audit = immagine_nativa_copertina(pdf, 0)
    assert (image is not None) == (appearance == 'invisible')
    if image:
        image.close()
        assert 'privi di bordo e aspetto grafico' in audit[0]


def test_invalid_pdf_keeps_explicit_negative_outcome():
    image, audit = immagine_nativa_copertina(b'not a pdf', 0)
    assert image is None and 'non adottata' in audit[0]
