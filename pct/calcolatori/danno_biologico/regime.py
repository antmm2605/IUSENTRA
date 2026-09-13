"""Scelta della tabella applicabile: ambito del danno e data del sinistro.

La tabella non si sceglie a piacere. Per i sinistri da circolazione e per la
responsabilita' sanitaria il codice delle assicurazioni private impone le
proprie tabelle (art. 139 fino a nove punti, art. 138 e tabella unica nazionale
da dieci punti in su); fuori da quell'ambito la liquidazione resta equitativa
ex art. 1226 c.c. e il parametro nazionale sono le tabelle milanesi
(Cass. 12408/2011). La data del sinistro discrimina perche' la tabella unica
nazionale si applica solo ai sinistri successivi alla sua entrata in vigore
(art. 5 D.P.R. 12/2025): per i sinistri anteriori le macrolesioni continuano a
liquidarsi con le tabelle milanesi.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, NamedTuple

from pct.calcolatori._base import parse_date

ENTRATA_IN_VIGORE_TUN = date(2025, 3, 5)

AMBITO_CIRCOLAZIONE = "circolazione"
AMBITO_SANITARIA = "sanitaria"
AMBITO_CIVILE = "civile"

AMBITI: Dict[str, str] = {
    AMBITO_CIRCOLAZIONE: "Sinistro da circolazione di veicoli a motore o natanti",
    AMBITO_SANITARIA: "Responsabilita' sanitaria (art. 7 comma 4 L. 24/2017)",
    AMBITO_CIVILE: "Altra responsabilita' civile (liquidazione equitativa ex art. 1226 c.c.)",
}

REGIME_ART_139 = "art_139"
REGIME_TUN = "tun"
REGIME_MILANO = "milano"


class Regime(NamedTuple):
    """Tabella applicabile e motivazione della scelta."""

    codice: str
    etichetta: str
    motivazione: str


def ambito_valido(valore: str) -> str:
    return valore if valore in AMBITI else AMBITO_CIRCOLAZIONE


def soggetto_al_codice_assicurazioni(ambito: str) -> bool:
    return ambito in (AMBITO_CIRCOLAZIONE, AMBITO_SANITARIA)


def scegli(ambito: str, punti: int, data_sinistro: date) -> Regime:
    """Individua la tabella applicabile all'ambito, ai punti e alla data."""
    if not soggetto_al_codice_assicurazioni(ambito):
        return Regime(
            REGIME_MILANO,
            "Tabelle milanesi edizione 2024",
            "Fuori dall'ambito degli artt. 138 e 139 del codice delle assicurazioni private "
            "la liquidazione e' equitativa ex art. 1226 c.c. e il parametro nazionale sono le "
            "tabelle milanesi (Cass. 7 giugno 2011 n. 12408).",
        )
    if punti <= 9:
        return Regime(
            REGIME_ART_139,
            "Art. 139 codice delle assicurazioni private",
            "Postumi pari o inferiori al 9 per cento: si applica la tabella di legge delle "
            "lesioni di lieve entita' (art. 139 D.Lgs. 209/2005).",
        )
    if data_sinistro >= ENTRATA_IN_VIGORE_TUN:
        return Regime(
            REGIME_TUN,
            "Tabella unica nazionale (D.P.R. 12/2025)",
            "Sinistro del "
            f"{data_sinistro.strftime('%d/%m/%Y')}, successivo al 5 marzo 2025: si applica la "
            "tabella unica nazionale delle macrolesioni (art. 138 D.Lgs. 209/2005, "
            "D.P.R. 13 gennaio 2025 n. 12, art. 5).",
        )
    return Regime(
        REGIME_MILANO,
        "Tabelle milanesi edizione 2024",
        "Sinistro del "
        f"{data_sinistro.strftime('%d/%m/%Y')}, anteriore al 5 marzo 2025: la tabella unica "
        "nazionale non si applica (art. 5 D.P.R. 12/2025) e le macrolesioni si liquidano con "
        "le tabelle milanesi.",
    )


def leggi_data(valore: object) -> date | None:
    return parse_date(valore)
