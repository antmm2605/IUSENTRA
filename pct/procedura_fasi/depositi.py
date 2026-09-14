"""Le fasi, le prove e i termini di ogni canale di deposito che il software gestisce.

Una scheda per canale (PCT civile, PDP penale, PAT amministrativo, PTT
tributario): le fasi nell'ordine in cui avvengono, la prova che ciascuna
produce, il collegamento fra gli stati registrati dal software e la fase, i
termini con la loro norma. Nulla di questo modifica la macchina a stati del
deposito (`pct/deposito.py`, `pct/fascicoli.EsitoDepositoPCT`): la scheda la
spiega e la cita.
"""

from __future__ import annotations

from typing import Any


def _fase(codice: str, nome: str, descrizione: str, prova: str, *fonti: str) -> dict[str, Any]:
    return {"codice": codice, "nome": nome, "descrizione": descrizione, "prova": prova, "fonti": list(fonti)}


def _termine(evento: str, termine: str, *fonti: str, template: str = "") -> dict[str, Any]:
    voce = {"evento": evento, "termine": termine, "fonti": list(fonti)}
    if template:
        voce["template"] = template
    return voce


SCHEDE_DEPOSITO: dict[str, dict[str, Any]] = {
    "PCT_TELEMATICO": {
        "canale": "PCT_TELEMATICO",
        "nome": "Deposito telematico civile (PCT)",
        "base": "art. 196-quater e 196-sexies disp. att. c.p.c.; D.M. 44/2011, art. 13; Specifiche tecniche DGSIA 7/8/2024, art. 17",
        "fasi": [
            _fase("predisposizione", "Predisposizione della busta",
                  "L'atto in PDF nativo firmato digitalmente, gli allegati e il DatiAtto.xml vengono raccolti nella busta telematica cifrata per l'ufficio destinatario.",
                  "busta .enc e DatiAtto.xml conservati nel fascicolo", "dispatt_196quater", "dgsia_art17"),
            _fase("invio", "Invio", "La busta è inviata via PEC al gestore dei servizi telematici del Ministero.",
                  "messaggio PEC inviato", "dm44_art13"),
            _fase("accettazione_pec", "Ricevuta di accettazione", "Il gestore PEC del mittente accetta il messaggio.",
                  "ricevuta di accettazione (RAC)", "dm44_art13"),
            _fase("consegna", "Ricevuta di avvenuta consegna: il deposito è avvenuto",
                  "La conferma del completamento della trasmissione è il momento in cui il deposito si ha per avvenuto; è tempestivo se generata entro la fine del giorno di scadenza.",
                  "ricevuta di avvenuta consegna (RdAC)", "dispatt_196sexies", "dm44_art13"),
            _fase("controlli_automatici", "Esito dei controlli automatici",
                  "Il gestore controlla la busta: WARN (anomalia non bloccante), ERROR (bloccante, serve la cancelleria), FATAL (busta non elaborabile: PEC di rifiuto).",
                  "PEC di esito dei controlli automatici", "dgsia_art17"),
            _fase("esito_cancelleria", "Accettazione o rifiuto della cancelleria",
                  "La cancelleria accetta l'atto (PEC di avvenuto deposito, anche dopo il suo intervento) oppure lo rifiuta con motivazione: solo con l'accettazione l'atto è nel fascicolo d'ufficio.",
                  "PEC di accettazione o di rifiuto della cancelleria", "dgsia_art17"),
        ],
        "stati_software": {
            "INVIATO": "invio", "ACCETTATO_PEC": "accettazione_pec", "ACCETTATO": "accettazione_pec",
            "CONSEGNATO": "consegna", "WARN_CONTROLLI": "controlli_automatici", "ERRORE_CONTROLLI": "controlli_automatici",
            "ERRORE": "controlli_automatici", "ACCETTATO_CANCELLERIA": "esito_cancelleria",
            "RIFIUTATO_CANCELLERIA": "esito_cancelleria", "RIFIUTATO": "esito_cancelleria",
        },
        "tempistiche": [
            _termine("Tempestività del deposito", "la conferma della trasmissione (ricevuta di avvenuta consegna) deve essere generata entro la fine del giorno di scadenza", "dispatt_196sexies"),
            _termine("Anomalia WARN", "non blocca: la cancelleria valuta la segnalazione (es. procura mancante, firma non valida)", "dgsia_art17"),
            _termine("Anomalia ERROR", "bloccante fino all'intervento della cancelleria", "dgsia_art17"),
            _termine("Anomalia FATAL", "rifiuto comunicato via PEC: il deposito va ripetuto, e vale il termine originario", "dgsia_art17"),
            _termine("Atti oltre la dimensione massima", "il deposito può essere eseguito con più trasmissioni", "dispatt_196sexies"),
        ],
    },
    "PDP_PENALE": {
        "canale": "PDP_PENALE",
        "nome": "Deposito telematico penale (Portale Deposito atti Penali)",
        "base": "art. 111-bis c.p.p.; Specifiche tecniche DGSIA 7/8/2024, art. 19",
        "fasi": [
            _fase("predisposizione", "Predisposizione", "L'atto in forma di documento informatico firmato e gli allegati sono preparati per il caricamento sul PDP.",
                  "atto firmato nel fascicolo", "cpp_111bis"),
            _fase("invio", "Invio dal PDP", "Inserimento dei dati richiesti, caricamento dell'atto e degli allegati, comando di invio.",
                  "stato INVIATO sul PDP", "dgsia_art19"),
            _fase("ricevuta", "Ricevuta di accettazione del deposito", "Il PDP genera la ricevuta con identificativo unico nazionale anno/numero, dati inseriti, data e ora dell'invio rilevate dai sistemi del Ministero.",
                  "ricevuta PDF scaricabile dal PDP", "dgsia_art19"),
            _fase("transito", "In transito", "Il deposito è in attesa di smistamento al sistema dell'ufficio giudiziario; il PDP cancella i dati personali.",
                  "stato IN TRANSITO", "dgsia_art19"),
            _fase("verifica", "Verifica e accettazione", "Accettazione automatica se i dati coincidono con il registro; altrimenti IN VERIFICA a cura del personale dell'ufficio.",
                  "stato ACCETTATO o IN VERIFICA in «Consultazione - Depositi»", "dgsia_art19"),
            _fase("esito", "Esito", "ACCETTATO (atto associato al procedimento), RIFIUTATO (motivazione sul PDP) oppure ERRORE TECNICO (ripetere il deposito).",
                  "stato finale sul PDP", "dgsia_art19"),
        ],
        "stati_software": {
            "INVIATO": "invio", "IN_TRANSITO": "transito", "IN TRANSITO": "transito", "ACCETTATO_PEC": "ricevuta",
            "CONSEGNATO": "transito", "IN_VERIFICA": "verifica", "IN VERIFICA": "verifica", "WARN_CONTROLLI": "verifica",
            "ERRORE_CONTROLLI": "esito", "ERRORE_TECNICO": "esito", "ERRORE": "esito",
            "ACCETTATO": "esito", "ACCETTATO_CANCELLERIA": "esito", "RIFIUTATO": "esito", "RIFIUTATO_CANCELLERIA": "esito",
        },
        "tempistiche": [
            _termine("Prova dell'invio", "la ricevuta di accettazione del deposito riporta data e ora rilevate dai sistemi del Ministero", "dgsia_art19"),
            _termine("Errore tecnico", "il difensore è invitato dal messaggio di stato del PDP a effettuare nuovamente il deposito", "dgsia_art19"),
            _termine("Impugnazioni", "quindici, trenta o quarantacinque giorni secondo i casi dell'art. 544 c.p.p.; più quindici giorni per il difensore dell'imputato giudicato in assenza", "cpp_585"),
        ],
    },
    "PAT_AMMINISTRATIVO": {
        "canale": "PAT_AMMINISTRATIVO",
        "nome": "Deposito nel processo amministrativo telematico (PAT)",
        "base": "c.p.a. artt. 29, 45, 46 e 92; regole tecnico-operative D.P.C.M. 40/2016",
        "fasi": [
            _fase("notifica", "Notifica del ricorso", "Il ricorso è notificato alle parti intimate nel termine di decadenza dell'azione.",
                  "ricevute PEC o relazione di notifica", "cpa_29"),
            _fase("deposito", "Deposito in segreteria", "Ricorso e atti soggetti a notificazione sono depositati nel termine perentorio di trenta giorni dal perfezionamento dell'ultima notificazione.",
                  "ricevuta di deposito PAT", "cpa_45", "cpa_dpcm_40_2016"),
            _fase("controlli", "Controlli del sistema", "Il PAT verifica il modulo di deposito e gli allegati; l'esito è comunicato via PEC.",
                  "PEC di esito del deposito", "cpa_dpcm_40_2016"),
            _fase("costituzione", "Costituzione delle parti intimate", "Le parti intimate possono costituirsi entro sessanta giorni dal perfezionamento della notificazione.",
                  "memorie e documenti depositati", "cpa_46"),
            _fase("esito", "Esito della segreteria", "La segreteria accetta il deposito o segnala le irregolarità da sanare.",
                  "stato del deposito nel fascicolo PAT", "cpa_dpcm_40_2016"),
        ],
        "stati_software": {
            "INVIATO": "deposito", "ACCETTATO_PEC": "deposito", "CONSEGNATO": "controlli", "WARN_CONTROLLI": "controlli",
            "ERRORE_CONTROLLI": "controlli", "ACCETTATO_CANCELLERIA": "esito", "RIFIUTATO_CANCELLERIA": "esito",
            "ACCETTATO": "esito", "RIFIUTATO": "esito", "ERRORE": "controlli",
        },
        "tempistiche": [
            _termine("Azione di annullamento", "sessanta giorni (decadenza)", "cpa_29"),
            _termine("Deposito del ricorso notificato", "trenta giorni dal perfezionamento dell'ultima notificazione, anche per il destinatario", "cpa_45"),
            _termine("Costituzione delle parti intimate", "sessanta giorni dal perfezionamento della notificazione nei propri confronti", "cpa_46"),
            _termine("Impugnazioni", "sessanta giorni dalla notificazione della sentenza", "cpa_92"),
        ],
    },
    "PTT_TRIBUTARIO": {
        "canale": "PTT_TRIBUTARIO",
        "nome": "Deposito nel processo tributario telematico (PTT/SIGIT)",
        "base": "D.Lgs. 175/2024 (Testo unico della giustizia tributaria), artt. 61, 64, 67, 68 e 69 — gli artt. 18-23 del D.Lgs. 546/1992 sono abrogati",
        "fasi": [
            _fase("ricorso", "Ricorso", "Il processo è introdotto con ricorso alla corte di giustizia tributaria di primo grado, con i contenuti richiesti dall'art. 64.",
                  "ricorso firmato", "tu175_art64"),
            _fase("proposizione", "Proposizione: notifica del ricorso", "Il ricorso è proposto mediante notifica, entro sessanta giorni dalla notificazione dell'atto impugnato.",
                  "ricevute PEC di notifica", "tu175_art67", "tu175_art61"),
            _fase("costituzione", "Costituzione in giudizio: deposito telematico", "Il ricorrente, entro trenta giorni dalla proposizione, deposita telematicamente il ricorso nella segreteria della corte adita.",
                  "ricevuta di deposito SIGIT", "tu175_art68", "tu175_art61"),
            _fase("resistente", "Costituzione della parte resistente", "L'ente impositore o l'agente della riscossione si costituisce entro sessanta giorni dalla notifica del ricorso.",
                  "controdeduzioni depositate", "tu175_art69"),
            _fase("esito", "Esito", "La segreteria registra il deposito; le comunicazioni successive arrivano via PEC.",
                  "comunicazioni PEC della segreteria", "tu175_art61"),
        ],
        "stati_software": {
            "INVIATO": "costituzione", "ACCETTATO_PEC": "costituzione", "CONSEGNATO": "costituzione", "WARN_CONTROLLI": "esito",
            "ERRORE_CONTROLLI": "esito", "ACCETTATO_CANCELLERIA": "esito", "RIFIUTATO_CANCELLERIA": "esito",
            "ACCETTATO": "esito", "RIFIUTATO": "esito", "ERRORE": "esito",
        },
        "tempistiche": [
            _termine("Proposizione del ricorso", "sessanta giorni dalla notificazione dell'atto impugnato, a pena di inammissibilità", "tu175_art67"),
            _termine("Costituzione del ricorrente", "trenta giorni dalla proposizione, a pena di inammissibilità, con deposito telematico", "tu175_art68"),
            _termine("Costituzione del resistente", "sessanta giorni dalla notifica del ricorso", "tu175_art69"),
        ],
    },
}

_ALIAS_CANALE = {
    "PCT": "PCT_TELEMATICO", "PCT_CIVILE": "PCT_TELEMATICO", "CIVILE": "PCT_TELEMATICO", "PDP": "PDP_PENALE",
    "PENALE": "PDP_PENALE", "PAT": "PAT_AMMINISTRATIVO", "AMMINISTRATIVO": "PAT_AMMINISTRATIVO",
    "PTT": "PTT_TRIBUTARIO", "SIGIT": "PTT_TRIBUTARIO", "TRIBUTARIO": "PTT_TRIBUTARIO",
}


def canale_deposito(valore: str) -> str:
    chiave = " ".join(str(valore or "").split()).upper().replace(" ", "_")
    if chiave in SCHEDE_DEPOSITO:
        return chiave
    return _ALIAS_CANALE.get(chiave, "")


def scheda_deposito(canale: str) -> dict[str, Any]:
    scheda = SCHEDE_DEPOSITO.get(canale_deposito(canale))
    return dict(scheda) if scheda else {}


def fase_deposito(canale: str, stato: str) -> dict[str, Any]:
    """La fase della scheda in cui si trova un deposito nello stato registrato."""
    scheda = scheda_deposito(canale) or SCHEDE_DEPOSITO["PCT_TELEMATICO"]
    codice = scheda["stati_software"].get(" ".join(str(stato or "").split()).upper(), "")
    for fase in scheda["fasi"]:
        if fase["codice"] == codice:
            return dict(fase)
    return {}


__all__ = ["SCHEDE_DEPOSITO", "canale_deposito", "fase_deposito", "scheda_deposito"]
