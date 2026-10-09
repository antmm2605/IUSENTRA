from types import SimpleNamespace

from PIL import Image

from pct.document_intelligence.catalog_identita_personale import residenza_riga_cartacea
from pct.document_intelligence.catalog_identita_personale import concorda_residenza_cartacea


def test_numeric_prefix_needs_same_source_street_and_civic():
    first = ('VIA ICIRCONVALLAZ. TV3', '13')
    second = ('VIA 1 CIRCONVALLAZ TV3', '13')
    source = 'Via.Vin 1 CIRCONVALLAZ. TV3 Nn 13 Pian Int.4'
    assert concorda_residenza_cartacea(first, second, source)
    assert not concorda_residenza_cartacea(first, second, 'Via.Vin I CIRCONVALLAZ TV3 Nn 13 Pian')
    assert not concorda_residenza_cartacea(first, second, source.replace('13', '14'))
    assert not concorda_residenza_cartacea(first, second, source.replace('TV3', 'TV4'))
    assert not concorda_residenza_cartacea(('VIA IRIS', '13'), ('VIA 1 RIS', '13'), '')
    assert not concorda_residenza_cartacea(('VIA ROMA', '13'), ('VIA ROMA', '14'), source)


def test_civic_is_delimited_before_floor_and_interior():
    assert residenza_riga_cartacea('Via. Via 1 CIRCONVALLAZ. TV3 Num. 13 Piano 2 Int. 4') == ('VIA 1 CIRCONVALLAZ. TV3', '13')
    assert residenza_riga_cartacea('Via. Via ROMA Nn I3 Piano 2') is None
    assert residenza_riga_cartacea('Via. Vin ROMA Num 13 Piano 2') is None
    assert residenza_riga_cartacea('Via. Via ROMA Num 13 Piano 2\nVia. Via ROMA Num 14 Piano 2') is None


def test_missing_address_crops_and_zooms_before_context(monkeypatch):
    import legal_ocr.motore.identita as identity
    import legal_ocr.motore.lettura as reading
    import legal_ocr.motore.immagine as image_tools
    words = [
        dict(text='Nome.', left=120, top=1487, width=87, height=26),
        dict(text='Vie', left=127, top=1830, width=43, height=27),
        dict(text='Num.', left=578, top=1823, width=63, height=24),
        dict(text='13', left=656, top=1823, width=25, height=24),
    ]
    monkeypatch.setattr(reading, '_leggi', lambda *args, **kwargs: (words, ''))
    monkeypatch.setattr(image_tools, 'scala_caratteri_zona', lambda image: 1)
    received = []
    context = 'Cognome: ROSSI Nome: MARIO\nVia. Via ROMA Num 13 Piano 2'
    def second_reader(image, **kwargs):
        received.append(image.size)
        return SimpleNamespace(testo=context if len(received) > 1 else 'lettura insufficiente', confidenza=.94)
    monkeypatch.setattr(identity, 'leggi_con_secondo_lettore', second_reader)
    with Image.new('RGB', (1785, 2525), 'white') as image:
        text, audit = identity.recupera_residenza_cartacea(image, "CARTA D'IDENTITÀ\nCognome: ROSSI\nNome: MARIO")
    assert text and residenza_riga_cartacea(text) == ('VIA ROMA', '13')
    assert received[0][1] < received[1][1]
    assert received[1] == tuple(value * 2 for value in received[2])
    assert 'zoom ×2.00 prima dei trattamenti' in audit[0]


def test_verified_existing_address_does_not_start_new_ocr(monkeypatch):
    import legal_ocr.motore.identita as identity
    import legal_ocr.motore.lettura as reading
    def unexpected(*args, **kwargs):
        raise AssertionError('Il campo già letto non deve essere riletto')
    monkeypatch.setattr(reading, '_leggi', unexpected)
    assert identity.recupera_residenza_cartacea(None, "CARTA D'IDENTITÀ\nVia. Via ROMA Num 13 Piano 2") == ('', [])
