"""Strutture dell'analisi dell'harness: ogni affermazione giuridica porta le norme su cui si fonda e le loro ancore."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rif:
    """Norma citata: chiave del catalogo, comma (facoltativo) e parole letterali del testo vigente che la fondano."""
    chiave: str
    ancora: str
    comma: str = ""


@dataclass
class Punto:
    testo: str
    rif: list[Rif] = field(default_factory=list)
    verificato: bool = True
    motivo: str = ""


@dataclass
class Analisi:
    regola: str                                  # identificativo della regola applicata
    materia: str
    capito: list[str] = field(default_factory=list)
    inquadramento: list[Punto] = field(default_factory=list)
    conclusione: list[Punto] = field(default_factory=list)
    competenza: list[Punto] = field(default_factory=list)
    procedibilita: list[Punto] = field(default_factory=list)
    rito: list[Punto] = field(default_factory=list)
    termini: list[Punto] = field(default_factory=list)
    cosa_fare: list[str] = field(default_factory=list)
    dubbi: list[str] = field(default_factory=list)
    bozza: str = ""
    modello: str = ""                            # scheda del catalogo dei modelli d'atto
    valore: float | None = None
    giudice: str = ""

    def sezioni(self) -> list[tuple[str, list[Punto]]]:
        return [("Inquadramento giuridico", self.inquadramento), ("Competenza e valore", self.competenza),
                ("Condizioni di procedibilità", self.procedibilita), ("Rito", self.rito), ("Termini", self.termini),
                ("Conclusione", self.conclusione)]

    def punti(self) -> list[Punto]:
        return [p for _, lista in self.sezioni() for p in lista]
