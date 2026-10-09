"""Il modello guida i tentativi; non certifica i campi del titolare."""
from types import SimpleNamespace

import pytest

from legal_ocr.motore import identita
from pct.document_intelligence.catalog_identita_personale import modello_identita_italiana


INNER = ('Cognome ROSSI Nome MARIO Nato il 01/01/1980 Residenza ROMA '
         'Statura 175 Capelli CASTANI Occhi VERDI')


def test_inner_paper_face_without_cover_is_model_only():
    assert modello_identita_italiana(INNER) == 'carta_cartacea'
    assert identita._riscontro_carta(INNER) is None


@pytest.mark.parametrize('removed', ['Cognome', 'Nome', 'Nato il', 'Residenza', 'Statura', 'Capelli', 'Occhi'])
def test_partial_personal_form_does_not_establish_paper_model(removed):
    assert not modello_identita_italiana(INNER.replace(removed, ''))


def test_inner_paper_profile_does_not_override_cie_or_health():
    assert modello_identita_italiana(INNER + ' COGNOME / SURNAME') == ''
    assert modello_identita_italiana('TESSERA SANITARIA ' + INNER) == 'tessera_sanitaria'


def test_measured_orientation_remains_on_paper_without_blind_turns(monkeypatch):
    image = SimpleNamespace(width=400, height=700)
    monkeypatch.setattr(identita, '_orientamento_riscontrato', lambda image: 270)
    assert list(identita._angoli_lettura(image, modello='carta_cartacea')) == [0, 270]
    monkeypatch.setattr(identita, '_orientamento_riscontrato', lambda image: 0)
    assert list(identita._angoli_lettura(image, modello='carta_cartacea')) == [0]
    assert list(identita._angoli_lettura(image)) == [0, 90, 270]
