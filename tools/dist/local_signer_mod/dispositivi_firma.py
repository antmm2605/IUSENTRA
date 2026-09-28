"""Produttori dei dispositivi di firma e librerie PKCS#11: copia per il Local Signer.

Il Local Signer gira sul PC dell'avvocato senza il resto di IUSENTRA: questa tabella è la
stessa di ``pct/data/cataloghi/firma_digitale.json`` (sezioni ``produttori_dispositivo`` e
``cartelle_librerie``); un test verifica che le due restino uguali. Nessun percorso arriva
dal browser: il browser indica al più il produttore, e le librerie si cercano solo qui.
"""

from __future__ import annotations

import sys

PRODUTTORI = {'bit4id': {'nome': 'Bit4id (Aruba Key, token e smart card della maggior parte dei prestatori)',
            'librerie': {'windows': ['bit4xpki.dll',
                                     'bit4ipki.dll',
                                     'bit4opki.dll',
                                     'bit4cpki.dll',
                                     'bit4p11.dll'],
                         'linux': ['libbit4xpki.so', 'libbit4ipki.so', 'libbit4opki.so', 'libbit4p11.so'],
                         'macos': ['libbit4xpki.dylib', 'libbit4ipki.dylib', 'libbit4opki.dylib']}},
 'athena': {'nome': 'Athena / ASE Card',
            'librerie': {'windows': ['asepkcs.dll'],
                         'linux': ['libASEP11.so'],
                         'macos': ['libASEP11.dylib']}},
 'incard': {'nome': 'Incard', 'librerie': {'windows': ['inp11lib.dll'], 'linux': [], 'macos': []}},
 'oberthur': {'nome': 'Oberthur / IDEMIA',
              'librerie': {'windows': ['OCSCryptoki.dll'], 'linux': [], 'macos': []}},
 'cardos': {'nome': 'Siemens / Atos CardOS',
            'librerie': {'windows': ['SI_PKCS11.dll', 'siecap11.dll'], 'linux': [], 'macos': []}},
 'safenet': {'nome': 'Thales SafeNet eToken',
             'librerie': {'windows': ['eTPKCS11.dll'],
                          'linux': ['libeTPkcs11.so'],
                          'macos': ['libeTPkcs11.dylib']}},
 'idprime': {'nome': 'Thales / Gemalto IDPrime',
             'librerie': {'windows': ['IDPrimePKCS11.dll'],
                          'linux': ['libIDPrimePKCS11.so'],
                          'macos': ['libIDPrimePKCS11.dylib']}},
 'charismathics': {'nome': 'Charismathics (dispositivi InfoCert e Lextel)',
                   'librerie': {'windows': ['cvP11.dll', 'cvcP11.dll'], 'linux': [], 'macos': []}},
 'namirial_oki': {'nome': 'Namirial (driver Oki)',
                  'librerie': {'windows': ['OkiPKCS11.dll'], 'linux': [], 'macos': []}},
 'italtel': {'nome': 'Italtel (carte storiche)',
             'librerie': {'windows': ['IpmPki32.dll', 'IPMpkiLC.dll', 'IpmPkiLU.dll'],
                          'linux': [],
                          'macos': []}},
 'opensc': {'nome': 'OpenSC (driver aperto, molte carte)',
            'librerie': {'windows': ['opensc-pkcs11.dll'],
                         'linux': ['opensc-pkcs11.so'],
                         'macos': ['opensc-pkcs11.so', 'opensc-pkcs11.dylib']}}}

CARTELLE = {'windows': ['C:\\Windows\\System32',
             'C:\\Windows\\SysWOW64',
             'C:\\Program Files\\Bit4id',
             'C:\\Program Files\\Bit4id\\MinVa',
             'C:\\Program Files\\Bit4id\\MinVa\\windows',
             'C:\\Program Files (x86)\\Bit4id',
             'C:\\Program Files (x86)\\Bit4id\\MinVa',
             'C:\\Program Files\\Namirial',
             'C:\\Program Files (x86)\\Namirial',
             'C:\\Program Files\\OpenSC Project\\OpenSC\\pkcs11'],
 'linux': ['/usr/lib',
           '/usr/lib64',
           '/usr/local/lib',
           '/usr/lib/x86_64-linux-gnu',
           '/usr/lib/aarch64-linux-gnu',
           '/usr/lib/x86_64-linux-gnu/pkcs11',
           '/usr/lib64/pkcs11',
           '/lib/bit4id',
           '/usr/lib/bit4id',
           '/usr/local/lib/bit4id'],
 'macos': ['/usr/local/lib', '/Library/OpenSC/lib', '/Library/bit4id/pkcs11', '/usr/local/lib/bit4id']}


def sistema_corrente() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def nomi_librerie(sistema: str | None = None) -> list[str]:
    """Tutti i nomi di file delle librerie note per il sistema."""
    sistema = sistema or sistema_corrente()
    nomi: list[str] = []
    for voce in PRODUTTORI.values():
        for nome in voce["librerie"].get(sistema, []):
            if nome not in nomi:
                nomi.append(nome)
    return nomi


def percorsi_candidati(produttore: str = "", sistema: str | None = None) -> list[str]:
    """Percorsi possibili delle librerie: del produttore indicato, o di tutti."""
    sistema = sistema or sistema_corrente()
    chiave = str(produttore or "").strip().lower()
    scelti = [PRODUTTORI[chiave]] if chiave in PRODUTTORI else ([] if chiave else list(PRODUTTORI.values()))
    separatore = "\\" if sistema == "windows" else "/"
    percorsi: list[str] = []
    for voce in scelti:
        for nome in voce["librerie"].get(sistema, []):
            for cartella in CARTELLE.get(sistema, []):
                percorso = f"{cartella.rstrip(separatore)}{separatore}{nome}"
                if percorso not in percorsi:
                    percorsi.append(percorso)
    return percorsi


__all__ = ["CARTELLE", "PRODUTTORI", "nomi_librerie", "percorsi_candidati", "sistema_corrente"]
