"""Durata delle indagini preliminari dopo la riforma Cartabia (D.Lgs. 150/2022).

- Art. 405 c. 2 c.p.p.: il pubblico ministero conclude le indagini entro un anno dall'iscrizione del nome
  nel registro delle notizie di reato; sei mesi per le contravvenzioni; un anno e sei mesi per i delitti
  dell'art. 407 c. 2.
- Art. 406 c. 1-2: una sola proroga, per indagini complesse, per non più di sei mesi.
- Art. 407 c. 1-2: durata massima diciotto mesi (un anno per le contravvenzioni), due anni nei casi del
  comma 2. C. 3: gli atti compiuti dopo la scadenza non sono utilizzabili.
- Art. 407-bis c. 2: azione penale o richiesta di archiviazione entro tre mesi dalla scadenza del termine
  dell'art. 405 c. 2 o, se è stato notificato l'avviso ex art. 415-bis, dalla scadenza dei termini dei
  commi 3 e 4 di quell'articolo; nove mesi nei casi dell'art. 407 c. 2.
- Art. 415-bis c. 3: venti giorni per memorie, documenti e richiesta di interrogatorio.
- Art. 240-bis disp. att. c.p.p. (art. 2 L. 742/1969): la sospensione feriale vale anche per i termini
  delle indagini preliminari.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from pct.calcolatori._base import clean_text, parse_date, safe_bool
from pct.termini_penali.calendario import fmt, oggi, sospensione_feriale, termine_giorni, termine_mesi

TIPI = {
    "contravvenzione": {"etichetta": "Contravvenzione", "ordinario": 6, "massimo": 12, "decisione": 3},
    "delitto": {"etichetta": "Delitto", "ordinario": 12, "massimo": 18, "decisione": 3},
    "delitto_407": {"etichetta": "Delitto dell'art. 407 c. 2 c.p.p.", "ordinario": 18, "massimo": 24, "decisione": 9},
}


def calcola(dati: Mapping[str, Any]) -> dict[str, Any]:
    iscrizione = parse_date(dati.get("ind_data_iscrizione"))
    if not iscrizione:
        raise ValueError("Inserisci la data di iscrizione del nome nel registro delle notizie di reato.")
    tipo = clean_text(dati.get("ind_tipo")) or "delitto"
    if tipo not in TIPI:
        raise ValueError("Tipo di reato non riconosciuto.")
    voce = TIPI[tipo]
    sospensione = sospensione_feriale(
        detenuto_con_rinuncia=safe_bool(dati.get("tp_detenuto_rinuncia")),
        criminalita_organizzata=safe_bool(dati.get("tp_criminalita_organizzata")),
    )
    ordinario = termine_mesi(iscrizione, voce["ordinario"], sospensione, "iscrizione nel registro (art. 335)")
    massimo = termine_mesi(iscrizione, voce["massimo"], sospensione, "iscrizione nel registro (art. 335)")
    proroga = safe_bool(dati.get("ind_proroga"))
    chiusura = massimo if proroga else ordinario
    scadenze = [
        {"titolo": "Scadenza del termine delle indagini (art. 405 c. 2)", "data": ordinario.scadenza.isoformat(),
         "norma": "art. 405 c. 2 c.p.p."},
        {"titolo": "Durata massima delle indagini (art. 407)", "data": massimo.scadenza.isoformat(),
         "norma": "art. 407 c.p.p."},
    ]
    termini = [
        {"termine": "Termine ordinario (art. 405 c. 2)", "durata": f"{voce['ordinario']} mesi", "scadenza": fmt(ordinario.scadenza)},
        {"termine": "Con la proroga, una sola volta per 6 mesi (art. 406)", "durata": f"{voce['massimo']} mesi",
         "scadenza": fmt(massimo.scadenza)},
        {"termine": "Durata massima (art. 407)", "durata": f"{voce['massimo']} mesi", "scadenza": fmt(massimo.scadenza)},
    ]
    avviso = parse_date(dati.get("ind_data_avviso_415bis"))
    note = [sospensione.motivo,
            "Gli atti di indagine compiuti dopo la scadenza non sono utilizzabili (art. 407 c. 3)."]
    if avviso:
        memorie = termine_giorni(avviso, 20, sospensione, "notificazione dell'avviso ex art. 415-bis")
        termini.append({"termine": "Memorie e richiesta di interrogatorio (art. 415-bis c. 3)", "durata": "20 giorni",
                        "scadenza": fmt(memorie.scadenza)})
        scadenze.append({"titolo": "Memorie dopo l'avviso di conclusione indagini (art. 415-bis)",
                         "data": memorie.scadenza.isoformat(), "norma": "art. 415-bis c. 3 c.p.p."})
        base_decisione, descrizione = memorie.scadenza, "scadenza dei termini dell'art. 415-bis"
        note.append("Se è stato chiesto l'interrogatorio o sono state presentate richieste di indagine, i termini "
                    "dell'art. 415-bis c. 4 possono spostare la decorrenza: aggiorna la data di conseguenza.")
    else:
        base_decisione, descrizione = chiusura.scadenza, "scadenza del termine delle indagini"
    decisione = termine_mesi(base_decisione, voce["decisione"], sospensione, descrizione)
    termini.append({"termine": "Azione penale o richiesta di archiviazione (art. 407-bis c. 2)",
                    "durata": f"{voce['decisione']} mesi", "scadenza": fmt(decisione.scadenza)})
    scadenze.append({"titolo": "Termine per l'esercizio dell'azione penale o l'archiviazione (art. 407-bis)",
                     "data": decisione.scadenza.isoformat(), "norma": "art. 407-bis c. 2 c.p.p."})
    adesso = oggi()
    return {
        "reato": voce["etichetta"],
        "iscrizione": fmt(iscrizione),
        "proroga_concessa": "sì" if proroga else "no",
        "chiusura_indagini": fmt(chiusura.scadenza),
        "stato": "indagini scadute" if chiusura.scadenza < adesso else "indagini in corso",
        "termini": termini,
        "passaggi": chiusura.passi,
        "scadenze_proposte": scadenze,
        "notes": note,
        "warnings": ["La data di iscrizione è quella del nome dell'indagato nel registro (art. 335): se il giudice "
                     "ne ha retrodatato l'iscrizione (art. 335-quater) usa la data stabilita."],
    }


__all__ = ["TIPI", "calcola"]
