from types import SimpleNamespace
import sys

import pytest

from legal_ocr.motore.codici_identita import codice_fiscale_da_barre
from pct.codice_fiscale import _checksum


MRZ = 'C<ITACA12345AA7<<<<<<<<<<<<<<< 8001014M3001019ITA<<<<<<<<<<<8 ROSSI<<MARIO<<<<<<<<<<<<<<<<<<'
CF = 'RSSMRA80A01H501' + _checksum('RSSMRA80A01H501')


@pytest.mark.parametrize('value,valid,accepted', [(CF, True, True), (CF, False, False),
    ('VRDLGI80A01H501' + _checksum('VRDLGI80A01H501'), True, False),
    (CF[:-1] + ('A' if CF[-1] != 'A' else 'B'), True, False)])
def test_barcode_cf_requires_decoder_checksum_and_same_card_mrz(monkeypatch, value, valid, accepted):
    row = SimpleNamespace(text=value, format='Code 39', valid=valid)
    monkeypatch.setitem(sys.modules, 'zxingcpp', SimpleNamespace(read_barcodes=lambda _: [row]))
    result, proof = codice_fiscale_da_barre(object(), MRZ)
    assert bool(result) is accepted
    assert proof
    assert not codice_fiscale_da_barre(object(), MRZ.replace('8001014', '8001015'))[0]
    assert not codice_fiscale_da_barre(object(), '')[0]


def test_multiple_barcode_codes_never_select_first(monkeypatch):
    other = 'VRDLGI80A01H501' + _checksum('VRDLGI80A01H501')
    rows = [SimpleNamespace(text=value, format='Code 39', valid=True) for value in (CF, other)]
    monkeypatch.setitem(sys.modules, 'zxingcpp', SimpleNamespace(read_barcodes=lambda _: rows))
    assert not codice_fiscale_da_barre(object(), MRZ)[0]
