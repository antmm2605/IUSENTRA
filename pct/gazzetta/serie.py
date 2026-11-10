"""Le sei serie della Gazzetta Ufficiale, con l'indirizzo ufficiale dell'elenco degli ultimi 30 giorni.

Indirizzi verificati il 10/11/2026: ogni elenco «30giorni» risponde 200 con i collegamenti ai sommari dei
fascicoli (`/gazzetta/<percorso>/caricaDettaglio?dataPubblicazioneGazzetta=AAAA-MM-GG&numeroGazzetta=N`).
"""

from __future__ import annotations

from dataclasses import dataclass

SITO = "https://www.gazzettaufficiale.it"
HOST_AMMESSI = ("www.gazzettaufficiale.it", "gazzettaufficiale.it")
VERIFICATO_IL = "2026-11-10"


@dataclass(frozen=True)
class Serie:
    codice: str  # SG, S1 … S5 (tipoSerie dei collegamenti ufficiali)
    percorso: str  # segmento degli indirizzi ufficiali
    etichetta: str
    nome_breve: str

    @property
    def url_elenco(self) -> str:
        return f"{SITO}/30giorni/{self.percorso}"

    def url_sommario(self, data_iso: str, numero: str) -> str:
        return f"{SITO}/gazzetta/{self.percorso}/caricaDettaglio?dataPubblicazioneGazzetta={data_iso}&numeroGazzetta={numero}"


SERIE: tuple[Serie, ...] = (
    Serie("SG", "serie_generale", "Serie generale", "Generale"),
    Serie("S1", "corte_costituzionale", "1ª Serie speciale - Corte costituzionale", "Corte costituzionale"),
    Serie("S2", "unione_europea", "2ª Serie speciale - Unione europea", "Unione europea"),
    Serie("S3", "regioni", "3ª Serie speciale - Regioni", "Regioni"),
    Serie("S4", "concorsi", "4ª Serie speciale - Concorsi ed esami", "Concorsi ed esami"),
    Serie("S5", "contratti", "5ª Serie speciale - Contratti pubblici", "Contratti pubblici"),
)
PER_CODICE: dict[str, Serie] = {serie.codice: serie for serie in SERIE}
PER_PERCORSO: dict[str, Serie] = {serie.percorso: serie for serie in SERIE}
# Le serie che riguardano l'attività forense ordinaria: le ultime pubblicazioni in Panoramica vengono da qui.
SERIE_PRINCIPALI = ("SG", "S1")


__all__ = ["HOST_AMMESSI", "PER_CODICE", "PER_PERCORSO", "SERIE", "SERIE_PRINCIPALI", "SITO", "Serie", "VERIFICATO_IL"]
