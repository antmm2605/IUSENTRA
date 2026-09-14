"""Accenti dell'italiano: «citta'» e' «città», «perche'» e' «perché», «E'» e' «È».

Il motore rende l'accento con un apostrofo, sbaglia acuto e grave o lo perde
del tutto. Le regole sono quelle dell'ortografia italiana: le vocali a, i, o, u
in fine di parola prendono sempre l'accento grave; la e prende l'acuto nei
composti di «che» e in poche altre parole (né, sé, poté), il grave altrove.
I troncamenti («po'», «va'», «da'») restano com'erano: l'apostrofo li' e'
corretto. L'accento mancante si reintegra solo su parole che senza accento non
esistono in italiano («societa», «responsabilita», «cosi»).
"""

from __future__ import annotations

import re

from .regola import Regola, regola_regex

ACUTE_IN_E = frozenset({
    "perché", "poiché", "affinché", "benché", "purché", "sicché", "giacché", "finché", "nonché",
    "cosicché", "pressoché", "anziché", "granché", "fuorché", "allorché", "dopodiché", "talché",
    "macché", "perocché", "ancorché", "ché", "né", "sé", "poté", "ripeté", "mercé", "testé",
    "viceré", "ventitré", "trentatré", "quarantatré", "cinquantatré", "sessantatré", "settantatré",
    "ottantatré", "novantatré", "tré",
})
GRAVI_IN_E = frozenset({"è", "cioè", "caffè", "tè", "ahimè", "ohimè", "lacchè", "bignè", "gilè", "canapè", "purè", "frappè", "relè", "diè"})
# Troncamenti dell'italiano: l'apostrofo finale e' giusto e non e' un accento.
TRONCAMENTI = frozenset({"po", "mo", "be", "to", "va", "fa", "da", "sta", "di", "ve", "ca", "co", "fe", "de", "me", "te", "ce"})

# Parole che senza accento non sono italiane: qui l'accento si puo' rimettere.
SENZA_ACCENTO = {
    "citta": "città", "societa": "società", "attivita": "attività", "responsabilita": "responsabilità",
    "proprieta": "proprietà", "comproprieta": "comproprietà", "possibilita": "possibilità",
    "capacita": "capacità", "incapacita": "incapacità", "qualita": "qualità", "quantita": "quantità",
    "liberta": "libertà", "volonta": "volontà", "facolta": "facoltà", "autorita": "autorità",
    "validita": "validità", "invalidita": "invalidità", "nullita": "nullità", "esigibilita": "esigibilità",
    "opportunita": "opportunità", "difficolta": "difficoltà", "conformita": "conformità",
    "legittimita": "legittimità", "illegittimita": "illegittimità", "ammissibilita": "ammissibilità",
    "inammissibilita": "inammissibilità", "procedibilita": "procedibilità", "improcedibilita": "improcedibilità",
    "tempestivita": "tempestività", "tardivita": "tardività", "esecutivita": "esecutività",
    "definitivita": "definitività", "titolarita": "titolarità", "contitolarita": "contitolarità",
    "universita": "università", "comunita": "comunità", "identita": "identità", "entita": "entità",
    "gravita": "gravità", "priorita": "priorità", "modalita": "modalità", "finalita": "finalità",
    "formalita": "formalità", "irregolarita": "irregolarità", "regolarita": "regolarità",
    "veridicita": "veridicità", "autenticita": "autenticità", "genuinita": "genuinità",
    "pubblicita": "pubblicità", "disponibilita": "disponibilità", "indisponibilita": "indisponibilità",
    "affidabilita": "affidabilità", "credibilita": "credibilità", "attendibilita": "attendibilità",
    "novita": "novità", "continuita": "continuità", "attualita": "attualità", "potesta": "potestà",
    "eredita": "eredità", "pieta": "pietà", "dignita": "dignità", "sanita": "sanità",
    "maternita": "maternità", "paternita": "paternità", "realta": "realtà", "mobilita": "mobilità",
    "immobilita": "immobilità", "utilita": "utilità", "inutilita": "inutilità", "fedelta": "fedeltà",
    "lealta": "lealtà", "eta": "età", "meta": "metà", "serieta": "serietà", "gratuita": "gratuità",
    "onerosita": "onerosità", "solidarieta": "solidarietà", "sussidiarieta": "sussidiarietà",
    "proporzionalita": "proporzionalità", "ragionevolezza": "ragionevolezza", "specialita": "specialità",
    "generalita": "generalità", "particolarita": "particolarità", "estraneita": "estraneità",
    "contrarieta": "contrarietà", "irritualita": "irritualità", "ritualita": "ritualità",
    "colpevolezza": "colpevolezza", "punibilita": "punibilità", "imputabilita": "imputabilità",
    "pericolosita": "pericolosità", "recidivita": "recidività", "abitualita": "abitualità",
    "sospensibilita": "sospensibilità", "impugnabilita": "impugnabilità", "opponibilita": "opponibilità",
    "gia": "già", "piu": "più", "cosi": "così", "puo": "può", "cioe": "cioè", "perche": "perché",
    "poiche": "poiché", "affinche": "affinché", "nonche": "nonché", "sicche": "sicché", "benche": "benché",
    "purche": "purché", "finche": "finché", "giacche": "giacché", "cosicche": "cosicché", "anziche": "anziché",
    "allorche": "allorché", "dopodiche": "dopodiché", "pressoche": "pressoché", "fuorche": "fuorché",
    "ancorche": "ancorché", "lunedi": "lunedì", "martedi": "martedì", "mercoledi": "mercoledì",
    "giovedi": "giovedì", "venerdi": "venerdì", "virtu": "virtù", "gioventu": "gioventù",
    "servitu": "servitù", "schiavitu": "schiavitù", "tribu": "tribù", "laggiu": "laggiù", "quaggiu": "quaggiù",
    "percio": "perciò", "pero": "però", "oblo": "oblò", "falo": "falò", "ventitre": "ventitré",
    "trentatre": "trentatré",
}
_GRAVE = {"a": "à", "i": "ì", "o": "ò", "u": "ù", "A": "À", "I": "Ì", "O": "Ò", "U": "Ù"}

_APOSTROFO_FINALE = re.compile(r"\b([A-Za-zÀ-ÿ]+)([aeiouAEIOU])'(?![\w'])")
_E_SOLA = re.compile(r"(?<![\w'])([eE])'(?![\w'])")
_ACCENTO_ACUTO_ERRATO = re.compile(r"(?<=[A-Za-z])([áíúó])(?![\w])")
_E_FINALE = re.compile(r"\b([A-Za-zÀ-ÿ]*)([èé])(?![\w])")
_E_MAIUSCOLA_FINALE = re.compile(r"\b([A-Za-zÀ-ÿ]*)([ÈÉ])(?![\w])")
_SENZA_ACCENTO = re.compile(r"\b(" + "|".join(sorted(map(re.escape, SENZA_ACCENTO), key=len, reverse=True)) + r")\b", re.IGNORECASE)


def accento_sulla_e(radice: str) -> str:
    """«é» o «è» per la parola radice+e, secondo l'ortografia; vuoto se non si sa."""
    base = radice.lower()
    if base + "é" in ACUTE_IN_E or base.endswith("ch") or (base.endswith("tr") and len(base) > 2):
        return "é"
    if base + "è" in GRAVI_IN_E:
        return "è"
    return ""


def _con_e(radice: str, vocale: str) -> str:
    accento = accento_sulla_e(radice) or "è"
    return accento.upper() if vocale.isupper() else accento


def _apostrofo_finale(match: re.Match[str]) -> str:
    radice, vocale = match.group(1), match.group(2)
    intera = (radice + vocale).lower()
    if intera in TRONCAMENTI:
        return match.group(0)
    if vocale.lower() == "e":
        parola_accentata = _con_e(radice, vocale)
        return radice + parola_accentata
    return radice + _GRAVE[vocale]


def _e_sola(match: re.Match[str]) -> str:
    return "È" if match.group(1).isupper() else "è"


def _acuto_errato(match: re.Match[str]) -> str:
    return {"á": "à", "í": "ì", "ú": "ù", "ó": "ò"}[match.group(1)]


def _e_finale(match: re.Match[str]) -> str:
    radice, accentata = match.group(1), match.group(2)
    if not radice:
        return "è" if accentata.islower() else "È"
    accento = accento_sulla_e(radice)
    if not accento:
        return match.group(0)
    return radice + (accento.upper() if accentata.isupper() else accento)


def _senza_accento(match: re.Match[str]) -> str:
    originale = match.group(1)
    canonico = SENZA_ACCENTO[originale.lower()]
    if originale.isupper():
        return canonico.upper()
    if originale[:1].isupper():
        return canonico[:1].upper() + canonico[1:]
    return canonico


REGOLE: tuple[Regola, ...] = (
    regola_regex("acc.e_sola.v1", "«E'» e «e'»", "Verbo essere scritto «è» ed «È» al posto dell'apostrofo.", _E_SOLA, _e_sola),
    regola_regex("acc.apostrofo.v1", "accento scritto con l'apostrofo", "Vocale finale con apostrofo riportata alla lettera accentata.", _APOSTROFO_FINALE, _apostrofo_finale),
    regola_regex("acc.acuto_errato.v1", "accento acuto su a, i, o, u", "In italiano a, i, o, u finali prendono l'accento grave.", _ACCENTO_ACUTO_ERRATO, _acuto_errato),
    regola_regex("acc.e_finale.v1", "acuto e grave sulla e", "«perchè» → «perché», «cioé» → «cioè», secondo l'ortografia.", _E_FINALE, _e_finale),
    regola_regex("acc.e_maiuscola.v1", "acuto e grave sulla E maiuscola", "Stessa regola sulla maiuscola.", _E_MAIUSCOLA_FINALE, _e_finale),
    regola_regex("acc.mancante.v1", "accento perso dal motore", "Reintegrato su parole che senza accento non esistono («societa» → «società»).", _SENZA_ACCENTO, _senza_accento),
)

__all__ = ["ACUTE_IN_E", "GRAVI_IN_E", "REGOLE", "SENZA_ACCENTO", "TRONCAMENTI", "accento_sulla_e"]
