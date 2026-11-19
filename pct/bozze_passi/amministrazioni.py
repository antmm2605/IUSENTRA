"""Le amministrazioni dello Stato nelle bozze: denominazione per esteso e chi le rappresenta.

Negli atti la parte pubblica si indica con la denominazione ufficiale, non con la sigla della scheda del fascicolo:
«Ministero dell'Istruzione e del Merito, in persona del Ministro pro tempore». Il Ministero sta in giudizio in persona
del Ministro, suo organo di vertice, ed è domiciliato presso l'Avvocatura dello Stato (art. 11 R.D. 1611/1933); gli
altri enti in persona del legale rappresentante pro tempore.

Le denominazioni sono quelle stabilite dalla legge: art. 2 D.Lgs. 300/1999 come modificato dal D.L. 173/2022
(convertito dalla L. 204/2022), che ha rinominato i Ministeri dal 2022; le denominazioni storiche (MIUR) restano
quelle del tempo del titolo. Una sigla che il software non conosce non si indovina: resta un segnaposto.
"""

from __future__ import annotations

import re

from .modello import manca

# Sigla → denominazione ufficiale (D.Lgs. 300/1999, art. 2, nel testo vigente dopo il D.L. 173/2022).
SIGLE_MINISTERI = {
    "MIM": "Ministero dell'Istruzione e del Merito",
    "MUR": "Ministero dell'Università e della Ricerca",
    "MIUR": "Ministero dell'Istruzione, dell'Università e della Ricerca",
    "MEF": "Ministero dell'Economia e delle Finanze",
    "MIMIT": "Ministero delle Imprese e del Made in Italy",
    "MIT": "Ministero delle Infrastrutture e dei Trasporti",
    "MAECI": "Ministero degli Affari Esteri e della Cooperazione Internazionale",
    "MASE": "Ministero dell'Ambiente e della Sicurezza Energetica",
    "MASAF": "Ministero dell'Agricoltura, della Sovranità Alimentare e delle Foreste",
    "MLPS": "Ministero del Lavoro e delle Politiche Sociali",
}
_RE_SIGLA = re.compile(r"^[A-Z]{2,6}$")
_MINUSCOLE = {"di", "del", "della", "dello", "dei", "degli", "delle", "e", "ed", "in", "per", "a", "al", "alla", "da", "con"}


def _forma_propria(testo: str) -> str:
    """«MINISTERO DELL'ISTRUZIONE E DEL MERITO» → «Ministero dell'Istruzione e del Merito»."""
    parole = []
    for indice, parola in enumerate(testo.split()):
        bassa = parola.lower()
        if indice and bassa in _MINUSCOLE:
            parole.append(bassa)
        elif "'" in bassa or "’" in bassa:
            prima, apice, dopo = bassa.replace("’", "'").partition("'")
            parole.append(f"{prima if indice else prima.capitalize()}{apice}{dopo.capitalize()}")
        else:
            parole.append(bassa.capitalize())
    return " ".join(parole)


def denominazione(controparte: str) -> str:
    """La denominazione per esteso della parte pubblica (sigla nota → nome ufficiale; sigla ignota → segnaposto)."""
    nome = " ".join(str(controparte or "").split()).strip(" .,;")
    if not nome:
        return ""
    sigla = nome.replace(".", "").upper()
    if sigla in SIGLE_MINISTERI:
        return SIGLE_MINISTERI[sigla]
    if _RE_SIGLA.match(nome.replace(".", "")):
        return f"{nome} {manca('denominazione per esteso dell’amministrazione, come nel titolo esecutivo')}"
    return _forma_propria(nome) if nome.isupper() else nome


def rappresentante(nome_esteso: str) -> str:
    """Chi rappresenta l'amministrazione negli atti: il Ministro per i Ministeri, altrimenti il legale rappresentante."""
    return "in persona del Ministro pro tempore" if nome_esteso.lower().startswith("ministero") else \
        "in persona del legale rappresentante pro tempore"


__all__ = ["SIGLE_MINISTERI", "denominazione", "rappresentante"]
