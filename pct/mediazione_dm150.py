"""
Motore dei costi organismo mediazione ex D.M. 24 ottobre 2023, n. 150.

Il modulo calcola il costo minimo dell'organismo di mediazione nei casi
piu' ricorrenti del preventivo:
- primo incontro senza accordo
- conciliazione al primo incontro
- prosecuzione senza accordo
- prosecuzione con accordo

Le formule seguono gli articoli 28, 30 e 31 del D.M. 150/2023, usando gli
importi minimi della Tabella A per gli organismi pubblici come baseline
prudenziale e verificabile.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


REGIME_VOLONTARIA = "volontaria"
REGIME_OBBLIGATORIA = "obbligatoria_demandata"

ESITO_PRIMO_INCONTRO_SENZA_ACCORDO = "primo_incontro_senza_accordo"
ESITO_PRIMO_INCONTRO_CON_ACCORDO = "primo_incontro_con_accordo"
ESITO_SUCCESSIVI_SENZA_ACCORDO = "incontri_successivi_senza_accordo"
ESITO_SUCCESSIVI_CON_ACCORDO = "incontri_successivi_con_accordo"

RIDUZIONE_OBBLIGATORIA = 0.80
MAGGIORAZIONE_PRIMO_ACCORDO = 1.10
MAGGIORAZIONE_SUCCESSIVI_ACCORDO = 1.25
MAGGIORAZIONE_ART31_COMMA3 = 1.20


@dataclass(frozen=True)
class ScaglioneMediazioneDm150:
    min_value: float
    max_value: Optional[float]
    label: str
    spese_avvio: float
    spese_primo_incontro: float
    tabella_a_minimo: float


@dataclass(frozen=True)
class RisultatoMediazioneDm150:
    valore: float
    scaglione: str
    regime: str
    esito: str
    spese_avvio_base: float
    spese_mediazione_primo_base: float
    spese_avvio: float
    spese_mediazione_primo_incontro: float
    tabella_a_minimo: float
    ulteriori_spese_mediazione: float
    totale_organismo: float
    riduzione_obbligatoria_applicata: bool
    art31_comma3_maggiorazione_20: bool
    riferimento_normativo: str = "D.M. 24 ottobre 2023, n. 150 - artt. 28, 30 e 31"
    riferimento_url: str = (
        "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?"
        "atto.codiceRedazionale=23G00163&atto.dataPubblicazioneGazzetta=2023-10-31"
        "&atto.tipoProvvedimento=DECRETO"
    )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["regime_label"] = label_regime_mediazione_dm150(self.regime)
        payload["esito_label"] = label_esito_mediazione_dm150(self.esito)
        payload["descrizione_operativa"] = descrizione_operativa_mediazione_dm150(self)
        return payload


SCAGLIONI_MEDIAZIONE_DM150: tuple[ScaglioneMediazioneDm150, ...] = (
    ScaglioneMediazioneDm150(
        min_value=0.0,
        max_value=1000.0,
        label="Fino a € 1.000",
        spese_avvio=40.0,
        spese_primo_incontro=60.0,
        tabella_a_minimo=80.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=1000.01,
        max_value=5000.0,
        label="Da € 1.000,01 a € 5.000",
        spese_avvio=75.0,
        spese_primo_incontro=120.0,
        tabella_a_minimo=160.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=5000.01,
        max_value=10000.0,
        label="Da € 5.000,01 a € 10.000",
        spese_avvio=75.0,
        spese_primo_incontro=120.0,
        tabella_a_minimo=290.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=10000.01,
        max_value=25000.0,
        label="Da € 10.000,01 a € 25.000",
        spese_avvio=75.0,
        spese_primo_incontro=120.0,
        tabella_a_minimo=440.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=25000.01,
        max_value=50000.0,
        label="Da € 25.000,01 a € 50.000",
        spese_avvio=75.0,
        spese_primo_incontro=120.0,
        tabella_a_minimo=720.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=50000.01,
        max_value=150000.0,
        label="Da € 50.000,01 a € 150.000",
        spese_avvio=110.0,
        spese_primo_incontro=170.0,
        tabella_a_minimo=1200.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=150000.01,
        max_value=250000.0,
        label="Da € 150.000,01 a € 250.000",
        spese_avvio=110.0,
        spese_primo_incontro=170.0,
        tabella_a_minimo=1500.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=250000.01,
        max_value=500000.0,
        label="Da € 250.000,01 a € 500.000",
        spese_avvio=110.0,
        spese_primo_incontro=170.0,
        tabella_a_minimo=2500.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=500000.01,
        max_value=1500000.0,
        label="Da € 500.000,01 a € 1.500.000",
        spese_avvio=110.0,
        spese_primo_incontro=170.0,
        tabella_a_minimo=3900.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=1500000.01,
        max_value=2500000.0,
        label="Da € 1.500.000,01 a € 2.500.000",
        spese_avvio=110.0,
        spese_primo_incontro=170.0,
        tabella_a_minimo=4600.0,
    ),
    ScaglioneMediazioneDm150(
        min_value=2500000.01,
        max_value=5000000.0,
        label="Da € 2.500.000,01 a € 5.000.000",
        spese_avvio=110.0,
        spese_primo_incontro=170.0,
        tabella_a_minimo=6500.0,
    ),
)

SCAGLIONE_INDETERMINABILE = ScaglioneMediazioneDm150(
    min_value=50000.01,
    max_value=150000.0,
    label="Valore indeterminabile",
    spese_avvio=110.0,
    spese_primo_incontro=170.0,
    tabella_a_minimo=1200.0,
)


def label_regime_mediazione_dm150(regime: str) -> str:
    if regime == REGIME_OBBLIGATORIA:
        return "Obbligatoria / demandata dal giudice"
    return "Volontaria"


def label_esito_mediazione_dm150(esito: str) -> str:
    mapping = {
        ESITO_PRIMO_INCONTRO_SENZA_ACCORDO: "Solo primo incontro senza accordo",
        ESITO_PRIMO_INCONTRO_CON_ACCORDO: "Accordo raggiunto al primo incontro",
        ESITO_SUCCESSIVI_SENZA_ACCORDO: "Incontri successivi senza accordo",
        ESITO_SUCCESSIVI_CON_ACCORDO: "Incontri successivi con accordo",
    }
    return mapping.get(esito, esito)


def scaglione_mediazione_dm150(valore: float, *, indeterminabile: bool = False) -> ScaglioneMediazioneDm150:
    if indeterminabile or valore <= 0:
        return SCAGLIONE_INDETERMINABILE
    for row in SCAGLIONI_MEDIAZIONE_DM150:
        if valore >= row.min_value and (row.max_value is None or valore <= row.max_value):
            return row
    return ScaglioneMediazioneDm150(
        min_value=5000000.01,
        max_value=None,
        label="Oltre € 5.000.000",
        spese_avvio=110.0,
        spese_primo_incontro=170.0,
        tabella_a_minimo=round(valore * 0.002, 2),
    )


def descrizione_operativa_mediazione_dm150(result: RisultatoMediazioneDm150 | Dict[str, Any]) -> str:
    if isinstance(result, dict):
        data = result
    else:
        data = asdict(result)
        data["regime_label"] = label_regime_mediazione_dm150(data.get("regime", ""))
        data["esito_label"] = label_esito_mediazione_dm150(data.get("esito", ""))
    return (
        "Costi organismo mediazione D.M. 150/2023 - "
        f"{data.get('regime_label') or label_regime_mediazione_dm150(str(data.get('regime') or ''))}, "
        f"{data.get('esito_label') or label_esito_mediazione_dm150(str(data.get('esito') or ''))}, "
        f"{data.get('scaglione', '')}"
    ).strip().rstrip(",")


def calcola_costi_mediazione_dm150(
    valore: float,
    *,
    regime: str = REGIME_VOLONTARIA,
    esito: str = ESITO_PRIMO_INCONTRO_SENZA_ACCORDO,
    art31_comma3_maggiorazione_20: bool = False,
    indeterminabile: bool = False,
) -> RisultatoMediazioneDm150:
    scaglione = scaglione_mediazione_dm150(valore, indeterminabile=indeterminabile)
    regime_norm = regime if regime in {REGIME_VOLONTARIA, REGIME_OBBLIGATORIA} else REGIME_VOLONTARIA
    esito_norm = esito if esito in {
        ESITO_PRIMO_INCONTRO_SENZA_ACCORDO,
        ESITO_PRIMO_INCONTRO_CON_ACCORDO,
        ESITO_SUCCESSIVI_SENZA_ACCORDO,
        ESITO_SUCCESSIVI_CON_ACCORDO,
    } else ESITO_PRIMO_INCONTRO_SENZA_ACCORDO

    riduzione = RIDUZIONE_OBBLIGATORIA if regime_norm == REGIME_OBBLIGATORIA else 1.0
    spese_avvio = round(scaglione.spese_avvio * riduzione, 2)
    spese_primo = round(scaglione.spese_primo_incontro * riduzione, 2)
    differenziale_tabella_a = max(scaglione.tabella_a_minimo - scaglione.spese_primo_incontro, 0.0)

    moltiplicatore_ulteriori = 0.0
    maggiorazione_art31 = False
    if esito_norm == ESITO_PRIMO_INCONTRO_CON_ACCORDO:
        moltiplicatore_ulteriori = MAGGIORAZIONE_PRIMO_ACCORDO
    elif esito_norm == ESITO_SUCCESSIVI_SENZA_ACCORDO:
        moltiplicatore_ulteriori = 1.0
    elif esito_norm == ESITO_SUCCESSIVI_CON_ACCORDO:
        moltiplicatore_ulteriori = MAGGIORAZIONE_SUCCESSIVI_ACCORDO
        maggiorazione_art31 = bool(art31_comma3_maggiorazione_20)
        if maggiorazione_art31:
            moltiplicatore_ulteriori *= MAGGIORAZIONE_ART31_COMMA3

    ulteriori = round(differenziale_tabella_a * moltiplicatore_ulteriori * riduzione, 2)
    totale = round(spese_avvio + spese_primo + ulteriori, 2)

    return RisultatoMediazioneDm150(
        valore=round(valore or 0.0, 2),
        scaglione=scaglione.label,
        regime=regime_norm,
        esito=esito_norm,
        spese_avvio_base=round(scaglione.spese_avvio, 2),
        spese_mediazione_primo_base=round(scaglione.spese_primo_incontro, 2),
        spese_avvio=spese_avvio,
        spese_mediazione_primo_incontro=spese_primo,
        tabella_a_minimo=round(scaglione.tabella_a_minimo, 2),
        ulteriori_spese_mediazione=ulteriori,
        totale_organismo=totale,
        riduzione_obbligatoria_applicata=regime_norm == REGIME_OBBLIGATORIA,
        art31_comma3_maggiorazione_20=maggiorazione_art31,
    )
