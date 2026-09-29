"""Termini per impugnare e opporsi nel processo penale.

Base normativa (testi vigenti consultati il 29/09/2026, riferimenti in
docs/specs/ministero/fonti_ufficiali/2026-09-29/penale/README.md):

- Art. 585 c.p.p. (mod. D.Lgs. 150/2022): 15 giorni per i provvedimenti emessi in camera di consiglio e
  per la motivazione contestuale (art. 544 c. 1); 30 giorni quando la motivazione è depositata entro
  15 giorni (art. 544 c. 2); 45 giorni quando il giudice fissa un termine più lungo, non oltre 90 giorni
  (art. 544 c. 3). C. 1-bis: +15 giorni per l'impugnazione del difensore dell'imputato giudicato in
  assenza. C. 2: decorrenza dalla notificazione o comunicazione dell'avviso di deposito (camera di
  consiglio), dalla lettura (motivazione contestuale), dalla scadenza del termine per il deposito o,
  se la sentenza è depositata oltre il termine (art. 548 c. 2), dalla notificazione o comunicazione
  dell'avviso di deposito. C. 4: motivi nuovi fino a 15 giorni prima dell'udienza.
- Art. 461 c.p.p.: opposizione al decreto penale di condanna entro 15 giorni dalla notificazione.
- Art. 309 c.p.p.: riesame delle ordinanze che dispongono una misura coercitiva, 10 giorni
  dall'esecuzione o notificazione. Art. 310: appello cautelare, 10 giorni. Art. 311: ricorso per
  cassazione, 10 giorni dalla comunicazione o notificazione dell'avviso di deposito.
- Art. 324 c.p.p.: riesame delle misure cautelari reali, 10 giorni dall'esecuzione o dalla diversa data
  di conoscenza; art. 322-bis: appello reale (rinvio all'art. 310).
- Art. 415-bis c. 3 c.p.p.: 20 giorni dalla notifica dell'avviso di conclusione delle indagini per
  memorie, documenti, richiesta di interrogatorio.
- Art. 408 c. 3 e 3-bis c.p.p.: opposizione alla richiesta di archiviazione entro 20 giorni, 30 per i
  delitti commessi con violenza alla persona e per il furto in abitazione e con strappo.
- Art. 172 c.p.p. e L. 742/1969 per il computo (pct.termini_penali.calendario).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping

from pct.calcolatori._base import clean_text, parse_date, safe_bool, safe_int
from pct.termini_penali.calendario import fmt, oggi, sospensione_feriale, termine_giorni

ATTI: dict[str, dict[str, Any]] = {
    "impugnazione_sentenza": {"etichetta": "Appello o ricorso per cassazione contro la sentenza (art. 585 c.p.p.)"},
    "opposizione_decreto_penale": {"etichetta": "Opposizione al decreto penale di condanna (art. 461 c.p.p.)", "giorni": 15,
                                   "evento": "Notificazione del decreto penale", "norma": "art. 461 c. 1 c.p.p."},
    "riesame_personale": {"etichetta": "Riesame di misura coercitiva (art. 309 c.p.p.)", "giorni": 10,
                          "evento": "Esecuzione o notificazione dell'ordinanza", "norma": "art. 309 c. 1 c.p.p."},
    "appello_cautelare": {"etichetta": "Appello cautelare (artt. 310 e 322-bis c.p.p.)", "giorni": 10,
                          "evento": "Notificazione o comunicazione dell'ordinanza", "norma": "art. 310 c. 2 c.p.p."},
    "ricorso_cautelare": {"etichetta": "Ricorso per cassazione in materia cautelare (art. 311 c.p.p.)", "giorni": 10,
                          "evento": "Comunicazione o notificazione dell'avviso di deposito", "norma": "art. 311 c. 1 c.p.p."},
    "riesame_reale": {"etichetta": "Riesame di sequestro o misura reale (art. 324 c.p.p.)", "giorni": 10,
                      "evento": "Esecuzione del provvedimento o diversa data di conoscenza", "norma": "art. 324 c. 1 c.p.p."},
    "memorie_415bis": {"etichetta": "Memorie e interrogatorio dopo l'avviso di conclusione indagini (art. 415-bis c.p.p.)",
                       "giorni": 20, "evento": "Notificazione dell'avviso ex art. 415-bis", "norma": "art. 415-bis c. 3 c.p.p."},
    "opposizione_archiviazione": {"etichetta": "Opposizione alla richiesta di archiviazione (art. 408 c.p.p.)", "giorni": 20,
                                  "evento": "Notificazione dell'avviso della richiesta di archiviazione",
                                  "norma": "art. 408 c. 3 c.p.p."},
    "motivi_nuovi": {"etichetta": "Motivi nuovi (art. 585 c. 4 c.p.p.)"},
}

MOTIVAZIONI = {
    "camera_consiglio": ("Provvedimento in camera di consiglio", 15),
    "contestuale": ("Motivazione contestuale letta in udienza (art. 544 c. 1)", 15),
    "quindici_giorni": ("Motivazione entro 15 giorni (art. 544 c. 2)", 30),
    "termine_giudice": ("Termine più lungo fissato dal giudice, fino a 90 giorni (art. 544 c. 3)", 45),
}


def _sospensione(dati: Mapping[str, Any]):
    return sospensione_feriale(
        detenuto_con_rinuncia=safe_bool(dati.get("tp_detenuto_rinuncia")),
        criminalita_organizzata=safe_bool(dati.get("tp_criminalita_organizzata")),
        urgenza_dichiarata=safe_bool(dati.get("tp_urgenza")),
    )


def _risultato(atto: str, etichetta: str, scadenza: date, passi: list[dict[str, str]], note: list[str],
               norma: str, avvisi: list[str] | None = None) -> dict[str, Any]:
    adesso = oggi()
    giorni = (scadenza - adesso).days
    return {
        "atto": ATTI[atto]["etichetta"],
        "termine": etichetta,
        "scadenza": fmt(scadenza),
        "scadenza_iso": scadenza.isoformat(),
        "giorni_residui": giorni if giorni >= 0 else "scaduto",
        "norma": norma,
        "passaggi": passi,
        "scadenze_proposte": [{"titolo": ATTI[atto]["etichetta"], "data": scadenza.isoformat(), "norma": norma}],
        "notes": note,
        "warnings": list(avvisi or []),
    }


def _sentenza(dati: Mapping[str, Any]) -> dict[str, Any]:
    modo = clean_text(dati.get("tp_motivazione")) or "quindici_giorni"
    if modo not in MOTIVAZIONI:
        raise ValueError("Indica come è stata depositata la motivazione.")
    etichetta, giorni = MOTIVAZIONI[modo]
    evento = parse_date(dati.get("tp_data_evento"))
    if not evento:
        raise ValueError("Inserisci la data della pronuncia, della lettura o dell'avviso di deposito.")
    sospensione = _sospensione(dati)
    note = [sospensione.motivo]
    avvisi: list[str] = []
    passi: list[dict[str, str]] = []
    avviso_deposito = parse_date(dati.get("tp_data_avviso_deposito"))
    if modo == "camera_consiglio":
        decorrenza, descrizione = evento, "notificazione o comunicazione dell'avviso di deposito (art. 585 c. 2 lett. a)"
    elif modo == "contestuale":
        decorrenza, descrizione = evento, "lettura del provvedimento in udienza (art. 585 c. 2 lett. b)"
    else:
        giorni_deposito = 15 if modo == "quindici_giorni" else safe_int(dati.get("tp_giorni_deposito"), 0)
        if modo == "termine_giudice" and not 15 < giorni_deposito <= 90:
            raise ValueError("Il termine fissato dal giudice per la motivazione va da 16 a 90 giorni (art. 544 c. 3).")
        deposito = termine_giorni(evento, giorni_deposito, sospensione, "pronuncia della sentenza")
        passi += deposito.passi
        passi.append({"passaggio": f"Scadenza del termine per il deposito della motivazione ({giorni_deposito} giorni)",
                      "data": fmt(deposito.scadenza)})
        if avviso_deposito:
            decorrenza = avviso_deposito
            descrizione = "notificazione o comunicazione dell'avviso di deposito della sentenza depositata oltre il termine (artt. 548 c. 2 e 585 c. 2 lett. c)"
        else:
            decorrenza = deposito.scadenza
            descrizione = "scadenza del termine per il deposito della motivazione (art. 585 c. 2 lett. c)"
            avvisi.append("Se la sentenza è stata depositata dopo la scadenza, indica la data dell'avviso di deposito: "
                          "il termine decorre da lì (art. 548 c. 2).")
    if safe_bool(dati.get("tp_assente")):
        giorni += 15
        etichetta += "; +15 giorni per il difensore dell'imputato giudicato in assenza (art. 585 c. 1-bis)"
    computo = termine_giorni(decorrenza, giorni, sospensione, descrizione)
    passi += computo.passi
    note.append(f"Termine di {giorni} giorni dalla {descrizione}.")
    note.append("Se la decorrenza è diversa per l'imputato e per il difensore vale per entrambi quella che scade per "
                "ultima (art. 585 c. 3). I termini sono a pena di decadenza (art. 585 c. 5).")
    note.append("Il deposito telematico è tempestivo se accettato entro le ore 24 dell'ultimo giorno (art. 172 c. 6-bis).")
    return _risultato("impugnazione_sentenza", etichetta, computo.scadenza, passi, note, "art. 585 c.p.p.", avvisi)


def _motivi_nuovi(dati: Mapping[str, Any]) -> dict[str, Any]:
    udienza = parse_date(dati.get("tp_data_evento"))
    if not udienza:
        raise ValueError("Inserisci la data dell'udienza.")
    ultimo = udienza - timedelta(days=15)
    passi = [{"passaggio": "Udienza", "data": fmt(udienza)},
             {"passaggio": "Quindici giorni prima dell'udienza (art. 585 c. 4)", "data": fmt(ultimo)}]
    note = ["I motivi nuovi si presentano fino a quindici giorni prima dell'udienza: la data indicata è l'ultimo "
            "giorno utile a ritroso, senza giorni di sospensione.",
            "L'inammissibilità dell'impugnazione si estende ai motivi nuovi (art. 585 c. 4)."]
    avvisi = ["Termine a ritroso: se cade in giorno festivo verificare l'orientamento sull'anticipazione."]
    return _risultato("motivi_nuovi", "Fino a 15 giorni prima dell'udienza", ultimo, passi, note, "art. 585 c. 4 c.p.p.", avvisi)


def calcola(dati: Mapping[str, Any]) -> dict[str, Any]:
    atto = clean_text(dati.get("tp_atto")) or "impugnazione_sentenza"
    if atto not in ATTI:
        raise ValueError("Atto non riconosciuto.")
    if atto == "impugnazione_sentenza":
        return _sentenza(dati)
    if atto == "motivi_nuovi":
        return _motivi_nuovi(dati)
    voce = ATTI[atto]
    evento = parse_date(dati.get("tp_data_evento"))
    if not evento:
        raise ValueError(f"Inserisci la data: {voce['evento'].lower()}.")
    giorni = voce["giorni"]
    norma = voce["norma"]
    etichetta = f"{giorni} giorni"
    if atto == "opposizione_archiviazione" and safe_bool(dati.get("tp_violenza_persona")):
        giorni, norma, etichetta = 30, "art. 408 c. 3-bis c.p.p.", "30 giorni (delitti con violenza alla persona, furto in abitazione o con strappo)"
    sospensione = _sospensione(dati)
    computo = termine_giorni(evento, giorni, sospensione, voce["evento"].lower())
    note = [sospensione.motivo, f"{etichetta} dalla data: {voce['evento'].lower()}."]
    avvisi: list[str] = []
    if atto in {"riesame_personale", "appello_cautelare", "ricorso_cautelare"}:
        note.append("Se l'indagato è in custodia cautelare e rinuncia alla sospensione feriale, spunta l'opzione: "
                    "il termine corre anche in agosto.")
    if atto == "riesame_personale":
        note.append("Per il difensore il termine decorre dalla notificazione dell'avviso di deposito dell'ordinanza "
                    "(art. 309 c. 3): indica quella data se è successiva.")
    if atto == "opposizione_decreto_penale":
        note.append("Per il difensore il termine decorre dalla notificazione del decreto al difensore, se successiva.")
    return _risultato(atto, etichetta, computo.scadenza, computo.passi, note, norma, avvisi)


def opzioni() -> list[tuple[str, str]]:
    return [(chiave, voce["etichetta"]) for chiave, voce in ATTI.items()]


__all__ = ["ATTI", "MOTIVAZIONI", "calcola", "opzioni"]
