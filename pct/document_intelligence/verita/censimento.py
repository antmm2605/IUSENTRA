"""Censimento delle etichette certe di un fascicolo e riepilogo dello studio.

Il censimento unisce le due fonti (deposito telematico e decisioni dell'avvocato), segnala i conflitti e misura
quanto la catalogazione attuale concorda con le etichette certe. Il riepilogo contiene solo conteggi e voci:
nessun nome di file, nessun testo, nessun dato del cliente.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from .decisioni import etichette_dalle_decisioni
from .modello import LIVELLO_AVVOCATO, LIVELLO_DEPOSITO, EtichettaCerta
from .portale import ATTO, PROVVEDIMENTO, chiave_portale, etichetta_dal_portale

# Voci riconosciute dalla struttura XML (radice ministeriale, FatturaPA): già certe, non servono ad addestrare.
_STRUTTURALI = ("Dati strutturati PST", "XML FatturaPA", "Ricevuta PCT", "Ricevuta PEC")


def _strutturale(etichetta: str) -> bool:
    return any(segno in etichetta for segno in _STRUTTURALI)


def censisci(documenti: Iterable[Any], assegnazioni: Iterable[Any], *, fascicolo_id: str,
             conferme_massive: set[str] = frozenset()) -> dict[str, Any]:
    """Etichette certe, conflitti e concordanza del catalogo per un fascicolo."""
    documenti = list(documenti)
    assegnazioni = list(assegnazioni)
    per_documento = {str(getattr(a, "document_id", "") or ""): a for a in assegnazioni}

    dal_portale = [e for e in (etichetta_dal_portale(d, fascicolo_id=fascicolo_id) for d in documenti) if e]
    dall_avvocato = etichette_dalle_decisioni(assegnazioni, conferme_massive=conferme_massive)
    avvocato_per_documento = {e.document_id: e for e in dall_avvocato if not e.negativa}

    etichette: list[EtichettaCerta] = list(dall_avvocato)
    conflitti: list[dict[str, str]] = []
    for etichetta in dal_portale:
        decisa = avvocato_per_documento.get(etichetta.document_id)
        if decisa is None:
            etichette.append(etichetta)
        elif decisa.etichetta != etichetta.etichetta:
            # Prevale la decisione dell'avvocato su quel documento; il conflitto resta visibile.
            conflitti.append({"document_id": etichetta.document_id, "portale": etichetta.etichetta, "avvocato": decisa.etichetta})

    concordanza: list[dict[str, str]] = []
    for etichetta in dal_portale:
        assegnazione = per_documento.get(etichetta.document_id)
        if assegnazione is None or str(getattr(assegnazione, "source_state", "")) == "manual_override":
            continue
        concordanza.append({"voce": etichetta.etichetta, "catalogo": str(getattr(assegnazione, "document_label", "") or "")})

    non_mappati: Counter[str] = Counter()
    for documento in documenti:
        chiave = chiave_portale(documento)
        if chiave and chiave[0] in {ATTO, PROVVEDIMENTO} and etichetta_dal_portale(documento, fascicolo_id=fascicolo_id) is None:
            non_mappati[f"{chiave[0]}: {chiave[1]}"] += 1

    strutturali = sum(1 for a in assegnazioni if _strutturale(str(getattr(a, "document_label", "") or "")))
    return {
        "fascicolo_id": str(fascicolo_id),
        "documenti": len(documenti),
        "etichette": [e for e in etichette if not _strutturale(e.etichetta)],
        "conflitti": conflitti,
        "concordanza": concordanza,
        "portale_non_mappati": dict(non_mappati),
        "strutturali": strutturali,
        "conferme_massive": len(conferme_massive),
    }


def riepilogo(censimenti: Iterable[dict[str, Any]], *, minimo_per_voce: int = 30) -> dict[str, Any]:
    """Conteggi dello studio: etichette per livello, fonte e voce; concordanza del catalogo con il deposito."""
    per_livello: Counter[str] = Counter()
    per_fonte: Counter[str] = Counter()
    per_voce: Counter[str] = Counter()
    negative: Counter[str] = Counter()
    non_mappati: Counter[str] = Counter()
    concordi: Counter[str] = Counter()
    misurati: Counter[str] = Counter()
    fascicoli = documenti = conflitti = strutturali = massive = 0
    for censimento in censimenti:
        fascicoli += 1
        documenti += int(censimento.get("documenti") or 0)
        conflitti += len(censimento.get("conflitti") or [])
        strutturali += int(censimento.get("strutturali") or 0)
        massive += int(censimento.get("conferme_massive") or 0)
        non_mappati.update(censimento.get("portale_non_mappati") or {})
        for etichetta in censimento.get("etichette") or []:
            if etichetta.negativa:
                negative[etichetta.etichetta] += 1
                continue
            per_livello[etichetta.livello] += 1
            per_fonte[etichetta.fonte] += 1
            per_voce[etichetta.etichetta] += 1
        for riga in censimento.get("concordanza") or []:
            misurati[riga["voce"]] += 1
            concordi[riga["voce"]] += int(riga["voce"] == riga["catalogo"])
    return {
        "fascicoli": fascicoli,
        "documenti": documenti,
        "etichette_positive": sum(per_voce.values()),
        "per_livello": {"deposito_telematico": per_livello[LIVELLO_DEPOSITO], "avvocato": per_livello[LIVELLO_AVVOCATO]},
        "per_fonte": dict(per_fonte),
        "per_voce": dict(per_voce.most_common()),
        "voci_addestrabili": sorted(voce for voce, n in per_voce.items() if n >= minimo_per_voce),
        "voci_sotto_soglia": sorted(voce for voce, n in per_voce.items() if n < minimo_per_voce),
        "rifiuti_avvocato": dict(negative),
        "conflitti_deposito_avvocato": conflitti,
        "conferme_massive_escluse": massive,
        "xml_strutturali_esclusi": strutturali,
        "portale_non_mappati": dict(non_mappati.most_common(60)),
        "concordanza_catalogo_con_deposito": {
            voce: {"misurati": misurati[voce], "concordi": concordi[voce]} for voce in sorted(misurati)
        },
    }


__all__ = ["censisci", "riepilogo"]
