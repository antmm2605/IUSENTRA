"""Passo 6 dell'harness: controlli di coerenza prima di rispondere.

1. Ogni affermazione giuridica deve trovare la sua ancora nel testo vigente della norma citata; se non la trova non
   viene affermata e passa fra i dubbi con il motivo.
2. Ogni articolo citato nel testo finale (anche nella bozza) deve esistere nel catalogo e leggersi dall'archivio:
   un riferimento sconosciuto è un riferimento non verificato e abbassa l'affidabilità.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .modello import Analisi, Punto
from .norme import NORME, contiene, testo_norma

_SIGLE = {
    "c.c.": "cc", "c.p.c.": "cpc", "c.p.": "cp", "c.p.p.": "cpp", "c.p.a.": "cpa",
    "d.l. 132/2014": "dl132", "d.lgs. 28/2010": "dlgs28", "l. 742/1969": "l742", "l. 392/1978": "l392",
    "l. 604/1966": "l604", "l. 898/1970": "l898", "d.lgs. 206/2005": "dlgs206", "d.p.r. 1199/1971": "dpr1199",
    "d.p.r. 115/2002": "dpr115", "d.lgs. 546/1992": "dlgs546", "d.lgs. 104/2010": "cpa",
}
_ATTO = r"(c\.p\.a\.|c\.p\.c\.|c\.p\.p\.|c\.c\.|c\.p\.|d\.l\. 132/2014|d\.lgs\. 28/2010|l\. \d{2,4}/\d{4}|d\.lgs\. \d+/\d{4}|d\.p\.r\. \d+/\d{4})"
_NUM = r"\d{1,4}(?:-(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies|undecies|duodecies))?(?:\.\d{1,2})?"
_CITAZIONE = re.compile(r"\bartt?\.\s*((?:" + _NUM + r")(?:(?:\s*,\s*|\s+e\s+|\s*-\s*)" + _NUM + r")*)"
                        r"(?:\s*(?:ss\.|e ss\.|seg\w*))?(?:,\s*comm[ai]\s*[\d\s,e-]+(?:,\s*n+\.\s*[\d-]+(?:-bis)?)?)?(?:,)?\s+" + _ATTO,
                        re.IGNORECASE)


def chiave_da_citazione(numero: str, atto: str) -> str:
    atto = atto.lower()
    prefisso = _SIGLE.get(atto)
    if prefisso is None:
        return ""
    return f"{prefisso}:{numero.lower().replace('-', '').replace('.', '')}"


def citazioni(testo: str) -> list[tuple[str, str]]:
    """Coppie (citazione letta, chiave del catalogo) per ogni articolo qualificato dal suo atto."""
    out = []
    for m in _CITAZIONE.finditer(testo.replace("D.P.R.", "d.P.R.").replace("d.P.R.", "d.p.r.")):
        for numero in re.findall(_NUM, m.group(1), re.IGNORECASE):
            out.append((f"art. {numero} {m.group(2)}", chiave_da_citazione(numero, m.group(2))))
    return out


@dataclass
class EsitoControllo:
    norme_verificate: list[str] = field(default_factory=list)
    affermazioni_tolte: list[str] = field(default_factory=list)
    citazioni_non_verificate: list[str] = field(default_factory=list)

    @property
    def pulito(self) -> bool:
        return not self.affermazioni_tolte and not self.citazioni_non_verificate


def _verifica_punto(p: Punto) -> None:
    for r in p.rif:
        if r.chiave not in NORME:
            p.verificato, p.motivo = False, f"norma «{r.chiave}» non presente nel catalogo dell'harness"
            return
        if testo_norma(r.chiave) is None:
            p.verificato, p.motivo = False, f"{NORME[r.chiave].citazione}: testo vigente non leggibile dall'archivio"
            return
        if not contiene(r.chiave, r.ancora):
            p.verificato, p.motivo = False, f"{NORME[r.chiave].citazione}: il testo vigente non contiene «{r.ancora}»"
            return
    p.verificato = True


def verifica_analisi(a: Analisi) -> EsitoControllo:
    esito = EsitoControllo()
    for nome, lista in a.sezioni():
        tenuti = []
        for p in lista:
            _verifica_punto(p)
            if p.verificato:
                tenuti.append(p)
                for r in p.rif:
                    if r.chiave not in esito.norme_verificate:
                        esito.norme_verificate.append(r.chiave)
            else:
                esito.affermazioni_tolte.append(p.motivo)
                a.dubbi.append(f"Non affermato perché non verificato ({p.motivo}): {p.testo}")
        lista[:] = tenuti
    return esito


def verifica_citazioni(testo: str, esito: EsitoControllo) -> None:
    for citazione, chiave in citazioni(testo):
        if not chiave or chiave not in NORME or testo_norma(chiave) is None:
            if citazione not in esito.citazioni_non_verificate:
                esito.citazioni_non_verificate.append(citazione)
