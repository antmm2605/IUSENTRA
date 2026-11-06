"""Citazioni contenute nelle decisioni: norme applicate e precedenti richiamati.

Il testo ufficiale di una decisione dice quali norme applica («art. 2087 c.c.», «art. 63, comma 2, d.lgs. n. 165 del
2001») e quali precedenti richiama («Cass., Sez. U, n. 24418 del 2010», «Corte cost. n. 194 del 2018»). Questo lettore
li riconosce con regole dichiarate e li restituisce in forma normalizzata, pronti per le tabelle ``norme``,
``sentenza_norme`` e ``sentenza_precedenti`` dell'archivio. Non interpreta il principio affermato: lo legge l'avvocato.
"""

from __future__ import annotations

import re
from typing import Any

VERSIONE_LETTORE = "2026.11.06.citazioni.v1"

_SUFFISSO = r"(?:(?:\s?-\s?|\s)?(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies|undecies|duodecies|terdecies|quaterdecies|quinquiesdecies))?"
_ARTICOLO = rf"(?P<art>\d{{1,4}}{_SUFFISSO}(?:\.\d{{1,3}})?)"
_COMMA = r"(?:,?\s*(?:comma|co\.|c\.)\s*(?P<comma>\d{1,3}(?:-?bis|-?ter)?|primo|secondo|terzo|quarto|quinto|sesto))?"
_LETTERA = r"(?:,?\s*lett(?:era)?\.?\s*(?P<lettera>[a-z]{1,2})\)?)?(?:,?\s*n(?:um)?\.\s*\d{1,2})?"
_ATTO_NUMERO = r"(?:n\.\s*)?(?P<numero>\d{1,5})\s*(?:/|del(?:l['’])?\s*(?:\d{1,2}\s+\w+\s+)?)\s*(?P<anno>(?:19|20)\d{2})"
# Codici: sigla nel testo -> sigla normalizzata.
_MESI = r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
_CODICI = (
    ("c.p.c.", r"c\.\s?p\.\s?c\.|cod\.\s?proc\.\s?civ\.|codice di procedura civile"),
    ("c.p.p.", r"c\.\s?p\.\s?p\.|cod\.\s?proc\.\s?pen\.|codice di procedura penale"),
    ("disp. att. c.c.", r"disp\.\s?att\.\s?c\.\s?c\."),
    ("disp. att. c.p.c.", r"disp\.\s?att\.\s?c\.\s?p\.\s?c\."),
    ("c.c.", r"c\.\s?c\.|cod\.\s?civ\.|codice civile"),
    ("c.p.", r"c\.\s?p\.(?!\s?[cp]\.)|cod\.\s?pen\.|codice penale"),
    ("c.p.a.", r"c\.\s?p\.\s?a\.|cod\.\s?proc\.\s?amm\."),
    ("Cost.", r"Cost\.|Costituzione"),
)
_ATTI = (
    ("D.Lgs.", r"d\.\s?lgs\.?|decreto legislativo"),
    ("D.P.R.", r"d\.\s?p\.\s?r\.?|decreto del presidente della repubblica"),
    ("D.L.", r"d\.\s?l\.(?!\s?gs)|decreto[\s-]legge"),
    ("L.", r"l\.|legge"),
)
_RE_CODICE = re.compile(rf"\bart(?:t|icol[oi])?\.?\s*{_ARTICOLO}{_COMMA}{_LETTERA}\s*,?\s*(?:del\s+|dello\s+)?(?P<codice>{'|'.join(f'(?:{p})' for _, p in _CODICI)})", re.IGNORECASE)
_RE_ATTO = re.compile(rf"\bart(?:t|icol[oi])?\.?\s*{_ARTICOLO}{_COMMA}{_LETTERA}\s*,?\s*(?:del(?:la|l['’])?\s+)?(?P<tipo>{'|'.join(f'(?:{p})' for _, p in _ATTI)})\s*{_ATTO_NUMERO}", re.IGNORECASE)
_RE_CASS = re.compile(rf"\b(?:Cass(?:azione)?\.?|Sez(?:ioni)?\.?\s*U(?:n(?:ite)?)?\.?|S\.\s?U\.|Sez\.?\s*(?:lav|[1-6]|trib)\.?)[^;()]{{0,60}}?\b{_ATTO_NUMERO}", re.IGNORECASE)
_RE_COST = re.compile(rf"\b(?:Corte\s+cost(?:ituzionale)?\.?|C\.\s?cost\.)[^;()]{{0,40}}?(?:sent(?:enza)?\.?|ord(?:inanza)?\.?)?\s*{_ATTO_NUMERO}", re.IGNORECASE)
# «Cass. S.U. 27 dicembre 2019, n. 34476», «Cass., sez. lav., 14 aprile 2017, n. 8758»: prima la data, poi il numero.
_RE_CASS_DATA = re.compile(rf"\b(?P<capo>Cass(?:azione)?\.?[^;()]{{0,40}}?)\b\d{{1,2}}\s+{_MESI}\s+(?P<anno>(?:19|20)\d{{2}}),?\s*n\.\s*(?P<numero>\d{{1,5}})", re.IGNORECASE)
# «art. 63, comma 2, del d.lgs. 30 marzo 2001, n. 165»: la data dell'atto prima del numero.
_RE_ATTO_DATA = re.compile(rf"\bart(?:t|icol[oi])?\.?\s*{_ARTICOLO}{_COMMA}{_LETTERA}\s*,?\s*(?:del(?:la|l['’])?\s+)?(?P<tipo>{'|'.join(f'(?:{p})' for _, p in _ATTI)})\s*\d{{1,2}}\s+{_MESI}\s+(?P<anno>(?:19|20)\d{{2}}),?\s*n\.\s*(?P<numero>\d{{1,5}})", re.IGNORECASE)
_ORDINALI = {"primo": "1", "secondo": "2", "terzo": "3", "quarto": "4", "quinto": "5", "sesto": "6"}


def _sigla(testo: str, tabella) -> str:
    return next((sigla for sigla, schema in tabella if re.fullmatch(schema, testo.strip(), re.IGNORECASE)), "")


def _articolo(valore: str) -> str:
    return re.sub(r"[\s-]+", "-", valore.strip().lower())


def norme_citate(testo: str) -> list[dict[str, Any]]:
    """Norme citate nel testo, una sola volta ciascuna (atto, articolo, comma, lettera), nell'ordine in cui compaiono."""
    pulito = re.sub(r"\s+", " ", testo or "")
    trovate: dict[tuple, dict[str, Any]] = {}
    for m in _RE_CODICE.finditer(pulito):
        sigla = _sigla(m["codice"], _CODICI)
        chiave = (sigla, _articolo(m["art"]), _ORDINALI.get((m["comma"] or "").lower(), m["comma"] or ""), (m["lettera"] or "").lower())
        trovate.setdefault(chiave, {"tipo_norma": "codice", "sigla": sigla, "articolo": chiave[1], "comma": chiave[2], "lettera": chiave[3],
                                    "testo_riferimento": m.group(0)[:160], "posizione": m.start()})
    for m in [*_RE_ATTO.finditer(pulito), *_RE_ATTO_DATA.finditer(pulito)]:
        sigla = f"{_sigla(m['tipo'], _ATTI)} {int(m['numero'])}/{m['anno']}"
        chiave = (sigla, _articolo(m["art"]), _ORDINALI.get((m["comma"] or "").lower(), m["comma"] or ""), (m["lettera"] or "").lower())
        trovate.setdefault(chiave, {"tipo_norma": "legge", "sigla": sigla, "articolo": chiave[1], "comma": chiave[2], "lettera": chiave[3],
                                    "testo_riferimento": m.group(0)[:160], "posizione": m.start()})
    return sorted(trovate.values(), key=lambda voce: voce["posizione"])


def precedenti_citati(testo: str, *, anno_decisione: int | None = None) -> list[dict[str, Any]]:
    """Precedenti di Cassazione e Corte costituzionale richiamati nel testo."""
    pulito = re.sub(r"\s+", " ", testo or "")
    trovati: dict[tuple, dict[str, Any]] = {}
    for organo, schema in (("Corte costituzionale", _RE_COST), ("Corte di Cassazione", _RE_CASS), ("Corte di Cassazione", _RE_CASS_DATA)):
        for m in schema.finditer(pulito):
            anno = int(m["anno"])
            if anno_decisione and anno > anno_decisione:
                continue  # un precedente non può essere successivo alla decisione che lo cita
            sezione = "U" if organo.startswith("Corte di") and re.search(r"Sez(?:ioni)?\.?\s*U|S\.\s?U\.", m.group(0), re.IGNORECASE) else ""
            if organo.startswith("Corte di") and re.search(r"lav", m.group(0), re.IGNORECASE):
                sezione = "L"
            chiave = (organo, sezione, str(int(m["numero"])), anno)
            if organo.startswith("Corte di") and any(k[0] == "Corte costituzionale" and k[2:] == chiave[2:] for k in trovati):
                continue
            trovati.setdefault(chiave, {"organo_giudicante": organo, "sezione": sezione, "numero_sentenza": chiave[2], "anno_sentenza": anno,
                                        "riferimento_testuale": m.group(0)[:200], "tipo_relazione": "citata", "verificata": 0})
    return list(trovati.values())
