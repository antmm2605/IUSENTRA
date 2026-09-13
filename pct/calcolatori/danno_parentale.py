"""Danno da perdita del rapporto parentale — tabelle a punti Milano 2024.

Base normativa e giurisprudenziale:
- Artt. 2043 e 2059 c.c.; art. 8 CEDU (tutela della vita familiare).
- Cass. 21/04/2021 n. 10579 e Cass. 29/09/2021 n. 26300: la liquidazione va
  fatta con una tabella a punti che elenchi le circostanze rilevanti e i
  relativi punteggi.
- Tabelle integrate a punti dell'Osservatorio sulla giustizia civile di Milano,
  edizione 2024, con i valori aggiornati all'1.1.2024.

I punteggi e i valori punto vivono in ``pct/data/tabelle_danno`` e sono letti
dal modulo ``pct.calcolatori.danno_biologico.parentale``: qui resta la lettura
del modulo e la composizione del risultato.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_int
from pct.calcolatori.danno_biologico import parentale, tabelle

# Il parametro E della tabella e' rimesso all'apprezzamento del giudice fino al
# massimo dei punti: la scala qui sotto traduce in punti le intensita' che
# l'Osservatorio elenca come circostanze di fatto rilevanti (frequentazioni,
# condivisione di festivita', vacanze, attivita', assistenza).
_INTENSITA_RELAZIONE: Dict[str, tuple] = {
    "massima": (1.0, "Relazione quotidiana e dipendenza dalla vittima primaria"),
    "molto_intensa": (0.8, "Frequentazione giornaliera e condivisione della vita quotidiana"),
    "intensa": (0.6, "Frequentazione frequente e condivisione abituale"),
    "ordinaria": (0.4, "Frequentazione e condivisione sporadiche"),
    "debole": (0.2, "Contatti rari"),
    "assente": (0.0, "Rapporto assente o conflittuale"),
}


def _riga(label: str, dettaglio: str, punti: int, massimo: int) -> Dict[str, Any]:
    return {"label": label, "detail": dettaglio, "punti": int(punti), "max": int(massimo)}


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    nome = clean_text(payload.get("dp_categoria")) or parentale.NUCLEO_PRIMARIO
    voce = parentale.categoria(nome)

    eta_vittima = safe_int(payload.get("dp_eta_vittima"), -1)
    eta_congiunto = safe_int(payload.get("dp_eta_congiunto"), -1)
    if not 0 <= eta_vittima <= 120:
        raise ValueError("Indica l'eta' della vittima primaria al momento del fatto.")
    if not 0 <= eta_congiunto <= 120:
        raise ValueError("Indica l'eta' del congiunto superstite al momento del fatto.")

    scelta_convivenza = clean_text(payload.get("dp_convivenza")) or "nessuna"
    opzioni = parentale.opzioni_convivenza(nome)
    if scelta_convivenza not in opzioni:
        raise ValueError("Situazione di convivenza non prevista dalla tabella della categoria scelta.")

    superstiti = max(0, safe_int(payload.get("dp_superstiti")))
    intensita = clean_text(payload.get("dp_qualita_relazione")) or "ordinaria"
    if intensita not in _INTENSITA_RELAZIONE:
        raise ValueError("Intensita' della relazione non riconosciuta.")

    quota, etichetta_relazione = _INTENSITA_RELAZIONE[intensita]
    massimo_relazione = parentale.punti_massimi_relazione(nome)
    punti_relazione = int(round(massimo_relazione * quota))

    fasce_primaria = voce["fasce_eta_vittima_primaria"]
    fasce_secondaria = voce["fasce_eta_vittima_secondaria"]
    parametri: List[Dict[str, Any]] = [
        _riga(
            "A. Eta' della vittima primaria", f"{eta_vittima} anni",
            parentale.punti_eta_vittima_primaria(nome, eta_vittima), fasce_primaria[0][1],
        ),
        _riga(
            "B. Eta' della vittima secondaria", f"{eta_congiunto} anni",
            parentale.punti_eta_vittima_secondaria(nome, eta_congiunto), fasce_secondaria[0][1],
        ),
        _riga(
            "C. Convivenza", scelta_convivenza.replace("_", " "),
            parentale.punti_convivenza(nome, scelta_convivenza), max(opzioni.values()),
        ),
        _riga(
            "D. Sopravvivenza di altri congiunti",
            "nessun superstite" if superstiti == 0 else f"{superstiti} superstiti",
            parentale.punti_superstiti(nome, superstiti),
            parentale.punti_superstiti(nome, 0),
        ),
        _riga("E. Qualita' e intensita' della relazione", etichetta_relazione, punti_relazione, massimo_relazione),
    ]

    punti_totali = sum(int(r["punti"]) for r in parametri)
    punti_massimi = int(voce["punti_massimi"])
    punti_liquidati = min(punti_totali, punti_massimi)
    cap = float(voce["cap"])
    lordo = round(punti_liquidati * float(voce["valore_punto"]), 2)
    liquidato = parentale.importo(nome, punti_liquidati)

    avvisi: List[str] = []
    if punti_totali > punti_massimi:
        avvisi.append(
            f"I punti attribuiti ({punti_totali}) superano i {punti_massimi} attribuibili dalla "
            "tabella: il conteggio e' fermato al massimo previsto."
        )
    if lordo > cap:
        avvisi.append(
            f"L'importo per punti ({lordo:,.2f} €) supera il tetto della categoria: la "
            f"liquidazione e' ricondotta a {cap:,.2f} €, salvo circostanze eccezionali motivate."
            .replace(",", "@").replace(".", ",").replace("@", ".")
        )

    fonte = tabelle.fonte(tabelle.MILANO_2024_PARENTALE)
    return {
        "categoria": nome,
        "categoria_label": voce["label"],
        "valore_punto": float(voce["valore_punto"]),
        "punti_max": punti_massimi,
        "parametri": parametri,
        "punti_totali": punti_totali,
        "punti_liquidati": punti_liquidati,
        "importo": liquidato,
        "massimale_categoria": cap,
        "forbice_minima": float(voce["forbice_minima"]),
        "tabelle_applicate": [fonte.come_dizionario()],
        "notes": [
            "Tabella integrata a punti di Milano, edizione 2024, con i cinque parametri "
            "richiesti da Cass. 10579/2021: eta' della vittima primaria, eta' della vittima "
            "secondaria, convivenza, sopravvivenza di altri congiunti, qualita' e intensita' "
            "della relazione.",
            f"Valore punto {voce['valore_punto']:.2f} €, punti attribuibili {punti_massimi}, "
            f"tetto della categoria {cap:.2f} €.",
            "Il parametro E resta rimesso all'apprezzamento del giudice: la scala di intensita' "
            "traduce in punti le circostanze di fatto elencate dall'Osservatorio "
            "(frequentazioni, festivita', vacanze, attivita' condivise, assistenza).",
            _dati_nota_cap(),
        ],
        "warnings": avvisi,
        "sources": [fonte.come_sorgente()],
    }


def _dati_nota_cap() -> str:
    return str(tabelle.carica(tabelle.MILANO_2024_PARENTALE)["nota_cap"])
