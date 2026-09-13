"""Ricostruzione dell'impaginazione di una pagina dai token OCR.

Il riconoscimento del testo restituisce parole con la loro posizione: da sole
non bastano per un atto. Questo modulo ricompone da quelle parole la struttura
che l'avvocato si aspetta di ritrovare — titoli, capoversi, elenchi e tabelle —
in ordine di lettura, cosi' che il testo inserito nell'editor conservi la forma
del documento acquisito invece di diventare un blocco unico.

Nessun motore OCR e nessuna dipendenza esterna: la funzione lavora sui token
gia' prodotti ed e' quindi deterministica e verificabile con dati sintetici.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

TITOLO = "titolo"
PARAGRAFO = "paragrafo"
ELENCO = "elenco"
TABELLA = "tabella"
FIGURA = "figura"

# Un vuoto orizzontale piu' largo di questo multiplo della larghezza media di un
# carattere separa due celle; sotto, e' lo spazio fra parole della stessa cella.
_GAP_COLONNA = 2.6
# Due righe appartengono allo stesso capoverso se il salto verticale non supera
# questo multiplo dell'altezza tipica della riga.
_SALTO_CAPOVERSO = 1.75
_RIENTRO_CAPOVERSO = 1.6
_ALTEZZA_TITOLO = 1.18
_PAROLE_MASSIME_TITOLO = 14

_MARCATORE_ELENCO = re.compile(
    r"^(?:[-•·–—*]|\(?[a-zA-Z]\)|\(?[ivxIVX]{1,4}\)|\d{1,3}[.)])\s+",
)
_FINE_PERIODO = re.compile(r"[.:;!?»\"']\s*$")


@dataclass(slots=True)
class Parola:
    testo: str
    sinistra: float
    alto: float
    larghezza: float
    altezza: float
    confidenza: float = 0.0

    @property
    def destra(self) -> float:
        return self.sinistra + self.larghezza

    @property
    def basso(self) -> float:
        return self.alto + self.altezza


@dataclass(slots=True)
class Riga:
    parole: list[Parola]

    @property
    def testo(self) -> str:
        return " ".join(parola.testo for parola in self.parole).strip()

    @property
    def sinistra(self) -> float:
        return min(parola.sinistra for parola in self.parole)

    @property
    def destra(self) -> float:
        return max(parola.destra for parola in self.parole)

    @property
    def alto(self) -> float:
        return min(parola.alto for parola in self.parole)

    @property
    def basso(self) -> float:
        return max(parola.basso for parola in self.parole)

    @property
    def altezza(self) -> float:
        return statistics.median([parola.altezza for parola in self.parole]) or 1.0

    @property
    def confidenza(self) -> float:
        valori = [parola.confidenza for parola in self.parole if parola.confidenza > 0]
        return sum(valori) / len(valori) if valori else 0.0


@dataclass(slots=True)
class Blocco:
    """Un blocco riconosciuto nella pagina, in ordine di lettura."""

    tipo: str
    testo: str = ""
    righe: list[list[str]] = field(default_factory=list)
    riquadro: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    confidenza: float = 0.0
    pagina: int = 1

    def come_dizionario(self) -> dict[str, Any]:
        voce: dict[str, Any] = {
            "tipo": self.tipo,
            "riquadro": [round(valore, 2) for valore in self.riquadro],
            "confidenza": round(self.confidenza, 4),
            "pagina": self.pagina,
        }
        if self.tipo == TABELLA:
            voce["righe"] = [list(riga) for riga in self.righe]
            voce["colonne"] = len(self.righe[0]) if self.righe else 0
        else:
            voce["testo"] = self.testo
        return voce


def _riquadro(righe: Sequence[Riga]) -> tuple[float, float, float, float]:
    return (
        min(riga.sinistra for riga in righe),
        min(riga.alto for riga in righe),
        max(riga.destra for riga in righe),
        max(riga.basso for riga in righe),
    )


def _confidenza(righe: Sequence[Riga]) -> float:
    valori = [riga.confidenza for riga in righe if riga.confidenza > 0]
    return sum(valori) / len(valori) if valori else 0.0


def righe_da_parole(parole: Iterable[dict[str, Any]]) -> list[Riga]:
    """Raggruppa le parole nelle righe dichiarate dal motore, in ordine di lettura."""
    gruppi: dict[tuple[int, int, int], list[Parola]] = {}
    ordine: list[tuple[int, int, int]] = []
    for grezza in parole:
        testo = str(grezza.get("testo") or grezza.get("text") or "").strip()
        if not testo:
            continue
        chiave = (
            int(grezza.get("blocco", grezza.get("block", 0)) or 0),
            int(grezza.get("capoverso", grezza.get("par", 0)) or 0),
            int(grezza.get("riga", grezza.get("line", 0)) or 0),
        )
        if chiave not in gruppi:
            gruppi[chiave] = []
            ordine.append(chiave)
        gruppi[chiave].append(
            Parola(
                testo=testo,
                sinistra=float(grezza.get("sinistra", grezza.get("left", 0)) or 0),
                alto=float(grezza.get("alto", grezza.get("top", 0)) or 0),
                larghezza=float(grezza.get("larghezza", grezza.get("width", 0)) or 0),
                altezza=float(grezza.get("altezza", grezza.get("height", 0)) or 0),
                confidenza=float(grezza.get("confidenza", grezza.get("conf", 0)) or 0),
            )
        )
    righe = [Riga(sorted(gruppi[chiave], key=lambda parola: parola.sinistra)) for chiave in ordine]
    righe = [riga for riga in righe if riga.parole]
    righe.sort(key=lambda riga: (round(riga.alto / max(1.0, riga.altezza * 0.6)), riga.sinistra))
    return righe


def _larghezza_carattere(righe: Sequence[Riga]) -> float:
    misure = [
        parola.larghezza / len(parola.testo)
        for riga in righe
        for parola in riga.parole
        if parola.testo and parola.larghezza > 0
    ]
    return statistics.median(misure) if misure else 6.0


def segmenti_riga(riga: Riga, soglia: float) -> list[tuple[float, float, str]]:
    """Spezza la riga dove il vuoto orizzontale supera la soglia: sono le celle."""
    segmenti: list[tuple[float, float, list[str]]] = []
    for parola in riga.parole:
        if segmenti and parola.sinistra - segmenti[-1][1] <= soglia:
            precedente = segmenti[-1]
            precedente[2].append(parola.testo)
            segmenti[-1] = (precedente[0], max(precedente[1], parola.destra), precedente[2])
        else:
            segmenti.append((parola.sinistra, parola.destra, [parola.testo]))
    return [(inizio, fine, " ".join(testi)) for inizio, fine, testi in segmenti]


def _blocchi_tabellari(righe: Sequence[Riga], soglia_colonna: float) -> list[tuple[int, int]]:
    """Intervalli di righe consecutive che si comportano come una tabella."""
    multiple = [len(segmenti_riga(riga, soglia_colonna)) >= 2 for riga in righe]
    grezzi = _sequenze(multiple)
    uniti = _unisci_righe_con_cella_sola(grezzi, righe, multiple, soglia_colonna)
    return [
        intervallo for intervallo in uniti
        if intervallo[1] - intervallo[0] >= 2
        and sum(1 for i in range(*intervallo) if multiple[i]) >= 2
        and _colonne_allineate([righe[i] for i in range(*intervallo)], soglia_colonna)
    ]


def _sequenze(bandiere: Sequence[bool]) -> list[tuple[int, int]]:
    """Tutti gli intervalli massimali di righe con piu' celle, anche di una sola riga."""
    intervalli: list[tuple[int, int]] = []
    inizio = None
    for indice, attiva in enumerate(bandiere):
        if attiva and inizio is None:
            inizio = indice
        elif not attiva and inizio is not None:
            intervalli.append((inizio, indice))
            inizio = None
    if inizio is not None:
        intervalli.append((inizio, len(bandiere)))
    return intervalli


def _unisci_righe_con_cella_sola(
    intervalli: list[tuple[int, int]], righe: Sequence[Riga], multiple: Sequence[bool], soglia: float
) -> list[tuple[int, int]]:
    """Assorbe la riga con una cella sola in mezzo a due porzioni di tabella.

    Nelle tabelle di un atto capita spesso che una riga abbia una sola voce
    compilata: senza questo passaggio spezzerebbe la tabella in due, e
    entrambi i tronconi verrebbero scartati perche' troppo corti.
    """
    if len(intervalli) < 2:
        return list(intervalli)
    unite: list[tuple[int, int]] = [intervalli[0]]
    for inizio, fine in intervalli[1:]:
        precedente = unite[-1]
        buco = list(range(precedente[1], inizio))
        if len(buco) == 1 and not multiple[buco[0]] and _sulla_prima_colonna(righe[buco[0]], righe[precedente[0]], soglia):
            unite[-1] = (precedente[0], fine)
        else:
            unite.append((inizio, fine))
    return unite


def _sulla_prima_colonna(riga: Riga, riferimento: Riga, soglia: float) -> bool:
    colonne = [segmento[0] for segmento in segmenti_riga(riferimento, soglia)]
    return bool(colonne) and abs(riga.sinistra - colonne[0]) <= soglia


def _colonne_allineate(righe: Sequence[Riga], soglia: float) -> bool:
    """Le celle si incolonnano? Altrimenti sono capoversi con spaziatura larga."""
    inizi = [[segmento[0] for segmento in segmenti_riga(riga, soglia)] for riga in righe]
    if len({len(valori) for valori in inizi}) > 2:
        return False
    riferimento = inizi[0]
    for valori in inizi[1:]:
        for posizione in valori:
            if min((abs(posizione - atteso) for atteso in riferimento), default=soglia) > soglia:
                return False
    return True


def _tabella(righe: Sequence[Riga], soglia: float, pagina: int) -> Blocco:
    bande: list[list[float]] = []
    for riga in righe:
        for inizio, fine, _ in segmenti_riga(riga, soglia):
            for banda in bande:
                if inizio <= banda[1] + soglia and fine >= banda[0] - soglia:
                    banda[0] = min(banda[0], inizio)
                    banda[1] = max(banda[1], fine)
                    break
            else:
                bande.append([inizio, fine])
    bande.sort(key=lambda banda: banda[0])
    griglia: list[list[str]] = []
    for riga in righe:
        celle = [""] * len(bande)
        for inizio, fine, testo in segmenti_riga(riga, soglia):
            centro = (inizio + fine) / 2
            indice = min(range(len(bande)), key=lambda i: abs(((bande[i][0] + bande[i][1]) / 2) - centro))
            celle[indice] = f"{celle[indice]} {testo}".strip()
        griglia.append(celle)
    return Blocco(TABELLA, righe=griglia, riquadro=_riquadro(righe), confidenza=_confidenza(righe), pagina=pagina)


def _unisci_righe(righe: Sequence[Riga]) -> str:
    testo = ""
    for riga in righe:
        pezzo = riga.testo
        if testo.endswith("-") and pezzo[:1].islower():
            testo = testo[:-1] + pezzo
        else:
            testo = f"{testo} {pezzo}".strip()
    return re.sub(r"\s+", " ", testo).strip()


def _tipo_testuale(righe: Sequence[Riga], altezza_tipica: float) -> str:
    testo = _unisci_righe(righe)
    if _MARCATORE_ELENCO.match(testo):
        return ELENCO
    if len(righe) == 1:
        parole = testo.split()
        alta = righe[0].altezza >= altezza_tipica * _ALTEZZA_TITOLO
        maiuscola = testo == testo.upper() and any(carattere.isalpha() for carattere in testo)
        if len(parole) <= _PAROLE_MASSIME_TITOLO and (alta or maiuscola) and not _FINE_PERIODO.search(testo):
            return TITOLO
    return PARAGRAFO


def _capoversi(righe: Sequence[Riga], altezza_tipica: float, pagina: int) -> list[Blocco]:
    blocchi: list[Blocco] = []
    corrente: list[Riga] = []
    for riga in righe:
        if corrente:
            precedente = corrente[-1]
            salto = riga.alto - precedente.basso
            rientro = abs(riga.sinistra - corrente[0].sinistra)
            nuovo = (
                salto > altezza_tipica * _SALTO_CAPOVERSO
                or rientro > altezza_tipica * _RIENTRO_CAPOVERSO
                or bool(_MARCATORE_ELENCO.match(riga.testo))
                or (_FINE_PERIODO.search(precedente.testo) and precedente.destra < corrente[0].sinistra + (riga.destra - riga.sinistra) * 0.72)
            )
            if nuovo:
                blocchi.append(
                    Blocco(_tipo_testuale(corrente, altezza_tipica), testo=_unisci_righe(corrente),
                           riquadro=_riquadro(corrente), confidenza=_confidenza(corrente), pagina=pagina)
                )
                corrente = []
        corrente.append(riga)
    if corrente:
        blocchi.append(
            Blocco(_tipo_testuale(corrente, altezza_tipica), testo=_unisci_righe(corrente),
                   riquadro=_riquadro(corrente), confidenza=_confidenza(corrente), pagina=pagina)
        )
    return [blocco for blocco in blocchi if blocco.testo]


def analizza_pagina(parole: Iterable[dict[str, Any]], *, pagina: int = 1) -> list[Blocco]:
    """Blocchi della pagina in ordine di lettura: titoli, capoversi, elenchi, tabelle."""
    righe = righe_da_parole(parole)
    if not righe:
        return []
    altezza_tipica = statistics.median([riga.altezza for riga in righe]) or 1.0
    soglia_colonna = _larghezza_carattere(righe) * _GAP_COLONNA
    intervalli = _blocchi_tabellari(righe, soglia_colonna)

    blocchi: list[Blocco] = []
    cursore = 0
    for inizio, fine in intervalli:
        if inizio > cursore:
            blocchi.extend(_capoversi(righe[cursore:inizio], altezza_tipica, pagina))
        blocchi.append(_tabella(righe[inizio:fine], soglia_colonna, pagina))
        cursore = fine
    if cursore < len(righe):
        blocchi.extend(_capoversi(righe[cursore:], altezza_tipica, pagina))
    return blocchi
