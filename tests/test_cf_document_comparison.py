from pct.codice_fiscale import _checksum, calcola, confronta_con_dati


DATO = dict(cognome='Rossi', nome='Mario', sesso='M', data_nascita='1980-01-01',
            luogo_nascita='Roma', provincia_nascita='RM')


def test_confronto_non_sostituisce_codice_e_rifiuta_provincia_errata():
    code = calcola(**DATO)['codice_fiscale']
    assert confronta_con_dati(code, **DATO)['stato'] == 'concordante'
    assert confronta_con_dati('', **DATO)['stato'] == 'non_letto'
    assert confronta_con_dati(code, **(DATO | {'provincia_nascita': 'VI'}))['stato'] == 'incompleto'
    assert confronta_con_dati(code, **(DATO | {'nome': 'Luigi'}))['stato'] == 'discordante'
    wrong = code[:-1] + ('A' if code[-1] != 'A' else 'B')
    assert confronta_con_dati(wrong, **DATO)['stato'] == 'non_valido'


def test_omocodia_compatibile_non_assegnazione_ufficiale():
    code = calcola(**DATO)['codice_fiscale']
    first = code[:14] + 'M'
    variant = first + _checksum(first)
    result = confronta_con_dati(variant, **DATO)
    assert result['stato'] == 'omocodia_compatibile'
    assert result['letto'] == variant
    assert confronta_con_dati(variant, **(DATO | {'nome': ''}))['stato'] == 'incompleto'
