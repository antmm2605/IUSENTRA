"""Formato e margini della pagina, intestazioni e piedi, modalita' «esatto».

La modalita' «esatto» posiziona ogni riga alle coordinate del PDF: serve per
gli allegati da riprodurre tali e quali, non per l'editor."""

from __future__ import annotations

import re

try:  # PyMuPDF e' dichiarato in requirements.txt; senza, l'importazione fedele si spegne
    import pymupdf as fitz  # nome nuovo dalla 1.24; `import fitz` e' deprecato
except ImportError:  # pragma: no cover - ambienti senza PyMuPDF
    try:
        import fitz
    except ImportError:
        fitz = None  # type: ignore[assignment]

from .taratura import Taratura, _pt
from .modello import Elemento, Riga
from .paragrafi import _html_tratti


# ===========================================================================
# 5. Pagina, intestazioni e piedi
# ===========================================================================

def _margini(pagina: fitz.Page, righe: list[Riga], altri: list[Elemento]) -> tuple[float, float, float, float]:
    riquadri = [fitz.Rect(r.bbox) for r in righe] + [fitz.Rect(e.bbox) for e in altri]
    if not riquadri:
        return (56.7, 56.7, 56.7, 56.7)
    sx = min(r.x0 for r in riquadri)
    dx = pagina.rect.width - max(r.x1 for r in riquadri)
    su = min(r.y0 for r in riquadri)
    giu = pagina.rect.height - max(r.y1 for r in riquadri)
    # su una pagina che finisce a meta' il "margine basso" e' solo spazio
    # vuoto: in quel caso si assume simmetrico a quello alto
    if giu > su * 2.2:
        giu = su
    return (max(0.0, su), max(0.0, dx), max(0.0, giu), max(0.0, sx))


_FORMATI = {
    "A4": (595.3, 841.9), "A5": (419.5, 595.3), "A3": (841.9, 1190.6),
    "Letter": (612.0, 792.0), "Legal": (612.0, 1008.0),
}


def _formato(pagina: fitz.Page) -> tuple[str, str]:
    l, a = pagina.rect.width, pagina.rect.height
    orientamento = "orizzontale" if l > a else "verticale"
    corto, lungo = min(l, a), max(l, a)
    for nome, (fl, fa) in _FORMATI.items():
        if abs(corto - fl) < 6 and abs(lungo - fa) < 6:
            return nome, orientamento
    return f"{corto:.0f}×{lungo:.0f} pt", orientamento


def _testate_e_piedi(pagine_righe: list[list[Riga]], altezza: float) -> tuple[set[str], set[str]]:
    """Righe identiche ripetute in cima o in fondo a piu' pagine."""
    if len(pagine_righe) < 2:
        return set(), set()
    alto: dict[str, int] = {}
    basso: dict[str, int] = {}
    for righe in pagine_righe:
        for r in righe:
            testo = re.sub(r"\d+", "#", r.testo.strip())
            if not testo:
                continue
            if r.bbox[1] < altezza * Taratura.FASCIA_TESTATA:
                alto[testo] = alto.get(testo, 0) + 1
            elif r.bbox[3] > altezza * (1 - Taratura.FASCIA_TESTATA):
                basso[testo] = basso.get(testo, 0) + 1
    minimo = max(2, len(pagine_righe) // 2)
    return ({t for t, n in alto.items() if n >= minimo},
            {t for t, n in basso.items() if n >= minimo})


# ===========================================================================
# 6. Modalita' "esatto"
# ===========================================================================

def _pagina_esatta(pagina: fitz.Page, righe: list[Riga],
                   immagini: list[Elemento], grafica: list[Elemento],
                   numero: int) -> str:
    pezzi = [
        f'<section class="iu-doc-pagina iu-doc-pagina--esatta" data-pagina="{numero}" '
        f'style="width:{_pt(pagina.rect.width)}pt;height:{_pt(pagina.rect.height)}pt">'
    ]
    for e in immagini + grafica:
        x0, y0, x1, y1 = e.bbox
        sorgente = re.search(r'src="([^"]+)"', e.html)
        if not sorgente:
            continue
        pezzi.append(
            f'<img src="{sorgente.group(1)}" style="position:absolute;'
            f'left:{_pt(x0)}pt;top:{_pt(y0)}pt;width:{_pt(x1 - x0)}pt;'
            f'height:{_pt(y1 - y0)}pt" alt="">'
        )
    for r in righe:
        corpo = r.corpo
        pezzi.append(
            f'<div style="position:absolute;left:{_pt(r.bbox[0])}pt;'
            f'top:{_pt(r.bbox[1])}pt;white-space:pre;line-height:1">'
            f'{_html_tratti(r.tratti, corpo, "")}</div>'
        )
    pezzi.append("</section>")
    return "".join(pezzi)
