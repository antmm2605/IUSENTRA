"""Improcedibilità per superamento dei termini del giudizio di impugnazione (art. 344-bis c.p.p.).

- C. 1-2: due anni per il giudizio di appello, un anno per quello di cassazione.
- C. 3: i termini decorrono dal novantesimo giorno successivo alla scadenza del termine per il deposito
  della motivazione (art. 544, come eventualmente prorogato ex art. 154 disp. att.).
- C. 4: proroga con ordinanza per giudizi complessi fino a un anno in appello e sei mesi in cassazione;
  ulteriori proroghe per i delitti gravi ivi indicati.
- C. 6: i termini sono sospesi nei casi dell'art. 159 c. 1 c.p., per la rinnovazione dell'istruttoria
  (fino a 60 giorni) e per le nuove ricerche dell'imputato.
- Art. 2 L. 134/2021: si applica ai reati commessi dal 1° gennaio 2020 (c. 3); per le impugnazioni
  proposte entro il 31 dicembre 2024 i termini sono di tre anni in appello e di un anno e sei mesi in
  cassazione (c. 5); se gli atti erano già pervenuti al giudice dell'impugnazione il 19/10/2021, i termini
  decorrono da quella data (c. 4).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping

from pct.calcolatori._base import clean_text, parse_date, safe_bool, safe_int
from pct.termini_penali.calendario import aggiungi_mesi, fmt, oggi, sospensione_feriale, termine_giorni

INIZIO_APPLICAZIONE = date(2020, 1, 1)
FINE_TRANSITORIO = date(2024, 12, 31)
ENTRATA_IN_VIGORE = date(2021, 10, 19)


def calcola(dati: Mapping[str, Any]) -> dict[str, Any]:
    fatto = parse_date(dati.get("imp_data_fatto"))
    if not fatto:
        raise ValueError("Inserisci la data del fatto.")
    if fatto < INIZIO_APPLICAZIONE:
        raise ValueError("L'improcedibilità dell'art. 344-bis si applica ai reati commessi dal 1° gennaio 2020 "
                         "(art. 2 c. 3 L. 134/2021): per i fatti precedenti vale la prescrizione.")
    grado = clean_text(dati.get("imp_grado")) or "appello"
    if grado not in {"appello", "cassazione"}:
        raise ValueError("Grado non riconosciuto.")
    pronuncia = parse_date(dati.get("imp_data_pronuncia"))
    if not pronuncia:
        raise ValueError("Inserisci la data della sentenza impugnata.")
    giorni_motivazione = safe_int(dati.get("imp_giorni_motivazione"), 15) or 15
    if not 0 <= giorni_motivazione <= 90:
        raise ValueError("Il termine per la motivazione va da 0 (contestuale) a 90 giorni (art. 544 c.p.p.).")
    proposta = parse_date(dati.get("imp_data_impugnazione"))
    passi: list[dict[str, str]] = []
    if giorni_motivazione:
        deposito = termine_giorni(pronuncia, giorni_motivazione, sospensione_feriale(), "pronuncia della sentenza")
        passi += deposito.passi
        scadenza_motivazione = deposito.scadenza
    else:
        scadenza_motivazione = pronuncia
        passi.append({"passaggio": "Motivazione contestuale: nessun termine di deposito", "data": fmt(pronuncia)})
    decorrenza = scadenza_motivazione + timedelta(days=90)
    passi.append({"passaggio": "Novantesimo giorno dalla scadenza del termine per la motivazione (art. 344-bis c. 3)",
                  "data": fmt(decorrenza)})
    if safe_bool(dati.get("imp_atti_pervenuti_prima")) and decorrenza < ENTRATA_IN_VIGORE:
        decorrenza = ENTRATA_IN_VIGORE
        passi.append({"passaggio": "Atti già pervenuti al 19/10/2021: decorrenza dall'entrata in vigore (art. 2 c. 4 L. 134/2021)",
                      "data": fmt(decorrenza)})
    transitorio = bool(proposta and proposta <= FINE_TRANSITORIO)
    if grado == "appello":
        mesi, norma = (36, "art. 2 c. 5 L. 134/2021") if transitorio else (24, "art. 344-bis c. 1 c.p.p.")
    else:
        mesi, norma = (18, "art. 2 c. 5 L. 134/2021") if transitorio else (12, "art. 344-bis c. 2 c.p.p.")
    if not proposta:
        avviso_transitorio = "Indica la data dell'impugnazione: se proposta entro il 31/12/2024 i termini sono più lunghi."
    else:
        avviso_transitorio = ""
    proroghe = max(0, safe_int(dati.get("imp_proroghe_mesi")))
    sospensione = max(0, safe_int(dati.get("imp_giorni_sospensione")))
    fine = aggiungi_mesi(decorrenza, mesi + proroghe) + timedelta(days=sospensione)
    passi.append({"passaggio": f"Termine di {mesi} mesi ({norma})" + (f" + {proroghe} mesi di proroga" if proroghe else "")
                  + (f" + {sospensione} giorni di sospensione" if sospensione else ""), "data": fmt(fine)})
    adesso = oggi()
    avvisi = [a for a in (avviso_transitorio,) if a]
    avvisi.append("Il termine non si applica ai delitti puniti con l'ergastolo (art. 344-bis c. 9): verificare.")
    return {
        "grado": "Giudizio di appello" if grado == "appello" else "Giudizio di cassazione",
        "decorrenza": fmt(decorrenza),
        "termine": f"{mesi} mesi" + (f" + {proroghe} di proroga" if proroghe else ""),
        "improcedibilita_dal": fmt(fine + timedelta(days=1)),
        "definizione_entro": fmt(fine),
        "stato": "termine superato" if fine < adesso else f"{(fine - adesso).days} giorni residui",
        "passaggi": passi,
        "scadenze_proposte": [{"titolo": f"Termine massimo del giudizio di {grado} (art. 344-bis)", "data": fine.isoformat(),
                               "norma": norma}],
        "notes": [
            "La sospensione feriale non è applicata: il termine misura la durata del giudizio.",
            "Le proroghe (c. 4) e le sospensioni (c. 6) vanno indicate come risultano dalle ordinanze e dai verbali.",
        ],
        "warnings": avvisi,
    }


__all__ = ["calcola"]
