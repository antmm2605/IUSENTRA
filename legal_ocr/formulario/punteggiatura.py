"""Punteggiatura ed elisioni: gli spazi vanno dove l'italiano li mette.

Il motore inserisce uno spazio prima della virgola o dopo l'apostrofo di
un'elisione («l' atto», «dell' udienza») e lo dimentica dopo il punto fra due
periodi («contumacia.Per»). Sono regole della lingua, non del documento, e
valgono per qualunque atto.
"""

from __future__ import annotations

import re

from .regola import Regola, regola_regex

# Parole che in italiano si elidono davanti a vocale o h: l'apostrofo si lega
# alla parola seguente e lo spazio in mezzo e' sempre un errore di lettura.
_ELISIONI = (
    "dell|all|dall|nell|sull|coll|pell|quell|quest|sant|senz|tutt|mezz|quand|bell|grand|buon|"
    "cent|trent|quarant|cinquant|sessant|settant|ottant|novant|vent|quattr|diciott|nessun|alcun|"
    "ciascun|qualcun|anch|com|dov|cos|or|tal|un|gl|dagl|negl|degl|agl|sugl|cogl|d|l|n|s|m|t|v|c|"
    "dell'altr|un'altr"
)
_ELISIONE_SPAZIATA = re.compile(rf"\b({_ELISIONI})'\s+(?=[aeiouhAEIOUHàèéìòùÀÈÉÌÒÙ])", re.IGNORECASE)
_SPAZIO_PRIMA_DI_VIRGOLA = re.compile(r"(?<=[A-Za-zÀ-ÿ)»”\"\]])[ \t]+([,;:!?])")
_SPAZIO_PRIMA_DI_PUNTO = re.compile(r"(?<=[\w)»”\"])[ \t]+\.(?=\s|$|[»”\")\]])")
_SPAZIO_DOPO_PARENTESI = re.compile(r"\(\s+(?=\S)")
_SPAZIO_PRIMA_DI_PARENTESI = re.compile(r"(?<=\S)\s+\)")
_VIRGOLA_SENZA_SPAZIO = re.compile(r"(?<=[A-Za-zÀ-ÿ)»”\"])[,;](?=[A-Za-zÀ-ÿ])")
_PUNTO_SENZA_SPAZIO = re.compile(r"(?<=[a-zà-ùA])\.(?=[A-ZÀ-Ù][a-zà-ù]{2})")
# Un indirizzo PEC spezzato dagli spazi attorno alla chiocciola.
_PEC_SPAZIATA = re.compile(r"(?<=[\w.\-])\s+@\s+(?=[\w.\-])|(?<=[\w.\-])\s+@(?=[\w.\-])|(?<=[\w.\-])@\s+(?=[\w.\-])")


def _virgola_con_spazio(match: re.Match[str]) -> str:
    return f"{match.group(0)} "


REGOLE: tuple[Regola, ...] = (
    regola_regex("pun.elisione.v1", "spazio dopo l'apostrofo", "Elisione riunita alla parola seguente («l' atto» → «l'atto»).", _ELISIONE_SPAZIATA, r"\1'"),
    regola_regex("pun.virgola.v1", "spazio prima della punteggiatura", "Spazio tolto prima di virgola, punto e virgola, due punti.", _SPAZIO_PRIMA_DI_VIRGOLA, r"\1"),
    regola_regex("pun.punto.v1", "spazio prima del punto", "Spazio tolto fra la parola e il punto che la segue.", _SPAZIO_PRIMA_DI_PUNTO, "."),
    regola_regex("pun.parentesi.v1", "spazi dentro le parentesi", "Spazi tolti subito dopo «(» e subito prima di «)».", re.compile(r"\(\s+(?=\S)|(?<=\S)\s+\)"), lambda m: "(" if m.group(0).startswith("(") else ")"),
    regola_regex("pun.virgola_spazio.v1", "spazio dopo la virgola", "Spazio aggiunto dopo la virgola fra due parole.", _VIRGOLA_SENZA_SPAZIO, _virgola_con_spazio),
    regola_regex("pun.punto_spazio.v1", "spazio dopo il punto", "Spazio aggiunto fra la fine di un periodo e la maiuscola del successivo.", _PUNTO_SENZA_SPAZIO, ". "),
    regola_regex("space.pec.v1", "spazi nell'indirizzo PEC", "Spazi tolti attorno alla chiocciola di un indirizzo.", _PEC_SPAZIATA, "@"),
)

__all__ = ["REGOLE"]
