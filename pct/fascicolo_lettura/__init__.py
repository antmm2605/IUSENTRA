"""Lettura del fascicolo: che cosa tratta, che cosa è stato fatto, a che punto siamo.

Il fascicolo è il cuore del gestionale e contiene già tutto: atti, depositi con
le loro ricevute, notifiche con le loro prove, comunicazioni, udienze,
provvedimenti, scadenze, conformità, quadro economico. Questa lettura non
aggiunge nulla e non inventa nulla: mette in ordine quello che c'è e lo dice
in italiano, con la prova di ogni affermazione, così che l'avvocato capisca in
un minuto la pratica e sappia che cosa fare dopo.

Base normativa dei riferimenti usati nella lettura: fasi del deposito
telematico (D.M. 44/2011, artt. 13-16, Specifiche tecniche DGSIA);
perfezionamento della notifica a mezzo PEC (L. 53/1994, art. 3-bis);
costituzione dell'attore e memorie integrative (artt. 165 e 171-ter c.p.c.);
termini di impugnazione (artt. 325 e 327 c.p.c.); preventivo e conferimento
(art. 13 L. 247/2012).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ._testo import data_it, pulisci
from .cronologia import cronologia
from .depositi import depositi
from .documenti import documenti
from .fase import fase
from .intestazione import intestazione
from .modello import DatiLettura
from .narrativa import componi, narrativa
from .notifiche import notifiche
from .oggetto import oggetto
from .prossimi_passi import prossimi_passi

ROME_TZ = ZoneInfo("Europe/Rome")
VERSIONE_LETTURA = "2026.09.14.lettura-fascicolo.v1"


def _lacune(lettura: dict[str, Any]) -> list[str]:
    voci: list[str] = []
    testata = lettura["intestazione"]
    if not testata["rg"] and lettura["fase"]["codice"] not in {"stragiudiziale", "preparatoria", "chiusa"}:
        voci.append("numero di ruolo non registrato nel fascicolo")
    if not testata["ufficio"]:
        voci.append("ufficio giudiziario non indicato")
    for notifica in lettura["notifiche"]["aperte"]:
        if notifica["stato"] in {"SENT_WAITING_RAC", "RAC_RECEIVED", "PARTIAL_DELIVERY"}:
            voci.append(f"la notifica di «{notifica['atto']}» non ha ancora la ricevuta di avvenuta consegna")
    for deposito in lettura["depositi"]["in_corso"]:
        voci.append(f"il deposito di «{deposito['atto']}» non ha ancora l'accettazione della cancelleria")
    documenti_letti = lettura["documenti"]
    if documenti_letti["totale"] and not documenti_letti.get("procura") and lettura["fase"]["codice"] not in {"stragiudiziale"}:
        voci.append("nessun documento catalogato come procura alle liti")
    if documenti_letti["non_indicizzati"]:
        quanti = len(documenti_letti["non_indicizzati"])
        voci.append(f"{quanti} document{'o' if quanti == 1 else 'i'} senza testo indicizzato: la lettura non può citarne il contenuto")
    return voci[:8]


def costruisci_lettura(dati: DatiLettura) -> dict[str, Any]:
    """La lettura completa del fascicolo, come dati e come testo."""
    oggi = dati.oggi or datetime.now(ROME_TZ).date()
    testata = intestazione(dati.fascicolo, dati.parti, dati.catalogo)
    documenti_letti = documenti(dati.documenti, dati.catalogo)
    depositi_letti = depositi(dati.depositi)
    notifiche_lette = notifiche(dati.notifiche, dati.attivita)
    eventi = cronologia(dati.attivita, depositi_letti["tutti"], notifiche_lette["tutte"], documenti_letti["tutti"], dati.appuntamenti, oggi)
    fase_letta = fase(testata, documenti_letti, depositi_letti, notifiche_lette, eventi, dati.scadenze, oggi)
    passi = prossimi_passi(fase_letta, depositi_letti, notifiche_lette, documenti_letti, dati.scadenze, dati.conformita, dati.regia, dati.economico, oggi)
    lettura: dict[str, Any] = {
        "versione": VERSIONE_LETTURA,
        "generata_il": data_it(oggi),
        "intestazione": testata,
        "oggetto": oggetto(dati.fascicolo, dati.documenti, dati.catalogo),
        "cronologia": eventi,
        "depositi": depositi_letti,
        "notifiche": notifiche_lette,
        "documenti": documenti_letti,
        "conformita": dict(dati.conformita or {}),
        "economico": dict(dati.economico or {}),
        "fase": fase_letta,
        "prossimi_passi": passi,
    }
    lettura["lacune"] = _lacune(lettura)
    lettura["narrativa"] = narrativa(lettura)
    return lettura


def lettura_come_payload(lettura: dict[str, Any]) -> dict[str, Any]:
    """La lettura senza gli oggetti interni, pronta per JSON."""
    return {chiave: valore for chiave, valore in lettura.items() if not chiave.startswith("_")}


__all__ = ["VERSIONE_LETTURA", "DatiLettura", "componi", "costruisci_lettura", "lettura_come_payload", "pulisci"]
