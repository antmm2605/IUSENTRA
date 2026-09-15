"""Il collaudo del lettore: il software prova se stesso su pagine reali.

Le pagine del corpus (`corpus.py`) vengono renderizzate come immagini e lette
con il motore OCR reale (Tesseract, formulario compreso); il motore documenti
estrae i fatti e il collaudo li confronta con quelli attesi. Se il lettore
sbaglia — una data mancata, una data di nascita presa per udienza, una
tabella di date proposta come termini — il collaudo non passa e il pannello
delle letture lo dichiara: non è l'avvocato a dover controllare il lettore.
Il collaudo gira ogni notte nello scheduler e a ogni esecuzione dei test.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .corpus import CASI, Caso, corpo_del_caso

ROME_TZ = ZoneInfo("Europe/Rome")
VERSIONE_COLLAUDO = "2026.09.16.collaudo-lettore.v1"
FONT_CANDIDATI = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial.ttf",
)


def _font(dimensione: int):
    from PIL import ImageFont

    for percorso in FONT_CANDIDATI:
        try:
            return ImageFont.truetype(percorso, dimensione)
        except Exception:
            continue
    return ImageFont.load_default()


def genera_pagina(caso: Caso, *, larghezza: int = 1654, altezza: int = 2339, dimensione: int = 34):
    """La pagina del caso come immagine PIL (A4 a 200 dpi, testo nero su bianco)."""
    from PIL import Image, ImageDraw

    immagine = Image.new("RGB", (larghezza, altezza), "white")
    disegno = ImageDraw.Draw(immagine)
    font = _font(dimensione)
    y = 140
    for riga in caso.righe:
        disegno.text((140, y), riga, fill="black", font=font)
        y += int(dimensione * 1.7)
    return immagine


def _contesto():
    from pct.archivio_letture.collaudo import Contesto

    return Contesto(oggi=date(2026, 9, 15), anno_riferimento=2026, data_minima=date(2025, 6, 1))


def leggi_caso(caso: Caso, *, pytesseract: object | None = None, testo: str | None = None) -> dict[str, Any]:
    """Legge la pagina (o il testo dato) con motore e formulario e confronta i fatti con gli attesi."""
    from pct.archivio_letture import leggi_testo

    if testo is None:
        from legal_ocr.motore.testo import testo_da_immagine

        letto = testo_da_immagine(genera_pagina(caso), pytesseract=pytesseract)
        testo, confidenza, motore = letto.testo, letto.confidenza, letto.motore
    else:
        confidenza, motore = 1.0, "testo dato"
    fatti = leggi_testo(testo, origine="ocr", contesto=_contesto(), nome=f"{caso.id}.pdf")
    utili = {(f.categoria, f.campo, f.valore) for f in fatti if f.verifica in {"verificata", "plausibile"}}
    valori_utili = {f.valore.split("T")[0] for f in fatti if f.verifica in {"verificata", "plausibile"} and f.categoria == "data"}
    mancanti = [atteso for atteso in caso.attesi if atteso not in utili and (atteso[0], atteso[1], atteso[2].split("T")[0]) not in {(c, k, v.split("T")[0]) for c, k, v in utili}]
    indebiti = [vietato for vietato in caso.vietati if vietato in valori_utili]
    return {
        "id": caso.id, "titolo": caso.titolo, "superato": not mancanti and not indebiti, "attesi": len(caso.attesi), "trovati": len(caso.attesi) - len(mancanti),
        "mancanti": [f"{c}/{k} {v}" for c, k, v in mancanti], "indebiti": indebiti, "confidenza": round(float(confidenza), 3), "motore": motore,
        "fatti": [f"{f.categoria}/{f.campo} {f.valore} ({f.verifica})" for f in fatti][:20], "testo": testo[:600],
    }


def esegui_collaudo(*, pytesseract: object | None = None, casi: tuple[Caso, ...] = CASI) -> dict[str, Any]:
    """Tutti i casi con l'OCR reale; `superato` solo se ogni caso trova gli attesi e nulla di vietato."""
    from legal_ocr.formulario import VERSIONE_FORMULARIO
    from legal_ocr.motore import VERSIONE_MOTORE
    from pct.archivio_letture import VERSIONE_MOTORE_DOCUMENTI

    esiti = [leggi_caso(caso, pytesseract=pytesseract) for caso in casi]
    corretti = sum(1 for esito in esiti if esito["superato"])
    return {
        "versione": VERSIONE_COLLAUDO, "motore_ocr": VERSIONE_MOTORE, "formulario": VERSIONE_FORMULARIO, "motore_documenti": VERSIONE_MOTORE_DOCUMENTI,
        "eseguito_il": datetime.now(ROME_TZ).isoformat(timespec="seconds"), "superato": corretti == len(esiti) and bool(esiti), "corretti": corretti, "totali": len(esiti), "casi": esiti,
    }


def salva_esito(percorso: Path, esito: dict[str, Any]) -> None:
    percorso = Path(percorso)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(esito, ensure_ascii=False, indent=1), encoding="utf-8")


def ultimo_esito(percorso: Path) -> dict[str, Any]:
    """L'ultimo collaudo salvato, ridotto a ciò che il pannello mostra."""
    try:
        dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"eseguito": False}
    from pct.formatting import format_datetime_it

    return {
        "eseguito": True, "superato": bool(dati.get("superato")), "corretti": int(dati.get("corretti") or 0), "totali": int(dati.get("totali") or 0),
        "eseguito_il": str(dati.get("eseguito_il") or ""), "eseguito_il_it": format_datetime_it(dati.get("eseguito_il")) if dati.get("eseguito_il") else "",
        "casi_falliti": [str(c.get("titolo") or c.get("id")) for c in list(dati.get("casi") or []) if not c.get("superato")][:6],
    }


__all__ = ["CASI", "VERSIONE_COLLAUDO", "Caso", "esegui_collaudo", "genera_pagina", "leggi_caso", "salva_esito", "corpo_del_caso", "ultimo_esito"]
