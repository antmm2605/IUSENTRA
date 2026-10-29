"""Le etichette dichiarate nel deposito telematico e lette dal Portale dei Servizi Telematici.

Per ogni documento importato dal portale il software conserva la classificazione della busta (atto principale,
allegato, provvedimento, indice) e il tipo atto dichiarato nel deposito (`pct.fascicoli._documento_portale_payload`).
Il tipo atto descrive l'**atto principale** della busta o il **provvedimento**: per un allegato dice solo a quale
deposito appartiene, non che cosa è, quindi un allegato non riceve etichetta.

La corrispondenza fra tipo atto del portale e voce del catalogo è dichiarata a mano in questa tabella e si
allarga solo con riscontri: un tipo atto non elencato resta senza etichetta e viene contato nel censimento,
così si vede quali voci del portale mancano.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .modello import LIVELLO_DEPOSITO, EtichettaCerta

FONTE_PORTALE = "deposito_telematico_pst"
ATTO = "ATTO"
PROVVEDIMENTO = "PROVVEDIMENTO"

# (classificazione della busta, tipo atto normalizzato) → (voce del catalogo, sezione)
TIPI_ATTO: dict[tuple[str, str], tuple[str, str]] = {
    (PROVVEDIMENTO, "decreto ingiuntivo"): ("Decreto ingiuntivo", "provvedimenti"),
    (PROVVEDIMENTO, "sentenza"): ("Sentenza", "provvedimenti"),
    (PROVVEDIMENTO, "verbale di udienza"): ("Verbale di udienza", "provvedimenti"),
    (PROVVEDIMENTO, "verbale udienza"): ("Verbale di udienza", "provvedimenti"),
    (PROVVEDIMENTO, "decreto di fissazione udienza"): ("Decreto di fissazione udienza", "provvedimenti"),
    (PROVVEDIMENTO, "decreto fissazione udienza"): ("Decreto di fissazione udienza", "provvedimenti"),
    (ATTO, "decreto ingiuntivo"): ("Ricorso per decreto ingiuntivo", "atti"),
    (ATTO, "ricorso per decreto ingiuntivo"): ("Ricorso per decreto ingiuntivo", "atti"),
    (ATTO, "ricorso decreto ingiuntivo"): ("Ricorso per decreto ingiuntivo", "atti"),
    (ATTO, "atto di citazione"): ("Atto di citazione", "atti"),
    (ATTO, "citazione"): ("Atto di citazione", "atti"),
    (ATTO, "comparsa di costituzione e risposta"): ("Comparsa di costituzione e risposta", "atti"),
    (ATTO, "comparsa costituzione e risposta"): ("Comparsa di costituzione e risposta", "atti"),
    (ATTO, "comparsa conclusionale"): ("Comparsa conclusionale", "atti"),
    (ATTO, "opposizione a decreto ingiuntivo"): ("Opposizione a decreto ingiuntivo", "atti"),
    (ATTO, "atto di precetto"): ("Atto di precetto", "atti"),
    (ATTO, "atto di pignoramento"): ("Atto di pignoramento", "atti"),
    (ATTO, "intimazione di sfratto"): ("Intimazione di sfratto", "atti"),
    (ATTO, "note di trattazione scritta"): ("Note di trattazione scritta", "atti"),
    (ATTO, "note scritte"): ("Note di trattazione scritta", "atti"),
    (ATTO, "precisazione delle conclusioni"): ("Precisazione delle conclusioni", "atti"),
}
_PREFISSO_PROVVEDIMENTO = re.compile(r"^provvedimento\s*[-—–:]?\s*")


def _normalizza(valore: Any) -> str:
    testo = unicodedata.normalize("NFKD", str(valore or "").casefold())
    testo = "".join(car for car in testo if unicodedata.category(car) != "Mn")
    testo = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9—–\- ]+", " ", testo)).strip()
    return _PREFISSO_PROVVEDIMENTO.sub("", testo).strip(" -—–")


def chiave_portale(documento: Any) -> tuple[str, str] | None:
    """(classificazione, tipo atto normalizzato) di un documento importato dal portale; None se non lo è."""
    classificazione = str(getattr(documento, "classificazione_portale", "") or "").strip().upper()
    tipo = _normalizza(getattr(documento, "tipo_atto_portale", ""))
    if not classificazione or not tipo:
        return None
    return classificazione, tipo


def etichetta_dal_portale(documento: Any, *, fascicolo_id: str) -> EtichettaCerta | None:
    """L'etichetta dichiarata nel deposito, solo per atti principali e provvedimenti con corrispondenza dichiarata."""
    chiave = chiave_portale(documento)
    if chiave is None or chiave[0] not in {ATTO, PROVVEDIMENTO}:
        return None
    if str(getattr(documento, "allegato_portale", "") or "").strip().lower() == "true":
        return None
    voce = TIPI_ATTO.get(chiave)
    if voce is None:
        return None
    return EtichettaCerta(
        fascicolo_id=str(fascicolo_id), document_id=str(getattr(documento, "id", "") or ""), etichetta=voce[0],
        sezione=voce[1], livello=LIVELLO_DEPOSITO, fonte=FONTE_PORTALE, dettaglio=f"{chiave[0]}: {chiave[1]}",
        sha256=str(getattr(documento, "hash_sha256", "") or ""),
    )


__all__ = ["ATTO", "FONTE_PORTALE", "PROVVEDIMENTO", "TIPI_ATTO", "chiave_portale", "etichetta_dal_portale"]
