"""Surroga del mutuo — confronto tra piano attuale e offerta di portabilità.

Base normativa:
- Art. 120-quater T.U.B. (D.Lgs. 385/1993, introdotto dall'art. 4 D.Lgs.
  141/2010, che recepisce l'art. 8 D.L. 7/2007 «Bersani-bis», conv. L.
  40/2007, mod. art. 2, c. 450, L. 244/2007): portabilità del mutuo senza
  spese né oneri per il cliente; la banca subentrante paga i costi.
  Ambito soggettivo: persone fisiche e micro-imprese (comma 9, lett. a;
  def. micro-impresa: art. 1, c. 1, lett. t, D.Lgs. 11/2010).
- Art. 120-ter T.U.B.: nullità di penali o compensi per l'estinzione
  anticipata, totale o parziale, dei mutui contratti da persone fisiche
  per l'acquisto o la ristrutturazione di unità immobiliari adibite ad
  abitazione o all'esercizio della propria attività economica o
  professionale (contratti dal 2/2/2007; per i precedenti, penali ridotte
  ex accordo ABI-consumatori ai sensi dell'art. 7 D.L. 7/2007).

Il tool confronta la rata residua del mutuo in corso con la rata del mutuo
surrogato (piano francese sul debito residuo, che per legge resta invariato)
e quantifica il risparmio complessivo.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from pct.calcolatori._base import safe_float, safe_int

_FONTE_TUB_120Q = {
    "code": "tub_art_120_quater",
    "title": "Art. 120-quater T.U.B. — portabilità dei finanziamenti (surroga)",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:1993-09-01;385",
}


def _rata_francese(capitale: float, tasso_annuo: float, rate_totali: int, rate_anno: int) -> float:
    i = tasso_annuo / 100.0 / rate_anno
    if i <= 0:
        return capitale / rate_totali
    return capitale * i / (1.0 - (1.0 + i) ** (-rate_totali))


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    debito_residuo = safe_float(payload.get("sur_debito_residuo"))
    tan_attuale = safe_float(payload.get("sur_tan_attuale"))
    anni_residui = safe_int(payload.get("sur_anni_residui"))
    tan_nuovo = safe_float(payload.get("sur_tan_nuovo"))
    anni_nuovi = safe_int(payload.get("sur_anni_nuovi")) or anni_residui
    rate_anno = safe_int(payload.get("sur_rate_anno"), 12)

    if debito_residuo <= 0:
        raise ValueError("Inserisci il debito residuo del mutuo in corso.")
    for etichetta, tasso in (("attuale", tan_attuale), ("proposto", tan_nuovo)):
        if tasso < 0 or tasso > 100:
            raise ValueError(f"Il TAN {etichetta} deve essere compreso tra 0 e 100.")
    if anni_residui <= 0 or anni_residui > 50 or anni_nuovi <= 0 or anni_nuovi > 50:
        raise ValueError("Le durate devono essere comprese tra 1 e 50 anni.")
    if rate_anno not in (1, 2, 4, 6, 12):
        raise ValueError("Rate per anno ammesse: 1, 2, 4, 6, 12.")

    rate_attuali = anni_residui * rate_anno
    rate_nuove = anni_nuovi * rate_anno
    rata_attuale = _rata_francese(debito_residuo, tan_attuale, rate_attuali, rate_anno)
    rata_nuova = _rata_francese(debito_residuo, tan_nuovo, rate_nuove, rate_anno)

    totale_attuale = rata_attuale * rate_attuali
    totale_nuovo = rata_nuova * rate_nuove
    risparmio_totale = round(totale_attuale - totale_nuovo, 2)
    risparmio_rata = round(rata_attuale - rata_nuova, 2)

    warnings = [
        "Il confronto usa il TAN: chiedere alla banca subentrante anche il TAEG "
        "dell'offerta (eventuali polizze obbligatorie incidono sul costo effettivo).",
    ]
    if tan_attuale > 15 or tan_nuovo > 15:
        warnings.append(
            "Uno dei tassi supera il 15%: verificare le soglie antiusura trimestrali "
            "ex L. 108/1996 pubblicate dal MEF (art. 644 c.p.; art. 1815, c. 2, c.c.)."
        )
    if anni_nuovi > anni_residui:
        warnings.append(
            "La nuova durata è più lunga di quella residua: la rata scende ma gli "
            "interessi complessivi vanno valutati sul risparmio totale, che ne tiene conto."
        )
    if risparmio_totale <= 0:
        warnings.append("Con i dati inseriti l'offerta di surroga NON è conveniente.")

    return {
        "debito_residuo": round(debito_residuo, 2),
        "rata_attuale": round(rata_attuale, 2),
        "rata_nuova": round(rata_nuova, 2),
        "risparmio_per_rata": risparmio_rata,
        "interessi_residui_attuali": round(totale_attuale - debito_residuo, 2),
        "interessi_nuovo_piano": round(totale_nuovo - debito_residuo, 2),
        "risparmio_totale": risparmio_totale,
        "conveniente": risparmio_totale > 0,
        "numero_rate_nuove": rate_nuove,
        "notes": [
            "La surroga è gratuita per legge: nessuna penale, spesa notarile o costo "
            "di istruttoria può essere addebitato al cliente (art. 120-quater, c. 4, "
            "T.U.B.); il debito residuo trasferito resta invariato.",
            "La gratuità vale per persone fisiche e micro-imprese (art. 120-quater, "
            "c. 9, lett. a, T.U.B.); per le altre imprese la norma non si applica.",
        ],
        "warnings": warnings,
        "sources": [_FONTE_TUB_120Q],
    }
