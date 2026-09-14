"""Riferimenti giuridici trovati nel testo riconosciuto.

Dopo il riconoscimento la prima domanda dell'avvocato e' sempre la stessa: e'
il documento giusto? Il numero di ruolo, l'ufficio e la data di udienza sono la
risposta piu' rapida, e leggerli in cima al risultato evita di scorrere
l'intero atto per accorgersi che si e' aperto il fascicolo sbagliato.

Gli estrattori sono quelli della pipeline probatoria (`legal_ocr.ner_legal`),
gia' usati sui documenti acquisiti: qui servono come indicazione di lettura,
non come dato certificato, e la pagina li presenta per quello che sono.

Un accorgimento necessario: una data come «12/03/2026» contiene «12/03», che ha
la stessa forma di un numero di ruolo. I numeri di ruolo che compaiono dentro
una data riconosciuta vengono scartati, perche' un riferimento sbagliato in
cima al documento e' peggio di nessun riferimento.
"""

from __future__ import annotations

from typing import Any

from legal_ocr.ner_legal import extract_legal_entities

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
    """Numero di ruolo, ufficio, date e importi leggibili nel testo riconosciuto."""
    grezzo = str(testo or "")
    if not grezzo.strip():
        return {"numero_ruolo": [], "uffici": [], "date": [], "importi": []}
    try:
        entita = extract_legal_entities(grezzo) or {}
    except Exception:
        # I riferimenti sono un aiuto alla lettura: la loro assenza non deve
        # mai impedire all'avvocato di vedere il testo riconosciuto.
        return {"numero_ruolo": [], "uffici": [], "date": [], "importi": []}
    date = _elenco(entita.get("date"))
    ruoli: list[str] = []
    for voce in entita.get("numero_ruolo") or []:
        testo_ruolo = str((voce or {}).get("testo") or "").strip()
        if not testo_ruolo or testo_ruolo in ruoli:
            continue
        if any(testo_ruolo in data for data in date):
            continue
        ruoli.append(testo_ruolo)
    return {
        "numero_ruolo": ruoli[:MASSIMO_PER_TIPO],
        "uffici": _elenco(entita.get("uffici")),
        "date": date,
        "importi": _elenco(entita.get("importi")),
    }


__all__ = ["MASSIMO_PER_TIPO", "riferimenti_del_testo"]
