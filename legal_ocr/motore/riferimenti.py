"""Riferimenti giuridici leggibili nel testo riconosciuto: e' il documento giusto?

Numero di ruolo, ufficio, date e importi in cima al risultato evitano di
scorrere l'intero atto per accorgersi di aver aperto il fascicolo sbagliato.
Gli estrattori sono quelli della pipeline probatoria (`legal_ocr.ner_legal`):
qui servono come indicazione di lettura, non come dato certificato.

Una data come «12/03/2026» contiene «12/03», che ha la stessa forma di un
numero di ruolo: i numeri di ruolo che compaiono dentro una data riconosciuta
vengono scartati, perche' un riferimento sbagliato e' peggio di nessuno.
"""

from __future__ import annotations

from typing import Any

from ..ner_legal import extract_legal_entities

MASSIMO_PER_TIPO = 6


def _elenco(valori: Any) -> list[str]:
    if not isinstance(valori, list):
        return []
    puliti: list[str] = []
    for valore in valori:
        testo = str(valore or "").strip()
        if testo and testo not in puliti:
            puliti.append(testo)
    return puliti[:MASSIMO_PER_TIPO]


def riferimenti_del_testo(testo: str) -> dict[str, list[str]]:
    """Numero di ruolo, ufficio, date, importi e norme leggibili nel testo."""
    vuoto = {"numero_ruolo": [], "uffici": [], "date": [], "importi": [], "norme": []}
    grezzo = str(testo or "")
    if not grezzo.strip():
        return vuoto
    try:
        entita = extract_legal_entities(grezzo) or {}
    except Exception:
        return vuoto
    date = _elenco(entita.get("date"))
    ruoli: list[str] = []
    for voce in entita.get("numero_ruolo") or []:
        testo_ruolo = str((voce or {}).get("testo") or "").strip()
        if not testo_ruolo or testo_ruolo in ruoli:
            continue
        if any(testo_ruolo in data for data in date):
            continue
        ruoli.append(testo_ruolo)
    norme: list[str] = []
    for voce in entita.get("riferimenti_normativi") or entita.get("riferimenti") or []:
        testo_norma = str((voce or {}).get("testo") if isinstance(voce, dict) else voce or "").strip()
        if testo_norma and testo_norma not in norme:
            norme.append(testo_norma)
    return {
        "numero_ruolo": ruoli[:MASSIMO_PER_TIPO],
        "uffici": _elenco(entita.get("uffici")),
        "date": date,
        "importi": _elenco(entita.get("importi")),
        "norme": norme[:MASSIMO_PER_TIPO],
    }


__all__ = ["MASSIMO_PER_TIPO", "riferimenti_del_testo"]
