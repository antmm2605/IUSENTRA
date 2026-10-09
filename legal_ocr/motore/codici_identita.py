"""Riscontro locale del CF nel codice a barre del medesimo retro CIE."""
from __future__ import annotations

import re

from .mrz import righe_td1_complete


def codice_fiscale_da_barre(image, mrz_text: str) -> tuple[str, str]:
    checked = righe_td1_complete(mrz_text)
    if not checked or checked[0][2:5] != 'ITA':
        return '', 'Codice a barre: manca una MRZ italiana verificata dello stesso riquadro.'
    try:
        import zxingcpp
        from pct.codice_fiscale import _checksum, _codice_nome, _MESI_INV
        rows = zxingcpp.read_barcodes(image)
    except ImportError:
        return '', 'Lettore locale dei codici a barre non installato.'
    except (RuntimeError, ValueError):
        return '', 'Codice a barre: decodifica locale non completata.'
    codes = {row.text.strip().upper() for row in rows if row.valid and
             str(row.format) in {'Code 39', 'Code 128'} and
             re.fullmatch(r'[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]', row.text.strip().upper())}
    if len(codes) != 1:
        return '', 'Codice a barre: nessun CF univoco decodificato.'
    code = next(iter(codes))
    if _checksum(code[:15]) != code[-1]:
        return '', 'Codice a barre: CF con carattere di controllo discordante.'
    first, second, names = checked
    surname, given = names.split('<<', 1)
    birth = second[:6]
    month, day = int(birth[2:4]), int(birth[4:6])
    if month not in _MESI_INV or not 1 <= day <= 31 or second[7] not in {'M', 'F'}:
        return '', 'Codice a barre: dati MRZ insufficienti per il confronto fiscale.'
    expected = (_codice_nome(surname.replace('<', ' ')) + _codice_nome(given.replace('<', ' '), nome=True)
                + birth[:2] + _MESI_INV[month] + f"{day + (40 if second[7] == 'F' else 0):02d}")
    restored = list(code[:11])
    mapping = dict(zip('LMNPQRSTUV', '0123456789'))
    for position in (6, 7, 9, 10):
        restored[position] = mapping.get(restored[position], restored[position])
    if ''.join(restored) != expected:
        return '', 'Codice a barre: CF discordante da nome, cognome, nascita o sesso della MRZ.'
    return code, f'Codice a barre del retro CIE {first[5:14]}: CF decodificato localmente, checksum e dati MRZ concordanti; originale invariato.'
