"""Lettura del fascicolo: che cosa tratta, che cosa è stato fatto, a che punto siamo.

Il fascicolo è il cuore del gestionale e contiene già tutto: atti, depositi con
le loro ricevute, notifiche con le loro prove, comunicazioni, udienze,
provvedimenti, scadenze, conformità, quadro economico. Questa lettura non
aggiunge nulla e non inventa nulla: mette in ordine quello che c'è e lo dice
in italiano, con la prova di ogni affermazione, così che l'avvocato capisca in
un minuto la pratica e sappia che cosa fare dopo.

Base normativa: ogni norma citata nella lettura viene dal registro verificato
`pct/procedura_fasi/fonti.py` (deposito telematico: D.M. 44/2011 art. 13, art.
196-sexies disp. att. c.p.c., Specifiche tecniche DGSIA 7/8/2024 artt. 17 e 19;
notifiche: L. 53/1994 art. 3-bis, art. 147 c.p.c.; termini del processo: artt.
165, 166, 171-ter, 183, 189, 325, 327, 481 c.p.c. e le altre schede per rito;
incarico: art. 13 L. 247/2012).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pct.procedura_fasi import lacune_conoscenza, schede_per_fascicolo

from ._testo import data_it, pulisci
from .cronologia import cronologia
from .depositi import depositi
from .documenti import documenti
from .economico import economico
from .fase import fase
from .intestazione import intestazione
from .modello import DatiLettura
from .narrativa import componi, narrativa
from .notifiche import notifiche
from .oggetto import oggetto
from .pec import pec
from .prossimi_passi import prossimi_passi

ROME_TZ = ZoneInfo("Europe/Rome")
VERSIONE_LETTURA = "2026.09.14.lettura-fascicolo.v2"


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
    in_corso = lettura["depositi"]["in_corso"]
    if len(in_corso) > 3:
        voci.append(f"{len(in_corso)} depositi non hanno ancora l'accettazione della cancelleria")
    else:
        for deposito in in_corso:
            voci.append(f"il deposito di «{deposito['atto']}» non ha ancora l'accettazione della cancelleria")
    pec_letto = lettura.get("pec") or {}
    if pec_letto.get("da_controllare"):
        quante = len(pec_letto["da_controllare"])
        voci.append(f"{quante} PEC del presidio {'riguarda' if quante == 1 else 'riguardano'} la pratica ma {'è' if quante == 1 else 'sono'} ancora da controllare")
    documenti_letti = lettura["documenti"]
    if documenti_letti["totale"] and not documenti_letti.get("procura") and lettura["fase"]["codice"] not in {"stragiudiziale"}:
        voci.append("nessun documento catalogato come procura alle liti")
    if documenti_letti.get("da_acquisire"):
        quanti = len(documenti_letti["da_acquisire"])
        voci.append(f"{quanti} document{'o censito' if quanti == 1 else 'i censiti'} dal portale ma non scaricat{'o' if quanti == 1 else 'i'}: il presidio potrà leggerl{'o' if quanti == 1 else 'i'} solo dopo l'acquisizione")
    if documenti_letti["non_indicizzati"]:
        quanti = len(documenti_letti["non_indicizzati"])
        voci.append(f"{quanti} document{'o' if quanti == 1 else 'i'} in attesa di lettura dal presidio documentale: la lettura non può ancora citarne il contenuto")
    return voci[:8]


def costruisci_lettura(dati: DatiLettura) -> dict[str, Any]:
    """La lettura completa del fascicolo, come dati e come testo."""
    oggi = dati.oggi or datetime.now(ROME_TZ).date()
    testata = intestazione(dati.fascicolo, dati.parti, dati.catalogo)
    documenti_letti = documenti(dati.documenti, dati.catalogo)
    depositi_letti = depositi(dati.depositi, pulisci(dati.fascicolo.get("canale_operativo")))
    notifiche_lette = notifiche(dati.notifiche, dati.attivita)
    pec_letto = pec(dati.pec)
    economico_letto = economico(dati.economico, oggi)
    eventi = cronologia(dati.attivita, depositi_letti["tutti"], notifiche_lette["tutte"], documenti_letti["tutti"], dati.appuntamenti, oggi)
    fase_letta = fase(testata, documenti_letti, depositi_letti, notifiche_lette, eventi, dati.scadenze, oggi)
    passi, stato = prossimi_passi(
        intestazione=testata, fase_letta=fase_letta, depositi_letti=depositi_letti, notifiche_lette=notifiche_lette,
        documenti_letti=documenti_letti, scadenze=dati.scadenze, conformita=dati.conformita, regia=dati.regia,
        economico_letto=economico_letto, pec_letto=pec_letto, verifiche=dati.verifiche, oggi=oggi,
    )
    # Le schede procedurali pertinenti: rito, canale di deposito, canali di notifica usati.
    conoscenza = schede_per_fascicolo(
        tipo=pulisci(dati.fascicolo.get("tipo")),
        tipo_procedimento=pulisci(dati.fascicolo.get("tipo_procedimento")),
        canale_operativo=pulisci(dati.fascicolo.get("canale_operativo")),
        canali_notifica=[voce.get("canale_codice", "") for voce in notifiche_lette["tutte"] if voce.get("canale_codice")],
    )
    # Ciò che il fascicolo cita e le schede non coprono: dichiarato, non inventato.
    conoscenza["lacune"] = lacune_conoscenza(
        tipo=pulisci(dati.fascicolo.get("tipo")),
        tipo_procedimento=pulisci(dati.fascicolo.get("tipo_procedimento")),
        canale_operativo=pulisci(dati.fascicolo.get("canale_operativo")),
        riferimenti=[f"{pulisci(voce.get('titolo'))} {pulisci(voce.get('descrizione'))}" for voce in dati.scadenze]
        + [pulisci(termine.get("norma")) for voce in pec_letto["tutte"] for termine in voce.get("termini", [])],
    )
    lettura: dict[str, Any] = {
        "versione": VERSIONE_LETTURA,
        "generata_il": data_it(oggi),
        "intestazione": testata,
        "oggetto": oggetto(dati.fascicolo, dati.documenti, dati.catalogo),
        "cronologia": eventi,
        "depositi": depositi_letti,
        "notifiche": notifiche_lette,
        "pec": pec_letto,
        "documenti": documenti_letti,
        "conformita": dict(dati.conformita or {}),
        "economico": economico_letto,
        "fase": fase_letta,
        "prossimi_passi": passi,
        "stato_passi": stato,
        "conoscenza": conoscenza,
        "verifiche": dict(dati.verifiche or {}),
    }
    lettura["lacune"] = _lacune(lettura)
    lettura["narrativa"] = narrativa(lettura)
    return lettura


def lettura_come_payload(lettura: dict[str, Any]) -> dict[str, Any]:
    """La lettura senza gli oggetti interni, pronta per JSON."""
    return {chiave: valore for chiave, valore in lettura.items() if not chiave.startswith("_")}


__all__ = ["VERSIONE_LETTURA", "DatiLettura", "componi", "costruisci_lettura", "lettura_come_payload", "pulisci"]
