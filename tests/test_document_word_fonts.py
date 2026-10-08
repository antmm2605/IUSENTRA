"""Guardrail font incorporati dopo conversione reale e confronto delle due pagine."""
from io import BytesIO
import uuid
import zipfile

from docx import Document
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
import pytest

from web.services.document_word_fonts import prepare_source_fonts, embed_source_fonts


def font_bytes(rights=8):
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(['.notdef', 'space', 'A'])
    builder.setupCharacterMap({32: 'space', 65: 'A'})
    glyphs = {}
    for name in ['.notdef', 'space', 'A']:
        pen = TTGlyphPen(None)
        if name == 'A':
            pen.moveTo((0, 0))
            pen.lineTo((250, 700))
            pen.lineTo((500, 0))
            pen.closePath()
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (500, 0) for name in glyphs})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({'familyName': 'QA Font', 'styleName': 'Regular',
                            'uniqueFontIdentifier': 'QA Font', 'fullName': 'QA Font', 'psName': 'QAFont'})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200, fsType=rights)
    builder.setupPost()
    builder.setupMaxp()
    stream = BytesIO()
    builder.save(stream)
    return stream.getvalue()


class Source:
    def __init__(self, data):
        self.data = data

    def __iter__(self):
        return iter([self])

    def get_fonts(self, full=False):
        return [(10, 'ttf', 'TrueType', 'QAFont', 'F1', '')]

    def extract_font(self, xref):
        return 'QAFont', 'ttf', 'TrueType', self.data


@pytest.mark.parametrize('rights', [2, 4, 0x0200])
def test_restricted_preview_or_bitmap_fonts_never_enter_editable_document(tmp_path, rights):
    fonts, config = prepare_source_fonts(Source(font_bytes(rights)), tmp_path / 'fonts')
    assert fonts == [] and config is None
    assert not list((tmp_path / 'fonts').glob('*.ttf'))


def test_embedded_font_keeps_original_bytes_and_document_relationship(tmp_path):
    data = font_bytes()
    fonts, config = prepare_source_fonts(Source(data), tmp_path / 'fonts')
    document = Document()
    run = document.add_paragraph().add_run('A')
    run.font.name = 'QAFont'
    assert embed_source_fonts(document, fonts) == 1
    assert run.font.name == 'QA Font'
    table = document.part.part_related_by(RT.FONT_TABLE)
    from docx.oxml import parse_xml
    root = parse_xml(table.blob)
    embedded = root.find('.//' + qn('w:embedRegular'))
    key = uuid.UUID(embedded.get(qn('w:fontKey')))
    blob = bytearray(table.related_parts[embedded.get(qn('r:id'))].blob)
    mask = bytes.fromhex(key.hex)[::-1]
    for index in range(32):
        blob[index] ^= mask[index % 16]
    assert bytes(blob) == data
    assert config.is_file()
    path = tmp_path / 'result.docx'
    document.save(path)
    with zipfile.ZipFile(path) as archive:
        assert len([name for name in archive.namelist() if name.endswith('.odttf')]) == 1


def test_incomplete_font_does_not_claim_new_character_coverage(tmp_path):
    fonts, _ = prepare_source_fonts(Source(font_bytes()), tmp_path / 'fonts')
    document = Document()
    run = document.add_paragraph().add_run('AB')
    run.font.name = 'QAFont'
    assert embed_source_fonts(document, fonts) == 0
