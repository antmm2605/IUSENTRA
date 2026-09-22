"""Immagini, loghi e grafica vettoriale della pagina.

Le immagini vengono alleggerite prima di finire nell'HTML: un logo da 4 MB
dentro un data URI rende l'editor inutilizzabile."""

from __future__ import annotations

import base64
import io

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]

from .geometria import Riquadro
from .modello import Elemento
from .sorgente import PaginaSorgente
from .taratura import Taratura

# ===========================================================================
# 4. Immagini e grafica vettoriale
# ===========================================================================

#: lato lungo massimo di un'immagine incorporata (circa 200 dpi su A4)
LATO_MAX_IMMAGINE = 2200

#: sopra questo peso l'immagine viene ricompressa
PESO_MAX_IMMAGINE = 350 * 1024


#: peso a cui si punta per ogni immagine incorporata
PESO_OBIETTIVO = 600 * 1024

#: tentativi di riduzione: (lato lungo massimo, qualita' JPEG)
SCALINI = ((2200, 82), (1700, 76), (1300, 70), (1000, 66))


def alleggerisci_immagine(dati: bytes, estensione: str) -> tuple[bytes, str]:
    """
    Le foto a piena pagina di una scansione pesano megabyte l'una: incorporate
    tali e quali in base64 renderebbero il documento ingestibile nell'editor.
    Si scende di scalino finche' l'immagine non rientra nel peso obiettivo,
    partendo da una risoluzione da stampa: sul foglio non si vede differenza.
    """
    if Image is None or len(dati) <= PESO_MAX_IMMAGINE:
        return dati, estensione
    try:
        originale = Image.open(io.BytesIO(dati))
        originale.load()
    except Exception:
        return dati, estensione

    trasparenza = originale.mode in ("RGBA", "LA") or (
        originale.mode == "P" and "transparency" in originale.info)

    migliore, formato_migliore = dati, estensione
    for lato_max, qualita in SCALINI:
        img = originale
        lato = max(img.width, img.height)
        if lato > lato_max:
            fattore = lato_max / lato
            img = img.resize((max(1, int(img.width * fattore)),
                              max(1, int(img.height * fattore))), Image.LANCZOS)

        flusso = io.BytesIO()
        if trasparenza:
            img.convert("RGBA").save(flusso, "PNG", optimize=True)
            formato = "png"
        else:
            img.convert("RGB").save(flusso, "JPEG", quality=qualita,
                                    optimize=True, progressive=True)
            formato = "jpeg"

        prodotto = flusso.getvalue()
        if len(prodotto) < len(migliore):
            migliore, formato_migliore = prodotto, formato
        if len(prodotto) <= PESO_OBIETTIVO:
            break

    return migliore, formato_migliore


def estrai_immagini(pagina: PaginaSorgente, larghezza_pagina: float,
                    salta_pagina_intera: bool = False,
                    dpi: int = Taratura.DPI_GRAFICA) -> list[Elemento]:
    """Le immagini incorporate, riprese dalla pagina disegnata.

    PyMuPDF consegnava i byte originali dell'immagine; qui si ritaglia la zona
    dalla pagina renderizzata. Costa un po' di risoluzione sulle immagini molto
    grandi, ma restituisce quello che il lettore fa vedere davvero: maschere,
    trasparenze e ritagli sono gia' applicati, e non resta nessun formato
    esotico da riconvertire.

    `salta_pagina_intera` serve sulle pagine scansionate: li' l'unica immagine
    e' la scansione stessa e riprodurla sotto al testo riconosciuto
    raddoppierebbe il contenuto e gonfierebbe il documento.
    """
    fuori: list[Elemento] = []
    visti: set[str] = set()
    area_pagina = pagina.rect.get_area()

    for immagine in pagina.immagini:
        r = Riquadro(immagine["x0"], immagine["top"],
                     immagine["x1"], immagine["bottom"])
        if r.width < Taratura.IMMAGINE_MINIMA or r.height < Taratura.IMMAGINE_MINIMA:
            continue
        if salta_pagina_intera and r.get_area() > area_pagina * 0.8:
            continue
        impronta = f"{round(r.x0)}:{round(r.y0)}:{round(r.x1)}:{round(r.y1)}"
        if impronta in visti:
            continue
        visti.add(impronta)
        try:
            dati = pagina.png(dpi=dpi, ritaglio=r)
        except Exception:
            continue

        dati, estensione = alleggerisci_immagine(dati, "png")
        tipo = "jpeg" if estensione in ("jpg", "jpeg") else estensione
        sorgente = f"data:image/{tipo};base64," + base64.b64encode(dati).decode()
        quota = min(100.0, (r.width / larghezza_pagina) * 100)
        centrata = abs((r.x0 + r.x1) / 2 - larghezza_pagina / 2) < larghezza_pagina * 0.06
        stile_p = "text-align:center" if centrata else "text-align:left"
        fuori.append(Elemento(
            tipo="immagine",
            html=(f'<p style="{stile_p};margin:0.35em 0">'
                  f'<img src="{sorgente}" style="width:{quota:.1f}%;height:auto" '
                  f'alt="Immagine del documento"></p>'),
            top=r.y0,
            bbox=tuple(r),
        ))
    return fuori


def estrai_grafica(
    pagina: PaginaSorgente, esclusi: list[Riquadro], dpi: int = Taratura.DPI_GRAFICA,
) -> list[Elemento]:
    """
    Loghi, cornici, timbri e firme disegnati a vettori: si raggruppano i
    tracciati vicini e si rasterizza la zona, cosi' l'aspetto resta identico.

    Le zone dei campi modulo restano fuori: la loro cornice e' solo il vestito
    grafico del campo e la scritta che contengono viene gia' letta come testo,
    quindi rasterizzarle raddoppierebbe ogni etichetta.
    """
    esclusi = list(esclusi) + pagina.campi_modulo

    riquadri = []
    for d in pagina.disegni:
        r = Riquadro(d["x0"], d["top"], d["x1"], d["bottom"])
        if r.width < Taratura.GRAFICA_MINIMA or r.height < Taratura.GRAFICA_MINIMA:
            continue
        if r.width > pagina.rect.width * 0.97 and r.height > pagina.rect.height * 0.97:
            continue    # sfondo di pagina
        if any(e.intersects(r) and (e & r).get_area() > r.get_area() * 0.6 for e in esclusi):
            continue
        riquadri.append(r)

    gruppi: list[Riquadro] = []
    for r in sorted(riquadri, key=lambda x: (x.y0, x.x0)):
        for indice, g in enumerate(gruppi):
            # il margine di sei punti tiene insieme i tracciati di uno stesso
            # timbro, che nel PDF arrivano come decine di pezzi staccati
            if Riquadro(g.x0 - 6, g.y0 - 6, g.x1 + 6, g.y1 + 6).intersects(r):
                gruppi[indice] = g.unito(r)
                break
        else:
            gruppi.append(r)

    fuori: list[Elemento] = []
    for g in gruppi:
        if g.width < 14 or g.height < 14:
            continue          # filetti e righini: li rende gia' il paragrafo
        if g.height < 3.5:
            continue
        try:
            dati = pagina.png(dpi=dpi, ritaglio=g, trasparente=True)
        except Exception:
            continue
        dati, estensione = alleggerisci_immagine(dati, "png")
        sorgente = (f"data:image/{estensione};base64,"
                    + base64.b64encode(dati).decode())
        quota = min(100.0, (g.width / pagina.rect.width) * 100)
        centrata = abs((g.x0 + g.x1) / 2 - pagina.rect.width / 2) < pagina.rect.width * 0.06
        fuori.append(Elemento(
            tipo="grafica",
            html=(f'<p style="text-align:{"center" if centrata else "left"};margin:0.3em 0">'
                  f'<img src="{sorgente}" style="width:{quota:.1f}%;height:auto" '
                  f'alt="Grafica del documento"></p>'),
            top=g.y0,
            bbox=tuple(g),
        ))
    return fuori
