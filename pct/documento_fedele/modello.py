"""Il modello della conversione: tratto, riga, elemento, pagina, documento.

Sono dati puri, senza dipendenze da PyMuPDF: la lettura li riempie, la
composizione li usa, i test li costruiscono a mano."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional


# ===========================================================================
# Modello
# ===========================================================================

@dataclass
class Tratto:
    testo: str
    famiglia: str
    corpo: float
    grassetto: bool = False
    corsivo: bool = False
    sottolineato: bool = False
    barrato: bool = False
    apice: bool = False
    pedice: bool = False
    colore: str = "#000000"
    evidenziato: Optional[str] = None
    collegamento: Optional[str] = None

    def chiave(self) -> tuple:
        return (self.famiglia, round(self.corpo, 1), self.grassetto, self.corsivo,
                self.sottolineato, self.barrato, self.apice, self.pedice,
                self.colore, self.evidenziato, self.collegamento)


@dataclass
class Riga:
    tratti: list[Tratto] = field(default_factory=list)
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    origine_y: float = 0.0

    @property
    def testo(self) -> str:
        return "".join(t.testo for t in self.tratti)

    @property
    def corpo(self) -> float:
        corpi = [t.corpo for t in self.tratti if t.testo.strip()]
        return statistics.median(corpi) if corpi else 11.0


@dataclass
class Elemento:
    """Un pezzo di pagina, gia' pronto per l'HTML."""
    tipo: str                      # paragrafo | titolo | elenco | tabella | immagine | grafica
    html: str
    top: float
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)


@dataclass
class PaginaConvertita:
    numero: int
    larghezza: float
    altezza: float
    orientamento: str
    margini: tuple[float, float, float, float]
    html: str = ""
    da_ocr: bool = False
    elementi: int = 0
    tabelle: int = 0
    immagini: int = 0


@dataclass
class DocumentoConvertito:
    pagine: list[PaginaConvertita] = field(default_factory=list)
    html: str = ""
    formato: dict = field(default_factory=dict)
    avvisi: list[str] = field(default_factory=list)
    #: i caratteri incontrati nel documento, gia' ricondotti alle famiglie che
    #: l'editor offre in tendina: un carattere fuori tendina si presenterebbe
    #: all'avvocato come «carattere mancante»
    caratteri: list[str] = field(default_factory=list)

    @property
    def statistiche(self) -> dict:
        return {
            "pagine": len(self.pagine),
            "pagine_da_ocr": sum(1 for p in self.pagine if p.da_ocr),
            "tabelle": sum(p.tabelle for p in self.pagine),
            "immagini": sum(p.immagini for p in self.pagine),
            "elementi": sum(p.elementi for p in self.pagine),
            "caratteri": self.caratteri,
            "formato": self.formato,
            "avvisi": self.avvisi,
        }
