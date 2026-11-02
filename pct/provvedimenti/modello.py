"""Il contratto d'uscita: ciò che il software propone dopo aver letto un provvedimento.

Ogni ``Voce`` è un passo proposto all'avvocato e porta con sé tutto ciò che serve a
mostrarlo e a correggerlo (livello «passaggi visibili + regole dello studio"):

* ``regola_id`` stabile (``legge.<regola>`` per i termini di legge della tabella
  versionata, ``giudice.<oggetto>`` per ciò che il dispositivo scrive,
  ``127ter.*`` per il decreto di trattazione scritta);
* ``norme``: identificativi del registro ``pct/procedura_fasi/fonti.py`` (URL ufficiale,
  data di consultazione, estratto);
* ``prova``: l'estratto del provvedimento da cui la voce nasce;
* ``dati``: i dati in ingresso (udienza del fascicolo, data della comunicazione…);
* ``confidenza`` e ``stato`` (``da_confermare`` per date che cambiano agenda o
  scadenziario, ``proposto`` per adempimenti e attese, ``da_chiedere`` quando il
  software non può decidere da solo e pone una ``domanda``).

Il modello è puro e serializzabile: nessun accesso a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

GENERI = ("udienza", "termine", "adempimento", "verifica", "attesa", "da_verificare")
STATO_PER_GENERE = {
    "udienza": "da_confermare", "termine": "da_confermare", "adempimento": "proposto",
    "verifica": "proposto", "attesa": "proposto", "da_verificare": "da_chiedere",
}


@dataclass(frozen=True)
class Voce:
    regola_id: str
    genere: str
    titolo: str
    norme: tuple[str, ...] = ()
    prova: str = ""
    dati: tuple[tuple[str, str, str], ...] = ()  # (etichetta, valore, fonte)
    confidenza: float = 0.0
    chi: str = ""
    giorno: date | None = None
    ora: str = ""
    perentorio: bool | None = None
    facoltativo: bool = False
    modalita: str = ""
    domanda: str = ""
    nota: str = ""
    calcolo: str = ""
    codice: str = ""
    tipo_termine: str = ""
    dies_a_quo: date | None = None
    scadenziario: bool = False
    id_appuntamento: str = ""
    campi_scadenza: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.genere not in GENERI:
            raise ValueError(f"Genere di voce non ammesso: {self.genere}")
        if not self.regola_id:
            raise ValueError("Ogni voce dichiara la regola che l'ha prodotta.")

    @property
    def stato(self) -> str:
        return STATO_PER_GENERE[self.genere]

    def chiave(self, fascicolo_id: str = "") -> str:
        """Stabile per caso: stessa regola, stesso fascicolo, stessa data → stessa chiave."""
        return f"{self.regola_id}:{fascicolo_id or '-'}:{self.giorno.isoformat() if self.giorno else 'senza-data'}"

    def riga(self) -> str:
        quando = f" — {self.giorno:%d/%m/%Y}" + (f" ore {self.ora}" if self.ora else "") if self.giorno else ""
        if self.genere == "da_verificare":
            return f"Da verificare: {self.domanda or self.titolo}"
        return f"{self.titolo}{quando}"

    def come_dizionario(self, fascicolo_id: str = "") -> dict[str, Any]:
        return {
            "chiave": self.chiave(fascicolo_id),
            "regolaId": self.regola_id,
            "genere": self.genere,
            "stato": self.stato,
            "titolo": self.titolo,
            "chi": self.chi,
            "data": self.giorno.isoformat() if self.giorno else "",
            "ora": self.ora,
            "perentorio": self.perentorio,
            "facoltativo": self.facoltativo,
            "modalita": self.modalita,
            "norme": list(self.norme),
            "prova": self.prova,
            "dati": [{"etichetta": e, "valore": v, "fonte": f} for e, v, f in self.dati],
            "confidenza": self.confidenza,
            "domanda": self.domanda,
            "nota": self.nota,
            "calcolo": self.calcolo,
            "codice": self.codice,
            "decorrenza": self.dies_a_quo.isoformat() if self.dies_a_quo else "",
            "scadenziario": self.scadenziario,
        }


@dataclass
class EsitoProvvedimento:
    """Il provvedimento letto: che cosa è, in quale materia, e le voci proposte."""

    tipi: tuple[str, ...]
    materia: str
    voci: list[Voce] = field(default_factory=list)
    note_127_ter: Any = None  # EsitoDecretoNote, quando il caso è il decreto senza data
    data_pronuncia: date | None = None

    @property
    def riconosciuto(self) -> bool:
        return bool(self.tipi)

    def da_chiedere(self) -> list[Voce]:
        return [voce for voce in self.voci if voce.genere == "da_verificare"]

    def righe_descrizione(self) -> list[str]:
        if self.note_127_ter is not None:
            righe = list(self.note_127_ter.righe_descrizione())
            return righe + [f"Dal provvedimento: {v.riga()}" for v in self.voci if not v.regola_id.startswith("127ter.")]
        return [f"Dal provvedimento: {voce.riga()}" for voce in self.voci]

    def come_dizionario(self, fascicolo_id: str = "") -> dict[str, Any]:
        return {
            "tipi": list(self.tipi),
            "materia": self.materia,
            "dataPronuncia": self.data_pronuncia.isoformat() if self.data_pronuncia else "",
            "voci": [voce.come_dizionario(fascicolo_id) for voce in self.voci],
        }


__all__ = ["GENERI", "STATO_PER_GENERE", "EsitoProvvedimento", "Voce"]
