"""Le fasi, le prove e i termini di ogni canale di notifica che il software gestisce.

Una scheda per canale: notifica in proprio a mezzo PEC (L. 53/1994), notifica
tramite UNEP, notifica a mezzo posta (L. 890/1982), comunicazioni e
notificazioni di cancelleria. Gli stati del presidio notifiche
(`pct/notifiche_legali.py`, `web/services/notification_presidia_payloads.py`)
sono ricondotti alla fase della scheda senza modificarli.
"""

from __future__ import annotations

from typing import Any


def _fase(codice: str, nome: str, descrizione: str, prova: str, *fonti: str) -> dict[str, Any]:
    return {"codice": codice, "nome": nome, "descrizione": descrizione, "prova": prova, "fonti": list(fonti)}


def _termine(evento: str, termine: str, *fonti: str) -> dict[str, Any]:
    return {"evento": evento, "termine": termine, "fonti": list(fonti)}


SCHEDE_NOTIFICA: dict[str, dict[str, Any]] = {
    "pec": {
        "canale": "pec",
        "nome": "Notifica in proprio a mezzo PEC (L. 53/1994)",
        "base": "L. 53/1994, artt. 3-bis e 9; art. 147 c.p.c.; D.L. 179/2012, art. 16-ter; Specifiche tecniche DGSIA 7/8/2024, art. 26",
        "fasi": [
            _fase("presupposti", "Presupposti e destinatari", "L'avvocato verifica l'atto da notificare e ricava l'indirizzo PEC del destinatario dai pubblici elenchi (ReGIndE, INI-PEC, INAD).",
                  "estrazione dal pubblico elenco conservata", "l53_art3bis", "dl179_art16ter"),
            _fase("atto", "Atto e attestazione di conformità", "L'atto originale informatico è in PDF o PDF/A ottenuto da documento testuale; le copie richiedono l'attestazione di conformità.",
                  "atto notificato e attestazione", "dgsia_art26", "dispatt_196undecies"),
            _fase("relata", "Relata di notifica", "La relazione di notificazione è redatta su documento informatico separato e sottoscritta con firma digitale.",
                  "relata firmata", "l53_art3bis"),
            _fase("invio", "Invio della PEC", "La notifica via PEC può essere eseguita senza limiti orari.",
                  "messaggio PEC inviato conservato in originale", "cpc_147", "l53_art3bis"),
            _fase("accettazione", "Ricevuta di accettazione: perfezionata per il notificante", "La notificazione si perfeziona per il notificante nel momento in cui è generata la ricevuta di accettazione.",
                  "ricevuta di accettazione (RAC)", "cpc_147"),
            _fase("consegna", "Ricevuta di avvenuta consegna: perfezionata per il destinatario", "Per il destinatario si perfeziona con la ricevuta di avvenuta consegna; se generata tra le 21 e le 7, alle ore 7 del giorno successivo.",
                  "ricevuta di avvenuta consegna (RdAC) completa per ogni destinatario", "cpc_147"),
            _fase("mancata_consegna", "Mancata consegna", "Un avviso di mancata consegna non prova la notifica: va rinnovata.",
                  "avviso di mancata consegna", "cpc_147"),
            _fase("deposito_prova", "Deposito della prova", "Ricevute di accettazione e di consegna e copia dell'atto notificato sono trasmesse all'ufficio nella busta telematica, con i dati delle ricevute nel DatiAtto.xml.",
                  "deposito accettato con le ricevute", "dgsia_art26", "l53_art9"),
        ],
        "stati_presidio": {
            "DETECTED": "presupposti", "NEEDS_REVIEW": "presupposti", "NOTIFICATION_CONFIRMED": "presupposti",
            "RECIPIENTS_TO_VERIFY": "presupposti", "ORIGINAL_TO_ACQUIRE": "atto", "ORIGINAL_ACQUIRED": "atto",
            "READY_FOR_RELATA": "relata", "RELATA_DRAFTED": "relata", "RELATA_SIGNED": "relata", "READY_TO_SEND": "invio",
            "SENT_WAITING_RAC": "accettazione", "RAC_RECEIVED": "consegna", "PARTIAL_DELIVERY": "consegna",
            "DELIVERY_COMPLETE": "deposito_prova", "DELIVERY_FAILED": "mancata_consegna", "PROOF_TO_DEPOSIT": "deposito_prova",
            "PROOF_DEPOSITED": "deposito_prova", "CLOSED": "deposito_prova",
        },
        "tempistiche": [
            _termine("Orario", "senza limiti orari; la consegna generata tra le 21 e le 7 vale dalle ore 7", "cpc_147"),
            _termine("Perfezionamento per il notificante", "al momento della ricevuta di accettazione", "cpc_147"),
            _termine("Perfezionamento per il destinatario", "al momento della ricevuta di avvenuta consegna", "cpc_147"),
            _termine("Deposito della prova", "le ricevute e la copia dell'atto notificato entrano nella busta del deposito; per opposizioni e impugnazioni il deposito è contestuale alla notifica", "dgsia_art26", "l53_art9"),
        ],
    },
    "unep": {
        "canale": "unep",
        "nome": "Notifica tramite ufficiale giudiziario (UNEP)",
        "base": "art. 147 c.p.c.; L. 890/1982 per la notifica a mezzo posta eseguita dall'ufficiale giudiziario",
        "fasi": [
            _fase("richiesta", "Richiesta all'UNEP", "L'atto, con la richiesta di notifica, è consegnato o trasmesso all'ufficio notificazioni.",
                  "richiesta di notifica protocollata", "cpc_147"),
            _fase("esecuzione", "Esecuzione", "L'ufficiale giudiziario notifica a mani, a mezzo posta o per via telematica nel rispetto degli orari di legge.",
                  "relazione di notificazione", "cpc_147", "l890_art8"),
            _fase("restituzione", "Restituzione dell'atto notificato", "L'atto con la relazione di notifica torna allo studio ed è la prova da conservare e depositare.",
                  "atto con relazione di notifica", "cpc_147"),
        ],
        "stati_presidio": {
            "DETECTED": "richiesta", "NEEDS_REVIEW": "richiesta", "NOTIFICATION_CONFIRMED": "richiesta", "RECIPIENTS_TO_VERIFY": "richiesta",
            "READY_TO_SEND": "richiesta", "SENT_WAITING_RAC": "esecuzione", "RAC_RECEIVED": "esecuzione", "PARTIAL_DELIVERY": "esecuzione",
            "DELIVERY_COMPLETE": "restituzione", "DELIVERY_FAILED": "esecuzione", "PROOF_TO_DEPOSIT": "restituzione", "PROOF_DEPOSITED": "restituzione", "CLOSED": "restituzione",
        },
        "tempistiche": [
            _termine("Orario delle notificazioni non telematiche", "non prima delle ore 7 e non dopo le ore 21", "cpc_147"),
            _termine("Mancato recapito postale", "deposito entro due giorni lavorativi e avviso raccomandato; compiuta giacenza dopo dieci giorni dalla spedizione dell'avviso", "l890_art8"),
        ],
    },
    "posta": {
        "canale": "posta",
        "nome": "Notifica a mezzo posta (L. 890/1982)",
        "base": "L. 890/1982, art. 8",
        "fasi": [
            _fase("spedizione", "Spedizione del piego", "L'atto è spedito in plico raccomandato con avviso di ricevimento.",
                  "ricevuta di spedizione", "l890_art8"),
            _fase("consegna", "Consegna o deposito", "Se il piego non è recapitato, è depositato entro due giorni lavorativi presso il punto di deposito e ne è dato avviso con raccomandata.",
                  "avviso di ricevimento o avviso di deposito", "l890_art8"),
            _fase("perfezionamento", "Perfezionamento", "La notifica si ha per eseguita dalla data del ritiro o, in mancanza, decorsi dieci giorni dalla spedizione dell'avviso di deposito (compiuta giacenza).",
                  "avviso di ricevimento restituito", "l890_art8"),
        ],
        "stati_presidio": {
            "DETECTED": "spedizione", "NEEDS_REVIEW": "spedizione", "NOTIFICATION_CONFIRMED": "spedizione", "READY_TO_SEND": "spedizione",
            "SENT_WAITING_RAC": "consegna", "RAC_RECEIVED": "consegna", "PARTIAL_DELIVERY": "consegna", "DELIVERY_FAILED": "consegna",
            "DELIVERY_COMPLETE": "perfezionamento", "PROOF_TO_DEPOSIT": "perfezionamento", "PROOF_DEPOSITED": "perfezionamento", "CLOSED": "perfezionamento",
        },
        "tempistiche": [
            _termine("Deposito del piego non recapitato", "entro due giorni lavorativi dal tentativo di notifica", "l890_art8"),
            _termine("Compiuta giacenza", "dieci giorni dalla spedizione della raccomandata di avviso, salvo ritiro anteriore; il piego resta a disposizione sei mesi", "l890_art8"),
        ],
    },
    "cancelleria": {
        "canale": "cancelleria",
        "nome": "Comunicazioni e notificazioni di cancelleria via PEC",
        "base": "art. 136 c.p.c.; D.M. 44/2011, art. 16; Specifiche tecniche DGSIA 7/8/2024, art. 21",
        "fasi": [
            _fase("invio", "Invio dall'ufficio", "Il gestore dei servizi telematici invia la comunicazione alla PEC del destinatario risultante dai pubblici elenchi; il contenuto è nel corpo e nel file Comunicazione.xml.",
                  "messaggio PEC ricevuto con Comunicazione.xml", "cpc_136", "dm44_art16", "dgsia_art21"),
            _fase("ricezione", "Ricezione e presidio", "Lo studio acquisisce la comunicazione, la collega al fascicolo e ne ricava termini e udienze.",
                  "PEC catalogata nel presidio con fascicolo collegato", "dgsia_art21"),
            _fase("adempimento", "Adempimento", "Ogni termine o udienza comunicati entrano nello scadenziario con la norma di riferimento.",
                  "scadenza registrata", "cpc_136"),
        ],
        "stati_presidio": {},
        "tempistiche": [
            _termine("Ricevute", "il gestore conserva nel fascicolo informatico le ricevute PEC e gli avvisi di mancata consegna: la comunicazione vale dalla consegna alla PEC del destinatario", "dgsia_art21"),
        ],
    },
}

_ALIAS_CANALE = {
    "PEC": "pec", "PEC_IN_PROPRIO": "pec", "AVVOCATO": "pec", "UNEP": "unep", "UFFICIALE_GIUDIZIARIO": "unep",
    "POSTA": "posta", "POSTALE": "posta", "A_MEZZO_POSTA": "posta", "RACCOMANDATA": "posta", "NON_PEC": "posta", "NONPEC": "posta",
    "CANCELLERIA": "cancelleria", "COMUNICAZIONE": "cancelleria", "UFFICIO": "cancelleria",
}


def canale_notifica(valore: str) -> str:
    chiave = " ".join(str(valore or "").split()).upper().replace(" ", "_").replace("-", "_")
    if chiave.lower() in SCHEDE_NOTIFICA:
        return chiave.lower()
    return _ALIAS_CANALE.get(chiave, "")


def scheda_notifica(canale: str) -> dict[str, Any]:
    scheda = SCHEDE_NOTIFICA.get(canale_notifica(canale))
    return dict(scheda) if scheda else {}


def fase_notifica(canale: str, stato_presidio: str) -> dict[str, Any]:
    """La fase della scheda per lo stato del presidio; PEC in proprio se il canale non è noto."""
    scheda = scheda_notifica(canale) or SCHEDE_NOTIFICA["pec"]
    codice = scheda["stati_presidio"].get(" ".join(str(stato_presidio or "").split()).upper(), "")
    for fase in scheda["fasi"]:
        if fase["codice"] == codice:
            return dict(fase)
    return {}


__all__ = ["SCHEDE_NOTIFICA", "canale_notifica", "fase_notifica", "scheda_notifica"]
