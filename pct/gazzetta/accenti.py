"""Gli accenti finali che la Gazzetta Ufficiale scrive con l'apostrofo («legittimita'», «e'», «piu'»), solo se univoci.

I testi della Gazzetta (sommari e atti) usano la grafia telematica storica: la vocale accentata finale è scritta
come vocale più apostrofo. A video si mostra la parola italiana corretta, ma solo nei casi in cui non ci sono dubbi;
il testo salvato resta quello della fonte (la ricerca trova comunque entrambe le grafie: l'indice ignora apostrofi
e accenti).

Una parola si corregge solo se tutte queste condizioni valgono:
- l'apostrofo chiude la parola (dopo c'è uno spazio, un segno di punteggiatura o la fine del testo) e non chiude
  una citazione aperta con un apostrofo nella stessa riga (« 'Gazzetta' » resta com'è);
- la parola è nell'elenco delle forme univoche (``FORME_UNIVOCHE``: «e'» → «è», «piu'» → «più», «perche'» →
  «perché»…), oppure il dizionario italiano conosce la forma accentata e **non** conosce quella senza accento
  («citta'» → «città» perché «citta» non è una parola; «Ministero'» non cambia perché «ministero» esiste);
- «po'», «mo'», «de'», «ne'», «se'», «si'», «di'», «fa'», «sta'», «va'», «da'» non si toccano mai: sono apostrofi
  veri o hanno due letture.
"""

from __future__ import annotations

import re
from typing import Callable

# Monosillabi e congiunzioni con una sola lettura nei testi normativi.
FORME_UNIVOCHE: dict[str, str] = {
    "e'": "è", "piu'": "più", "gia'": "già", "puo'": "può", "cosi'": "così", "pero'": "però", "giu'": "giù",
    "perche'": "perché", "poiche'": "poiché", "affinche'": "affinché", "benche'": "benché", "finche'": "finché",
    "nonche'": "nonché", "purche'": "purché", "sicche'": "sicché", "anziche'": "anziché", "giacche'": "giacché",
    "cosicche'": "cosicché", "dopodiche'": "dopodiché",
    "qualita'": "qualità", "citta'": "città", "societa'": "società", "attivita'": "attività", "facolta'": "facoltà",
    "liberta'": "libertà", "proprieta'": "proprietà", "legittimita'": "legittimità", "modalita'": "modalità",
    "responsabilita'": "responsabilità", "necessita'": "necessità", "possibilita'": "possibilità",
    "universita'": "università", "comunita'": "comunità", "identita'": "identità", "validita'": "validità",
    "capacita'": "capacità", "autorita'": "autorità", "pubblicita'": "pubblicità", "entita'": "entità",
    "costituzionalita'": "costituzionalità", "illegittimita'": "illegittimità", "eredita'": "eredità",
    "realta'": "realtà", "verita'": "verità", "unita'": "unità", "quantita'": "quantità", "meta'": "metà",
    "sanita'": "sanità", "volonta'": "volontà", "attualita'": "attualità", "virtu'": "virtù", "lunedi'": "lunedì",
    "martedi'": "martedì", "mercoledi'": "mercoledì", "giovedi'": "giovedì", "venerdi'": "venerdì",
}
MAI = frozenset({"po'", "mo'", "de'", "ne'", "se'", "si'", "di'", "fa'", "sta'", "va'", "da'", "be'", "to'"})
VOCALE_ACCENTATA = {"a": "à", "i": "ì", "o": "ò", "u": "ù"}

_PAROLA = re.compile(r"(?<![\w'])([A-Za-zÀ-ÿ]*[aeiouAEIOU])'(?=[\s.,;:!?)\]»”\"-]|$)")
_APERTURA = re.compile(r"(?:^|(?<=[\s(«\"]))'(?=\w)")


def _con_maiuscole(originale: str, corretta: str) -> str:
    if originale.isupper() and len(originale) > 2:
        return corretta.upper()
    if originale[:1].isupper():
        return corretta[:1].upper() + corretta[1:]
    return corretta


def _accentata(parola: str, conosce: Callable[[str], bool] | None) -> str:
    """La forma accentata della parola senza apostrofo finale, o stringa vuota se non è univoca."""
    chiave = parola.casefold() + "'"
    if chiave in MAI:
        return ""
    if chiave in FORME_UNIVOCHE:
        return FORME_UNIVOCHE[chiave]
    if conosce is None or len(parola) < 3:
        return ""
    base = parola.casefold()
    finale = base[-1]
    candidati = [base[:-1] + "é", base[:-1] + "è"] if finale == "e" else [base[:-1] + VOCALE_ACCENTATA[finale]]
    noti = [c for c in candidati if conosce(c)]
    if len(noti) != 1 or conosce(base):
        return ""
    return noti[0]


def _riga(riga: str, conosce: Callable[[str], bool] | None) -> str:
    aperture = [m.start() for m in _APERTURA.finditer(riga)]

    def sostituisci(trovata: re.Match[str]) -> str:
        parola = trovata.group(1)
        # Un apostrofo che apre una citazione prima nella riga: questo potrebbe chiuderla, non si tocca.
        if any(posizione < trovata.start() for posizione in aperture):
            return trovata.group(0)
        corretta = _accentata(parola, conosce)
        return _con_maiuscole(parola, corretta) if corretta else trovata.group(0)

    return _PAROLA.sub(sostituisci, riga)


def accenta(testo: str, conosce: Callable[[str], bool] | None = None) -> str:
    """Il testo con gli accenti finali univoci al posto degli apostrofi; il resto resta identico."""
    if not testo or "'" not in testo:
        return testo or ""
    return "\n".join(_riga(riga, conosce) for riga in str(testo).split("\n"))


def conosce_di_sistema() -> Callable[[str], bool] | None:
    """Il controllo delle parole del dizionario italiano installato (``legal_ocr.lessico``), se c'è."""
    try:
        from legal_ocr.lessico.italiano import conosce, dizionario_di_sistema

        percorso, _parole = dizionario_di_sistema()
        return conosce if percorso else None
    except Exception:
        return None


__all__ = ["FORME_UNIVOCHE", "MAI", "accenta", "conosce_di_sistema"]
