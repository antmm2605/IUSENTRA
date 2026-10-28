"""Integrità del testo storico compresso prima della lettura al modello."""
import hashlib

import pytest

from lex.normativa.testi_archiviati import MAGIC,MAX_BYTES,archivia_testo,leggi_testo


def test_testo_storico_intero_utf8_e_impronta_invariati():
    original=("Art. 1. È conservato l’intero testo: qualità, quantità e importo € 1.234,56.\n"*500)
    stored=archivia_testo(original)
    assert isinstance(stored,bytes)
    assert len(stored)<len(original.encode())
    received=leggi_testo(stored)
    assert received==original
    assert hashlib.sha256(received.encode()).hexdigest()==hashlib.sha256(original.encode()).hexdigest()


def test_edizione_legacy_e_testo_breve_non_vengono_alterati():
    original="Art. 1. Testo integrale breve."
    assert archivia_testo(original)==original
    assert leggi_testo(original)==original


@pytest.mark.parametrize("change",[lambda b:b[:-1],lambda b:b+b"dati estranei",lambda b:b[:-1]+bytes([b[-1]^1])])
def test_payload_compresso_troncato_aggiunto_o_alterato_non_letto(change):
    stored=archivia_testo("Testo normativo completo. "*500)
    with pytest.raises(ValueError):
        leggi_testo(change(stored))


def test_formati_non_registrati_e_dimensioni_abnormi_rifiutati():
    for value in [b"testo non dichiarato",MAGIC+(MAX_BYTES+1).to_bytes(8,"big")+b"x"]:
        with pytest.raises(ValueError):leggi_testo(value)
