"""Preparazione dell'immagine prima del riconoscimento del testo.

Una foto scattata col telefono arriva storta, con luce disomogenea e spesso a
una risoluzione troppo bassa per il motore OCR. Queste tre cose, non il motore,
sono la causa piu' frequente di un riconoscimento incompleto: qui la pagina
viene raddrizzata, illuminata in modo uniforme e portata alla densita' minima
utile, prima che il testo venga letto.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from web.services.document_tools import DocumentToolError

# Sotto questa densita' i caratteri di un atto non hanno abbastanza pixel per
# essere letti in modo affidabile: la pagina viene ingrandita fino a questo
# valore. Oltre i 400 dpi il guadagno sparisce e il tempo di calcolo esplode.
DPI_MINIMO = 300
DPI_MASSIMO = 400
LATO_MASSIMO = 5000
ANGOLO_MASSIMO_RADDRIZZAMENTO = 12.0

A4_LARGHEZZA_POLLICI = 210 / 25.4
A4_ALTEZZA_POLLICI = 297 / 25.4


@dataclass(frozen=True)
class PaginaPreparata:
    immagine: object
    dpi: int
    scala: float
    rotazione_gradi: float
    passaggi: tuple[str, ...]


def densita_pagina(larghezza: int, altezza: int) -> int:
    """Densita' che fa rientrare la pagina in un A4 nel suo orientamento."""
    lato_lungo, lato_corto = max(larghezza, altezza), min(larghezza, altezza)
    dpi = max(lato_lungo / A4_ALTEZZA_POLLICI, lato_corto / A4_LARGHEZZA_POLLICI)
    return int(min(600, max(72, round(dpi))))


def _pillow():
    try:
        from PIL import Image, ImageFilter, ImageOps  # noqa: F401
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise DocumentToolError("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    from PIL import Image, ImageFilter, ImageOps

    return Image, ImageFilter, ImageOps


def inclinazione_stimata(immagine) -> float:
    """Inclinazione della pagina in gradi, dal profilo di proiezione delle righe.

    Si prova a ruotare di poco in entrambi i sensi e si tiene l'angolo che rende
    piu' netta l'alternanza fra righe di testo e spazi bianchi: e' il criterio
    classico del profilo di proiezione, senza dipendenze esterne.
    """
    Image, _, ImageOps = _pillow()
    piccola = ImageOps.grayscale(immagine)
    larghezza = 800
    if piccola.width > larghezza:
        piccola = piccola.resize((larghezza, max(1, round(piccola.height * larghezza / piccola.width))), Image.BILINEAR)
    piccola = ImageOps.autocontrast(piccola, cutoff=2)

    def nitidezza(angolo: float) -> float:
        prova = piccola.rotate(angolo, resample=Image.BILINEAR, fillcolor=255) if angolo else piccola
        pixel = prova.load()
        somme = []
        for y in range(prova.height):
            scuri = 0
            for x in range(0, prova.width, 2):
                if pixel[x, y] < 160:
                    scuri += 1
            somme.append(scuri)
        if len(somme) < 3:
            return 0.0
        return sum((somme[i + 1] - somme[i]) ** 2 for i in range(len(somme) - 1))

    migliore, punteggio = 0.0, nitidezza(0.0)
    for angolo in (-8.0, -6.0, -4.0, -3.0, -2.0, -1.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0):
        valore = nitidezza(angolo)
        if valore > punteggio:
            migliore, punteggio = angolo, valore
    if abs(migliore) > ANGOLO_MASSIMO_RADDRIZZAMENTO:
        return 0.0
    return migliore


def _uniforma_illuminazione(immagine, ImageFilter):
    """Divide la pagina per il proprio sfondo: l'ombra sparisce, il testo resta."""
    from PIL import Image, ImageChops

    grigia = immagine.convert("L")
    raggio = max(8, round(min(grigia.width, grigia.height) / 24))
    sfondo = grigia.filter(ImageFilter.GaussianBlur(radius=raggio))
    chiara = ImageChops.invert(ImageChops.subtract(sfondo, grigia, scale=1.0, offset=0))
    return chiara.convert("L") if chiara.mode != "L" else chiara


def prepara_pagina(immagine, *, raddrizza: bool = True) -> PaginaPreparata:
    """Raddrizza, uniforma la luce e porta la pagina a una densita' leggibile."""
    Image, ImageFilter, ImageOps = _pillow()
    passaggi: list[str] = []
    lavoro = immagine

    rotazione = 0.0
    if raddrizza:
        try:
            rotazione = inclinazione_stimata(lavoro)
        except Exception:
            rotazione = 0.0
        if abs(rotazione) >= 0.5:
            lavoro = lavoro.rotate(rotazione, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
            passaggi.append(f"raddrizzamento {rotazione:+.1f}°")

    try:
        lavoro = _uniforma_illuminazione(lavoro, ImageFilter)
        passaggi.append("illuminazione uniformata")
    except Exception:
        lavoro = lavoro.convert("L")

    lavoro = ImageOps.autocontrast(lavoro, cutoff=1)
    passaggi.append("contrasto normalizzato")

    dpi_attuale = densita_pagina(lavoro.width, lavoro.height)
    scala = 1.0
    if dpi_attuale < DPI_MINIMO:
        scala = min(DPI_MINIMO / dpi_attuale, LATO_MASSIMO / max(lavoro.width, lavoro.height))
        if scala > 1.02:
            lavoro = lavoro.resize((round(lavoro.width * scala), round(lavoro.height * scala)), Image.LANCZOS)
            passaggi.append(f"ingrandimento ×{scala:.2f}")
        else:
            scala = 1.0

    lavoro = lavoro.filter(ImageFilter.UnsharpMask(radius=1.4, percent=110, threshold=3))
    passaggi.append("nitidezza")

    dpi = min(DPI_MASSIMO, max(DPI_MINIMO, densita_pagina(lavoro.width, lavoro.height)))
    return PaginaPreparata(immagine=lavoro, dpi=dpi, scala=scala, rotazione_gradi=rotazione, passaggi=tuple(passaggi))


def regioni_grafiche(immagine, parole: list[dict], *, soglia_area: float = 0.012) -> list[dict]:
    """Zone con inchiostro ma senza testo riconosciuto: firme, timbri, grafici.

    Servono all'avvocato per sapere che nella pagina c'e' qualcosa che l'OCR non
    puo' trascrivere, invece di lasciargli credere che il testo sia tutto.
    """
    Image, ImageFilter, ImageOps = _pillow()
    grigia = ImageOps.grayscale(immagine)
    passo = max(1, round(max(grigia.width, grigia.height) / 200))
    colonne = max(1, grigia.width // passo)
    righe_griglia = max(1, grigia.height // passo)
    piccola = grigia.resize((colonne, righe_griglia), Image.BILINEAR)
    pixel = piccola.load()

    coperta = [[False] * colonne for _ in range(righe_griglia)]
    for parola in parole:
        x0 = max(0, int(float(parola.get("left", 0)) / passo) - 1)
        y0 = max(0, int(float(parola.get("top", 0)) / passo) - 1)
        x1 = min(colonne - 1, int((float(parola.get("left", 0)) + float(parola.get("width", 0))) / passo) + 1)
        y1 = min(righe_griglia - 1, int((float(parola.get("top", 0)) + float(parola.get("height", 0))) / passo) + 1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                coperta[y][x] = True

    inchiostro = [[(pixel[x, y] < 170) and not coperta[y][x] for x in range(colonne)] for y in range(righe_griglia)]
    visitati = [[False] * colonne for _ in range(righe_griglia)]
    regioni: list[dict] = []
    area_minima = soglia_area * colonne * righe_griglia
    for y0 in range(righe_griglia):
        for x0 in range(colonne):
            if not inchiostro[y0][x0] or visitati[y0][x0]:
                continue
            pila = [(x0, y0)]
            visitati[y0][x0] = True
            punti = []
            while pila:
                x, y = pila.pop()
                punti.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < colonne and 0 <= ny < righe_griglia and inchiostro[ny][nx] and not visitati[ny][nx]:
                        visitati[ny][nx] = True
                        pila.append((nx, ny))
            if len(punti) < area_minima:
                continue
            xs = [punto[0] for punto in punti]
            ys = [punto[1] for punto in punti]
            regioni.append({
                "riquadro": [xs[0] * passo, min(ys) * passo, (max(xs) + 1) * passo, (max(ys) + 1) * passo],
                "copertura": round(len(punti) / (colonne * righe_griglia), 4),
            })
    regioni.sort(key=lambda regione: regione["riquadro"][1])
    return regioni[:8]
