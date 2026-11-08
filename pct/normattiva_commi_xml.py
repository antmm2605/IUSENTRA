"""Commi non numerati dei testi Normattiva, letti dalla struttura dell'XML ufficiale.

Negli atti più vecchi (es. D.P.R. 633/1972) i commi non hanno numero: nel testo dell'archivio i capoversi sono fusi e
il «terzo comma» non si può individuare con certezza. L'XML pubblicato da Normattiva conserva invece i capoversi:
ogni comma è un paragrafo con rientro di primo livello («padding-left:2px»), mentre lettere e numeri hanno un
rientro maggiore e restano nel comma che li precede. Le intestazioni centrate (numero e rubrica dell'articolo) e le
note di aggiornamento dopo il testo («-------------», «AGGIORNAMENTO») non sono commi.

Si legge solo l'XML da cui è stato importato l'atto (stesso archivio e stessa voce): nessuna altra fonte.
"""

from __future__ import annotations

import html
import os
import re
import zipfile
from pathlib import Path

_ARTICOLO = re.compile(r'<articolo\b[^>]*>(?P<corpo>.*?)</articolo>', re.DOTALL)
_NUM = re.compile(r"<num>\s*(?P<num>[^<]*)</num>")
_PARAGRAFO = re.compile(r'<h:p\b(?P<attr>[^>]*)>(?P<testo>.*?)</h:p>', re.DOTALL)
_RIENTRO = re.compile(r'padding-left\s*:\s*(\d+)px')
_TAG = re.compile(r"<[^>]+>")
_LATINI = r"(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)"


def _normale(valore: str) -> str:
    return re.sub(r"[\s.\-]+", "", str(valore or "")).lower()


def _numero_articolo(etichetta: str) -> str:
    trovato = re.match(rf"\s*art(?:icolo|\.)?\s*(\d{{1,4}}(?:\s*-?\s*{_LATINI})?)", etichetta or "", re.IGNORECASE)
    return _normale(trovato[1]) if trovato else ""


def _pulisci(testo: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", testo)).split())


def commi_dell_articolo(xml: str, articolo: str) -> list[str]:
    """I commi dell'articolo indicato, in ordine; lista vuota se l'articolo non c'è o non è strutturato così."""
    voluto = _normale(articolo)
    for trovato in _ARTICOLO.finditer(xml):
        corpo = trovato["corpo"]
        numero = _NUM.search(corpo)
        if not numero or _numero_articolo(numero["num"]) != voluto:
            continue
        # L'intestazione (numero e rubrica) precede il primo <h:br/>; il rientro del primo capoverso che segue è
        # quello d'inizio comma per tutto l'articolo (2px, 6px... secondo l'impaginazione dell'atto).
        inizio_testo = corpo.find("<h:br/>")
        corpo_testo = corpo[inizio_testo + len("<h:br/>"):] if inizio_testo >= 0 else corpo
        commi: list[str] = []
        rientro_comma: int | None = None
        for paragrafo in _PARAGRAFO.finditer(corpo_testo):
            attributi, testo = paragrafo["attr"], _pulisci(paragrafo["testo"])
            if not testo or "text-align: center" in attributi or "text-align:center" in attributi:
                continue
            if re.fullmatch(rf"art(?:icolo|\.)?\s*\d+[\s\-]*(?:{_LATINI})?\.?", testo, re.IGNORECASE):
                continue
            if testo.startswith("---") or testo.upper().startswith("AGGIORNAMENTO"):
                break  # note di aggiornamento dopo il testo dell'articolo
            trovato = _RIENTRO.search(attributi)
            rientro = int(trovato[1]) if trovato else -1
            if rientro_comma is None:
                rientro_comma = rientro
            if rientro == rientro_comma or not commi:
                commi.append(testo)
            else:
                commi[-1] = f"{commi[-1]} {testo}"
        return commi
    return []


def _archivio(zip_path: str, raw_dir: str = "") -> Path | None:
    percorso = Path(zip_path or "")
    if percorso.is_file():
        return percorso
    cartella = raw_dir or os.getenv("IUSENTRA_NORMATTIVA_RAW_DIR", "")
    if cartella and percorso.name and (Path(cartella) / percorso.name).is_file():
        return Path(cartella) / percorso.name
    return None


def testo_comma_da_xml(zip_path: str, xml_entry: str, articolo: str, comma: str, *, raw_dir: str = "") -> str:
    """Il comma n. «comma» (solo numerico) dell'articolo, dall'XML ufficiale; stringa vuota se non individuabile."""
    if not str(comma).isdigit() or not articolo or not xml_entry:
        return ""
    archivio = _archivio(zip_path, raw_dir)
    if archivio is None:
        return ""
    try:
        with zipfile.ZipFile(archivio) as contenitore:
            xml = contenitore.read(xml_entry).decode("utf-8", "replace")
    except (KeyError, OSError, zipfile.BadZipFile):
        return ""
    commi = commi_dell_articolo(xml, articolo)
    indice = int(comma) - 1
    return commi[indice][:6000] if 0 <= indice < len(commi) else ""


__all__ = ["commi_dell_articolo", "testo_comma_da_xml"]
