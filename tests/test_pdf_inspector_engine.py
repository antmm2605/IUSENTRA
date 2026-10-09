"""Portable contracts, not a substitute for native OCR and real browser acceptance."""
from io import BytesIO
import sys
from types import SimpleNamespace

import pytest

from pct.document_intelligence import pdf_inspector_engine as engine
from pct.document_intelligence.extraction import extract_text_from_document


def pdf_bytes(texts):
    from reportlab.pdfgen import canvas
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    for text in texts:
        pdf.drawString(72, 700, text)
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def install_inspector(monkeypatch, process):
    monkeypatch.setitem(sys.modules, 'pdf_inspector', SimpleNamespace(process_pdf_with_ocr_bytes=process))


def response(texts, routed=(), hosted=()):
    return SimpleNamespace(
        pages=[SimpleNamespace(page_number=i, markdown=t) for i, t in enumerate(texts, 1)],
        markdown='\n\n'.join(texts), pages_routed_to_ocr=list(routed), pages_recommending_hosted=list(hosted),
    )


def test_all_pages_offline_in_order_without_eight_page_truncation(monkeypatch):
    texts = [f'Pagina {i}: quantità e totale € 1.234,56' for i in range(1, 13)]
    original = pdf_bytes(texts)
    calls = []
    def process(content, **options):
        calls.append(options)
        assert content == original
        return response(texts)
    install_inspector(monkeypatch, process)
    result = extract_text_from_document(original, 'atto.pdf', 'pdf')
    assert result.ok and len(result.pages) == 12
    assert [p.page_number for p in result.pages] == list(range(1, 13))
    assert result.pages[-1].text == texts[-1]
    assert all(c['offline'] is True for c in calls)
    assert result.extraction_engine == engine.ENGINE_VERSION


@pytest.mark.parametrize('pages', [[2], [1, 3], []])
def test_partial_or_unordered_pages_fail_closed(monkeypatch, pages):
    bad = response(['test'] * len(pages))
    for page, number in zip(bad.pages, pages):
        page.page_number = number
    install_inspector(monkeypatch, lambda *_a, **_k: bad)
    result = engine.extract_pdf_inspected(pdf_bytes(['prima', 'seconda']))
    assert not result.ok and not result.text and not result.pages
    assert 'tutte le pagine' in result.error_message


@pytest.mark.parametrize('raw', ['(cid:1)(cid:2)', 'RRoobbeerrttoo MMoonnttaaggnneessee'])
def test_corrupt_native_layer_is_replaced_not_fused(monkeypatch, raw):
    calls = []
    def process(content, **options):
        calls.append(options)
        return response(['Testo corretto senza duplicazioni' if options.get('mode') == 'force' else raw])
    install_inspector(monkeypatch, process)
    monkeypatch.setattr(engine, '_small_box_values', lambda image, existing: ([], []))
    result = engine.extract_pdf_inspected(pdf_bytes([raw]))
    assert result.ok and result.text == 'Testo corretto senza duplicazioni'
    assert len(calls) == 2 and calls[1]['mode'] == 'force' and calls[1]['offline'] is True
    assert any('originale invariato' in w for w in result.warnings)


def test_scanned_page_box_value_and_hosted_advice_remain_local(monkeypatch):
    calls = []
    def process(content, **options):
        calls.append(options)
        return response(['Fattura numero'], routed=[1], hosted=[1])
    install_inspector(monkeypatch, process)
    monkeypatch.setattr(engine, '_small_box_values', lambda image, existing: (
        ['Valore letto nel riquadro (0.100,0.100,0.050,0.020): 05'], []))
    result = engine.extract_pdf_inspected(pdf_bytes(['']))
    assert result.ok and ': 05' in result.text
    assert len(calls) == 1 and calls[0]['offline'] is True
    assert any('nessun invio a servizi esterni' in w for w in result.warnings)


def test_native_failure_is_not_binary_success_even_inside_p7m(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('modello locale assente')
    install_inspector(monkeypatch, fail)
    original = pdf_bytes(['Titolo del documento'])
    monkeypatch.setattr('pct.document_intelligence.extraction._unwrap_p7m_payload',
                        lambda *_: (original, 'atto.pdf', []))
    result = extract_text_from_document(b'PKCS7 envelope', 'atto.pdf.p7m', 'p7m')
    assert not result.ok and not result.text
    assert result.error_code == 'pdf_inspector_failed'


def test_signed_envelope_with_pdf_extension_reads_payload_not_signature(monkeypatch):
    payload = pdf_bytes(['Provvedimento reale'])
    monkeypatch.setattr('pct.document_intelligence.extraction._unwrap_p7m_payload',
                        lambda *_: (payload, 'atto.pdf', []))
    install_inspector(monkeypatch, lambda *_a, **_k: response(['Provvedimento reale']))
    result = extract_text_from_document(b'\x30\x82firma binaria', 'atto.pdf', 'pdf')
    assert result.ok and result.text == 'Provvedimento reale'
    assert result.extraction_engine == f'cades:{engine.ENGINE_VERSION}'


def test_unreadable_der_envelope_never_indexes_signature_strings(monkeypatch):
    original = b'\x30\x82firma binaria certificato Aruba'
    monkeypatch.setattr('pct.document_intelligence.extraction._unwrap_p7m_payload',
                        lambda *_: (original, 'atto.pdf', []))
    result = extract_text_from_document(original, 'atto.pdf', 'pdf')
    assert not result.ok and not result.text
    assert result.error_code == 'pdf_payload_unavailable'


def test_plain_markdown_and_ordinary_doubled_letters():
    assert engine.plain_markdown('# Titolo\n**quantità** <u>verificata</u>') == 'Titolo\nquantità verificata'
    assert not engine.duplicated_glyphs('avvocato, atto, ricevuta, allegato')


def test_identity_region_preserves_original_and_accepts_only_checked_rotation(monkeypatch):
    from PIL import Image, ImageDraw
    from legal_ocr.motore import identita
    install_identity_contour(monkeypatch)
    page = Image.new('RGB', (1000, 1400), 'white')
    ImageDraw.Draw(page).rectangle((300, 400, 600, 900), fill='gray')
    original = page.tobytes()
    mrz = ('I<UTOD231458907<<<<<<<<<<<<<<<\n'
           '7408122F1204159UTO<<<<<<<<<<<6\n'
           'ERIKSSON<<ANNA<MARIA<<<<<<<<<<')
    calls = []
    def read(image, **kwargs):
        calls.append((image.size, kwargs))
        return SimpleNamespace(confidenza=.97, testo=mrz if image.width > image.height else 'Testo senza riscontro MRZ')
    monkeypatch.setattr(identita, 'leggi_con_secondo_lettore', read)
    monkeypatch.setattr(identita, '_orientamento_riscontrato', lambda _: 90)
    text, warnings = identita.recupera_mrz_carta(page)
    assert text == mrz and len(calls) == 1  # orientamento diagnosticato prima dell'OCR
    assert calls[0][0][0] > calls[0][0][1]
    assert calls[0][1] == {'dpi': 216, 'preserva_risoluzione': True}
    assert page.tobytes() == original
    assert any('90°' in warning for warning in warnings)


def test_identity_region_never_repairs_wrong_check_digits(monkeypatch):
    from PIL import Image, ImageDraw
    from legal_ocr.motore import identita
    install_identity_contour(monkeypatch)
    page = Image.new('RGB', (1000, 1400), 'white')
    ImageDraw.Draw(page).rectangle((300, 400, 600, 900), fill='gray')
    calls = []
    def read(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(confidenza=.99, testo='I<UTOD231458900<<<<<<<<<<<<<<< 7408122F1204159UTO<<<<<<<<<<<6 ERIKSSON<<ANNA<MARIA<<<<<<<<<<')
    monkeypatch.setattr(identita, 'leggi_con_secondo_lettore', read)
    monkeypatch.setattr(identita, '_orientamento_riscontrato', lambda _: 0)
    text, warnings = identita.recupera_mrz_carta(page)
    assert not text and len(calls) == 7 and warnings  # preparazione + controlli finiti preesistenti


def install_identity_contour(monkeypatch):
    # Contratto portabile: OpenCV e PP-OCR reali sono provati nel container;
    # qui si verifica esclusivamente adozione, limite tentativi e immutabilità.
    monkeypatch.setitem(sys.modules, 'cv2', SimpleNamespace(RETR_EXTERNAL=0, CHAIN_APPROX_SIMPLE=0, MORPH_CLOSE=0, morphologyEx=lambda mask, *_: mask,
        findContours=lambda *_: ([object()], None), contourArea=lambda _: 150000,
        boundingRect=lambda _: (300, 400, 300, 500)))
    from legal_ocr.motore import geometria_identita, immagine
    monkeypatch.setattr(geometria_identita, 'prepara_geometria_identita', lambda image:
                        SimpleNamespace(immagine=image.copy(), passaggi=()))
    monkeypatch.setattr(immagine, 'scala_caratteri_zona', lambda image: 1)


def test_identity_page_with_cie_and_health_card_reads_separate_regions(monkeypatch):
    from PIL import Image
    from legal_ocr.motore import identita
    page = Image.new('RGB', (1000, 1400), 'white')
    regions = [(300, 100, 400, 250), (300, 800, 400, 250)]
    monkeypatch.setitem(sys.modules, 'cv2', SimpleNamespace(RETR_EXTERNAL=0, CHAIN_APPROX_SIMPLE=0, MORPH_CLOSE=0, morphologyEx=lambda mask, *_: mask,
        findContours=lambda *_: ([0, 1], None), contourArea=lambda _: 100000,
        boundingRect=lambda index: regions[index]))
    cie = ('IDENTITY CARD\nCA62436OK\nCOGNOME / SURNAME\nBORGESE\n'
           'NOME / NAME\nMARIA\nEMISSIONE / ISSUING\n10.03.2023')
    calls = []
    def read_region(image, x, y, width, height, pillow):
        calls.append((x, y))
        return (cie, ['fronte riscontrato']) if y == 100 else ('', [])
    monkeypatch.setattr(identita, '_leggi_regione', read_region)
    text, warnings = identita.recupera_mrz_carta(page)
    assert text == cie and warnings == ['fronte riscontrato']
    assert len(calls) == 2


def test_identity_distinct_cie_cards_never_merged(monkeypatch):
    from PIL import Image
    from legal_ocr.motore import identita
    page = Image.new('RGB', (1000, 1400), 'white')
    monkeypatch.setitem(sys.modules, 'cv2', SimpleNamespace(RETR_EXTERNAL=0, CHAIN_APPROX_SIMPLE=0, MORPH_CLOSE=0, morphologyEx=lambda mask, *_: mask,
        findContours=lambda *_: ([0, 1], None), contourArea=lambda _: 100000,
        boundingRect=lambda index: (300, 100 + index * 700, 400, 250)))
    template = 'IDENTITY CARD {} COGNOME / SURNAME NOME / NAME EMISSIONE / ISSUING'
    monkeypatch.setattr(identita, '_leggi_regione',
        lambda image, x, y, width, height, pillow: (template.format('CA62436OK' if y == 100 else 'CA11111AB'), []))
    text, warnings = identita.recupera_mrz_carta(page)
    assert not text and any('più carte distinte' in warning for warning in warnings)


def test_identity_same_card_regions_preserve_all_readings(monkeypatch):
    from PIL import Image
    from legal_ocr.motore import identita
    page = Image.new('RGB', (1000, 1400), 'white')
    monkeypatch.setitem(sys.modules, 'cv2', SimpleNamespace(RETR_EXTERNAL=0, CHAIN_APPROX_SIMPLE=0, MORPH_CLOSE=0, morphologyEx=lambda mask, *_: mask,
        findContours=lambda *_: ([0, 1], None), contourArea=lambda _: 100000,
        boundingRect=lambda index: (300, 100 + index * 700, 400, 250)))
    template = 'IDENTITY CARD CA11111AB COGNOME / SURNAME ROSSI NOME / NAME MARIO EMISSIONE / ISSUING '
    monkeypatch.setattr(identita, '_leggi_regione',
        lambda image, x, y, width, height, pillow: (template + str(y), [str(y)]))
    text, warnings = identita.recupera_mrz_carta(page)
    assert template + '100' in text and template + '800' in text
    assert warnings == ['100', '800']


@pytest.mark.parametrize('front_number,accepted', [('CA11111AB', True), ('CA22222CD', False)])
def test_identity_front_and_mrz_require_identical_document_number(monkeypatch, front_number, accepted):
    from PIL import Image
    from legal_ocr.motore import identita
    def digit(value):
        values = [0 if c == '<' else int(c) if c.isdigit() else ord(c) - 55 for c in value]
        return str(sum(n * (7, 3, 1)[i % 3] for i, n in enumerate(values)) % 10)
    number = 'CA11111AB'
    first = 'I<ITA' + number + digit(number) + '<' * 15
    birth, expiry = '800101', '300101'
    second = birth + digit(birth) + 'M' + expiry + digit(expiry) + 'ITA' + '<' * 11
    second += digit(first[5:30] + second[:7] + second[8:15] + second[18:29])
    mrz = '\n'.join((first, second, 'ROSSI<<MARIO<<<<<<<<<<<<<<<<<<'))
    front = f'IDENTITY CARD {front_number} COGNOME / SURNAME ROSSI NOME / NAME MARIO EMISSIONE / ISSUING'
    page = Image.new('RGB', (1000, 1400), 'white')
    monkeypatch.setitem(sys.modules, 'cv2', SimpleNamespace(RETR_EXTERNAL=0, CHAIN_APPROX_SIMPLE=0, MORPH_CLOSE=0, morphologyEx=lambda mask, *_: mask,
        findContours=lambda *_: ([0, 1], None), contourArea=lambda _: 100000,
        boundingRect=lambda index: (300, 100 + index * 700, 400, 250)))
    monkeypatch.setattr(identita, '_leggi_regione',
        lambda image, x, y, width, height, pillow: (front if y == 100 else mrz, [str(y)]))
    text, warnings = identita.recupera_mrz_carta(page)
    if accepted:
        assert front in text and mrz in text and warnings == ['100', '800']
    else:
        assert not text and any('più carte distinte' in warning for warning in warnings)


def test_health_card_never_supplies_cie_number():
    from legal_ocr.motore.identita import _riscontro_carta
    assert _riscontro_carta('TESSERA SANITARIA CA62436OK COGNOME NOME SCADENZA') is None


def test_cie_model_uses_italian_labels_without_repairing_personal_values():
    from legal_ocr.motore.identita import _riscontro_carta
    source = 'IDENTITY CARD CA11111AB COMUNE DI COGNOME ROSSI NOMEZNAME MARIO EMISSIONE'
    assert _riscontro_carta(source) == ('cie', 'CA11111AB')
    assert _riscontro_carta(source.replace('CA11111AB', 'CA1111IAB')) is None
    assert _riscontro_carta('IDENTITY CARD CA11111AB') is None


def test_health_card_region_requires_labelled_valid_cf_and_names():
    from legal_ocr.motore.identita import _riscontro_carta
    from pct.codice_fiscale import _checksum
    prefix = 'RSSMRA80A01H501'
    code = prefix + _checksum(prefix)
    source = f'TESSERA SANITARIA Codice{code} COGNOME ROSSI NOME MARIO'
    assert _riscontro_carta(source) == ('health', code)
    assert _riscontro_carta(source.replace(code, code[:-1] + ('A' if code[-1] != 'A' else 'B'))) is None


def test_cie_rear_labelled_cf_and_address_do_not_require_mrz():
    from legal_ocr.motore.identita import _riscontro_carta
    from pct.codice_fiscale import _checksum
    prefix = 'RSSMRA80A01H501'
    code = prefix + _checksum(prefix)
    source = 'CODICE FISCALE\nFISCAL CODE\n' + code + '\nINDIRIZZO DI RESIDENZA / RESIDENCE\nVIA ROMA N. 1 ROMA (RM)'
    assert _riscontro_carta(source) == ('cie_rear', code)
    assert _riscontro_carta(source.replace(code, code[:-1] + ('A' if code[-1] != 'A' else 'B'))) is None
    assert _riscontro_carta(source.replace('INDIRIZZO DI RESIDENZA / RESIDENCE', 'TESSERA SANITARIA')) is None


def test_paper_identity_profile_requires_issuer_and_birth_labels():
    from legal_ocr.motore.identita import _riscontro_carta
    assert _riscontro_carta("COMUNE DI ROMA CARTA D'IDENTITÀ N. AB1234567 Cognome ROSSI Nome MARIO Nato il 01/01/1980") == ('paper', 'AB1234567')
    assert _riscontro_carta("CARTA D'IDENTITÀ N. AB1234567 Cognome ROSSI Nome MARIO") is None


def test_orientation_recovery_is_shared_by_all_identity_models(monkeypatch):
    from types import SimpleNamespace
    from legal_ocr.motore import identita
    monkeypatch.setattr(identita, '_orientamento_riscontrato', lambda image: 0)
    image = SimpleNamespace(width=400, height=700)
    assert list(identita._angoli_lettura(image)) == [0, 90, 270]
    monkeypatch.setattr(identita, '_orientamento_riscontrato', lambda image: 180)
    assert list(identita._angoli_lettura(image)) == [0, 180, 90, 270]


def test_recognized_weak_paper_does_not_probe_mrz_strip(monkeypatch):
    from PIL import Image
    from types import SimpleNamespace
    from legal_ocr.motore import identita
    monkeypatch.setattr(identita, '_orientamento_riscontrato', lambda image: 0)
    reading = SimpleNamespace(testo="CARTA D'IDENTITÀ N. AB1234567", confidenza=.7)
    monkeypatch.setattr(identita, '_leggi_con_diagnosi', lambda *args, **kwargs: (reading, []))
    calls = []
    def original(image, **kwargs):
        calls.append(image.size)
        return reading
    monkeypatch.setattr(identita, 'leggi_con_secondo_lettore', original)
    with Image.new('RGB', (400, 700), 'white') as page:
        text, warnings = identita._leggi_regione(page, 0, 0, 400, 700, Image)
    assert text == ''
    assert 'Modello senza MRZ' in warnings[-1]
    assert len(calls) == 2  # preparazione + originale; modello cartaceo senza sonde CIE


def test_orientation_is_resolved_before_background_trials(monkeypatch):
    from PIL import Image
    from types import SimpleNamespace
    from legal_ocr.motore import identita
    monkeypatch.setattr(identita, '_orientamento_riscontrato', lambda image: 270)
    monkeypatch.setattr(identita, '_leggi_con_diagnosi', lambda *args, **kwargs: pytest.fail('carta orientata già leggibile'))
    monkeypatch.setattr(identita, '_riscontro_carta', lambda text: ('health', 'CF') if text == 'oriented' else None)
    monkeypatch.setattr(identita, 'leggi_con_secondo_lettore', lambda image, **kwargs:
        SimpleNamespace(testo='oriented' if image.width > image.height else 'weak', confidenza=.97))
    with Image.new('RGB', (400, 700), 'white') as page:
        text, warnings = identita._leggi_regione(page, 0, 0, 400, 700, Image)
    assert text == 'oriented' and any('rotazione di lettura 270°' in item for item in warnings)


@pytest.mark.parametrize('timeout_at', [None, 2])
def test_short_fields_include_boxes_after_32_and_continue_after_one_timeout(monkeypatch, timeout_at):
    from PIL import Image, ImageDraw
    import pytesseract
    page = Image.new('RGB', (1200, 2000), 'white')
    draw = ImageDraw.Draw(page)
    for index in range(40):
        y = 30 + index * 45
        draw.rectangle((60, y, 200, y + 32), outline='black', width=2)
        draw.rectangle((100, y + 8, 115, y + 24), fill='black')
    calls = []
    def read_box(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == timeout_at:
            raise RuntimeError('Timeout di collaudo')
        return {'text': [f'{len(calls):02}'], 'conf': [96]}
    monkeypatch.setattr(pytesseract, 'image_to_data', read_box)
    values, warnings = engine._small_box_values(page, '')
    assert len(calls) == 40
    assert len(values) == (39 if timeout_at else 40)
    assert values[-1].endswith(': 40')
    assert len(warnings) == (1 if timeout_at else 0)
