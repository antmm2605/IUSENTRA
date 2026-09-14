"""Importi in euro: il simbolo al suo posto e il numero scritto all'italiana.

«E 1.250,00», «C 1.250,00», «€1.250.00», «EUR 1.250 ,00», «1.250,00 E»: sono
tutte letture dello stesso importo. La forma canonica e' «€ 1.250,00»: simbolo,
spazio, migliaia con il punto, decimali con la virgola. Si interviene solo
davanti a numeri che hanno la forma di un importo, mai su numeri generici.
"""

from __future__ import annotations

import re

from .regola import Regola, regola_regex

# Un importo per forma: migliaia con il punto e/o due decimali con la virgola.
_IMPORTO = r"\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+,\d{2}"
_SIMBOLO_SCRITTO = re.compile(r"(?<![\w€])(?:€|(?:EUR|Eur|eur|Euro|euro)\.?)\s*[.:]?\s*(?=\d)")
_SIMBOLO_LETTO_MALE = re.compile(rf"(?<![\w€])[EC](?:\s?)(?=(?:{_IMPORTO})(?![\w]))")
_EURO_DOPO_LETTO_MALE = re.compile(rf"(?<=\d,\d\d)\s?[EC](?=\s*(?:[.;,)]|$))")
_SPAZI_NELL_IMPORTO = re.compile(r"(?<=€ )((?:\d{1,3}\s*[.]\s*)+\d{3}|\d+)\s*,\s*(\d{2})\b")
_MIGLIAIA_SPAZIATE = re.compile(r"(?<=€ )((?:\d{1,3}\s*\.\s*)+\d{3})(?![\d,])")
_DECIMALI_CON_PUNTO = re.compile(r"(?<=€ )(\d{1,3}(?:\.\d{3})*)\.(\d{2})(?![\d])")
_SIMBOLO_ATTACCATO = re.compile(r"€(?=\d)")


def _simbolo(_match: re.Match[str]) -> str:
    return "€ "


def _spazi(match: re.Match[str]) -> str:
    return f"{re.sub(r'\s+', '', match.group(1))},{match.group(2)}"


def _migliaia(match: re.Match[str]) -> str:
    return re.sub(r"\s+", "", match.group(1))


REGOLE: tuple[Regola, ...] = (
    regola_regex("val.simbolo.v1", "simbolo dell'euro", "«EUR», «Euro» e «€» davanti all'importo scritti «€ ».", _SIMBOLO_SCRITTO, _simbolo),
    regola_regex("val.simbolo_letto_male.v1", "euro letto come E o C", "Lettera letta al posto del simbolo «€» davanti a un importo.", _SIMBOLO_LETTO_MALE, "€ "),
    regola_regex("val.euro_dopo.v1", "euro dopo l'importo", "Lettera letta al posto del simbolo «€» dopo un importo.", _EURO_DOPO_LETTO_MALE, " €"),
    regola_regex("val.simbolo_spazio.v1", "spazio dopo l'euro", "Spazio fra il simbolo «€» e l'importo.", _SIMBOLO_ATTACCATO, "€ "),
    regola_regex("val.spazi.v1", "spazi dentro l'importo", "Spazi tolti fra migliaia e decimali di un importo.", _SPAZI_NELL_IMPORTO, _spazi),
    regola_regex("val.migliaia.v1", "spazi fra le migliaia", "Spazi tolti attorno al punto delle migliaia.", _MIGLIAIA_SPAZIATE, _migliaia),
    regola_regex("val.decimali.v1", "decimali con il punto", "Decimali di un importo in euro scritti con la virgola.", _DECIMALI_CON_PUNTO, r"\1,\2"),
)

__all__ = ["REGOLE"]
