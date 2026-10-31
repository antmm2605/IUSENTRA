"""Il risultato del calcolatore in italiano, senza conoscere il singolo strumento.

Stesse regole della pagina Strumenti legali (``frontend/src/strumentiLegaliData.ts``):
valori sintetici, tabelle di dettaglio, note, avvertenze e fonti ufficiali.
Gli importi in euro, le date gg/mm/aaaa e i decimali con la virgola.
"""
from __future__ import annotations

import re
from typing import Any

_NON_SINTETICHE = {"notes", "warnings", "sources", "scadenze_proposte", "scadenza_iso", "note", "avvertenze"}
_ETICHETTE = {
    "capital": "Capitale", "covered_days": "Giorni coperti", "days": "Giorni", "end_date": "Data finale",
    "start_date": "Data iniziale", "label": "Descrizione", "mode": "Regime", "total_amount": "Totale dovuto",
    "total_interest": "Interessi totali", "segments": "Dettaglio per periodo", "from": "Dal", "to": "Al",
    "interest": "Interessi", "rate": "Tasso annuo", "reference_rate": "Tasso di riferimento",
}
_EURO = re.compile(r"(total|totale|importo|interest|interessi|amount|capital|valore|base|compens|quota|spese|contributo|imposta|anticipazione|netto|lordo|residuo|canone|indennit|somma)")
_TASSO = re.compile(r"(rate|tasso|aliquota|percentual)")
_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TECNICHE = re.compile(r"(^|_)(code|codice|id|url|mode|tipo|categoria|grado|valore_tipo)$")


def etichetta(chiave: str) -> str:
    if chiave in _ETICHETTE:
        return _ETICHETTE[chiave]
    testo = chiave.replace("_", " ").strip()
    return testo[:1].upper() + testo[1:]


def euro(valore: float) -> str:
    testo = f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {testo}"


def valore_leggibile(chiave: str, valore: Any) -> str:
    if isinstance(valore, bool):
        return "sì" if valore else "no"
    if isinstance(valore, (int, float)):
        if _TASSO.search(chiave):
            return f"{float(valore):g}".replace(".", ",") + "%"
        if _EURO.search(chiave) and not chiave.endswith(("days", "giorni")):
            return euro(float(valore))
        return f"{valore:g}".replace(".", ",") if isinstance(valore, float) else str(valore)
    testo = str(valore)
    if _DATA_ISO.match(testo):
        return f"{testo[8:10]}/{testo[5:7]}/{testo[:4]}"
    return testo


def righe_sintetiche(risultato: dict[str, Any], limite: int = 12) -> list[str]:
    righe: list[str] = []
    for chiave, valore in risultato.items():
        if chiave in _NON_SINTETICHE or valore in (None, "", [], {}) or isinstance(valore, (dict, list)):
            continue
        if _TECNICHE.search(chiave) and (f"{chiave}_label" in risultato or (chiave == "mode" and "label" in risultato)):
            continue  # c'è già l'etichetta italiana dello stesso dato
        righe.append(f"- {etichetta(chiave.removesuffix('_label'))}: **{valore_leggibile(chiave, valore)}**")
        if len(righe) >= limite:
            break
    return righe


def tabella_dettaglio(risultato: dict[str, Any], massimo: int = 6) -> list[str]:
    for chiave, valore in risultato.items():
        if chiave in _NON_SINTETICHE or not isinstance(valore, list) or not valore:
            continue
        voci = [v for v in valore if isinstance(v, dict)]
        if len(voci) != len(valore):
            continue
        righe = [f"{etichetta(chiave)}:"]
        for voce in voci[:massimo]:
            parti = [f"{etichetta(k)} {valore_leggibile(k, v)}" for k, v in voce.items()
                     if not isinstance(v, (dict, list)) and v not in (None, "")]
            righe.append("- " + ", ".join(parti[:6]))
        if len(voci) > massimo:
            righe.append(f"- … altre {len(voci) - massimo} righe nella pagina dello strumento.")
        return righe
    return []


def testi(risultato: dict[str, Any], chiave: str) -> list[str]:
    valore = risultato.get(chiave)
    return [str(v) for v in valore if isinstance(v, str) and v.strip()] if isinstance(valore, list) else []


def fonti(risultato: dict[str, Any]) -> list[dict[str, str]]:
    elenco = risultato.get("sources")
    if not isinstance(elenco, list):
        return []
    return [{"title": str(v.get("title") or ""), "url": str(v.get("url") or "")}
            for v in elenco if isinstance(v, dict) and v.get("url")]


__all__ = ["etichetta", "euro", "fonti", "righe_sintetiche", "tabella_dettaglio", "testi", "valore_leggibile"]
