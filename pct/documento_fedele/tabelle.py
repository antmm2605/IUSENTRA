"""Tabelle del PDF, anche senza filetti, con celle unite e sfondi.

Una tabella riconosciuta come tale e' modificabile nell'editor; letta come
testo continuo diventa un blocco di righe che l'avvocato deve riscrivere."""

from __future__ import annotations

import statistics
from typing import Optional

try:  # PyMuPDF e' dichiarato in requirements.txt; senza, l'importazione fedele si spegne
    import pymupdf as fitz  # nome nuovo dalla 1.24; `import fitz` e' deprecato
except ImportError:  # pragma: no cover - ambienti senza PyMuPDF
    try:
        import fitz
    except ImportError:
        fitz = None  # type: ignore[assignment]

from .taratura import Taratura, _colore_da_float, _pt
from .modello import Elemento, Riga, Tratto
from .paragrafi import _allineamento, _html_tratti


# ===========================================================================
# 3. Tabelle
# ===========================================================================

def _sfondo_cella(pagina: fitz.Page, riquadro: fitz.Rect) -> Optional[str]:
    try:
        disegni = pagina.get_drawings()
    except Exception:
        return None
    for d in disegni:
        if d.get("fill") is None:
            continue
        r = fitz.Rect(d["rect"])
        if not r.intersects(riquadro):
            continue
        if (r & riquadro).get_area() < riquadro.get_area() * 0.8:
            continue
        colore = _colore_da_float(d.get("fill"))
        if colore and colore.lower() not in ("#ffffff", "#fefefe"):
            return colore
    return None


def estrai_tabelle(
    pagina: fitz.Page, righe: list[Riga],
    sinistra: Optional[float] = None, destra: Optional[float] = None,
) -> list[Elemento]:
    """Tabelle rigate e non, con celle unite, intestazioni e sfondi."""
    try:
        trovate = pagina.find_tables(strategy="lines_strict")
        if not trovate.tables:
            trovate = pagina.find_tables(strategy="text")
    except Exception:
        return []

    fuori: list[Elemento] = []
    for tabella in trovate.tables:
        riquadro = fitz.Rect(tabella.bbox)
        celle = [c for c in (tabella.cells or []) if c]
        if len(celle) < 4:
            continue

        xs = _accorpa(sorted({round(c[0], 1) for c in celle} | {round(c[2], 1) for c in celle}))
        ys = _accorpa(sorted({round(c[1], 1) for c in celle} | {round(c[3], 1) for c in celle}))
        if len(xs) < 2 or len(ys) < 2:
            continue
        n_col, n_rig = len(xs) - 1, len(ys) - 1
        griglia: list[list[Optional[dict]]] = [[None] * n_col for _ in range(n_rig)]

        for (x0, y0, x1, y1) in celle:
            c = _banda(xs, x0 + 0.5)
            r = _banda(ys, y0 + 0.5)
            if c is None or r is None or griglia[r][c] is not None:
                continue
            colspan = max(1, sum(1 for k in range(c, n_col) if xs[k + 1] <= x1 + Taratura.TOLLERANZA))
            rowspan = max(1, sum(1 for k in range(r, n_rig) if ys[k + 1] <= y1 + Taratura.TOLLERANZA))
            cella = fitz.Rect(x0, y0, x1, y1)
            griglia[r][c] = {
                "rect": cella,
                "colspan": colspan,
                "rowspan": rowspan,
                "sfondo": _sfondo_cella(pagina, cella),
                "righe": [g for g in righe if fitz.Rect(g.bbox).intersects(cella)
                          and (fitz.Rect(g.bbox) & cella).get_area()
                          > fitz.Rect(g.bbox).get_area() * 0.5],
            }
            for rr in range(r, min(n_rig, r + rowspan)):
                for cc in range(c, min(n_col, c + colspan)):
                    if (rr, cc) != (r, c) and griglia[rr][cc] is None:
                        griglia[rr][cc] = {"salta": True}

        fuori.append(Elemento(
            tipo="tabella",
            html=_html_tabella(griglia, xs, tabella, riquadro, sinistra, destra),
            top=riquadro.y0,
            bbox=tuple(riquadro),
        ))
    return fuori


def _accorpa(valori: list[float], tol: float = Taratura.TOLLERANZA) -> list[float]:
    if not valori:
        return []
    fuso = [valori[0]]
    for v in valori[1:]:
        if v - fuso[-1] <= tol:
            fuso[-1] = (fuso[-1] + v) / 2
        else:
            fuso.append(v)
    return fuso


def _banda(valori: list[float], v: float) -> Optional[int]:
    if v < valori[0] - Taratura.TOLLERANZA or v > valori[-1] + Taratura.TOLLERANZA:
        return None
    for k in range(len(valori) - 1):
        if v < valori[k + 1] - Taratura.TOLLERANZA:
            return k
    return len(valori) - 2


def _html_tabella(griglia, xs: list[float], tabella, riquadro: fitz.Rect,
                  sinistra: Optional[float] = None,
                  destra: Optional[float] = None) -> str:
    totale = max(1.0, xs[-1] - xs[0])

    # larghezza e posizione rispetto alla colonna di testo: una tabella
    # stretta e centrata deve restare stretta e centrata
    stile_tabella = []
    if sinistra is not None and destra is not None and destra > sinistra:
        colonna = destra - sinistra
        quota = max(10.0, min(100.0, (riquadro.width / colonna) * 100))
        stile_tabella.append(f"width:{quota:.1f}%")
        scarto_sx = riquadro.x0 - sinistra
        scarto_dx = destra - riquadro.x1
        if quota < 98:
            if abs(scarto_sx - scarto_dx) < colonna * 0.06:
                stile_tabella.append("margin-left:auto;margin-right:auto")
            elif scarto_sx > Taratura.RIENTRO_MINIMO:
                stile_tabella.append(f"margin-left:{_pt(scarto_sx)}pt")
    intestazione = set()
    try:
        if tabella.header and tabella.header.external is False:
            intestazione = {0}
    except Exception:
        pass

    attributo = f' style="{";".join(stile_tabella)}"' if stile_tabella else ""
    fuori = [f'<table class="iu-doc-tabella"{attributo}><tbody>']
    for indice_riga, fila in enumerate(griglia):
        fuori.append("<tr>")
        for cella in fila:
            if not cella or cella.get("salta"):
                continue
            tag = "th" if indice_riga in intestazione else "td"
            attributi = ""
            if cella["colspan"] > 1:
                attributi += f' colspan="{cella["colspan"]}"'
            if cella["rowspan"] > 1:
                attributi += f' rowspan="{cella["rowspan"]}"'

            righe_cella = cella["righe"]
            corpo = statistics.median([r.corpo for r in righe_cella]) if righe_cella else 10.0
            larghezza = (cella["rect"].width / totale) * 100
            stile = [f"width:{larghezza:.1f}%"]
            if cella["sfondo"]:
                stile.append(f"background-color:{cella['sfondo']}")
            if righe_cella:
                allinea = _allineamento(
                    righe_cella[0], cella["rect"].x0 + 2, cella["rect"].x1 - 2
                )
                if allinea != "left":
                    stile.append(f"text-align:{allinea}")

            # lo sfondo e' gia' sulla cella: toglierlo dai tratti evita di
            # ridipingere il colore dietro ogni parola
            pulite = []
            for r in righe_cella:
                tratti = []
                for t in r.tratti:
                    if cella["sfondo"] and t.evidenziato == cella["sfondo"]:
                        t = Tratto(**{**t.__dict__, "evidenziato": None})
                    tratti.append(t)
                pulite.append(Riga(tratti=tratti, bbox=r.bbox, origine_y=r.origine_y))

            contenuto = "<br>".join(
                _html_tratti(r.tratti, corpo, "") for r in pulite
            ) or "&nbsp;"
            fuori.append(f'<{tag}{attributi} style="{";".join(stile)}">{contenuto}</{tag}>')
        fuori.append("</tr>")
    fuori.append("</tbody></table>")
    return "".join(fuori)
