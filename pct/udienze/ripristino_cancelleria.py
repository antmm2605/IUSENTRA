"""Ripristino delle udienze annullate dalla rettifica automatica del 17/09/2026 ma confermate dalla cancelleria.

La rettifica di allora annullava un'udienza quando la rilettura di un documento non confermava piu' la data,
senza guardare le comunicazioni di cancelleria. Qui si ripristina SOLO l'udienza che ha una prova certificata:
Comunicazione.xml (Specifiche tecniche DGSIA, D.M. 44/2011 art. 34; art. 16 d.l. 179/2012) arrivata in una
busta PEC di un ufficio giudiziario (daticert.xml con mittente giustiziacert), stesso numero di ruolo e stessa
data in un contesto d'udienza o di termine. Nessuna deduzione: senza prova l'udienza resta com'e'.
"""
from __future__ import annotations

import hashlib
import html
from datetime import date
import re
from dataclasses import dataclass, field

# Note scritte dalla rettifica automatica (commit d6dcf9163 / a7a27ad6a del 17/09/2026).
MARCATORI_RETTIFICA = (
    "Rettifica automatica: la lettura corrente esclude questa data come udienza",
    "La lettura corrente non conferma più questo dato",
)
_DATA = r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"
_CONTESTO = re.compile(r"(UDIENZA|RINVIA\w*|RINVIO|DIFFERIMENTO|TERMINE)[^\n<]{0,60}?" + _DATA, re.I)
_RG = re.compile(r"(\d+)\s*/\s*(\d{4})")


@dataclass(frozen=True)
class Prova:
    rg: str
    data: str  # ISO
    pec_id: str
    sha256: str
    oggetto: str
    estratto: str
    fascicolo_id: str = ""


@dataclass
class Piano:
    ripristinare: list[dict] = field(default_factory=list)
    senza_prova: int = 0


def rg_normale(testo: str) -> str:
    m = _RG.search(str(testo or ""))
    return f"{int(m.group(1))}/{m.group(2)}" if m else ""


def prove_da_comunicazione(xml: str, *, daticert: str, pec_id: str, fascicolo_id: str = "") -> list[Prova]:
    """Date d'udienza o di termine certificate da una Comunicazione.xml di un ufficio; vuoto se la busta non e' di un ufficio."""
    if not re.search(r"<mittente(?:\s[^>]*)?>\s*[^<\s@]+@(?:[a-z0-9-]+\.)*giustiziacert\.it\s*</mittente>", daticert or "", re.I):
        return []
    nr = re.search(r"<NumeroRuolo>(.*?)</NumeroRuolo>", xml or "", re.S)
    rg = rg_normale(nr.group(1)) if nr else ""
    if not rg:
        return []
    oggetto = html.unescape((re.search(r"<Oggetto>(.*?)</Oggetto>", xml, re.S) or [None, ""])[1]).strip()
    contenuto = html.unescape((re.search(r"<Contenuto>(.*?)</Contenuto>", xml, re.S) or [None, ""])[1])
    impronta = hashlib.sha256(xml.encode("utf-8")).hexdigest()
    prove = []
    for m in _CONTESTO.finditer(contenuto):
        g, mm, a = int(m.group(2)), int(m.group(3)), int(m.group(4))
        try:
            date(a, mm, g)
        except ValueError:
            continue
        prima = contenuto[max(0, m.start(2) - 60):m.start(2)]
        revoca = re.search(r"REVOC\w*(.*)$", prima, re.I | re.S)
        if revoca and not re.search(r"FISSAT|TERMINE|RINVI|DIFFER", revoca.group(1), re.I):
            continue  # data dell'udienza revocata, non confermata
        prove.append(Prova(rg, f"{a:04d}-{mm:02d}-{g:02d}", pec_id, impronta, oggetto[:200], " ".join(m.group(0).split())[:160], fascicolo_id))
    return prove


def pianifica(appuntamenti: list[dict], prove: list[Prova]) -> Piano:
    """Udienze annullate dalla rettifica automatica con una prova della cancelleria per RG e data."""
    indice: dict[tuple[str, str, str], Prova] = {}
    for p in prove:
        if p.fascicolo_id:
            indice.setdefault((p.fascicolo_id, p.rg, p.data), p)
    piano = Piano()
    for a in appuntamenti:
        if str(a.get("tipo") or "").upper() != "UDIENZA" or str(a.get("stato") or "").upper() != "ANNULLATO":
            continue
        note = str(a.get("note") or "")
        if not any(m in note for m in MARCATORI_RETTIFICA):
            continue
        prova = indice.get((str(a.get("id_fascicolo") or ""), rg_normale(a.get("procedimento")), str(a.get("data_ora") or "")[:10]))
        if prova is None:
            piano.senza_prova += 1
            continue
        piano.ripristinare.append({"id": a["id"], "data": str(a.get("data_ora"))[:10], "rg": prova.rg,
                                   "impronta_riga": a.get("_impronta", ""),
                                   "prova": {"fascicolo_id": prova.fascicolo_id, "pec_id": prova.pec_id, "comunicazione_sha256": prova.sha256,
                                             "oggetto": prova.oggetto, "estratto": prova.estratto}})
    return piano


def nota_ripristino(voce: dict, operazione: str) -> str:
    p = voce["prova"]
    return (f"Ripristinata: la cancelleria conferma l'udienza (Comunicazione.xml {p['comunicazione_sha256'][:12]}, "
            f"PEC {p['pec_id']}, «{p['oggetto']}»). La rettifica automatica del 17/09/2026 l'aveva annullata senza "
            f"considerare la comunicazione. Operazione {operazione}.")
