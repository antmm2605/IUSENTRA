"""Riconoscimento del testo (OCR) di una pagina acquisita da scanner o fotocamera.

La pagina viene preparata (raddrizzata, illuminata in modo uniforme, portata a
una densita' leggibile), letta con piu' configurazioni del motore tenendo la
migliore, e restituita come PDF con testo ricercabile insieme alla struttura
riconosciuta: titoli, capoversi, elenchi, tabelle e le zone grafiche che l'OCR
non puo' trascrivere. Nessun contenuto viene persistito: il salvataggio nel
fascicolo resta un'azione esplicita dell'avvocato.

Base normativa: la copia informatica per immagine di documento analogico
(D.Lgs. 82/2005, art. 22) resta una scansione; l'OCR aggiunge solo lo strato di
testo selezionabile e non trasforma la scansione in atto nativo digitale
(Specifiche tecniche DGSIA D.M. 44/2011, art. 15, comma 1, lett. c).
"""

from __future__ import annotations

import io
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from legal_ocr.page_layout import Blocco, analizza_pagina
from web.services.document_ocr_image import densita_pagina, prepara_pagina, regioni_grafiche
from web.services.document_tools import DocumentToolError

MAX_OCR_IMAGE_BYTES = 60 * 1024 * 1024
MAX_OCR_PIXELS = 50_000_000
OCR_LANGUAGE = "ita"
OCR_TIMEOUT_SECONDS = 180
CONFIDENZA_MINIMA_ACCETTABILE = 0.72

# Un atto puo' essere impaginato in modi molto diversi: una colonna, due
# colonne, moduli con campi sparsi. Nessuna configurazione le legge tutte bene,
# quindi la pagina viene letta con piu' impostazioni e si tiene la migliore.
CONFIGURAZIONI = (
    ("blocco unico", "--oem 1 --psm 6 -c preserve_interword_spaces=1"),
    ("colonne", "--oem 1 --psm 4 -c preserve_interword_spaces=1"),
    ("automatica", "--oem 1 --psm 3 -c preserve_interword_spaces=1"),
    ("testo sparso", "--oem 1 --psm 11 -c preserve_interword_spaces=1"),
)

_OCR_SLOTS = threading.BoundedSemaphore(max(1, int(os.environ.get("IUSENTRA_OCR_PAGE_CONCURRENCY", "2") or 2)))

# Compatibilita' con il codice che importava questi nomi dalla versione precedente.
A4_WIDTH_INCHES = 210 / 25.4
A4_HEIGHT_INCHES = 297 / 25.4
page_dpi = densita_pagina


@dataclass(frozen=True)
class OcrPageResult:
    pdf: bytes
    paragraphs: list[str]
    dpi: int
    blocks: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    engine: str = ""
    steps: tuple[str, ...] = ()

    @property
    def characters(self) -> int:
        return sum(len(re.sub(r"\s+", "", paragraph)) for paragraph in self.paragraphs)

    @property
    def tables(self) -> int:
        return sum(1 for blocco in self.blocks if blocco.get("tipo") == "tabella")


def _load_page(data: bytes, rotation: int):
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise DocumentToolError("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    if not data:
        raise DocumentToolError("La pagina da riconoscere è vuota.")
    if len(data) > MAX_OCR_IMAGE_BYTES:
        raise DocumentToolError("La pagina supera 60 MB.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in {"JPEG", "PNG", "WEBP"}:
            raise DocumentToolError("Usa una pagina JPEG, PNG o WebP.")
        if image.width * image.height > MAX_OCR_PIXELS:
            raise DocumentToolError("La pagina supera 50 megapixel.")
        image = ImageOps.exif_transpose(image).convert("RGB")
    except DocumentToolError:
        raise
    except Exception as exc:
        raise DocumentToolError("La pagina non è un'immagine leggibile.") from exc
    angle = int(rotation or 0) % 360
    if angle in {90, 180, 270}:
        # Rotazione in senso orario, come l'anteprima dell'avvocato e il PDF multipagina.
        image = image.rotate(-angle, expand=True)
    return image


_LANGUAGE_READY = False


def _tesseract():
    global _LANGUAGE_READY
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise DocumentToolError("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    if _LANGUAGE_READY:
        return pytesseract
    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        raise DocumentToolError("Il motore di riconoscimento del testo non è installato sul server.") from exc
    if OCR_LANGUAGE not in languages:
        raise DocumentToolError("Il dizionario italiano per il riconoscimento del testo non è installato sul server.")
    _LANGUAGE_READY = True
    return pytesseract


def parole_da_dati(dati: dict[str, Any]) -> list[dict[str, Any]]:
    """Parole con posizione e confidenza, dai dati grezzi del motore."""
    testi = list(dati.get("text") or [])
    parole: list[dict[str, Any]] = []
    for indice, grezzo in enumerate(testi):
        testo = str(grezzo or "").strip()
        if not testo:
            continue
        try:
            confidenza = max(0.0, min(1.0, float(dati.get("conf", ["-1"])[indice]) / 100.0))
        except (TypeError, ValueError, IndexError):
            confidenza = 0.0
        def valore(chiave: str) -> int:
            try:
                return int(dati.get(chiave, [0])[indice])
            except (TypeError, ValueError, IndexError):
                return 0
        parole.append({
            "text": testo,
            "left": valore("left"),
            "top": valore("top"),
            "width": valore("width"),
            "height": valore("height"),
            "conf": confidenza,
            "block": valore("block_num"),
            "par": valore("par_num"),
            "line": valore("line_num"),
        })
    return parole


def punteggio_lettura(parole: list[dict[str, Any]]) -> float:
    """Qualita' di una lettura: quantita' di testo pesata dalla confidenza.

    Non basta contare i caratteri, perche' una configurazione sbagliata produce
    molto testo spazzatura con confidenza bassa; e non basta la confidenza
    media, perche' una lettura che riconosce tre parole sicure sarebbe la
    migliore. Le due misure vanno moltiplicate.
    """
    if not parole:
        return 0.0
    caratteri = sum(len(parola["text"]) for parola in parole)
    confidenze = [parola["conf"] for parola in parole if parola["conf"] > 0]
    media = sum(confidenze) / len(confidenze) if confidenze else 0.0
    leggibili = sum(1 for parola in parole if parola["conf"] >= 0.60) / len(parole)
    return caratteri * (0.35 + 0.65 * media) * (0.5 + 0.5 * leggibili)


def _confidenza_media(parole: list[dict[str, Any]]) -> float:
    valori = [parola["conf"] for parola in parole if parola["conf"] > 0]
    return sum(valori) / len(valori) if valori else 0.0


def _leggi_con_configurazioni(pytesseract, immagine, dpi: int) -> tuple[str, list[dict[str, Any]], str]:
    """Legge la pagina con tutte le configurazioni e restituisce la migliore."""
    from pytesseract import Output

    migliore: tuple[float, str, list[dict[str, Any]], str] = (-1.0, "", [], "")
    errori: list[str] = []
    for etichetta, opzioni in CONFIGURAZIONI:
        configurazione = f"{opzioni} --dpi {dpi}"
        try:
            dati = pytesseract.image_to_data(
                immagine, lang=OCR_LANGUAGE, config=configurazione,
                output_type=Output.DICT, timeout=OCR_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            errori.append(f"{etichetta}: {exc}")
            continue
        parole = parole_da_dati(dati)
        punteggio = punteggio_lettura(parole)
        if punteggio > migliore[0]:
            migliore = (punteggio, etichetta, parole, configurazione)
    if migliore[0] < 0:
        raise DocumentToolError(
            "Riconoscimento del testo non completato per questa pagina."
            + (f" ({errori[0]})" if errori else "")
        )
    return migliore[1], migliore[2], migliore[3]


def _blocchi_in_paragrafi(blocchi: list[Blocco]) -> list[str]:
    """Testo lineare dei blocchi, con le tabelle rese riga per riga."""
    paragrafi: list[str] = []
    for blocco in blocchi:
        if blocco.tipo == "tabella":
            paragrafi.extend(" | ".join(cella for cella in riga) for riga in blocco.righe if any(riga))
        elif blocco.testo:
            paragrafi.append(blocco.testo)
    return paragrafi


def recognize_page(data: bytes, rotation: int = 0, *, raddrizza: bool = True) -> OcrPageResult:
    """OCR in lingua italiana di una pagina; PDF ricercabile, struttura e zone grafiche."""
    pytesseract = _tesseract()
    originale = _load_page(data, rotation)
    preparata = None
    if not _OCR_SLOTS.acquire(timeout=45):
        originale.close()
        raise DocumentToolError("Il riconoscimento del testo è impegnato da altre pagine. Riprova tra qualche istante.")
    try:
        preparata = prepara_pagina(originale, raddrizza=raddrizza)
        immagine = preparata.immagine
        etichetta, parole, configurazione = _leggi_con_configurazioni(pytesseract, immagine, preparata.dpi)
        try:
            pdf = bytes(pytesseract.image_to_pdf_or_hocr(
                immagine, lang=OCR_LANGUAGE, extension="pdf",
                config=configurazione, timeout=OCR_TIMEOUT_SECONDS,
            ) or b"")
        except RuntimeError as exc:
            raise DocumentToolError("Il riconoscimento della pagina ha richiesto troppo tempo. Migliora luce e nitidezza e riprova.") from exc
        except DocumentToolError:
            raise
        except Exception as exc:
            raise DocumentToolError("Riconoscimento del testo non completato per questa pagina.") from exc
        try:
            figure = regioni_grafiche(immagine, parole)
        except Exception:
            figure = []
    finally:
        _OCR_SLOTS.release()
        if preparata is not None and preparata.immagine is not originale:
            try:
                preparata.immagine.close()
            except Exception:
                pass
        originale.close()

    if not pdf.startswith(b"%PDF-"):
        raise DocumentToolError("Riconoscimento del testo non completato per questa pagina.")

    blocchi = analizza_pagina(parole)
    return OcrPageResult(
        pdf=pdf,
        paragraphs=_blocchi_in_paragrafi(blocchi),
        dpi=preparata.dpi,
        blocks=[blocco.come_dizionario() for blocco in blocchi],
        figures=figure,
        confidence=round(_confidenza_media(parole), 4),
        engine=f"tesseract · lettura {etichetta}",
        steps=preparata.passaggi,
    )
