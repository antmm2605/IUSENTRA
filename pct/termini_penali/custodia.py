"""Durata massima della custodia cautelare (art. 303 c.p.p.).

Termini di fase (c. 1), calcolati sulla pena edittale massima del delitto (lett. a, b, b-bis) o sulla
pena inflitta con la sentenza di condanna (lett. c, d), e durata complessiva (c. 4):

- a) dall'inizio dell'esecuzione senza provvedimento che dispone il giudizio, ordinanza di giudizio
  abbreviato o sentenza di patteggiamento: 3 mesi (reclusione non superiore nel massimo a 6 anni),
  6 mesi (superiore a 6 anni), 1 anno (ergastolo o reclusione non inferiore nel massimo a 20 anni, o
  delitti dell'art. 407 c. 2 lett. a punti con reclusione superiore nel massimo a 6 anni);
- b) dal provvedimento che dispone il giudizio senza condanna di primo grado: 6 mesi (fino a 6 anni),
  1 anno (fino a 20 anni), 1 anno e 6 mesi (ergastolo o oltre 20 anni); per i delitti dell'art. 407
  c. 2 lett. a i termini sono aumentati fino a sei mesi (n. 3-bis);
- b-bis) dall'ordinanza che dispone il giudizio abbreviato senza condanna: 3, 6 e 9 mesi con le stesse
  fasce;
- c) e d) dalla condanna di primo grado (o di appello) senza condanna in appello (o irrevocabile):
  9 mesi (condanna non superiore a 3 anni), 1 anno (non superiore a 10 anni), 1 anno e 6 mesi
  (ergastolo o oltre 10 anni);
- c. 4) durata complessiva: 2, 4 e 6 anni con le fasce di pena edittale di 6 e 20 anni.

Il modulo non applica le sospensioni (art. 304), le proroghe (art. 305), la retrodatazione per
contestazioni a catena (art. 297 c. 3) né il computo della custodia sofferta all'estero: li dichiara.
La sospensione feriale non riguarda la durata della custodia.
"""

from __future__ import annotations

from typing import Any, Mapping

from pct.calcolatori._base import clean_text, parse_date, safe_bool, safe_int
from pct.termini_penali.calendario import fmt, oggi, sospensione_feriale, termine_mesi

FASI = {
    "indagini": "Indagini: nessun provvedimento che dispone il giudizio (lett. a)",
    "giudizio": "Giudizio di primo grado senza condanna (lett. b)",
    "abbreviato": "Giudizio abbreviato senza condanna (lett. b-bis)",
    "appello": "Dopo la condanna di primo grado, senza condanna in appello (lett. c)",
    "cassazione": "Dopo la condanna in appello, senza sentenza irrevocabile (lett. d)",
}


def _mesi(anni: Any, mesi: Any) -> int:
    return max(0, safe_int(anni)) * 12 + max(0, safe_int(mesi))


def _termine_fase(fase: str, edittale: int, ergastolo: bool, delitto_407: bool, condanna: int, condanna_ergastolo: bool) -> tuple[int, str]:
    if fase == "indagini":
        if ergastolo or edittale >= 240 or (delitto_407 and edittale > 72):
            return 12, "art. 303 c. 1 lett. a) n. 3"
        return (6, "art. 303 c. 1 lett. a) n. 2") if edittale > 72 else (3, "art. 303 c. 1 lett. a) n. 1")
    if fase in {"giudizio", "abbreviato"}:
        tabella = {"giudizio": (6, 12, 18), "abbreviato": (3, 6, 9)}[fase]
        lettera = "b)" if fase == "giudizio" else "b-bis)"
        if ergastolo or edittale > 240:
            return tabella[2], f"art. 303 c. 1 lett. {lettera} n. 3"
        return (tabella[1], f"art. 303 c. 1 lett. {lettera} n. 2") if edittale > 72 else (tabella[0], f"art. 303 c. 1 lett. {lettera} n. 1")
    lettera = "c)" if fase == "appello" else "d)"
    if condanna_ergastolo or condanna > 120:
        return 18, f"art. 303 c. 1 lett. {lettera} n. 3"
    return (12, f"art. 303 c. 1 lett. {lettera} n. 2") if condanna > 36 else (9, f"art. 303 c. 1 lett. {lettera} n. 1")


def _complessivo(edittale: int, ergastolo: bool) -> tuple[int, str]:
    if ergastolo or edittale > 240:
        return 72, "art. 303 c. 4 lett. c)"
    return (48, "art. 303 c. 4 lett. b)") if edittale > 72 else (24, "art. 303 c. 4 lett. a)")


def calcola(dati: Mapping[str, Any]) -> dict[str, Any]:
    fase = clean_text(dati.get("cus_fase")) or "indagini"
    if fase not in FASI:
        raise ValueError("Fase non riconosciuta.")
    inizio_fase = parse_date(dati.get("cus_data_inizio_fase"))
    inizio = parse_date(dati.get("cus_data_inizio_esecuzione")) or inizio_fase
    if not inizio_fase:
        raise ValueError("Inserisci la data da cui decorre la fase (esecuzione, rinvio a giudizio o sentenza).")
    ergastolo = safe_bool(dati.get("cus_ergastolo"))
    edittale = _mesi(dati.get("cus_pena_massima_anni"), dati.get("cus_pena_massima_mesi"))
    if not ergastolo and edittale <= 0:
        raise ValueError("Indica la pena massima prevista dalla legge per il delitto (o l'ergastolo).")
    condanna = _mesi(dati.get("cus_condanna_anni"), dati.get("cus_condanna_mesi"))
    condanna_ergastolo = safe_bool(dati.get("cus_condanna_ergastolo"))
    if fase in {"appello", "cassazione"} and not condanna and not condanna_ergastolo:
        raise ValueError("Per questa fase indica la pena inflitta con la sentenza di condanna.")
    delitto_407 = safe_bool(dati.get("cus_delitto_407"))
    nessuna = sospensione_feriale(non_processuale=True)
    mesi_fase, norma_fase = _termine_fase(fase, edittale, ergastolo, delitto_407, condanna, condanna_ergastolo)
    avvisi: list[str] = []
    if fase == "giudizio" and delitto_407:
        avvisi.append("Delitto dell'art. 407 c. 2 lett. a): il termine di fase è aumentato fino a sei mesi e l'aumento si "
                      "imputa alla fase precedente o alla lett. d) (art. 303 c. 1 lett. b n. 3-bis). Non è sommato qui.")
    fase_scade = termine_mesi(inizio_fase, mesi_fase, nessuna, "inizio della fase")
    mesi_tot, norma_tot = _complessivo(edittale, ergastolo)
    totale = termine_mesi(inizio, mesi_tot, nessuna, "inizio dell'esecuzione della custodia")
    adesso = oggi()
    termini = [
        {"termine": FASI[fase], "durata": f"{mesi_fase} mesi", "scadenza": fmt(fase_scade.scadenza), "norma": norma_fase},
        {"termine": "Durata complessiva della custodia", "durata": f"{mesi_tot // 12} anni", "scadenza": fmt(totale.scadenza),
         "norma": norma_tot},
    ]
    prima = min(fase_scade.scadenza, totale.scadenza)
    return {
        "fase": FASI[fase],
        "scadenza_fase": fmt(fase_scade.scadenza),
        "scadenza_complessiva": fmt(totale.scadenza),
        "prima_scadenza": fmt(prima),
        "stato": "termine superato: la misura perde efficacia (art. 306)" if prima < adesso else f"{(prima - adesso).days} giorni alla prima scadenza",
        "termini": termini,
        "scadenze_proposte": [
            {"titolo": "Scadenza del termine di fase della custodia cautelare", "data": fase_scade.scadenza.isoformat(), "norma": norma_fase},
            {"titolo": "Durata complessiva della custodia cautelare", "data": totale.scadenza.isoformat(), "norma": norma_tot},
        ],
        "notes": [
            "Pena edittale: massimo previsto dalla legge per il delitto, considerando le aggravanti a effetto speciale "
            "e quelle per cui la legge prevede una pena di specie diversa (art. 278 c.p.p.).",
            "La durata della custodia non è sospesa nel periodo feriale.",
        ],
        "warnings": avvisi + ["Non sono calcolate sospensioni (art. 304), proroghe (art. 305) e retrodatazione per "
                              "contestazioni a catena (art. 297 c. 3): se ricorrono, aggiorna le date."],
    }


__all__ = ["FASI", "calcola"]
