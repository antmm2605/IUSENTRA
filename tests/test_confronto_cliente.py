"""Discordanze vere e false fra atti e anagrafica (verifica del 01/11/2026: 11 su 13 erano false)."""

import pytest

from pct.archivio_letture.confronto_cliente import (
    codice_fiscale_valido,
    discordanza_codice_fiscale,
    discordanza_nome,
)
from pct.codice_fiscale import _checksum

BASE = "RSSMRA80A01H501"
CF_VALIDO = BASE + _checksum(BASE)


def _sbagliato(cf: str) -> str:
    """Lo stesso codice con l'ultima lettera letta male dall'OCR."""
    return cf[:15] + ("4" if cf[15] != "4" else "0")


def test_codice_fiscale_con_carattere_di_controllo():
    assert codice_fiscale_valido(CF_VALIDO)
    assert not codice_fiscale_valido(_sbagliato(CF_VALIDO))
    assert not codice_fiscale_valido("ABC")


def test_codice_letto_male_non_e_una_discordanza():
    assert not discordanza_codice_fiscale(_sbagliato(CF_VALIDO), CF_VALIDO)
    assert not discordanza_codice_fiscale(CF_VALIDO, CF_VALIDO)
    altro = "VRDLGU75B12F205" + _checksum("VRDLGU75B12F205")
    assert discordanza_codice_fiscale(altro, CF_VALIDO)


@pytest.mark.parametrize("letto, anagrafica", [
    ("MINISTERO DELL'ISTRUZIONE E DEL MERITO", "Rossi Maria"),  # ente al posto del cliente
    ("Leonora Marzia Maione", "Maione Marzia"),  # secondo nome
    ("Maione Marzia", "Marzia Maione"),  # ordine diverso
    ("Ass. Ed.", "Rossi Maria Grazia"),  # titolo letto come nome
    ("Ed", "Rossi Maria"),
    ("Tribunale di Brescia Sezione Lavoro Giudice Dott", "Rossi Maria"),  # intestazione
])
def test_discordanze_false(letto, anagrafica):
    assert not discordanza_nome(letto, anagrafica)


def test_stesso_codice_fiscale_accanto_al_nome_indica_la_stessa_persona():
    citazione = f"La Prof.ssa Rosa Maria, c.f. {CF_VALIDO}, rappresentata e difesa dall'Avv. Tizio."
    assert not discordanza_nome("Rosa Maria", "Rossi Maria", citazione=citazione, cf_anagrafica=CF_VALIDO)


def test_nome_davvero_diverso_resta_una_discordanza():
    assert discordanza_nome("Bianchi Laura", "Rossi Maria")
    assert discordanza_nome("Rosa Maria", "Rossi Maria", citazione="senza codice", cf_anagrafica=CF_VALIDO)


def test_cliente_ente_confrontato_con_ente():
    assert discordanza_nome("Comune di Locri", "Comune di Siderno")
    assert not discordanza_nome("Comune di Locri", "Comune di Locri")


def test_le_discordanze_registrate_con_regole_superate_non_si_mostrano():
    from web.services.discordanze_letture_runtime import ancora_discordante

    ente = {'codice': 'nome_cliente_atto', 'valoreAnagrafica': 'Scarfò Emanuela',
            'fonti': [{'valore': "MINISTERO DELL'ISTRUZIONE E DEL MERITO", 'citazione': ''}]}
    secondo_nome = {'codice': 'nome_cliente_atto', 'valoreAnagrafica': 'Maione Marzia',
                    'fonti': [{'valore': 'Leonora Marzia Maione', 'citazione': ''}]}
    vera = {'codice': 'nome_cliente_atto', 'valoreAnagrafica': 'Maione Marzia',
            'fonti': [{'valore': 'Rossi Giovanni', 'citazione': ''}]}
    cf_letto_male = {'codice': 'cf_cliente_atto', 'valoreAnagrafica': 'RSSMRA80A01H501U', 'valoriAtto': ['RSSMRA80A01H501X']}
    assert not ancora_discordante(ente)
    assert not ancora_discordante(secondo_nome)
    assert ancora_discordante(vera)
    assert not ancora_discordante(cf_letto_male)


def test_titolo_professionale_e_frammento_di_indirizzo_non_sono_discordanze():
    """Verifica a vista del 01/11/2026: «Ass. Ed.» davanti al nome e «Int.3 P.2» (interno e piano) letti come nomi."""
    from web.services.discordanze_letture_runtime import ancora_discordante

    falsa = {'codice': 'nome_cliente_atto', 'valoreAnagrafica': 'Rossi Maria Rosa',
             'fonti': [{'valore': 'Ass. Ed. Rossi Maria Rosa', 'citazione': ''}, {'valore': 'Int.3 P.2', 'citazione': ''}]}
    assert not ancora_discordante(falsa)
    assert not discordanza_nome('Int.3 P.2', 'Rossi Maria Rosa')
    assert not discordanza_nome('Ass. Ed. Rossi Maria Rosa', 'Rossi Maria Rosa')
    assert discordanza_nome('Rossi Marta Rosa', 'Rossi Maria Rosa')
