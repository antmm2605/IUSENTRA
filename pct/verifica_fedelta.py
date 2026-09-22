"""Quanto si e' spostato il documento dopo essere passato per l'editor.

Un PDF importato nell'editor atti, modificato e riesportato non e' piu' lo
stesso file: e' un documento ricostruito. La domanda dell'avvocato e' sempre
la stessa — "e' rimasto come prima?" — e finora la risposta era un'occhiata.

Qui la risposta e' un numero. Ogni parola del documento di partenza viene
cercata in quello di arrivo e si misura di quanto si e' spostata, in
millimetri. Il verdetto e' per pagina, cosi' l'avvocato vede dove guardare
invece di sfogliare tutto.

La misura serve in due momenti: prima di sostituire un documento nel
fascicolo, e in prova, per dire se una modifica al convertitore ha
migliorato o peggiorato l'importazione.

Solo pdfplumber (MIT). Nessuna libreria AGPL.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

#: Sotto questo scarto la parola e' dove era: mezzo millimetro non si vede
#: nemmeno stampando.
SCARTO_TOLLERATO_MM = 1.0

#: Percentuale di parole entro la tolleranza sopra la quale il documento si
#: puo' sostituire senza farlo guardare a nessuno.
SOGLIA_BUONA = 95.0

#: Sotto questa percentuale il documento e' cambiato abbastanza da doverlo
#: rivedere pagina per pagina prima di depositarlo.
SOGLIA_SUFFICIENTE = 80.0

PUNTI_IN_MM = 25.4 / 72


class VerificaFedeltaError(ValueError):
    """Uno dei due PDF non si apre, o non ha parole da confrontare."""


@dataclass
class EsitoPagina:
    """Com'e' andata una pagina."""

    numero: int
    parole_attese: int = 0
    parole_ritrovate: int = 0
    scarto_x_mediano: float = 0.0
    scarto_y_mediano: float = 0.0
    scarto_x_massimo: float = 0.0
    scarto_y_massimo: float = 0.0
    entro_tolleranza: float = 0.0

    @property
    def parole_perse(self) -> int:
        return self.parole_attese - self.parole_ritrovate

    @property
    def verdetto(self) -> str:
        if self.parole_attese == 0:
            return "vuota"
        if self.parole_perse:
            return "da rivedere"
        if self.entro_tolleranza >= SOGLIA_BUONA:
            return "fedele"
        if self.entro_tolleranza >= SOGLIA_SUFFICIENTE:
            return "scostata"
        return "da rivedere"


@dataclass
class EsitoDocumento:
    """Il quadro d'insieme, piu' il dettaglio per pagina."""

    pagine: list[EsitoPagina] = field(default_factory=list)
    avvisi: list[str] = field(default_factory=list)

    @property
    def parole_attese(self) -> int:
        return sum(p.parole_attese for p in self.pagine)

    @property
    def parole_ritrovate(self) -> int:
        return sum(p.parole_ritrovate for p in self.pagine)

    @property
    def parole_perse_totali(self) -> int:
        return self.parole_attese - self.parole_ritrovate

    @property
    def entro_tolleranza(self) -> float:
        attese = self.parole_attese
        if not attese:
            return 0.0
        pesate = sum(p.entro_tolleranza * p.parole_attese for p in self.pagine)
        return pesate / attese

    @property
    def da_rivedere(self) -> list[int]:
        return [p.numero for p in self.pagine if p.verdetto == "da rivedere"]

    @property
    def verdetto(self) -> str:
        if not self.pagine:
            return "vuoto"
        if self.da_rivedere:
            return "da rivedere"
        if any(p.verdetto == "scostata" for p in self.pagine):
            return "scostato"
        return "fedele"

    def sommario(self) -> str:
        """Una riga da mostrare all'avvocato."""
        if not self.pagine:
            return "nessuna pagina da confrontare"
        persi = self.parole_attese - self.parole_ritrovate
        pezzi = [
            f"{self.entro_tolleranza:.1f}% delle parole entro "
            f"{SCARTO_TOLLERATO_MM:g} mm"
        ]
        if persi:
            pezzi.append(f"{persi} parole non ritrovate")
        if self.da_rivedere:
            elenco = ", ".join(str(n) for n in self.da_rivedere[:6])
            resto = "..." if len(self.da_rivedere) > 6 else ""
            pezzi.append(f"da rivedere: pagina {elenco}{resto}")
        return "; ".join(pezzi)


def _parole(percorso: Path) -> list[list[tuple[str, float, float]]]:
    """Le parole di ogni pagina, con la posizione dell'angolo in alto a sinistra."""
    try:
        pdf = pdfplumber.open(str(percorso))
    except Exception as errore:
        raise VerificaFedeltaError(f"PDF illeggibile: {percorso.name}") from errore
    with pdf:
        return [
            [
                (str(w["text"]), float(w["x0"]), float(w["top"]))
                for w in pagina.extract_words()
            ]
            for pagina in pdf.pages
        ]


def _confronta_pagina(numero: int, attese, trovate) -> EsitoPagina:
    esito = EsitoPagina(numero=numero, parole_attese=len(attese))
    if not attese:
        return esito

    indice: dict[str, list[tuple[float, float]]] = {}
    for testo, x, y in trovate:
        indice.setdefault(testo, []).append((x, y))

    scarti_x: list[float] = []
    scarti_y: list[float] = []
    dentro = 0
    for testo, x, y in attese:
        candidate = indice.get(testo)
        if not candidate:
            continue
        cx, cy = min(candidate, key=lambda c: abs(c[0] - x) + abs(c[1] - y))
        dx = abs(cx - x) * PUNTI_IN_MM
        dy = abs(cy - y) * PUNTI_IN_MM
        scarti_x.append(dx)
        scarti_y.append(dy)
        if dx <= SCARTO_TOLLERATO_MM and dy <= SCARTO_TOLLERATO_MM:
            dentro += 1

    esito.parole_ritrovate = len(scarti_x)
    if scarti_x:
        esito.scarto_x_mediano = round(statistics.median(scarti_x), 2)
        esito.scarto_y_mediano = round(statistics.median(scarti_y), 2)
        esito.scarto_x_massimo = round(max(scarti_x), 2)
        esito.scarto_y_massimo = round(max(scarti_y), 2)
        esito.entro_tolleranza = round(dentro / len(attese) * 100, 1)
    return esito


def confronta(partenza: str | Path, arrivo: str | Path) -> EsitoDocumento:
    """Misura quanto il documento di arrivo si discosta da quello di partenza.

    Solleva `VerificaFedeltaError` se uno dei due non si apre o se quello di
    partenza non ha parole: senza testo non c'e' niente da confrontare, e un
    confronto che non puo' fallire non serve a nessuno.
    """
    pagine_partenza = _parole(Path(partenza))
    pagine_arrivo = _parole(Path(arrivo))

    esito = EsitoDocumento()
    if not any(pagine_partenza):
        raise VerificaFedeltaError(
            "il documento di partenza non ha testo: non c'e' niente da confrontare"
        )

    if len(pagine_arrivo) != len(pagine_partenza):
        esito.avvisi.append(
            f"il documento era di {len(pagine_partenza)} pagine "
            f"ed e' tornato di {len(pagine_arrivo)}"
        )

    for numero, attese in enumerate(pagine_partenza, start=1):
        trovate = pagine_arrivo[numero - 1] if numero <= len(pagine_arrivo) else []
        esito.pagine.append(_confronta_pagina(numero, attese, trovate))

    return esito
