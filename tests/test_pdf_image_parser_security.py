"""Immagini sintetiche: un filtro DCT non autorizza parser di altri formati."""
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, NameObject
import pytest

from tests.test_identity_native_source import pdf_image


@pytest.mark.parametrize('image_format', ['JPEG', 'PNG', 'BMP', 'GIF', 'TIFF'])
@pytest.mark.parametrize('array_filter', [False, True])
def test_library_dct_filter_restricts_parser_selection(image_format, array_filter):
    fields = {NameObject('/Filter'): ArrayObject([NameObject('/DCTDecode')])} if array_filter else None
    pdf, _ = pdf_image(image_format=image_format, image_fields=fields)
    page = PdfReader(BytesIO(pdf)).pages[0]
    if image_format == 'JPEG':
        extracted = page.images[0]
        assert extracted.image.format == 'JPEG' and extracted.image.size == (160, 100)
        with Image.open(BytesIO(extracted.data), formats=('JPEG',)) as image:
            assert image.size == (160, 100)
    else:
        with pytest.raises((UnidentifiedImageError, PdfReadError)):
            _ = page.images[0]
