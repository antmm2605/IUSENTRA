"""Guardrail della prima lettura: non sostituisce l'accettazione nel browser."""
from io import BytesIO
from types import SimpleNamespace
import sys

from PIL import Image
import pytest

from pct.document_intelligence import pdf_inspector_engine as engine


def _pdf(texts):
    from reportlab.pdfgen import canvas
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    for text in texts:
        pdf.drawString(72, 700, text)
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def _ocr(text, confidence=.97, hosted=False, page_number=1):
    return SimpleNamespace(pages=[SimpleNamespace(page_number=page_number, markdown=text,
        provenance=SimpleNamespace(ocr_confidence=confidence))],
        pages_recommending_hosted=[1] if hosted else [])


def _install(monkeypatch, native, read, prepare=None):
    from legal_ocr.motore import copertina_cartacea, identita, preparazione_identita
    inspector = SimpleNamespace(extract_pages_markdown_bytes=native, process_pdf_with_ocr_bytes=read)
    monkeypatch.setitem(sys.modules, 'pdf_inspector', inspector)
    monkeypatch.setattr(preparazione_identita, 'prepara_riquadro_identita', prepare or
        (lambda image: SimpleNamespace(immagine=image.copy(), orientamento=0, passaggi=('Preparazione controllata.',))))
    monkeypatch.setattr(engine, '_small_box_values', lambda *_: ([], []))
    monkeypatch.setattr(identita, 'recupera_mrz_carta', lambda *_: ('', []))
    monkeypatch.setattr(identita, 'recupera_residenza_cartacea', lambda *_: ('', []))
    monkeypatch.setattr(identita, 'recupera_titolare_cartacea', lambda *_: ('', []), raising=False)
    monkeypatch.setattr(copertina_cartacea, 'copertina_cartacea_applicabile', lambda _: False, raising=False)
    return inspector


def _native(texts, scans=()):
    return SimpleNamespace(pages=[SimpleNamespace(page=i, markdown=text, needs_ocr=i in scans,
                                                 ocr_reason='scansione' if i in scans else None)
                                  for i, text in enumerate(texts)])


def test_diagnosis_and_preparation_precede_first_data_ocr_for_all_five_pages(monkeypatch):
    events = []
    original = _pdf([''] * 5)
    def native(content):
        assert content == original
        events.append('native')
        return _native([''] * 5, scans=range(5))
    def prepare(image):
        events.append('prepare')
        return SimpleNamespace(immagine=image.copy(), orientamento=0, passaggi=('Diagnosi senza trasformazione.',))
    def read(content, **options):
        assert content != original
        assert options['offline'] is True and options['mode'] == 'force' and options['dpi'] == 216.0
        events.append('ocr')
        return _ocr(f'Campo pagina {events.count("ocr")}')
    _install(monkeypatch, native, read, prepare)
    result = engine.extract_pdf_inspected(original, identity_scan=True)
    assert result.ok, result.error_message
    assert events == ['native'] + ['prepare', 'ocr'] * 5
    assert [page.page_number for page in result.pages] == list(range(1, 6))
    assert result.pages[-1].text == 'Campo pagina 5'
    assert not result.identity_recoveries
    assert [item['mode'] for item in result.identity_sources] == ['ocr'] * 5
    assert [item['page_number'] for item in result.identity_sources] == list(range(1, 6))


def test_native_text_preserved_without_primary_data_ocr(monkeypatch):
    text = 'CARTA DI IDENTITA\nCOGNOME ROSSI\nNOME MARIO\nCOMUNE DI ROMA'
    def forbidden(*_args, **_kwargs):
        pytest.fail('Il testo nativo affidabile non richiede OCR primario né preparazione globale.')
    _install(monkeypatch, lambda _: _native([text]), forbidden, forbidden)
    result = engine.extract_pdf_inspected(_pdf(['Testo nativo completo']), identity_scan=True)
    assert result.ok and result.text == text
    assert result.identity_sources == [{'page_number': 1, 'mode': 'native', 'text': text}]
    assert result.pages[0].identity_sources == result.identity_sources


@pytest.mark.parametrize('raw', ['(cid:1)(cid:2)', 'RRoobbeerrttoo MMoonnttaaggnneessee',
                                'Firmato Da: ESEMPIO Serial: 12345'])
def test_unreliable_native_text_is_prepared_then_replaced(monkeypatch, raw):
    events = []
    def prepare(image):
        events.append('prepare')
        return SimpleNamespace(immagine=image.copy(), orientamento=0, passaggi=())
    def read(*_, **__):
        events.append('ocr')
        return _ocr('Testo letto dalla fonte')
    _install(monkeypatch, lambda _: _native([raw]), read, prepare)
    result = engine.extract_pdf_inspected(_pdf([raw]), identity_scan=True)
    assert result.ok and result.text == 'Testo letto dalla fonte'
    assert events == ['prepare', 'ocr']


@pytest.mark.parametrize('indices', [[1], [0, 2], []])
def test_native_metadata_missing_or_unordered_fails_before_ocr(monkeypatch, indices):
    def forbidden(*_args, **_kwargs):
        pytest.fail('Nessun OCR su una sequenza nativa incompleta.')
    pages = [SimpleNamespace(page=i, markdown='', needs_ocr=True) for i in indices]
    _install(monkeypatch, lambda _: SimpleNamespace(pages=pages), forbidden, forbidden)
    result = engine.extract_pdf_inspected(_pdf(['uno', 'due']), identity_scan=True)
    assert not result.ok and 'tutte le pagine' in result.error_message


@pytest.mark.parametrize('original,variant', [
    ('CARTA DI IDENTITA\nAT1234567', 'CARTA DI IDENTITA\nAT1234568'),
    ('SCADENZA 11/10/2033', 'SCADENZA 11/10/2013'),
    ('COGNOME\nROSSI\nNOME\nMARIO', 'COGNOME\nROSSI\nNOME\nMARIA'),
    ('COGNOME / SURNAME\nROSSI', 'COGNOME / SURNAME\nROSSO'),
    ('COGNOME ROSSI NOME MARIO DOCUMENTO DI PROVA', 'COGNOME ROSSI NOME MARIA DOCUMENTO DI PROVA'),
    ('CODICE FISCALE RSSMRA80A01H501U', 'CODICE FISCALE RSSMRA80A01H501V'),
    ('CARTA DI IDENTITA AT1234567 SCADENZA 11/10/2033', 'CARTA DI IDENTITA AT1234567'),
])
def test_changed_pixels_high_confidence_does_not_override_discordant_original(monkeypatch, original, variant):
    calls = []
    def prepare(image):
        return SimpleNamespace(immagine=Image.new('RGB', image.size, 'gray'), orientamento=0, passaggi=('Contrasto.',))
    def read(*_, **__):
        calls.append(1)
        return _ocr(variant, .99) if len(calls) == 1 else _ocr(original, .70)
    inspector = _install(monkeypatch, lambda _: None, read, prepare)
    source = Image.new('RGB', (100, 60), 'white')
    before = source.tobytes()
    text, recovery_source, audit, _ = engine._identity_page_read(source, inspector=inspector, options={'offline': True})
    try:
        assert text == original and len(calls) == 2
        assert source.tobytes() == before
        assert recovery_source.tobytes() == before
        assert any('scartata' in step for step in audit)
    finally:
        recovery_source.close()
        source.close()


def test_variant_improves_only_with_preserved_literals_and_model(monkeypatch):
    texts = iter([_ocr('CARTA DI IDENTITA\nAT1234567\nSCADENZA 11/10/2033', .95),
                  _ocr('CARTA DI IDENTITA\nAT1234567', .80)])
    inspector = _install(monkeypatch, lambda _: None, lambda *_a, **_k: next(texts),
        lambda image: SimpleNamespace(immagine=Image.new('RGB', image.size, 'gray'), orientamento=0, passaggi=()))
    with Image.new('RGB', (100, 60), 'white') as source:
        text, recovery_source, audit, _ = engine._identity_page_read(source, inspector=inspector, options={'offline': True})
        recovery_source.close()
    assert '11/10/2033' in text and any('variante mantenuta' in step for step in audit)


def test_recovery_uses_original_oriented_pixels_not_rectified_coordinates(monkeypatch):
    def prepare(image):
        return SimpleNamespace(immagine=Image.new('RGB', (300, 180), 'gray'), orientamento=90, passaggi=())
    inspector = _install(monkeypatch, lambda _: None, lambda *_a, **_k: _ocr('Testo invariato'), prepare)
    with Image.new('RGB', (100, 60), 'white') as source:
        source.putpixel((1, 2), (0, 0, 0))
        text, recovery_source, _, _ = engine._identity_page_read(source, inspector=inspector, options={'offline': True})
        with source.rotate(90, expand=True) as expected:
            assert recovery_source.size == expected.size
            assert recovery_source.tobytes() == expected.tobytes()
        recovery_source.close()
    assert text == 'Testo invariato'


def test_identity_recoveries_keep_original_page_numbers(monkeypatch):
    from legal_ocr.motore import identita
    _install(monkeypatch, lambda _: _native(['', ''], scans=(0, 1)), lambda *_a, **_k: _ocr('Prima lettura'))
    monkeypatch.setattr(identita, 'recupera_mrz_carta', lambda *_: ('Recupero governato', ['Controllo effettuato.']))
    result = engine.extract_pdf_inspected(_pdf(['', '']), identity_scan=True)
    assert result.ok
    assert [(page.page_number, page.text) for page in result.identity_recoveries] == [
        (1, 'Recupero governato'), (2, 'Recupero governato')]
    assert result.identity_sources == [
        {'page_number': 1, 'mode': 'ocr', 'text': 'Prima lettura'},
        {'page_number': 1, 'mode': 'recovery', 'text': 'Recupero governato'},
        {'page_number': 2, 'mode': 'ocr', 'text': 'Prima lettura'},
        {'page_number': 2, 'mode': 'recovery', 'text': 'Recupero governato'},
    ]


def test_address_recovery_does_not_qualify_surrounding_exploratory_ocr(monkeypatch):
    from legal_ocr.motore import identita
    text = 'CARTA DI IDENTITA\nCOGNOME ROSSI\nNOME MARIO'
    _install(monkeypatch, lambda _: _native([''], scans=(0,)), lambda *_a, **_k: _ocr(text))
    monkeypatch.setattr(identita, 'recupera_residenza_cartacea', lambda *_:
                        ('CARTA DI IDENTITA\nVia VIA ROMA Num. 12 Piano 1', ['Riscontro della zona.']))
    result = engine.extract_pdf_inspected(_pdf(['']), identity_scan=True)
    assert result.ok
    assert result.identity_sources == [
        {'page_number': 1, 'mode': 'ocr', 'text': text},
        {'page_number': 1, 'mode': 'recovery', 'text': 'CARTA DI IDENTITA\nVia VIA ROMA Num. 12 Piano 1'},
    ]
    assert not result.identity_recoveries  # contratto storico mantenuto
    assert result.pages[0].identity_sources == result.identity_sources


def test_paper_holder_recovery_precedes_address_once_without_contaminating_its_input(monkeypatch):
    from legal_ocr.motore import identita
    source = 'CARTA DI IDENTITA\nAT1234567\nDI\nROSSI\nMARIO'
    holder = 'CARTA DI IDENTITA\nAT1234567\nCOGNOME ROSSI\nNOME MARIO'
    calls = []
    _install(monkeypatch, lambda _: _native([''], scans=(0,)), lambda *_a, **_k: _ocr(source))
    def recover_holder(image, known):
        calls.append('holder')
        assert known == source
        return holder, ['Titolare concordante in due letture.']
    def recover_address(image, known):
        calls.append('address')
        assert known == source  # il nuovo titolo non diventa una seconda carta
        return '', []
    monkeypatch.setattr(identita, 'recupera_titolare_cartacea', recover_holder)
    monkeypatch.setattr(identita, 'recupera_residenza_cartacea', recover_address)
    result = engine.extract_pdf_inspected(_pdf(['']), identity_scan=True)
    assert result.ok and calls == ['holder', 'address']
    assert result.identity_sources == [
        {'page_number': 1, 'mode': 'ocr', 'text': source},
        {'page_number': 1, 'mode': 'recovery', 'text': holder},
    ]
    assert [(page.page_number, page.text) for page in result.identity_recoveries] == [(1, holder)]


@pytest.mark.parametrize('recovered', ['', 'CARTA DI IDENTITA\nAT1234567\nCOGNOME ROSSI\nNOME MARIO'])
def test_paper_cover_native_pixels_only_after_failed_render_once_and_closed(monkeypatch, recovered):
    from legal_ocr.motore import copertina_cartacea, fonte_identita, identita
    primary = 'CARTA DI IDENTITA\nAT1234567\nDI\nRIGHE INCERTE'
    original = _pdf([''])
    calls = []
    _install(monkeypatch, lambda _: _native([''], scans=(0,)), lambda *_a, **_k: _ocr(primary))
    pixels = Image.new('RGB', (73, 31), 'white')
    def native_source(content, index):
        assert content == original and index == 0
        calls.append('native_source')
        return pixels, ['Sorgente PDF monoimmagine verificata, 73 × 31 pixel.']
    def recover_holder(image, known):
        assert known == primary
        calls.append('native_holder' if image is pixels else 'render_holder')
        return (recovered, ['Riscontro nativo terminato.']) if image is pixels else ('', ['Render insufficiente.'])
    def recover_address(image, known):
        calls.append('address')
        assert known == primary and image is not pixels
        return '', []
    monkeypatch.setattr(copertina_cartacea, 'copertina_cartacea_applicabile', lambda text: text == primary)
    monkeypatch.setattr(fonte_identita, 'immagine_nativa_copertina', native_source)
    monkeypatch.setattr(identita, 'recupera_titolare_cartacea', recover_holder)
    monkeypatch.setattr(identita, 'recupera_residenza_cartacea', recover_address)
    result = engine.extract_pdf_inspected(original, identity_scan=True)
    assert result.ok, result.error_message
    assert calls == ['render_holder', 'native_source', 'native_holder', 'address']
    assert result.identity_sources[0] == {'page_number': 1, 'mode': 'ocr', 'text': primary}
    assert len(result.identity_sources) == (2 if recovered else 1)
    if recovered:
        assert result.identity_sources[1] == {'page_number': 1, 'mode': 'recovery',
                                              'text': recovered, 'pixel_source': 'pdf_native_image'}
    assert result.pages[0].identity_sources == result.identity_sources
    assert any('73 × 31 pixel' in warning for warning in result.warnings)
    with pytest.raises(ValueError):
        pixels.getpixel((0, 0))


@pytest.mark.parametrize('holder,applicable,native_none', [('titolare riscontrato', True, False), ('', False, False), ('', True, True)])
def test_native_cover_not_retried_when_render_works_or_gate_or_geometry_rejects(monkeypatch, holder, applicable, native_none):
    from legal_ocr.motore import copertina_cartacea, fonte_identita, identita
    primary = 'CARTA DI IDENTITA\nAT1234567\nDI\nROSSI'
    _install(monkeypatch, lambda _: _native([''], scans=(0,)), lambda *_a, **_k: _ocr(primary))
    calls = []
    def render(*_):
        calls.append('render')
        return holder, []
    def native(*_):
        assert native_none
        calls.append('native')
        return None, ['Struttura nativa non applicabile.']
    monkeypatch.setattr(copertina_cartacea, 'copertina_cartacea_applicabile', lambda _: applicable)
    monkeypatch.setattr(identita, 'recupera_titolare_cartacea', render)
    monkeypatch.setattr(fonte_identita, 'immagine_nativa_copertina', native)
    result = engine.extract_pdf_inspected(_pdf(['']), identity_scan=True)
    assert result.ok
    assert calls == (['render', 'native'] if native_none else ['render'])


@pytest.mark.parametrize('source,count', [('IDENTITY CARD\nCA12345AB', 1), ('CARTA DI IDENTITA\nAT1234567', 5)])
def test_paper_holder_not_called_for_other_models_or_unbounded_files(monkeypatch, source, count):
    from legal_ocr.motore import identita
    _install(monkeypatch, lambda _: _native([''] * count, scans=range(count)), lambda *_a, **_k: _ocr(source))
    def forbidden(*_):
        pytest.fail('Recupero copertina fuori perimetro.')
    monkeypatch.setattr(identita, 'recupera_titolare_cartacea', forbidden)
    result = engine.extract_pdf_inspected(_pdf([''] * count), identity_scan=True)
    assert result.ok and len(result.pages) == count


def test_preparation_error_remains_explicit_without_unprepared_fallback(monkeypatch):
    def broken(_):
        raise RuntimeError('Preparazione non disponibile')
    def forbidden(*_args, **_kwargs):
        pytest.fail('Nessun OCR grezzo dopo una preparazione fallita.')
    _install(monkeypatch, lambda _: _native([''], scans=(0,)), forbidden, broken)
    result = engine.extract_pdf_inspected(_pdf(['']), identity_scan=True)
    assert not result.ok and 'Preparazione non disponibile' in result.error_message


def test_serialization_and_reading_use_same_resolution(monkeypatch):
    import pypdfium2
    sizes = []
    def read(content, **options):
        with pypdfium2.PdfDocument(content) as pdf:
            page = pdf[0]
            bitmap = page.render(scale=options['dpi'] / 72)
            try:
                sizes.append((bitmap.width, bitmap.height))
            finally:
                bitmap.close()
                page.close()
        return _ocr('CARTA DI IDENTITA AT1234567')
    inspector = _install(monkeypatch, lambda _: None, read)
    with Image.new('RGB', (1080, 720), 'white') as source:
        _, recovery_source, _, _ = engine._identity_page_read(source, inspector=inspector, options={'offline': True})
        recovery_source.close()
    assert sizes == [(1080, 720)]
