"""Lo spazio libero dell'ultima pagina dove scrivere l'attestazione di conformità.

L'attestazione si scrive sulla copia, di solito sotto l'ultimo testo, come fa l'avvocato
sul foglio: accanto alla firma della parte se c'è, mai sopra quello che è già scritto.
Si guarda la pagina come immagine (PDFium), perché la copia di un originale analogico è
spesso una scansione: il testo non si legge come testo, ma l'inchiostro si vede.

Il modulo non modifica il PDF: dice solo dove c'è posto, in punti PDF, o che non c'è.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Più scuro di così è inchiostro; più chiaro è carta (anche di una scansione ingrigita).
SOGLIA_INCHIOSTRO = 200
#: Una riga di pixel conta come scritta se l'inchiostro supera questa quota della fascia.
QUOTA_RIGA_SCRITTA = 0.004
MARGINE = 56.7  # 2 cm
DISTANZA_DAL_TESTO = 10.0
SCALA = 1.5


@dataclass(frozen=True)
class Spazio:
    """Angolo in alto a sinistra del blocco, in punti PDF (origine in basso a sinistra)."""

    x: float
    y_alto: float


def _inchiostro(pagina):
    import numpy as np

    immagine = pagina.render(scale=SCALA, grayscale=True).to_pil().convert("L")
    return np.asarray(immagine) < SOGLIA_INCHIOSTRO


def _margine_sinistro(inchiostro) -> float:
    """Dove comincia il testo della pagina: il blocco si allinea lì, come un capoverso."""
    import numpy as np

    righe = inchiostro.any(axis=1)
    if not righe.any():
        return MARGINE
    primi = inchiostro[righe].argmax(axis=1) / SCALA
    margine = float(np.percentile(primi, 10))
    return margine if MARGINE * 0.6 <= margine <= MARGINE * 2.5 else MARGINE


def _profilo_righe(inchiostro, x0: float, x1: float):
    """Per ogni riga di pixel (dall'alto) se nella fascia [x0, x1] c'è scritto."""
    sinistra, destra = int(max(x0, 0) * SCALA), int(min(x1 * SCALA, inchiostro.shape[1]))
    fascia = inchiostro[:, sinistra:destra]
    minimo = max(2, int(fascia.shape[1] * QUOTA_RIGA_SCRITTA))
    return fascia.sum(axis=1) > minimo


def cerca(pdf: bytes, larghezza: float, altezza: float, *, riserva_basso: float = 0.0) -> Spazio | None:
    """Dove sta un blocco largo `larghezza` e alto `altezza` nell'ultima pagina, o None.

    Il blocco si allinea al margine sinistro del testo e si mette subito sotto l'ultima riga scritta
    nella sua fascia; se lì non entra (la pagina è piena fino in fondo) si prova nel vuoto
    più alto che basta, dalla metà della pagina in giù. `riserva_basso` lascia libero il
    fondo per la firma visibile.
    """
    from pct.rendering_pdf import apri_documento

    documento = apri_documento(pdf)
    try:
        pagina = documento[len(documento) - 1]
        if int(pagina.get_rotation() or 0) % 360:
            return None
        larghezza_pagina, altezza_pagina = float(pagina.get_width()), float(pagina.get_height())
        inchiostro = _inchiostro(pagina)
        x = _margine_sinistro(inchiostro)
        if x + larghezza > larghezza_pagina - MARGINE / 2:
            x = MARGINE
        if x + larghezza > larghezza_pagina - MARGINE / 2:
            return None
        scritte = _profilo_righe(inchiostro, x - 4, x + larghezza + 4)
    finally:
        documento.close()

    righe = len(scritte)
    fondo_utile = int((altezza_pagina - max(riserva_basso, MARGINE * 0.7)) * SCALA)
    serve = int((altezza + DISTANZA_DAL_TESTO) * SCALA)
    alto_utile = int(MARGINE * SCALA)

    # Vuoti della fascia: (inizio, fine) in righe di pixel, dentro l'area utile.
    vuoti: list[tuple[int, int]] = []
    inizio = None
    for riga in range(alto_utile, min(fondo_utile, righe)):
        if not scritte[riga]:
            inizio = riga if inizio is None else inizio
        elif inizio is not None:
            vuoti.append((inizio, riga))
            inizio = None
    if inizio is not None:
        vuoti.append((inizio, min(fondo_utile, righe)))
    adatti = [(a, b) for a, b in vuoti if b - a >= serve]
    if not adatti:
        return None
    ultima_scritta = max((r for r in range(min(fondo_utile, righe)) if scritte[r]), default=alto_utile)
    dopo_il_testo = [(a, b) for a, b in adatti if a >= ultima_scritta]
    meta = righe // 2
    scelto = dopo_il_testo[0] if dopo_il_testo else next(((a, b) for a, b in adatti if b > meta), None)
    if scelto is None:
        return None
    y_pixel = scelto[0] + int(DISTANZA_DAL_TESTO * SCALA) if scelto[0] > alto_utile else scelto[0]
    return Spazio(x=x, y_alto=altezza_pagina - y_pixel / SCALA)


__all__ = ["Spazio", "cerca"]
