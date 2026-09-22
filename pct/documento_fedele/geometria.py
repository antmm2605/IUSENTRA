"""Il rettangolo della pagina, senza PyMuPDF.

Dentro `documento_fedele` la geometria era quella di PyMuPDF: `fitz.Rect`
compariva trentotto volte — riquadri di span, di caratteri, di celle, di
immagini, di evidenziature. Finche' resta li', il pacchetto non puo' uscire
dall'AGPL nemmeno sostituendo il lettore.

`Riquadro` ripete l'interfaccia che quel codice usava davvero — `x0`, `y0`,
`x1`, `y1`, `width`, `height`, `get_area()`, `intersects()` e l'operatore `&`
— cosi' i file che la usano cambiano solo la riga di importazione.

Le coordinate sono quelle della pagina PDF con l'origine in alto a sinistra,
la stessa convenzione di pdfplumber (`top` cresce scendendo): `y0` e' il bordo
superiore, `y1` quello inferiore. E' anche la convenzione che usava
`fitz.Rect`, quindi nessun calcolo esistente va ribaltato.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Riquadro:
    """Un rettangolo sulla pagina. Immutabile: le operazioni ne creano di nuovi."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __init__(self, *valori) -> None:
        """Accetta quattro coordinate, una sequenza, o un altro rettangolo.

        La forma con la sequenza serve perche' il codice che legge il PDF
        riceve i riquadri come tuple (`span["bbox"]`) e li passava a
        `fitz.Rect` cosi' com'erano.
        """
        if len(valori) == 1:
            unico = valori[0]
            if all(hasattr(unico, n) for n in ("x0", "y0", "x1", "y1")):
                # copre Riquadro e i rettangoli delle librerie di lettura,
                # che durante la migrazione arrivano ancora da PyMuPDF
                numeri = (unico.x0, unico.y0, unico.x1, unico.y1)
            elif isinstance(unico, Iterable):
                numeri = tuple(float(v) for v in unico)
            elif hasattr(unico, "__getitem__"):
                numeri = tuple(float(unico[i]) for i in range(4))
            else:
                raise TypeError(f"riquadro non riconosciuto: {unico!r}")
        else:
            numeri = tuple(float(v) for v in valori)

        if len(numeri) != 4:
            raise ValueError(f"un riquadro vuole quattro coordinate, non {len(numeri)}")

        object.__setattr__(self, "x0", float(numeri[0]))
        object.__setattr__(self, "y0", float(numeri[1]))
        object.__setattr__(self, "x1", float(numeri[2]))
        object.__setattr__(self, "y1", float(numeri[3]))

    # -- misure -------------------------------------------------------------

    @property
    def width(self) -> float:
        return abs(self.x1 - self.x0)

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)

    def get_area(self) -> float:
        """L'area, sempre positiva. Il nome resta quello di PyMuPDF."""
        return self.width * self.height

    @property
    def vuoto(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def normalizzato(self) -> Riquadro:
        """Lo stesso rettangolo con gli angoli nell'ordine giusto."""
        return Riquadro(
            min(self.x0, self.x1), min(self.y0, self.y1),
            max(self.x0, self.x1), max(self.y0, self.y1),
        )

    # -- rapporti fra rettangoli --------------------------------------------

    def __and__(self, altro: Riquadro | Iterable) -> Riquadro:
        """L'intersezione. Se non si toccano, un rettangolo di area zero."""
        a = self.normalizzato()
        b = Riquadro(altro).normalizzato()
        x0, y0 = max(a.x0, b.x0), max(a.y0, b.y0)
        x1, y1 = min(a.x1, b.x1), min(a.y1, b.y1)
        if x1 <= x0 or y1 <= y0:
            return Riquadro(0.0, 0.0, 0.0, 0.0)
        return Riquadro(x0, y0, x1, y1)

    def intersects(self, altro: Riquadro | Iterable) -> bool:
        """Vero se i due rettangoli hanno una parte in comune con area.

        Come in PyMuPDF, due rettangoli che si sfiorano su un bordo non si
        intersecano, e un rettangolo degenere non interseca niente.
        """
        return not (self & altro).vuoto

    def contiene(self, altro: Riquadro | Iterable) -> bool:
        a = self.normalizzato()
        b = Riquadro(altro).normalizzato()
        return a.x0 <= b.x0 and a.y0 <= b.y0 and a.x1 >= b.x1 and a.y1 >= b.y1

    def unito(self, altro: Riquadro | Iterable) -> Riquadro:
        """Il rettangolo piu' piccolo che contiene entrambi."""
        a = self.normalizzato()
        b = Riquadro(altro).normalizzato()
        return Riquadro(
            min(a.x0, b.x0), min(a.y0, b.y0), max(a.x1, b.x1), max(a.y1, b.y1)
        )

    def sovrapposizione(self, altro: Riquadro | Iterable) -> float:
        """Quanta parte di questo rettangolo sta dentro l'altro, da 0 a 1."""
        mia = self.get_area()
        if mia <= 0:
            return 0.0
        return (self & altro).get_area() / mia

    # -- comodita' ----------------------------------------------------------

    def __iter__(self):
        return iter((self.x0, self.y0, self.x1, self.y1))

    def __repr__(self) -> str:
        return f"Riquadro({self.x0:.1f}, {self.y0:.1f}, {self.x1:.1f}, {self.y1:.1f})"
