"""Preparazione dell'immagine prima della lettura.

Una foto scattata col telefono arriva storta, con luce disomogenea e spesso a
una risoluzione troppo bassa per il motore. Queste tre cose, non il motore,
sono la causa piu' frequente di un riconoscimento incompleto: qui la pagina
viene raddrizzata, illuminata in modo uniforme, ritagliata del bordo scuro e
portata alla densita' minima utile. Il motore legge meglio la pagina in scala
di grigi: la binarizzazione resta una seconda possibilita' per le scansioni a
basso contrasto, misurata e provata solo se la prima lettura e' povera.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errori import ErroreLettura

# Sotto questa densita' i caratteri di un atto non hanno abbastanza pixel per
# essere letti in modo affidabile; oltre i 400 dpi il guadagno sparisce e il
# tempo di calcolo cresce senza motivo.
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


@dataclass(frozen=True)
class DiagnosiZonaTesto:
    scura: bool
    chiara: bool
    basso_contrasto: bool
    sfocata: bool
    livello_sfondo: int
    escursione: int
    rapporto_bordi: float
    illuminazione_irregolare: bool = False

    @property
    def richiede_intervento(self) -> bool:
        return self.scura or self.chiara or self.basso_contrasto or self.sfocata or self.illuminazione_irregolare


def diagnostica_zona_testo(immagine) -> DiagnosiZonaTesto:
    """Misure sulla zona originale, prima dell'ingrandimento.

    Una zona uniforme non prova testo recuperabile e non attiva trattamenti.
    Le soglie guidano i tentativi: non certificano leggibilità o dati personali.
    """
    from PIL import ImageFilter, ImageStat
    grigia = immagine.convert('L')
    try:
        histogram = grigia.histogram()
        total = sum(histogram)
        def percentile(fraction):
            accumulated = 0
            for value, count in enumerate(histogram):
                accumulated += count
                if accumulated >= total * fraction:
                    return value
            return 255
        low, high = percentile(.10), percentile(.90)
        spread = high - low
        variance = ImageStat.Stat(grigia).var[0]
        edges = grigia.filter(ImageFilter.FIND_EDGES)
        try:
            inner = edges.crop((1, 1, max(2, edges.width - 1), max(2, edges.height - 1)))
            try:
                ratio = ImageStat.Stat(inner).var[0] / max(variance, 1)
            finally:
                inner.close()
        finally:
            edges.close()
        has_signal = spread >= 8 and variance >= 4
        backgrounds = []
        # Il percentile alto nei quattro quadranti misura lo sfondo, senza
        # assumere che la media della foto (ritratto incluso) sia carta bianca.
        for left, top, right, bottom in ((0, 0, .5, .5), (.5, 0, 1, .5), (0, .5, .5, 1), (.5, .5, 1, 1)):
            box = (int(left * grigia.width), int(top * grigia.height),
                   max(1, int(right * grigia.width)), max(1, int(bottom * grigia.height)))
            tile = grigia.crop(box)
            try:
                values = tile.histogram()
                threshold, count = sum(values) * .9, 0
                for level, quantity in enumerate(values):
                    count += quantity
                    if count >= threshold:
                        backgrounds.append(level)
                        break
            finally:
                tile.close()
        irregular = has_signal and len(backgrounds) == 4 and max(backgrounds) - min(backgrounds) >= 65
        return DiagnosiZonaTesto(has_signal and high < 170,
            has_signal and low > 150 and spread < 60,
            has_signal and spread < 65,
            has_signal and spread >= 30 and ratio < .12,
            high, spread, round(ratio, 5), irregular)
    finally:
        grigia.close()


def prepara_zona_testo(immagine, diagnosi: DiagnosiZonaTesto) -> PaginaPreparata:
    """Applica soltanto i trattamenti indicati dalla diagnosi della zona.

    Non ruota, non ritaglia e non ingrandisce: questi interventi hanno
    presupposti separati. Il chiamante confronta poi le letture ottenute.
    """
    from PIL import ImageFilter, ImageOps
    working = immagine.copy()
    steps = []
    try:
        if diagnosi.scura or diagnosi.illuminazione_irregolare:
            renewed = _uniforma_illuminazione(working, ImageFilter)
            working.close()
            working = renewed
            steps.append('illuminazione normalizzata: ' +
                ('sfondo disomogeneo rilevato' if diagnosi.illuminazione_irregolare else 'zona scura rilevata'))
        if diagnosi.chiara or diagnosi.basso_contrasto:
            gray = working.convert('L')
            try:
                renewed = ImageOps.autocontrast(gray, cutoff=1)
            finally:
                gray.close()
            working.close()
            working = renewed
            steps.append('contrasto normalizzato: escursione insufficiente rilevata')
        if diagnosi.sfocata:
            renewed = working.filter(ImageFilter.UnsharpMask(radius=1.4, percent=110, threshold=3))
            working.close()
            working = renewed
            steps.append('nitidezza: bordi attenuati rilevati')
        return PaginaPreparata(working, 216, 1.0, 0.0, tuple(steps))
    except Exception:
        working.close()
        raise


def passaggi_diagnosi_zona(diagnosi: DiagnosiZonaTesto):
    """Un solo intervento per lettura; nessun accumulo prima del riscontro.

    Il chiamante confronta l'esito e scarta una prova insufficiente prima
    di provare la successiva sull'immagine di riferimento preservata.
    """
    from dataclasses import replace
    clean = replace(diagnosi, scura=False, chiara=False, basso_contrasto=False,
                    sfocata=False, illuminazione_irregolare=False)
    for flags in (
        {'scura': diagnosi.scura, 'illuminazione_irregolare': diagnosi.illuminazione_irregolare},
        {'chiara': diagnosi.chiara, 'basso_contrasto': diagnosi.basso_contrasto},
        {'sfocata': diagnosi.sfocata},
    ):
        if any(flags.values()):
            yield replace(clean, **flags)


def scala_caratteri_zona(immagine) -> float:
    """Stima i glifi sulla zona di testo, senza assumere che sia una pagina A4.

    Esclude contorni grandi, rumore puntiforme e linee. La misura richiede
    almeno cinque componenti plausibili; non certifica il contenuto letto.
    """
    import statistics
    import cv2
    import numpy as np
    gray = immagine.convert('L')
    try:
        pixels = np.asarray(gray)
        # La soglia locale distingue le lettere sottili dal fondo decorato
        # della carta. Questa maschera misura soltanto, non sostituisce la foto.
        binary = cv2.adaptiveThreshold(pixels, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 21, 10)
        _, _, components, _ = cv2.connectedComponentsWithStats(binary, 8)
        heights = [int(height) for _, _, width, height, area in components[1:]
                   if 3 <= height <= min(60, immagine.height * .65)
                   and .08 <= width / height <= 2 and .1 <= area / (width * height) <= .95]
        if len(heights) < 5:
            return 1.0
        return min(4.0, max(1.0, 32 / statistics.median(heights)),
                   2400 / max(immagine.size))
    finally:
        gray.close()


def separa_sfondo_zona_testo(immagine, *, modalita: str = 'rimuovi') -> PaginaPreparata | None:
    """Seleziona solo pixel prossimi al fondo locale, su una copia.

    Il chiamante la prova dopo una lettura insufficiente. I tratti scuri
    restano invariati: non si cancellano linee nere per indovinare lettere
    sottostanti. Nessun riempimento generativo o ricostruzione del testo.
    Una zona già bianca o uniforme non attiva il trattamento.
    """
    from PIL import Image, ImageChops, ImageFilter
    if modalita not in {'rimuovi', 'schiarisci', 'scurisci'}:
        raise ValueError('Modalità sfondo non prevista')
    gray = immagine.convert('L')
    background = None
    masks = []
    try:
        histogram = gray.histogram()
        count = sum(histogram)
        midtones = sum(histogram[40:245])
        if not count or midtones / count < .10 or len([n for n in histogram if n]) < 8:
            return None
        kernel = min(31, max(3, (min(gray.size) // 8) | 1))
        try:
            import cv2
            import numpy as np
            background = Image.fromarray(cv2.dilate(np.asarray(gray), np.ones((kernel, kernel), np.uint8),
                                                    borderType=cv2.BORDER_REPLICATE))
        except ImportError:
            background = gray.filter(ImageFilter.MaxFilter(kernel))
        # Un tratto sbiadito deve restare distinguibile dal fondo: il
        # margine è relativo alla carta locale, non alla pagina intera.
        difference = ImageChops.subtract(background, gray)
        masks.append(difference)
        proximity = difference.point([255 if value <= 8 else 0 for value in range(256)])
        masks.append(proximity)
        eligible = gray.point([255 if 96 < value < 245 else 0 for value in range(256)])
        masks.append(eligible)
        selection = ImageChops.multiply(proximity, eligible)
        masks.append(selection)
        selected = selection.histogram()[255]
        if selected / count < .01:
            return None
        working = gray.copy()
        if modalita == 'rimuovi':
            working.paste(255, mask=selection)
        else:
            delta = 24 if modalita == 'schiarisci' else -24
            toned = gray.point([max(97, min(255, value + delta)) for value in range(256)])
            try:
                working.paste(toned, mask=selection)
            finally:
                toned.close()
        label = {'rimuovi': 'separazione sfondo', 'schiarisci': 'schiarimento sfondo',
                 'scurisci': 'scurimento sfondo'}[modalita]
        return PaginaPreparata(working, 216, 1.0, 0.0,
            (f'{label}: {selected} pixel selezionati per luminanza locale; tratti scuri preservati',))
    finally:
        for mask in masks:
            mask.close()
        if background is not None:
            background.close()
        gray.close()


def densita_pagina(larghezza: int, altezza: int) -> int:
    """Densita' che fa rientrare la pagina in un A4 nel suo orientamento."""
    lato_lungo, lato_corto = max(larghezza, altezza), min(larghezza, altezza)
    dpi = max(lato_lungo / A4_ALTEZZA_POLLICI, lato_corto / A4_LARGHEZZA_POLLICI)
    return int(min(600, max(72, round(dpi))))


def orienta_testo(immagine, *, pytesseract, lingua: str = "ita"):
    """Orientamento misurato sul testo, senza modificare la fonte.

    OSD debole sulle carte fotografiche non costituisce prova. In quel caso
    confrontiamo quattro miniature con lo stesso motore e punteggio condivisi.
    La rotazione viene adottata solo con un vantaggio netto sulla posizione 0.
    """
    from .lettura import _leggi, testo_per_righe
    from .punteggio import punteggio_lettura

    if not callable(getattr(pytesseract, "image_to_data", None)):
        return immagine, 0
    try:
        osd = pytesseract.image_to_osd(immagine, output_type="dict", timeout=8)
        if float(osd.get("orientation_conf", 0)) >= 15:
            angle = (-int(osd.get("rotate", 0))) % 360
            return (immagine.rotate(angle, expand=True), angle) if angle else (immagine, 0)
    except Exception:
        pass
    sample = immagine.copy()
    sample.thumbnail((1600, 1600))
    scores = {}
    try:
        for angle in (0, 90, 180, 270):
            candidate = sample.rotate(angle, expand=True) if angle else sample
            try:
                words, _ = _leggi(pytesseract, candidate, lingua=lingua,
                    opzioni="--oem 1 --psm 11", dpi=150, timeout=8)
                scores[angle] = punteggio_lettura(words, testo_per_righe(words))
            except Exception:
                scores[angle] = 0
            finally:
                if candidate is not sample:
                    candidate.close()
    finally:
        sample.close()
    best = max(scores, key=scores.get)
    if best and scores[best] > max(50, scores[0] * 1.25):
        return immagine.rotate(best, expand=True), best
    return immagine, 0


def _pillow():
    try:
        from PIL import Image, ImageFilter, ImageOps
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise ErroreLettura("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
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
    from PIL import ImageChops

    grigia = immagine.convert("L")
    raggio = max(8, round(min(grigia.width, grigia.height) / 24))
    sfondo = grigia.filter(ImageFilter.GaussianBlur(radius=raggio))
    chiara = ImageChops.invert(ImageChops.subtract(sfondo, grigia, scale=1.0, offset=0))
    return chiara.convert("L") if chiara.mode != "L" else chiara


def ritaglia_bordo(immagine):
    """Toglie il bordo scuro o il piano attorno al foglio fotografato.

    Un foglio fotografato su una scrivania ha attorno un margine che non e'
    pagina: contiene ombre e oggetti che il motore prova a leggere. Si ritaglia
    solo se il contenuto occupa una parte chiara e centrale, mai se il ritaglio
    porterebbe via la pagina stessa.
    """
    Image, _, ImageOps = _pillow()
    from PIL import ImageChops

    try:
        grigia = ImageOps.grayscale(immagine)
        # I margini bianchi appartengono al foglio: ritagliarli cambia
        # l'impaginazione e ingrandisce artificialmente il testo esportato.
        # La rimozione del bordo è riservata a uno sfondo esterno scuro.
        from PIL import ImageStat
        bordo = max(1, min(grigia.size) // 100)
        angoli = [(0, 0, bordo, bordo), (grigia.width - bordo, 0, grigia.width, bordo),
                  (0, grigia.height - bordo, bordo, grigia.height),
                  (grigia.width - bordo, grigia.height - bordo, grigia.width, grigia.height)]
        if all(ImageStat.Stat(grigia.crop(angolo)).mean[0] >= 245 for angolo in angoli):
            return immagine, False
        bianco = Image.new("L", grigia.size, 255)
        differenza = ImageChops.difference(grigia, bianco)
        maschera = differenza.point(lambda pixel: 255 if pixel > 10 else 0)
        riquadro = maschera.getbbox()
    except Exception:
        return immagine, False
    if not riquadro:
        return immagine, False
    sinistra, alto, destra, basso = riquadro
    larghezza_contenuto = destra - sinistra
    altezza_contenuto = basso - alto
    toglie_margine = larghezza_contenuto < grigia.width * 0.9 or altezza_contenuto < grigia.height * 0.9
    conserva_pagina = larghezza_contenuto >= grigia.width * 0.35 and altezza_contenuto >= grigia.height * 0.35
    if not (toglie_margine and conserva_pagina):
        return immagine, False
    margine = max(8, int(min(grigia.size) * 0.015))
    return immagine.crop((max(0, sinistra - margine), max(0, alto - margine), min(grigia.width, destra + margine), min(grigia.height, basso + margine))), True


def prepara_pagina(immagine, *, raddrizza: bool = True, ritaglia: bool = True) -> PaginaPreparata:
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
            lavoro = lavoro.rotate(rotazione, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255) if lavoro.mode == "RGB" else 255)
            passaggi.append(f"raddrizzamento {rotazione:+.1f}°")

    if ritaglia:
        lavoro, ritagliata = ritaglia_bordo(lavoro)
        if ritagliata:
            passaggi.append("bordo ritagliato")

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


def soglia_otsu(immagine) -> int:
    """Soglia di binarizzazione che separa meglio inchiostro e carta (Otsu)."""
    _, _, ImageOps = _pillow()
    grigia = ImageOps.grayscale(immagine)
    istogramma = grigia.histogram()
    totale = sum(istogramma)
    if totale <= 0:
        return 128
    somma_pesata = sum(indice * conteggio for indice, conteggio in enumerate(istogramma))
    peso_sfondo = 0
    somma_sfondo = 0
    migliore = 128
    varianza_migliore = -1.0
    for soglia, conteggio in enumerate(istogramma):
        peso_sfondo += conteggio
        if peso_sfondo <= 0:
            continue
        peso_testo = totale - peso_sfondo
        if peso_testo <= 0:
            break
        somma_sfondo += soglia * conteggio
        media_sfondo = somma_sfondo / peso_sfondo
        media_testo = (somma_pesata - somma_sfondo) / peso_testo
        varianza = peso_sfondo * peso_testo * (media_sfondo - media_testo) ** 2
        if varianza > varianza_migliore:
            varianza_migliore = varianza
            migliore = soglia
    return migliore


def varianti_contrasto(immagine) -> list[tuple[str, object]]:
    """Versioni binarizzate della pagina per le scansioni a basso contrasto.

    Si provano solo quando la lettura in scala di grigi e' povera: sulla
    maggior parte delle pagine la binarizzazione perde qualcosa, sulle copie
    sbiadite e' l'unico modo per far emergere il testo.
    """
    try:
        _, _, ImageOps = _pillow()
        grigia = ImageOps.grayscale(immagine)
        otsu = soglia_otsu(grigia)
        soglie = sorted({max(48, min(210, round(otsu * 0.45))), max(48, min(210, round(otsu * 0.70))), max(48, min(210, otsu))})
        return [
            (f"contrasto-{soglia}", grigia.point(lambda pixel, limite=soglia: 0 if pixel < limite else 255, mode="1"))
            for soglia in soglie
        ]
    except Exception:
        return []


def regioni_grafiche(immagine, parole: list[dict], *, soglia_area: float = 0.012) -> list[dict]:
    """Zone con inchiostro ma senza testo riconosciuto: firme, timbri, grafici.

    Servono all'avvocato per sapere che nella pagina c'e' qualcosa che l'OCR non
    puo' trascrivere, invece di lasciargli credere che il testo sia tutto.
    """
    Image, _, ImageOps = _pillow()
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


def apri_immagine(data: bytes, rotazione: int = 0):
    """Apre una pagina JPEG/PNG/WebP/TIFF e la ruota in senso orario di 90/180/270 gradi."""
    Image, _, ImageOps = _pillow()
    import io

    if not data:
        raise ErroreLettura("La pagina da riconoscere è vuota.")
    try:
        immagine = Image.open(io.BytesIO(data))
        if immagine.format not in {"JPEG", "PNG", "WEBP", "TIFF", "BMP", "GIF"}:
            raise ErroreLettura("Usa una pagina JPEG, PNG, WebP o TIFF.")
        immagine = ImageOps.exif_transpose(immagine).convert("RGB")
    except ErroreLettura:
        raise
    except Exception as exc:
        raise ErroreLettura("La pagina non è un'immagine leggibile.") from exc
    angolo = int(rotazione or 0) % 360
    if angolo in {90, 180, 270}:
        immagine = immagine.rotate(-angolo, expand=True)
    return immagine


__all__ = [
    "A4_ALTEZZA_POLLICI",
    "A4_LARGHEZZA_POLLICI",
    "ANGOLO_MASSIMO_RADDRIZZAMENTO",
    "DPI_MASSIMO",
    "DPI_MINIMO",
    "LATO_MASSIMO",
    "PaginaPreparata",
    "apri_immagine",
    "densita_pagina",
    "inclinazione_stimata",
    "prepara_pagina",
    "regioni_grafiche",
    "ritaglia_bordo",
    "soglia_otsu",
    "varianti_contrasto",
]
