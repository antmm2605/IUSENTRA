"""Commi degli articoli dalla fonte ufficiale (Normattiva, XML NIR/Akoma Ntoso), senza mai dividere per frasi.

Il testo archiviato degli articoli è su una riga sola: la divisione in commi si legge dall'XML ufficiale di
Normattiva, dove ogni comma è un paragrafo (``h:p`` nel formato NIR dei codici; ``paragraph`` con ``num`` in
Akoma Ntoso). Si conserva solo dove inizia ogni comma, contato in caratteri non bianchi, con l'impronta del testo
senza spazi: al momento della lettura i commi si applicano solo se il testo archiviato coincide con quello letto
nell'XML (stessa versione). Se non coincide, l'articolo resta intero: nessuna divisione indovinata.

Le voci elencate dentro un comma (numeri «1)», lettere «a)», trattini) restano nel comma che le introduce.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

INDICE = Path(__file__).with_name("dati") / "commi_vigenti.json"
_NOTE = re.compile(r"\s*-{5,}\s*(?=AGGIORNAMENTO\b)")
_VOCE_INTERNA = re.compile(r"^\s*(?:\(\(\s*)?(?:\d{1,3}(?:\s*-?\s*[a-z]{3,12})?[)°]|[a-z]{1,2}(?:-?[a-z]{3,12})?\)|-\s|–\s|•)")
_SPAZI = re.compile(r"\s+")
_SOLO_NOTE = re.compile(r"(?:\s*\(\(?\d{1,4}[a-z]?\)\)?)+\s*")


def senza_spazi(testo: str) -> str:
    return _SPAZI.sub("", testo or "")


def impronta(testo: str) -> str:
    return hashlib.sha256(senza_spazi(testo).encode("utf-8")).hexdigest()[:24]


def chiave(data_atto: str, numero_atto: str, articolo: str) -> str:
    articolo = re.sub(r"[\s.\-]", "", str(articolo or "")).lower()
    articolo = re.sub(r"^art(?:icolo)?", "", articolo)
    return f"{str(data_atto or '')[:10]}|{str(numero_atto or '').strip().lstrip('0')}|{articolo}"


def raggruppa_commi(paragrafi: Iterable[str]) -> list[str]:
    """Paragrafi del corpo → commi: un elenco interno resta con il comma che lo introduce."""
    commi: list[str] = []
    for paragrafo in paragrafi:
        testo = " ".join(str(paragrafo or "").split())
        if not testo:
            continue
        # Un comma comincia con la maiuscola (o con il suo numero): un paragrafo in minuscolo, una voce
        # d'elenco o un solo richiamo di nota («(67)(72)») continuano il comma precedente.
        if commi and (_VOCE_INTERNA.match(testo) or testo[:1].islower() or _SOLO_NOTE.fullmatch(testo)):
            commi[-1] = f"{commi[-1]} {testo}"
        else:
            commi.append(testo)
    return commi


def voce_indice(intestazione: list[str], commi: list[str]) -> dict:
    """Inizio di ogni comma in caratteri non bianchi, nel testo «intestazione + commi»."""
    inizi, contati = [], len(senza_spazi(" ".join(intestazione)))
    for comma in commi:
        inizi.append(contati)
        contati += len(senza_spazi(comma))
    return {"impronta": impronta(" ".join([*intestazione, *commi])), "inizi": inizi}


@lru_cache(maxsize=1)
def _indice(percorso: str = str(INDICE)) -> dict:
    try:
        apri = gzip.open if str(percorso).endswith(".gz") else open
        with apri(percorso, "rt", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return {"voci": {}}


def commi_articolo(testo: str, data_atto: str, numero_atto: str, articolo: str) -> list[str] | None:
    """I commi del testo archiviato, se l'XML ufficiale letto ha lo stesso testo; altrimenti None."""
    voce = _indice()["voci"].get(chiave(data_atto, numero_atto, articolo))
    if not voce or len(voce.get("inizi") or []) < 2:
        return None
    corpo = _NOTE.split(testo or "", maxsplit=1)[0]
    if impronta(corpo) != voce["impronta"]:
        return None
    inizi = list(voce["inizi"])
    tagli, contati = [], 0
    for posizione, carattere in enumerate(corpo):
        if not carattere.isspace():
            if inizi and contati == inizi[0]:
                tagli.append(posizione)
                inizi.pop(0)
            contati += 1
    if inizi:
        return None
    return [corpo[inizio:fine].strip() for inizio, fine in zip(tagli, [*tagli[1:], len(corpo)])]


def intestazione_articolo(testo: str, data_atto: str, numero_atto: str, articolo: str) -> str:
    """La parte prima del primo comma («Art. 155. (Computo dei termini).»), se i commi sono applicabili."""
    voce = _indice()["voci"].get(chiave(data_atto, numero_atto, articolo))
    commi = commi_articolo(testo, data_atto, numero_atto, articolo)
    if not voce or not commi:
        return ""
    corpo = _NOTE.split(testo or "", maxsplit=1)[0]
    return corpo[: corpo.find(commi[0])].strip()
