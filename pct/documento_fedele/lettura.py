"""Lettura degli span della pagina con tutto lo stile dichiarato dal PDF.

Carattere, corpo, grassetto, corsivo, sottolineato, barrato, colore del testo
e dello sfondo, collegamenti: quello che l'importazione «a testo» perde."""

from __future__ import annotations

import re
import statistics
from typing import Optional

try:  # PyMuPDF e' dichiarato in requirements.txt; senza, l'importazione fedele si spegne
    import pymupdf as fitz  # nome nuovo dalla 1.24; `import fitz` e' deprecato
except ImportError:  # pragma: no cover - ambienti senza PyMuPDF
    try:
        import fitz
    except ImportError:
        fitz = None  # type: ignore[assignment]

from .geometria import Riquadro
from .taratura import _colore, _colore_da_float, pila_font
from .modello import Riga, Tratto


# ===========================================================================
# 1. Lettura degli span con tutto lo stile
# ===========================================================================

#: bit dei flag di span in PyMuPDF
_APICE, _CORSIVO, _GRAZIE, _MONO, _GRASSETTO = 1, 2, 4, 8, 16


def _collegamenti(pagina: fitz.Page) -> list[tuple[Riquadro, str]]:
    fuori = []
    try:
        for l in pagina.get_links():
            uri = l.get("uri")
            if uri:
                fuori.append((Riquadro(l["from"]), uri))
    except Exception:
        pass
    return fuori


def _filetti(pagina: fitz.Page) -> list[tuple[float, float, float]]:
    """
    Filetti orizzontali sottili: (x0, x1, y). Servono a riconoscere
    sottolineature e barrature, che nel PDF non sono attributi del testo ma
    linee disegnate sopra o sotto le lettere.
    """
    fuori = []
    try:
        disegni = pagina.get_drawings()
    except Exception:
        return fuori
    for d in disegni:
        r = Riquadro(d["rect"])
        if r.height <= 2.4 and r.width > 5:
            fuori.append((r.x0, r.x1, (r.y0 + r.y1) / 2))
    return fuori


def _evidenziature(pagina: fitz.Page) -> list[tuple[Riquadro, str]]:
    """Rettangoli pieni chiari dietro il testo: sono evidenziazioni."""
    fuori = []
    try:
        disegni = pagina.get_drawings()
    except Exception:
        return fuori
    for d in disegni:
        if d.get("fill") is None or d.get("type") not in ("f", "fs"):
            continue
        colore = _colore_da_float(d.get("fill"))
        if not colore or colore.lower() in ("#ffffff", "#fefefe"):
            continue
        r = Riquadro(d["rect"])
        if 4 < r.height < 26 and r.width > 8:
            fuori.append((r, colore))
    return fuori


#: quanto un filetto puo' sporgere oltre il testo restando una decorazione,
#: in frazione della larghezza del testo stesso, e in punti per le parole corte
SPORGENZA_MASSIMA = 0.35
SPORGENZA_MINIMA_PT = 12.0


def _decorazioni(riquadro: Riquadro,
                 filetti: list[tuple[float, float, float]],
                 contenitore: Optional[Riquadro] = None) -> tuple[bool, bool]:
    """
    (sottolineato, barrato) per un riquadro.

    `contenitore` e' il riquadro su cui misurare la sporgenza del filetto:
    lavorando carattere per carattere va passato quello dello span, altrimenti
    ogni lettera vedrebbe sporgere la sottolineatura della propria parola.

    **Perche' la sporgenza e non la lunghezza.** Nel PDF una sottolineatura non
    e' un attributo del testo, e' una linea disegnata sotto le lettere: e lo
    sono anche i filetti di una tabella. Distinguerli sulla sola lunghezza
    («se e' molto piu' lungo del testo non e' una decorazione») lascia passare
    il bordo di una cella stretta, e il testo della cella esce sottolineato —
    in un atto con una tabella bordata, ogni cella. Una sottolineatura vera
    invece finisce dove finisce la parola: quello che la distingue e' quanto
    sporge oltre il testo, non quanto misura.
    """
    sottolineato = barrato = False
    esteso = contenitore if contenitore is not None else riquadro
    limite = max(esteso.width * SPORGENZA_MASSIMA, SPORGENZA_MINIMA_PT)
    for fx0, fx1, fy in filetti:
        copertura = min(fx1, riquadro.x1) - max(fx0, riquadro.x0)
        if copertura < riquadro.width * 0.6:
            continue
        sporgenza = max(0.0, esteso.x0 - fx0) + max(0.0, fx1 - esteso.x1)
        if sporgenza > limite:
            continue
        if -riquadro.height * 0.12 <= fy - riquadro.y1 <= 4.5:
            sottolineato = True
        elif riquadro.y0 + riquadro.height * 0.28 <= fy <= riquadro.y0 + riquadro.height * 0.70:
            barrato = True
    return sottolineato, barrato


def _sfondo(riquadro: Riquadro, sfondi: list[tuple[Riquadro, str]]) -> Optional[str]:
    for r, colore in sfondi:
        if r.intersects(riquadro) and (r & riquadro).get_area() > riquadro.get_area() * 0.55:
            return colore
    return None


def _indirizzo(riquadro: Riquadro, link: list[tuple[Riquadro, str]]) -> Optional[str]:
    for r, uri in link:
        if r.intersects(riquadro):
            return uri
    return None


def _tratti_da_span(
    span: dict,
    filetti: list[tuple[float, float, float]],
    sfondi: list[tuple[Riquadro, str]],
    link: list[tuple[Riquadro, str]],
    corpo_riga: float,
) -> list[Tratto]:
    """
    Uno span del PDF puo' contenere piu' stili: sottolineature, barrature ed
    evidenziazioni non sono attributi del testo ma linee e rettangoli disegnati
    sopra una PARTE delle lettere. Quando la decorazione copre solo un pezzo
    dello span, lo span viene spezzato carattere per carattere.
    """
    caratteri = span.get("chars") or []
    testo_intero = span.get("text") or "".join(c.get("c", "") for c in caratteri)
    if not testo_intero:
        return []

    flag = int(span.get("flags", 0))
    riquadro = Riquadro(span["bbox"])
    corpo = round(float(span.get("size", 11.0)), 1)
    nome = (span.get("font", "") or "").lower()

    apice = bool(flag & _APICE)
    pedice = False
    if not apice and corpo < corpo_riga * 0.78:
        pedice = span.get("origin", (0, 0))[1] > riquadro.y0 + riquadro.height * 0.72

    base = dict(
        famiglia=pila_font(span.get("font", "")),
        corpo=corpo,
        grassetto=bool(flag & _GRASSETTO) or "bold" in nome,
        corsivo=bool(flag & _CORSIVO) or "italic" in nome or "oblique" in nome,
        apice=apice,
        pedice=pedice,
        colore=_colore(span.get("color", 0)),
    )

    def _serve_spezzare() -> bool:
        for fx0, fx1, fy in filetti:
            if not (riquadro.y0 - 2 <= fy <= riquadro.y1 + 5):
                continue
            copertura = min(fx1, riquadro.x1) - max(fx0, riquadro.x0)
            if 1.0 < copertura < riquadro.width * 0.94:
                return True
        for r, _ in sfondi:
            if r.intersects(riquadro):
                comune = (r & riquadro).get_area()
                if 1.0 < comune < riquadro.get_area() * 0.94:
                    return True
        for r, _ in link:
            if r.intersects(riquadro):
                comune = (r & riquadro).get_area()
                if 1.0 < comune < riquadro.get_area() * 0.94:
                    return True
        return False

    if not caratteri or not _serve_spezzare():
        sottolineato, barrato = _decorazioni(riquadro, filetti)
        return [Tratto(
            testo=testo_intero, sottolineato=sottolineato, barrato=barrato,
            evidenziato=_sfondo(riquadro, sfondi),
            collegamento=_indirizzo(riquadro, link), **base,
        )]

    fuori: list[Tratto] = []
    for car in caratteri:
        lettera = car.get("c", "")
        if not lettera:
            continue
        cr = Riquadro(car["bbox"])
        if cr.width <= 0:
            cr = Riquadro(cr.x0, riquadro.y0, cr.x0 + 0.1, riquadro.y1)
        sotto, barra = _decorazioni(cr, filetti, riquadro)
        stato = dict(
            sottolineato=sotto, barrato=barra,
            evidenziato=_sfondo(cr, sfondi),
            collegamento=_indirizzo(cr, link),
        )
        if fuori and Tratto(testo="", **stato, **base).chiave() == fuori[-1].chiave():
            fuori[-1].testo += lettera
        else:
            fuori.append(Tratto(testo=lettera, **stato, **base))
    return fuori


def leggi_righe(pagina: fitz.Page) -> list[Riga]:
    """Tutte le righe di testo della pagina, con lo stile tratto per tratto."""
    filetti = _filetti(pagina)
    sfondi = _evidenziature(pagina)
    link = _collegamenti(pagina)

    dati = pagina.get_text("rawdict", flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)
    righe: list[Riga] = []
    for blocco in dati["blocks"]:
        if blocco.get("type") != 0:
            continue
        for linea in blocco.get("lines", []):
            span = linea.get("spans", [])
            if not span:
                continue
            corpo_riga = statistics.median([float(s.get("size", 11)) for s in span])
            tratti: list[Tratto] = []
            for uno in span:
                tratti.extend(_tratti_da_span(uno, filetti, sfondi, link, corpo_riga))
            if not tratti or not "".join(t.testo for t in tratti).strip():
                continue
            righe.append(Riga(
                tratti=tratti,
                bbox=tuple(linea["bbox"]),
                origine_y=span[0].get("origin", (0, linea["bbox"][1]))[1],
            ))
    righe.sort(key=lambda r: (round(r.bbox[1], 1), r.bbox[0]))
    return _unisci_segni_elenco(righe)


_RE_SEGNO = re.compile(r"^\s*([•·▪◦‣▶○●■□o§*+\-–—]|\(?\d{1,3}[.)]?|\(?[a-zA-Z][.)]|"
                       r"[ivxlcIVXLC]{1,6}[.)])\s*$")


def _unisci_segni_elenco(righe: list[Riga]) -> list[Riga]:
    """
    Nei PDF il pallino o il numero di un elenco e' quasi sempre un blocco di
    testo separato, messo a sinistra della voce. Senza ricucirlo, l'elenco si
    importa come una sequenza di paragrafi con dei numeri orfani in mezzo.

    Si ricuce solo quando il segno e' isolato, sta poco a sinistra della voce
    e - per i numeri nudi, che potrebbero essere una cella di tabella - se ne
    trova almeno un altro incolonnato sotto.
    """
    candidati: list[tuple[int, int]] = []          # (indice segno, indice voce)
    for i, riga in enumerate(righe):
        testo = riga.testo.strip()
        if not _RE_SEGNO.match(testo) or len(testo) > 6:
            continue
        altezza = max(1.0, riga.bbox[3] - riga.bbox[1])
        for j in range(i + 1, min(i + 4, len(righe))):
            altra = righe[j]
            if abs(altra.bbox[1] - riga.bbox[1]) > altezza * 0.6:
                continue
            stacco = altra.bbox[0] - riga.bbox[2]
            if not (0 <= stacco <= 26):
                continue
            candidati.append((i, j))
            break

    # un numero senza punto ne' parentesi puo' benissimo essere una cella di
    # tabella: lo si accetta solo se incolonnato con altri segni uguali
    def _debole(testo: str) -> bool:
        return bool(re.fullmatch(r"\(?\d{1,3}", testo.strip()))

    colonne: dict[int, int] = {}
    for i, _ in candidati:
        chiave = int(round(righe[i].bbox[0] / 4.0))
        colonne[chiave] = colonne.get(chiave, 0) + 1

    buoni = []
    for i, j in candidati:
        chiave = int(round(righe[i].bbox[0] / 4.0))
        if _debole(righe[i].testo) and colonne.get(chiave, 0) < 2:
            continue
        buoni.append((i, j))

    saltare = {j for _, j in buoni}
    unione = {i: j for i, j in buoni}

    fuori: list[Riga] = []
    for i, riga in enumerate(righe):
        if i in saltare:
            continue
        if i not in unione:
            fuori.append(riga)
            continue
        voce = righe[unione[i]]
        marcatore = Tratto(**{**voce.tratti[0].__dict__})
        marcatore.testo = f"{riga.testo.strip()} "
        fuori.append(Riga(
            tratti=[marcatore] + voce.tratti,
            bbox=(riga.bbox[0], min(riga.bbox[1], voce.bbox[1]),
                  voce.bbox[2], max(riga.bbox[3], voce.bbox[3])),
            origine_y=voce.origine_y,
        ))
    return fuori
