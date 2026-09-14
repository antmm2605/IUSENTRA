"""Il secondo lettore: PDF Inspector (PP-OCR) a conferma di Tesseract.

Due motori diversi sbagliano in punti diversi. Tesseract restituisce ogni
parola con la sua posizione, che serve per impaginazione, grassetto e PDF
ricercabile; PDF Inspector (rete PP-OCR su ONNX, gia' nel container di
produzione) legge il testo con un modello diverso e su molte scansioni e' piu'
sicuro sulle singole parole. Qui i due si confrontano riga per riga: dove
Tesseract e' incerto su una parola e il secondo lettore ha letto, nella stessa
posizione della riga, una parola diversa con alta confidenza, vince il secondo
lettore. Le parole sicure non si toccano e la posizione resta quella di
Tesseract. Se il secondo lettore non c'e', la lettura resta quella di Tesseract.
"""

from __future__ import annotations

import io
import os
import re
import threading
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# Sotto questa confidenza la parola di Tesseract e' contendibile.
CONFIDENZA_CONTENDIBILE = 0.85
# Sopra questa confidenza di pagina il secondo lettore puo' correggere.
CONFIDENZA_SECONDO_LETTORE = 0.90
# Somiglianza minima fra due righe perche' siano la stessa riga.
SOMIGLIANZA_RIGA = 0.72
DPI_SECONDO_LETTORE = 150.0
CARTELLA_MODELLI_PREDEFINITA = "/opt/iusentra/ocr/models"

_STATO = {"verificato": False, "disponibile": False}
_BLOCCO = threading.Lock()


@dataclass(frozen=True)
class LetturaSecondaria:
    testo: str
    confidenza: float
    motore: str
    secondi: float


def cartella_modelli() -> str:
    configurata = str(os.environ.get("IUSENTRA_PDF_OCR_MODEL_DIR") or "").strip()
    if configurata and Path(configurata).is_dir():
        return configurata
    if Path(CARTELLA_MODELLI_PREDEFINITA).is_dir():
        return CARTELLA_MODELLI_PREDEFINITA
    return ""


def secondo_lettore_disponibile() -> bool:
    """Vero se PDF Inspector e i suoi modelli sono installati su questo host."""
    if str(os.environ.get("IUSENTRA_OCR_SECONDO_LETTORE", "1")).strip().lower() in {"0", "false", "no", "off"}:
        return False
    with _BLOCCO:
        if _STATO["verificato"]:
            return _STATO["disponibile"]
        disponibile = False
        try:
            import pdf_inspector  # type: ignore # noqa: F401

            disponibile = bool(cartella_modelli())
        except Exception:
            disponibile = False
        _STATO.update(verificato=True, disponibile=disponibile)
        return disponibile


def azzera_verifica() -> None:
    with _BLOCCO:
        _STATO.update(verificato=False, disponibile=False)


def leggi_con_secondo_lettore(immagine: Any, *, dpi: float = DPI_SECONDO_LETTORE) -> LetturaSecondaria | None:
    """Testo della pagina letto da PDF Inspector, o None se non disponibile."""
    if not secondo_lettore_disponibile():
        return None
    inizio = time.monotonic()
    try:
        import pdf_inspector  # type: ignore

        contenitore = io.BytesIO()
        immagine.convert("RGB").save(contenitore, format="PDF", resolution=max(72.0, float(dpi) * 2))
        esito = pdf_inspector.process_pdf_with_ocr_bytes(
            contenitore.getvalue(), mode="force", dpi=float(dpi), offline=True, model_directory=cartella_modelli()
        )
        pagina = esito.pages[0]
        provenienza = getattr(pagina, "provenance", None)
        confidenza = float(getattr(provenienza, "ocr_confidence", 0.0) or 0.0)
        modello = str(getattr(provenienza, "ocr_model", "") or "pp-ocr")
        return LetturaSecondaria(str(pagina.markdown or ""), confidenza, f"pdf-inspector:{modello}", round(time.monotonic() - inizio, 3))
    except Exception:
        return None


_MARKDOWN = re.compile(r"^#{1,6}\s+|\*\*|__|^\s*[-*]\s+|`", re.MULTILINE)


def _righe_secondarie(testo: str) -> list[list[str]]:
    righe: list[list[str]] = []
    for riga in _MARKDOWN.sub("", str(testo or "")).splitlines():
        parole = riga.split()
        if parole:
            righe.append(parole)
    return righe


def _chiave(parola: str) -> str:
    return re.sub(r"[^\w]", "", parola.lower())


def _righe_tesseract(parole: list[dict[str, Any]]) -> list[list[int]]:
    righe: list[list[int]] = []
    chiave_corrente: tuple[int, int, int] | None = None
    for indice, parola in enumerate(parole):
        chiave = (int(parola.get("block") or 0), int(parola.get("par") or 0), int(parola.get("line") or 0))
        if chiave != chiave_corrente:
            righe.append([])
            chiave_corrente = chiave
        righe[-1].append(indice)
    return righe


def applica_consenso(parole: list[dict[str, Any]], secondaria: LetturaSecondaria | None) -> tuple[list[dict[str, Any]], int]:
    """Parole di Tesseract con le incerte sostituite dal secondo lettore; numero di sostituzioni."""
    if secondaria is None or secondaria.confidenza < CONFIDENZA_SECONDO_LETTORE or not parole:
        return parole, 0
    righe_secondarie = _righe_secondarie(secondaria.testo)
    if not righe_secondarie:
        return parole, 0
    testi_secondari = [" ".join(_chiave(p) for p in riga) for riga in righe_secondarie]
    nuove = [dict(parola) for parola in parole]
    sostituzioni = 0
    usate: set[int] = set()
    for indici in _righe_tesseract(parole):
        testo_riga = " ".join(_chiave(str(parole[i].get("text") or "")) for i in indici)
        if not testo_riga.strip():
            continue
        migliore, somiglianza = -1, 0.0
        for posizione, candidata in enumerate(testi_secondari):
            if posizione in usate or not candidata:
                continue
            valore = SequenceMatcher(None, testo_riga, candidata).ratio()
            if valore > somiglianza:
                migliore, somiglianza = posizione, valore
        if migliore < 0 or somiglianza < SOMIGLIANZA_RIGA:
            continue
        usate.add(migliore)
        riga_secondaria = righe_secondarie[migliore]
        allineatore = SequenceMatcher(None, [_chiave(str(parole[i].get("text") or "")) for i in indici], [_chiave(p) for p in riga_secondaria])
        for operazione, i1, i2, j1, j2 in allineatore.get_opcodes():
            if operazione != "replace" or (i2 - i1) != (j2 - j1):
                continue
            for scarto in range(i2 - i1):
                indice = indici[i1 + scarto]
                if float(parole[indice].get("conf") or 0.0) >= CONFIDENZA_CONTENDIBILE:
                    continue
                candidata = riga_secondaria[j1 + scarto]
                if not candidata or candidata == parole[indice].get("text"):
                    continue
                nuove[indice]["text"] = candidata
                nuove[indice]["conf"] = max(float(parole[indice].get("conf") or 0.0), secondaria.confidenza)
                nuove[indice]["consenso"] = True
                sostituzioni += 1
    return nuove, sostituzioni


__all__ = [
    "CONFIDENZA_CONTENDIBILE",
    "CONFIDENZA_SECONDO_LETTORE",
    "LetturaSecondaria",
    "applica_consenso",
    "azzera_verifica",
    "cartella_modelli",
    "leggi_con_secondo_lettore",
    "secondo_lettore_disponibile",
]
