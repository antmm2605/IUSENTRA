"""Abbreviazioni del linguaggio forense, riportate alla forma canonica.

«art .», «D. Lgs.», «d.p.c.m.», «RG 123/2024», «c. p. c.»: il motore legge le
lettere ma sparpaglia punti e spazi, e lo stesso riferimento compare in tre
forme diverse nello stesso atto. Le forme canoniche sono quelle d'uso nella
prassi forense e nei testi ufficiali (Normattiva, Cassazione): «art.», «D.Lgs.»,
«D.P.C.M.», «R.G.», «c.p.c.». Nessuna abbreviazione viene sciolta o
interpretata: si normalizza solo la scrittura.
"""

from __future__ import annotations

import re

from .regola import Regola, conserva_maiuscole, regola_regex

# Abbreviazioni con punto finale davanti a cui il motore lascia uno spazio.
_CON_PUNTO = (
    "avv|avv\\.ti|dott|dott\\.ssa|dr|sig|sigg|sig\\.ra|prof|ing|geom|rag|on|sen|spett|ill|egr|gent|"
    "pres|cons|giud|trib|cass|sez|un|co|lett|cfr|pag|pagg|all|doc|docc|ecc|es|ss|seg|segg|vol|"
    "cap|tab|fig|nn|cit|op|loc|ult|prec|succ|mod|tel|fax|cell|cod|fisc|civ|pen|amm|lav|fall|"
    "soc|ord|sent|dec|prot|rif|ric|resp|conv|att|proc|reg|gen"
)
_PUNTO_STACCATO = re.compile(rf"\b({_CON_PUNTO})\s+\.", re.IGNORECASE)

# «art 2043» e «Art.2043»: punto e spazio dell'articolo davanti al numero.
_ARTICOLO = re.compile(r"\b([Aa])rt(t?)(?:\s*\.)?\s*(?=[\dlIO(]|[a-z]?\d)")
_NUMERO = re.compile(r"\b([nN])\s*(?:[°º˚]|\.ro|r\.|\.)\s*(?=[\dlIO])")


def _articolo(match: re.Match[str]) -> str:
    return f"{match.group(1)}rt{match.group(2)}. "


def _numero(match: re.Match[str]) -> str:
    return f"{match.group(1)}. "


def _sigla(canonico: str, lettere: str, *nude: str) -> str:
    """Espressione di una sigla puntata letta con spazi, senza punti o nella forma nuda.

    Il punto finale, se c'e', viene sempre consumato: cosi' «S. p. A.Per» diventa
    «S.p.A.» seguito da «Per», e non «S.p.A.» piu' un punto avanzato.
    """
    puntata = r"\s*\.\s*".join(f"[{lettera.lower()}{lettera.upper()}]" for lettera in lettere) + r"(?:\s*\.|(?![\w]))"
    alternative = [puntata]
    if nude:
        alternative.append("(?:" + "|".join(re.escape(nuda) for nuda in nude) + r")(?:\.(?![\w])|(?![\w]))")
    return r"(?<![\w.])(?:" + "|".join(alternative) + ")"


def _codice(sigla: str, *lettere: str) -> tuple[str, str]:
    """Espressione di un codice con punti («c.p.c.») letto con spazi o senza punti."""
    return _sigla(sigla, "".join(lettere), "".join(lettere), "".join(lettere).upper()), sigla


def _canonico_codice(canonico: str):
    def sostituisci(match: re.Match[str]) -> str:
        return conserva_maiuscole(match.group(0), canonico) if canonico.islower() else canonico

    return sostituisci


_CODICI: tuple[tuple[str, str, str], ...] = (
    ("abbr.cpc.v1", *_codice("c.p.c.", "c", "p", "c")),
    ("abbr.cpp.v1", *_codice("c.p.p.", "c", "p", "p")),
    ("abbr.cpa.v1", *_codice("c.p.a.", "c", "p", "a")),
    ("abbr.cds.v1", *_codice("c.d.s.", "c", "d", "s")),
)
# «c.c.» e «c.p.» solo con i punti: «cc» e «cp» sono anche altre cose.
_CC = re.compile(r"(?<![\w.])[cC]\s*\.\s*[cC]\s*\.(?![\w])")
_CP = re.compile(r"(?<![\w.])[cC]\s*\.\s*[pP]\s*\.(?![\w.])")
_DISP_ATT = re.compile(r"\bdisp\s*\.\s*att\s*\.", re.IGNORECASE)

# Fonti normative. Il decreto legislativo si scrive «D.Lgs.», e il motore lo
# legge in ogni combinazione di punti e spazi («D. Lgs.», «DLgs», «D.L.vo»).
_DLGS = re.compile(r"\b[dD](?:\s*\.)?\s*[lL](?:\s*\.)?\s*(?:[gG][sS]|[vV][oO])(?:\s*\.)?(?=\s|$|[\d(,;:])")
_DL = re.compile(r"\b(?:[dD]\s*\.\s*[lL]\s*\.|DL)(?!\s*(?:[gG][sS]|[vV][oO]))(?=\s*(?:n\.?\s*)?\d)")
_DPR = re.compile(r"\b(?:[dD]\s*\.\s*[pP]\s*\.\s*[rR](?:\s*\.)?|DPR)(?![\w])")
_DPCM = re.compile(r"\b(?:[dD]\s*\.\s*[pP]\s*\.\s*[cC]\s*\.\s*[mM](?:\s*\.)?|DPCM)(?![\w])")
_DM = re.compile(r"\b(?:[dD]\s*\.\s*[mM]\s*\.|DM)(?=\s*(?:n\.?\s*)?\d)")
_RD = re.compile(r"\b(?:[rR]\s*\.\s*[dD]\s*\.|RD)(?=\s*(?:n\.?\s*)?\d)")
_LEGGE = re.compile(r"\b[lL]\s*\.\s*(?=(?:n\.?\s*)?\d{1,4}\s*/\s*\d{2,4})")
_DIRETTIVA_UE = re.compile(r"\b(?:Reg|Dir)\s*\.\s*(?:UE|CE|CEE)\b")

# Ruolo generale e registri: «R.G.» e' la forma canonica; «RG» resta ammesso
# solo quando e' seguito dal numero, per non toccare sigle di altro genere.
_RGNR = re.compile(r"\b[rR](?:\s*\.)?\s*[gG](?:\s*\.)?\s*[nN](?:\s*\.)?\s*[rR](?:\s*\.|(?![\w]))")
_RGAC = re.compile(r"\b[rR](?:\s*\.)?\s*[gG](?:\s*\.)?\s*[aA](?:\s*\.)?\s*[cC](?:\s*\.|(?![\w]))")
_NRG = re.compile(r"\b[nN](?:\s*\.)?\s*[rR](?:\s*\.)?\s*[gG](?:\s*\.)?(?=\s*\d)")
_RG = re.compile(r"\b(?:[rR]\s*\.\s*[gG](?:\s*\.)?|RG|Rg)(?=\s*(?:n\.?\s*)?[\dlIO])")
_RG_ZERO = re.compile(r"\bR\s*[G6]\s*0\b", re.IGNORECASE)

# Sigle d'ufficio e di procedura con i punti.
_SIGLE: tuple[tuple[str, str, str], ...] = (
    ("abbr.pqm.v1", _sigla("P.Q.M.", "pqm", "PQM"), "P.Q.M."),
    ("abbr.ctu.v1", _sigla("C.T.U.", "ctu", "CTU"), "C.T.U."),
    ("abbr.ctp.v1", _sigla("C.T.P.", "ctp", "CTP"), "C.T.P."),
    ("abbr.gip.v1", _sigla("G.I.P.", "gip", "GIP"), "G.I.P."),
    ("abbr.gup.v1", _sigla("G.U.P.", "gup", "GUP"), "G.U.P."),
    ("abbr.unep.v1", _sigla("U.N.E.P.", "unep", "UNEP"), "U.N.E.P."),
    ("abbr.gdp.v1", _sigla("G.d.P.", "gdp", "GdP"), "G.d.P."),
    ("abbr.pec.v1", r"\b[pP]\s*\.\s*[eE]\s*\.\s*[cC](?:\s*\.|(?![\w]))(?![\w])", "PEC"),
    ("abbr.piva.v1", r"\b[pP]\s*\.?\s*(?:IVA|Iva)\b(?!\.)", "P.IVA"),
    ("abbr.cf.v1", r"\b[cC]\s*\.\s*[fF]\s*\.(?=\s*[:A-Z0-9])", "C.F."),
    ("abbr.spa.v1", _sigla("S.p.A.", "spa", "SPA", "Spa"), "S.p.A."),
    ("abbr.srls.v1", _sigla("S.r.l.s.", "srls", "SRLS", "Srls"), "S.r.l.s."),
    ("abbr.srl.v1", _sigla("S.r.l.", "srl", "SRL", "Srl") , "S.r.l."),
    ("abbr.sas.v1", _sigla("S.a.s.", "sas", "SAS"), "S.a.s."),
    ("abbr.snc.v1", _sigla("S.n.c.", "snc", "SNC"), "S.n.c."),
    ("abbr.sezun.v1", r"\b[sS]ez\s*\.?\s*[uU]n(?:\s*\.|(?![\w]))", "Sez. Un."),
    ("abbr.cost.v1", r"\bCorte\s+[cC]ost(?:\s*\.|(?![\w]))", "Corte cost."),
)


def _regole_sigle() -> list[Regola]:
    regole: list[Regola] = []
    for identificativo, schema, canonico in _SIGLE:
        regole.append(regola_regex(identificativo, f"sigla {canonico}", f"Sigla riportata alla forma «{canonico}».", schema, canonico))
    return regole


REGOLE: tuple[Regola, ...] = (
    regola_regex("abbr.punto.v1", "punto delle abbreviazioni", "Spazio tolto fra l'abbreviazione e il suo punto («avv .» → «avv.»).", _PUNTO_STACCATO, r"\1."),
    regola_regex("punct.art.v1", "scrittura di «art.»", "Articolo scritto «art.» con lo spazio prima del numero.", _ARTICOLO, _articolo),
    regola_regex("punct.n.v1", "scrittura di «n.»", "Numero scritto «n.» al posto di «n°», «nr.» e «n .».", _NUMERO, _numero),
    *(regola_regex(identificativo, f"codice {canonico}", f"Codice riportato alla forma «{canonico}».", schema, _canonico_codice(canonico)) for identificativo, schema, canonico in _CODICI),
    regola_regex("abbr.cc.v1", "codice c.c.", "Codice civile riportato alla forma «c.c.».", _CC, _canonico_codice("c.c.")),
    regola_regex("abbr.cp.v1", "codice c.p.", "Codice penale riportato alla forma «c.p.».", _CP, _canonico_codice("c.p.")),
    regola_regex("abbr.dispatt.v1", "disposizioni di attuazione", "Riportato alla forma «disp. att.».", _DISP_ATT, "disp. att."),
    regola_regex("abbr.dlgs.v1", "decreto legislativo", "Riportato alla forma «D.Lgs.».", _DLGS, "D.Lgs."),
    regola_regex("abbr.dpcm.v1", "D.P.C.M.", "Riportato alla forma «D.P.C.M.».", _DPCM, "D.P.C.M."),
    regola_regex("abbr.dpr.v1", "D.P.R.", "Riportato alla forma «D.P.R.».", _DPR, "D.P.R."),
    regola_regex("abbr.dl.v1", "decreto-legge", "Riportato alla forma «D.L.».", _DL, "D.L."),
    regola_regex("abbr.dm.v1", "decreto ministeriale", "Riportato alla forma «D.M.».", _DM, "D.M."),
    regola_regex("abbr.rd.v1", "regio decreto", "Riportato alla forma «R.D.».", _RD, "R.D."),
    regola_regex("abbr.legge.v1", "legge", "Riportato alla forma «L.» davanti al numero.", _LEGGE, "L. "),
    regola_regex("abbr.rgnr.v1", "R.G.N.R.", "Registro notizie di reato riportato alla forma «R.G.N.R.».", _RGNR, "R.G.N.R."),
    regola_regex("abbr.rgac.v1", "R.G.A.C.", "Ruolo affari civili riportato alla forma «R.G.A.C.».", _RGAC, "R.G.A.C."),
    regola_regex("abbr.nrg.v1", "N.R.G.", "Riportato alla forma «N.R.G.».", _NRG, "N.R.G."),
    regola_regex("ocr.rg.zero.v1", "numero di ruolo letto male", "«RG0» letto dal motore riportato a «R.G. n.».", _RG_ZERO, "R.G. n."),
    regola_regex("abbr.rg.v1", "R.G.", "Ruolo generale riportato alla forma «R.G.».", _RG, "R.G."),
    *_regole_sigle(),
)

__all__ = ["REGOLE"]
