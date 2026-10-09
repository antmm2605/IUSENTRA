"""Controlli finiti della copertina; l'accettazione resta nel browser reale."""
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pytest

from legal_ocr.motore import copertina_cartacea as cover

SOURCE = "CARTA D'IDENTITÀ N. AB1234567 DI ROSSI MARIO"


def word(text, x, y, width=55, height=20, confidence=.95, line=1):
    return dict(text=text, left=x, top=y, width=width, height=height,
                conf=confidence, block=1, par=1, line=line)


def localization():
    return [word('CARTA', 80, 90, 100, 30), word("D'IDENTITA", 190, 90, 220, 30),
            word('N.', 100, 145, line=2), word('AB1234567', 160, 145, 160, 25, line=2),
            word('DI', 225, 200, line=3)]


def name_rows(surname='ROSSI', name='MARIO', offset=0):
    first = [word(part, 70 + i * 65, 25 + offset, line=4) for i, part in enumerate(surname.split())]
    second = [word(part, 70 + i * 65, 70 + offset, line=5) for i, part in enumerate(name.split())]
    return first + second


def context_rows(surname='ROSSI', name='MARIO'):
    return [word('CARTA', 10, 10), word("D'IDENTITA", 80, 10),
            word('AB1234567', 50, 60, 150, line=2), word('DI', 100, 110, line=3),
            *name_rows(surname, name, offset=120)]


def setup_readers(monkeypatch, *, locations=None, context=None, names=None, pp_context=None, pp_names=None):
    primary = iter([locations if locations is not None else localization(),
                    context if context is not None else context_rows(),
                    names if names is not None else name_rows()])
    secondary = iter([pp_context if pp_context is not None else SOURCE,
                      pp_names if pp_names is not None else 'ROSSI MARIO'])
    calls = []
    def read(image, **options):
        calls.append(('tesseract', image.size))
        return next(primary)
    def read_second(image, **options):
        assert options['preserva_risoluzione'] is True
        calls.append(('pp', image.size))
        return SimpleNamespace(testo=next(secondary), confidenza=.99)
    monkeypatch.setattr(cover, 'leggi_testo', read)
    monkeypatch.setattr(cover, 'leggi_con_secondo_lettore', read_second)
    return calls


def source_image():
    image = Image.new('RGB', (500, 400), 'white')
    ImageDraw.Draw(image).line((80, 340, 410, 340), fill='black', width=4)
    return image


def test_same_card_context_and_both_readers_are_required(monkeypatch):
    calls = setup_readers(monkeypatch)
    with source_image() as image:
        original = image.tobytes()
        text, audit = cover.recupera_titolare_cartacea(image, SOURCE)
        assert image.tobytes() == original
    assert 'Cognome: ROSSI\nNome: MARIO' in text and 'N. AB1234567' in text
    assert [call[0] for call in calls] == ['tesseract', 'tesseract', 'pp', 'tesseract', 'pp']
    assert any('bordo inferiore misurato' in entry for entry in audit)


@pytest.mark.parametrize('source', ['ROSSI MARIO',
                                   SOURCE + '\nCognome ROSSI\nNome MARIO',
                                   'IDENTITY CARD CA12345AB COGNOME SURNAME'])
def test_inapplicable_or_existing_fields_do_not_start_ocr(monkeypatch, source):
    monkeypatch.setattr(cover, 'leggi_testo', lambda *_a, **_k: pytest.fail('OCR non pertinente'))
    assert cover.recupera_titolare_cartacea(None, source) == ('', [])


@pytest.mark.parametrize('source', ["CARTA D'IDENTITÀ", SOURCE + ' CD7654321'])
def test_missing_or_discordant_number_is_explicit_without_new_ocr(monkeypatch, source):
    monkeypatch.setattr(cover, 'leggi_testo', lambda *_a, **_k: pytest.fail('Numero non univoco'))
    text, audit = cover.recupera_titolare_cartacea(None, source)
    assert not text and 'numero mancante o numeri discordanti' in audit[-1]


@pytest.mark.parametrize('extra', ['second_title', 'comune_di', 'foreign_panel', 'low_number'])
def test_location_is_unambiguous_and_belongs_to_title(monkeypatch, extra):
    positions = localization()
    if extra == 'second_title':
        positions += [word('CARTA', 80, 20, line=8), word("D'IDENTITA", 190, 20, line=8)]
    elif extra == 'comune_di':
        positions[-1]['text'] = 'COMUNE DI'
    elif extra == 'foreign_panel':
        positions[-1]['left'] = 430
    else:
        positions[3]['conf'] = .79
    calls = setup_readers(monkeypatch, locations=positions)
    with source_image() as image:
        text, audit = cover.recupera_titolare_cartacea(image, SOURCE)
    assert not text and audit and len(calls) == 1


@pytest.mark.parametrize('context', [SOURCE.replace('AB1234567', 'AB1234568'),
                                    SOURCE.replace("CARTA D'IDENTITÀ", 'ATTO'),
                                    SOURCE.replace('ROSSI', 'ROSSO')])
def test_context_discordance_rejects_even_perfect_isolated_names(monkeypatch, context):
    calls = setup_readers(monkeypatch, pp_context=context)
    with source_image() as image:
        text, _ = cover.recupera_titolare_cartacea(image, SOURCE)
    assert not text and len(calls) == 3


def test_third_name_line_is_rejected_without_truncation(monkeypatch):
    calls = setup_readers(monkeypatch, context=context_rows() + [word('LUIGI', 70, 235, line=6)])
    with source_image() as image:
        text, _ = cover.recupera_titolare_cartacea(image, SOURCE)
    assert not text and len(calls) == 3


def test_weak_name_never_inherits_second_reader_page_confidence(monkeypatch):
    context = context_rows()
    context[-1]['conf'] = .59
    calls = setup_readers(monkeypatch, context=context)
    with source_image() as image:
        text, _ = cover.recupera_titolare_cartacea(image, SOURCE)
    assert not text and len(calls) == 3


@pytest.mark.parametrize('primary,secondary', [(name_rows('ROSSO'), 'ROSSI MARIO'),
                                               (name_rows(), 'ROSSI MARIA')])
def test_name_discordance_never_corrects_characters(monkeypatch, primary, secondary):
    setup_readers(monkeypatch, names=primary, pp_names=secondary)
    with source_image() as image:
        text, audit = cover.recupera_titolare_cartacea(image, SOURCE)
    assert not text and 'discordante' in audit[-1]


def test_compound_names_stay_on_their_two_complete_rows(monkeypatch):
    full = SOURCE.replace('ROSSI MARIO', 'DE LUCA MARIO LUIGI')
    setup_readers(monkeypatch, context=context_rows('DE LUCA', 'MARIO LUIGI'),
                  names=name_rows('DE LUCA', 'MARIO LUIGI'), pp_context=full, pp_names='DE LUCA MARIO LUIGI')
    with source_image() as image:
        text, _ = cover.recupera_titolare_cartacea(image, full)
    assert 'Cognome: DE LUCA\nNome: MARIO LUIGI' in text


def test_missing_border_does_not_guess_name_region(monkeypatch):
    calls = setup_readers(monkeypatch)
    with Image.new('RGB', (500, 400), 'white') as image:
        text, audit = cover.recupera_titolare_cartacea(image, SOURCE)
    assert not text and 'bordo inferiore' in audit[-1] and len(calls) == 1


def test_localization_moves_with_document_instead_of_fixture_coordinates():
    original = localization()
    moved = [dict(w, left=w['left'] * 2 + 70, top=w['top'] * 2 + 30,
                  width=w['width'] * 2, height=w['height'] * 2) for w in original]
    location = cover._localizza(original, 'AB1234567')
    shifted = cover._localizza(moved, 'AB1234567')
    assert shifted == (location[0] * 2 + 70, location[1] * 2 + 30,
                       location[2] * 2 + 70, location[3] * 2 + 30, location[4] * 2)


def test_applicability_gate_is_shared_and_performs_no_reading(monkeypatch):
    monkeypatch.setattr(cover, 'leggi_testo', lambda *_a, **_k: pytest.fail('Gate puro'))
    assert cover.copertina_cartacea_applicabile(SOURCE)
    assert not cover.copertina_cartacea_applicabile(SOURCE + ' CD7654321')
    assert not cover.copertina_cartacea_applicabile('Cognome ROSSI Nome MARIO Nato il 01/01/1980')
