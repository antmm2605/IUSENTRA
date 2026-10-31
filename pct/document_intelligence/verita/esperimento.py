"""Misura del classificatore piccolo rispetto alle regole del catalogo e alle decisioni dell'avvocato.

- Addestramento: le proposte «quasi certe» delle regole (confidenza ≥ 96, voce governata, almeno `minimo` esempi
  per voce), esclusi i documenti di verifica scelti in modo stabile dall'identificativo.
- Verifica sulle quasi certe tenute da parte: quanto il modello riproduce le regole (non dice chi ha ragione).
- Fascia 90-95 e proposte incerte (sotto 90 o da rivedere): dove il modello, sicuro di sé, la pensa diversamente
  dalle regole. Sono i disaccordi da mostrare per primi all'avvocato.
- Decisioni dell'avvocato: l'unico confronto che misura davvero chi sbaglia meno.

Il riepilogo porta solo conteggi e voci pubblicabili; i disaccordi (identificativi e voci) restano sul server.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .censimento import CONFIDENZA_ARGENTO, VOCE_FUORI_ELENCO, _strutturale, voce_pubblicabile
from .classificatore import addestra, in_verifica

# Sopra questa probabilità il modello è «sicuro»: un disaccordo sicuro è un caso da far vedere all'avvocato.
SICUREZZA = 0.9


@dataclass(slots=True)
class Campione:
    document_id: str
    fascicolo_id: str
    testo: str
    voce: str
    confidenza: int
    stato: str
    origine: str
    voce_avvocato: str = ""  # voce confermata o corretta documento per documento dall'avvocato
    voce_spark: str = ""  # voce scelta dalla seconda lettura di Lex (Spark), se ammessa
    nomi: frozenset[str] = frozenset()  # parole dei nomi di persona noti al fascicolo, per la pseudonimizzazione
    voce_proposta: str = ""  # voce proposta dalle regole prima della correzione dell'avvocato

    @property
    def voce_delle_regole(self) -> str:
        """Ciò che le regole avevano proposto: dopo una correzione `voce` è già quella dell'avvocato."""
        return self.voce_proposta or self.voce


def _fascia(c: Campione) -> str:
    if c.stato == "proposed" and c.origine != "manual_override":
        if c.confidenza >= CONFIDENZA_ARGENTO:
            return "quasi_certa"
        if c.confidenza >= 90:
            return "90-95"
    if c.stato in {"proposed", "review_required"} and c.origine != "manual_override":
        return "incerta"
    return ""


def misura(campioni: list[Campione], *, minimo: int = 30) -> dict[str, Any]:
    """Addestra, misura e restituisce il riepilogo pubblicabile e l'elenco dei disaccordi (solo per il server)."""
    utili = [c for c in campioni if c.testo.strip()]
    quasi_certe = [c for c in utili if _fascia(c) == "quasi_certa" and not _strutturale(c.voce)
                   and voce_pubblicabile(c.voce) == c.voce]
    per_voce = Counter(c.voce for c in quasi_certe)
    voci = {v for v, n in per_voce.items() if n >= minimo}
    addestramento = [c for c in quasi_certe if c.voce in voci and not in_verifica(c.document_id)]
    verifica = [c for c in quasi_certe if c.voce in voci and in_verifica(c.document_id)]
    riepilogo: dict[str, Any] = {
        "documenti_con_testo": len(utili), "senza_testo": len(campioni) - len(utili),
        "voci_del_modello": sorted(voci), "esempi_addestramento": len(addestramento), "esempi_verifica": len(verifica),
    }
    if len({c.voce for c in addestramento}) < 2:
        riepilogo["esito"] = "esempi insufficienti per addestrare"
        return {"riepilogo": riepilogo, "disaccordi": []}
    modello = addestra([c.testo for c in addestramento], [c.voce for c in addestramento])

    def previsioni(gruppo: list[Campione]) -> list[tuple[str, float]]:
        return modello.predici([c.testo for c in gruppo]) if gruppo else []

    accordo: Counter[str] = Counter()
    for c, (voce, _p) in zip(verifica, previsioni(verifica)):
        accordo[c.voce] += int(voce == c.voce)
    riepilogo["verifica_quasi_certe"] = {
        "accordo_totale": sum(accordo.values()),
        "per_voce": {v: {"esempi": sum(1 for c in verifica if c.voce == v), "accordo": accordo[v]} for v in sorted(voci)},
    }

    disaccordi: list[dict[str, Any]] = []
    for fascia in ("90-95", "incerta"):
        gruppo = [c for c in utili if _fascia(c) == fascia]
        conteggi: Counter[str] = Counter()
        for c, (voce, p) in zip(gruppo, previsioni(gruppo)):
            if p < SICUREZZA:
                conteggi["modello_non_sicuro"] += 1
            elif c.voce not in voci:
                conteggi["voce_delle_regole_fuori_dal_modello"] += 1
                disaccordi.append(_disaccordo(c, voce, p, fascia))
            elif voce == c.voce:
                conteggi["concorda"] += 1
            else:
                conteggi["discorda"] += 1
                disaccordi.append(_disaccordo(c, voce, p, fascia))
        riepilogo[f"fascia_{fascia}"] = {"documenti": len(gruppo), **dict(conteggi)}

    decisi = [c for c in utili if c.voce_avvocato]
    giusti_modello = giusti_regole = 0
    for c, (voce, _p) in zip(decisi, previsioni(decisi)):
        giusti_modello += int(voce == c.voce_avvocato)
        giusti_regole += int(c.voce_delle_regole == c.voce_avvocato)
    riepilogo["decisioni_avvocato"] = {"documenti": len(decisi), "giuste_modello": giusti_modello,
                                       "giuste_regole": giusti_regole}
    coppie = Counter((voce_pubblicabile(d["voce_regole"]), d["voce_modello"]) for d in disaccordi)
    riepilogo["disaccordi_sicuri"] = len(disaccordi)
    riepilogo["disaccordi_per_coppia"] = {f"{r} → {m}": n for (r, m), n in coppie.most_common(30)}
    riepilogo["esito"] = "misurato"
    return {"riepilogo": riepilogo, "disaccordi": disaccordi}


def _disaccordo(c: Campione, voce: str, p: float, fascia: str) -> dict[str, Any]:
    return {"document_id": c.document_id, "fascicolo_id": c.fascicolo_id, "voce_regole": c.voce_delle_regole,
            "confidenza_regole": c.confidenza, "voce_modello": voce, "probabilita": round(p, 3), "fascia": fascia}


__all__ = ["SICUREZZA", "VOCE_FUORI_ELENCO", "Campione", "misura"]
