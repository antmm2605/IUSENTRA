"""I campi firma di un modulo PDF, presi dai widget AcroForm.

Un modulo ministeriale porta spesso **piu' impaginazioni sovrapposte** — l'autocertificazione per il contributo unificato ne ha sette, una per numero
di righe del nucleo familiare — e i widget delle varianti inutilizzate hanno
il bit Hidden acceso. Firmare su un widget nascosto significa mettere la
firma dove nessuno la vedra': si usa solo quello visibile."""

from __future__ import annotations

import re
from typing import Optional

try:  # PyMuPDF e' dichiarato in requirements.txt
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    try:
        import fitz
    except ImportError:
        fitz = None  # type: ignore[assignment]

from .taratura import ALTEZZA_MAX_PT, APPOGGIO_Y, ARIA_DALL_ETICHETTA, BIT_NASCOSTO, ETICHETTE, MARGINE_X, QUOTA_SOPRA_IL_RIGO, RE_FIRMA, SFORAMENTO_SUPERIORE
from .modello import CampoFirma


# ---------------------------------------------------------------------------
# Individuazione dei campi
# ---------------------------------------------------------------------------

def _nascosto(doc: fitz.Document, widget) -> bool:
    try:
        tipo, valore = doc.xref_get_key(widget.xref, "F")
    except Exception:
        return False
    if tipo != "int":
        return False
    return bool(int(valore) & BIT_NASCOSTO)


def _etichetta(nome: str) -> str:
    chiave = nome.strip().lower()
    if chiave in ETICHETTE:
        return ETICHETTE[chiave]
    pulito = re.sub(r"[_\-]+", " ", nome).strip()
    return pulito[:1].upper() + pulito[1:]


def _ostacoli(pagina: fitz.Page, rect: fitz.Rect) -> tuple[float, float]:
    """
    Quanto spazio c'e' davvero attorno al rigo: restituisce (limite alto,
    limite basso) tenendo conto del testo gia' stampato nella stessa colonna.
    Serve a non coprire diciture come "FIRMA" o "IL DICHIARANTE".
    """
    alto = rect.y0 - ALTEZZA_MAX_PT
    basso = rect.y1 + ALTEZZA_MAX_PT
    try:
        parole = pagina.get_text("words")
    except Exception:
        return alto, basso

    centro_campo = (rect.y0 + rect.y1) / 2

    for x0, y0, x1, y1, *_ in parole:
        if x1 < rect.x0 - 2 or x0 > rect.x1 + 2:      # altra colonna
            continue
        centro = (y0 + y1) / 2
        # Le diciture ("FIRMA", "IL DICHIARANTE") spesso sconfinano dentro il
        # riquadro del campo: conta la posizione del loro centro, non il bordo.
        if centro < centro_campo and y1 < rect.y1 - 2:
            alto = max(alto, y1 + ARIA_DALL_ETICHETTA)
        elif centro > centro_campo and y0 > rect.y1 - 2:
            basso = min(basso, y0 - ARIA_DALL_ETICHETTA)
    return alto, basso


def zona_firma(rect: fitz.Rect, pagina: Optional[fitz.Page] = None) -> fitz.Rect:
    """
    Riquadro in cui viene disegnata la firma: largo quanto il campo (meno i
    margini), appoggiato sul rigo e libero di salire sopra e scendere sotto
    quanto basta, senza invadere il testo prestampato.
    """
    rigo = rect.y1 - APPOGGIO_Y
    limite_alto = rect.y0 - ALTEZZA_MAX_PT
    limite_basso = rect.y1 + ALTEZZA_MAX_PT
    if pagina is not None:
        limite_alto, limite_basso = _ostacoli(pagina, rect)

    sopra = min(
        ALTEZZA_MAX_PT * QUOTA_SOPRA_IL_RIGO,
        max(rect.height, rect.height * SFORAMENTO_SUPERIORE),
        max(4.0, rigo - limite_alto),
    )
    sotto = min(sopra * (1 - QUOTA_SOPRA_IL_RIGO) / QUOTA_SOPRA_IL_RIGO,
                max(0.0, limite_basso - rigo))
    return fitz.Rect(rect.x0 + MARGINE_X, rigo - sopra, rect.x1 - MARGINE_X, rigo + sotto)


def campi_firmabili(percorso: str, *, solo_visibili: bool = True) -> list[CampoFirma]:
    """Campi firma del modulo, nella variante di impaginazione attiva."""
    doc = fitz.open(percorso)
    try:
        fuori: list[CampoFirma] = []
        visti: set[str] = set()
        for numero, pagina in enumerate(doc):
            for w in pagina.widgets():
                nome = (w.field_name or "").strip()
                if not nome or not RE_FIRMA.search(nome):
                    continue
                if solo_visibili and _nascosto(doc, w):
                    continue
                if nome in visti:
                    continue
                visti.add(nome)
                r = fitz.Rect(w.rect)
                fuori.append(
                    CampoFirma(
                        nome=nome,
                        etichetta=_etichetta(nome),
                        pagina=numero,
                        rect=(r.x0, r.y0, r.x1, r.y1),
                        zona=tuple(zona_firma(r, pagina)),
                        larghezza_pagina=pagina.rect.width,
                        altezza_pagina=pagina.rect.height,
                    )
                )
        return fuori
    finally:
        doc.close()


def campi_testo(percorso: str, *, solo_visibili: bool = True) -> list[dict]:
    """Campi compilabili non-firma, utili al portale clienti."""
    doc = fitz.open(percorso)
    try:
        fuori, visti = [], set()
        for numero, pagina in enumerate(doc):
            for w in pagina.widgets():
                nome = (w.field_name or "").strip()
                if not nome or RE_FIRMA.search(nome):
                    continue
                if w.field_type_string != "Text":
                    continue
                if solo_visibili and _nascosto(doc, w):
                    continue
                if nome in visti:
                    continue
                visti.add(nome)
                r = fitz.Rect(w.rect)
                fuori.append({
                    "nome": nome,
                    "etichetta": _etichetta(nome),
                    "pagina": numero,
                    "rect": (r.x0, r.y0, r.x1, r.y1),
                    "valore": w.field_value or "",
                })
        return fuori
    finally:
        doc.close()
