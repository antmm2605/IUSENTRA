"""Prescrizione del reato: calendario e regimi dopo la sentenza di primo grado.

- Art. 157 c.p. (L. 251/2005): tempo pari al massimo della pena edittale, non inferiore a 6 anni per i
  delitti e a 4 per le contravvenzioni; termini raddoppiati nei casi dei commi 6 e 7; imprescrittibili i
  reati puniti con l'ergastolo. Art. 158: decorrenza. Art. 161 c. 2: l'interruzione non può aumentare il
  termine di più di un quarto, della metà (recidiva aggravata art. 99 c. 2 e reati contro la P.A. ivi
  richiamati), di due terzi (recidiva reiterata art. 99 c. 4), del doppio (delinquenti abituali o
  professionali); nessun limite per i reati dell'art. 51 c. 3-bis e 3-quater c.p.p.
- Reati commessi dal 3 agosto 2017 al 31 dicembre 2019 (L. 103/2017, art. 159 c. 2-3 nel testo allora
  vigente): il corso della prescrizione è sospeso dal termine per il deposito della motivazione della
  condanna di primo grado fino alla pronuncia del dispositivo di appello, e da quello della condanna in
  appello fino al dispositivo definitivo, ciascuno per non più di un anno e sei mesi. Regime confermato
  per questi reati da Cass. Sez. Un. n. 20989/2025 e da Corte cost. n. 38/2026.
- Reati commessi dal 1° gennaio 2020 (L. 3/2019, poi L. 134/2021, art. 161-bis c.p.): il corso della
  prescrizione cessa definitivamente con la sentenza di primo grado, salvo annullamento con regressione;
  nei giudizi di impugnazione opera l'improcedibilità dell'art. 344-bis c.p.p.
- Il disegno di legge sulla prescrizione (A.C. 893, approvato dalla Camera il 16/01/2024) risultava
  all'esame del Senato alla data di consultazione (29/09/2026): se diventa legge va aggiunto un regime.
"""

from __future__ import annotations

from datetime import date, timedelta
from fractions import Fraction
from typing import Any, Mapping

from pct.calcolatori._base import clean_text, parse_date
from pct.termini_penali.calendario import aggiungi_mesi, fmt

INIZIO_ORLANDO = date(2017, 8, 3)
INIZIO_BLOCCO = date(2020, 1, 1)
CIRIELLI = date(2005, 12, 8)

INTERRUZIONI = {
    "quarto": (Fraction(5, 4), "Aumento di un quarto (art. 161 c. 2)"),
    "meta": (Fraction(3, 2), "Aumento della metà: recidiva aggravata o reati contro la P.A. richiamati (art. 161 c. 2)"),
    "due_terzi": (Fraction(5, 3), "Aumento di due terzi: recidiva reiterata (art. 161 c. 2)"),
    "doppio": (Fraction(2, 1), "Raddoppio: delinquente abituale o professionale (art. 161 c. 2)"),
    "nessun_limite": (None, "Nessun limite: reati dell'art. 51 c. 3-bis e 3-quater c.p.p."),
}


def aggiungi_periodo(inizio: date, mesi: Fraction) -> date:
    """Mesi interi a calendario; la frazione di mese residua in giorni (mese di trenta giorni)."""
    interi = int(mesi)
    giorni = round((mesi - interi) * 30)
    return aggiungi_mesi(inizio, interi) + timedelta(days=giorni)


def regime(data_fatto: date) -> str:
    if data_fatto >= INIZIO_BLOCCO:
        return "dal_2020"
    if data_fatto >= INIZIO_ORLANDO:
        return "orlando"
    return "ordinario"


def _sospensione_orlando(inizio: date | None, fine: date | None, grado: str) -> tuple[int, dict[str, str] | None]:
    if not inizio:
        return 0, None
    tetto = aggiungi_mesi(inizio, 18)
    if fine:
        effettiva = min(fine, tetto)
        giorni = max(0, (effettiva - inizio).days)
        return giorni, {"periodo": f"Sospensione dopo la condanna {grado}", "dal": fmt(inizio), "al": fmt(effettiva),
                        "giorni": str(giorni)}
    giorni = (tetto - inizio).days
    return giorni, {"periodo": f"Sospensione dopo la condanna {grado} (dispositivo non ancora pronunciato: massimo)",
                    "dal": fmt(inizio), "al": fmt(tetto), "giorni": str(giorni)}


def dopo_la_sentenza(data_fatto: date, dati: Mapping[str, Any], data_massima: date | None) -> dict[str, Any]:
    """Effetti della sentenza di primo grado e dei gradi successivi, secondo il regime del reato."""
    tipo = regime(data_fatto)
    esito: dict[str, Any] = {"regime": tipo, "giorni_aggiunti": 0, "periodi": [], "note": [], "avvisi": []}
    if data_fatto < CIRIELLI:
        esito["avvisi"].append("Fatto anteriore all'8/12/2005: confrontare con la disciplina previgente alla L. 251/2005 "
                               "e applicare quella più favorevole (art. 2 c. 4 c.p.; art. 10 L. 251/2005).")
    if tipo == "orlando":
        esito["etichetta"] = "Reato commesso tra il 3/8/2017 e il 31/12/2019: sospensioni della L. 103/2017"
        giorni1, periodo1 = _sospensione_orlando(parse_date(dati.get("presc_scadenza_motivazione_primo")),
                                                 parse_date(dati.get("presc_dispositivo_appello")), "di primo grado")
        giorni2, periodo2 = _sospensione_orlando(parse_date(dati.get("presc_scadenza_motivazione_appello")),
                                                 parse_date(dati.get("presc_dispositivo_cassazione")), "in appello")
        esito["giorni_aggiunti"] = giorni1 + giorni2
        esito["periodi"] = [p for p in (periodo1, periodo2) if p]
        esito["note"].append("Sospensione dal termine per il deposito della motivazione della condanna fino al dispositivo "
                             "del grado successivo, per non più di un anno e sei mesi per grado (art. 159 c. 2 c.p. nel testo "
                             "della L. 103/2017; Cass. Sez. Un. 20989/2025; Corte cost. 38/2026).")
        esito["note"].append("Se il grado successivo proscioglie o annulla la condanna, i periodi di sospensione si "
                             "computano di nuovo nel termine (art. 159 c. 3 nel testo della L. 103/2017).")
        if not periodo1:
            esito["avvisi"].append("Senza condanna di primo grado non c'è sospensione: se interviene, indica la scadenza del "
                                   "termine per il deposito della motivazione.")
    elif tipo == "dal_2020":
        esito["etichetta"] = "Reato commesso dal 1/1/2020: la prescrizione si ferma con la sentenza di primo grado (art. 161-bis c.p.)"
        sentenza = parse_date(dati.get("presc_data_sentenza_primo_grado"))
        if sentenza:
            if data_massima and data_massima <= sentenza:
                esito["blocco"] = f"Prescrizione maturata il {fmt(data_massima)}, prima della sentenza di primo grado del {fmt(sentenza)}"
            else:
                esito["blocco"] = f"Il corso della prescrizione è cessato con la sentenza di primo grado del {fmt(sentenza)}"
                esito["cessata"] = True
        esito["note"].append("Dopo la sentenza di primo grado, nei giudizi di impugnazione vale l'improcedibilità per "
                             "superamento dei termini dell'art. 344-bis c.p.p. (strumento «Improcedibilità in appello e "
                             "cassazione»). In caso di annullamento con regressione la prescrizione riprende a decorrere.")
    else:
        esito["etichetta"] = "Reato commesso prima del 3/8/2017: nessuna sospensione legata alla sentenza"
    esito["avvisi"].append("Riforma della prescrizione (A.C. 893) all'esame del Senato alla data di consultazione del "
                           "29/09/2026: se approvata, il regime va aggiornato.")
    return esito


def coefficiente(dati: Mapping[str, Any]) -> tuple[Fraction | None, str] | None:
    scelta = clean_text(dati.get("presc_interruzione"))
    return INTERRUZIONI.get(scelta) if scelta else None


__all__ = ["INTERRUZIONI", "aggiungi_periodo", "coefficiente", "dopo_la_sentenza", "regime"]
