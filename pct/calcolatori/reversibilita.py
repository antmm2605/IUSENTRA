"""Pensione di reversibilità (ai superstiti) — aliquote e cumulo redditi.

Base normativa:
- Aliquote di reversibilità: art. 22 L. 903/1965 (coniuge 60%; ciascun
  figlio 20% in concorso col coniuge, 40% se soli; genitori e fratelli o
  sorelle 15% ciascuno, nei casi di legge, con tetto del 100%) e art. 1,
  comma 41, primo periodo, L. 335/1995 (70% per il figlio unico). Ne
  derivano le combinazioni operative: 60% solo coniuge; 80% coniuge con
  un figlio; 100% coniuge con due o più figli; 70% un figlio solo; 80%
  due figli; 100% tre o più figli.
- Cumulo con i redditi del beneficiario: Tabella F allegata alla L.
  335/1995 (trattamento ridotto al 75%, 60%, 50% — cioè −25%, −40%, −50%
  — oltre 3, 4, 5 volte il trattamento minimo annuo del Fondo pensioni
  lavoratori dipendenti, pari a 13 volte l'importo mensile in vigore al
  1° gennaio). Clausola di salvaguardia (art. 1, c. 41, terzo periodo):
  il trattamento derivante dal cumulo non può essere inferiore a quello
  spettante con reddito pari al limite massimo della fascia precedente.
  Le riduzioni non operano se nel nucleo ci sono figli minori, studenti
  o inabili (art. 1, c. 41, ultimo periodo).
- Corte Cost. 162/2022: la decurtazione effettiva non può in ogni caso
  eccedere l'ammontare complessivo dei redditi aggiuntivi del
  beneficiario.

Il trattamento minimo INPS è rivalutato ogni anno con la perequazione: va
inserito dall'operatore dal comunicato/circolare INPS dell'anno di calcolo
(13 mensilità dell'importo al 1° gennaio), il tool non ne ipotizza il
valore (fail-closed).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float, safe_int

_FONTE_L335 = {
    "code": "l_335_1995_tab_f",
    "title": "L. 335/1995, art. 1 c. 41 e Tabella F — cumulo pensione ai superstiti",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1995-08-08;335",
}
_FONTE_L903 = {
    "code": "l_903_1965_art22",
    "title": "Art. 22 L. 903/1965 — aliquote della pensione ai superstiti",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1965-07-21;903",
}
_FONTE_CORTE = {
    "code": "corte_cost_162_2022",
    "title": "Corte Cost. 162/2022 — limite alla decurtazione per cumulo",
    "url": "https://www.cortecostituzionale.it/actionSchedaPronuncia.do?anno=2022&numero=162",
}


def _percentuale_fascia(reddito: float, trattamento_minimo: float) -> float:
    if reddito > 5 * trattamento_minimo:
        return 50.0
    if reddito > 4 * trattamento_minimo:
        return 40.0
    if reddito > 3 * trattamento_minimo:
        return 25.0
    return 0.0


def _aliquota(coniuge: bool, figli: int, genitori: int, fratelli: int) -> tuple[float, str]:
    if coniuge and figli >= 2:
        return 100.0, "coniuge con due o più figli"
    if coniuge and figli == 1:
        return 80.0, "coniuge con un figlio"
    if coniuge:
        return 60.0, "solo coniuge"
    if figli >= 3:
        return 100.0, "tre o più figli"
    if figli == 2:
        return 80.0, "due figli"
    if figli == 1:
        return 70.0, "un figlio"
    if genitori > 0:
        return min(15.0 * genitori, 100.0), f"{genitori} genitore/i (15% ciascuno)"
    if fratelli > 0:
        return min(15.0 * fratelli, 100.0), f"{fratelli} fratello/i o sorella/e (15% ciascuno)"
    return 0.0, "nessun superstite avente diritto indicato"


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    pensione = safe_float(payload.get("rev_pensione_annua"))
    coniuge = clean_text(payload.get("rev_coniuge")) == "1"
    figli = safe_int(payload.get("rev_figli"))
    genitori = safe_int(payload.get("rev_genitori"))
    fratelli = safe_int(payload.get("rev_fratelli"))
    reddito = safe_float(payload.get("rev_reddito_beneficiario"))
    trattamento_minimo = safe_float(payload.get("rev_trattamento_minimo"))
    figli_tutelati = clean_text(payload.get("rev_figli_tutelati")) == "1"

    if pensione <= 0:
        raise ValueError("Inserisci la pensione annua (o quota) del dante causa.")
    if figli < 0 or genitori < 0 or fratelli < 0:
        raise ValueError("I contatori dei superstiti non possono essere negativi.")
    if figli > 15 or genitori > 2 or fratelli > 15:
        raise ValueError("Verifica i contatori dei superstiti: valori fuori range.")

    aliquota, composizione = _aliquota(coniuge, figli, genitori, fratelli)
    if aliquota <= 0:
        raise ValueError(
            "Indica almeno un superstite (coniuge, figli, oppure genitori/fratelli nei casi di legge)."
        )

    lorda = pensione * aliquota / 100.0

    fascia = "nessuna riduzione"
    warnings: List[str] = []
    notes: List[str] = [
        f"Aliquota {aliquota:g}% ({composizione}) ex art. 22 L. 903/1965 e "
        "art. 1, c. 41, L. 335/1995.",
    ]

    applica_cumulo = reddito > 0 and not figli_tutelati and figli == 0
    if reddito > 0 and (figli > 0 or figli_tutelati):
        notes.append(
            "Riduzioni per cumulo non applicate: presenza di figli nel nucleo "
            "(minori, studenti o inabili) esclude la decurtazione "
            "(art. 1, c. 41, ultimo periodo, L. 335/1995)."
        )

    netta = lorda
    if applica_cumulo:
        if trattamento_minimo <= 0:
            raise ValueError(
                "Per la verifica del cumulo serve il trattamento minimo INPS annuo "
                "dell'anno di calcolo: 13 volte l'importo mensile del trattamento "
                "minimo FPLD in vigore al 1° gennaio (Tabella F, L. 335/1995)."
            )

        def _trattamento(reddito_cumulo: float) -> float:
            """Trattamento spettante a un dato reddito, con salvaguardia di fascia.

            Tabella F L. 335/1995 (−25/−40/−50% oltre 3/4/5 volte il minimo) e
            art. 1, c. 41, terzo periodo: il trattamento non può essere inferiore
            a quello spettante con reddito pari al limite massimo della fascia
            precedente, applicato in cascata.
            """

            fasce = [
                (3 * trattamento_minimo, 25.0),
                (4 * trattamento_minimo, 40.0),
                (5 * trattamento_minimo, 50.0),
            ]
            corrente = None
            for soglia_fascia, percentuale in fasce:
                if reddito_cumulo > soglia_fascia:
                    corrente = (soglia_fascia, percentuale)
            if corrente is None:
                return lorda
            soglia_fascia, percentuale = corrente
            pieno = lorda * (1.0 - percentuale / 100.0)
            salvaguardia = _trattamento(soglia_fascia) - (reddito_cumulo - soglia_fascia)
            return max(pieno, salvaguardia)

        netta = _trattamento(reddito)
        if reddito > 5 * trattamento_minimo:
            fascia = "reddito oltre 5 volte il trattamento minimo"
        elif reddito > 4 * trattamento_minimo:
            fascia = "reddito oltre 4 volte il trattamento minimo"
        elif reddito > 3 * trattamento_minimo:
            fascia = "reddito oltre 3 volte il trattamento minimo"

        if netta > lorda * (1.0 - _percentuale_fascia(reddito, trattamento_minimo) / 100.0) + 0.005:
            warnings.append(
                "Riduzione limitata dalla clausola di salvaguardia di fascia "
                "(art. 1, c. 41, terzo periodo, L. 335/1995)."
            )
        # Corte Cost. 162/2022: la decurtazione non può eccedere i redditi aggiuntivi.
        if lorda - netta > reddito:
            netta = lorda - reddito
            warnings.append(
                "Decurtazione limitata all'ammontare complessivo dei redditi "
                "aggiuntivi del beneficiario (Corte Cost. 162/2022)."
            )

    riduzione_importo = round(lorda - netta, 2)

    warnings.append(
        "Stima civilistica di massima: il calcolo INPS effettivo applica la "
        "perequazione, i redditi rilevanti in dettaglio e le decorrenze; "
        "verificare sempre con l'estratto e le circolari INPS dell'anno."
    )

    return {
        "composizione": composizione,
        "aliquota": aliquota,
        "pensione_dante_causa": round(pensione, 2),
        "reversibilita_lorda": round(lorda, 2),
        "fascia_cumulo": fascia,
        "riduzione_cumulo": round(riduzione_importo, 2),
        "reversibilita_spettante": round(netta, 2),
        "reversibilita_mensile_13": round(netta / 13.0, 2),
        "notes": notes,
        "warnings": warnings,
        "sources": [_FONTE_L903, _FONTE_L335, _FONTE_CORTE],
    }
