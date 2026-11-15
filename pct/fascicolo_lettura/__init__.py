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

from pct.fascicolo_pec_conteggio import conteggio_pec
from pct.procedura_fasi import lacune_conoscenza, schede_per_fascicolo

from ._testo import data_da, data_it, pulisci
from .archivio import archivio
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
from .ragionamento import vista as vista_ragionamento

ROME_TZ = ZoneInfo("Europe/Rome")
VERSIONE_LETTURA = "2026.11.15.lettura-fascicolo.v32"


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
    documenti_letti = lettura["documenti"]
    if documenti_letti["totale"] and not documenti_letti.get("procura") and lettura["fase"]["codice"] not in {"stragiudiziale"}:
        voci.append("nessun documento catalogato come procura alle liti")
    if documenti_letti.get("da_acquisire"):
        quanti = len(documenti_letti["da_acquisire"])
        voci.append(f"{quanti} document{'o censito' if quanti == 1 else 'i censiti'} dal portale ma non scaricat{'o' if quanti == 1 else 'i'}: il presidio potrà leggerl{'o' if quanti == 1 else 'i'} solo dopo l'acquisizione")
    archivio_letto = lettura.get("archivio") or {}
    if archivio_letto.get("da_confermare"):
        voci.append(_lacuna_conferme(archivio_letto["da_confermare"]))
    errori = int((archivio_letto.get("lettura_automatica") or {}).get("errori") or 0)
    if errori:
        voci.append(f"{errori} letture non riuscite: aprire «Letture e verifiche» per vedere le fonti e le cause")
    mancanti = lettura.get("documenti_da_riallineare") or []
    if mancanti:
        voci.append("Documenti acquisiti da riallineare al registro delle letture: " + ", ".join(voce["nome"] for voce in mancanti))
    return voci[:8]


def _lacuna_conferme(richieste: list[dict[str, Any]]) -> str:
    """Quali date attendono conferma, non solo quante: l'avvocato deve sapere su che cosa decidere."""
    nomi = []
    for voce in richieste[:3]:
        etichetta = pulisci(voce.get("etichetta")) or pulisci(voce.get("campo")) or "data"
        giorno = data_it(pulisci(voce.get("valore"))[:10])
        # L'etichetta del fatto porta spesso già la data («Termine del 22/11/2026»):
        # ripeterla produce «termine del 22/11/2026 del 22/11/2026».
        nomi.append(etichetta.lower() if not giorno or giorno in etichetta else f"{etichetta.lower()} del {giorno}")
    quanti = len(richieste)
    elenco = ", ".join(nomi) + (f" e altre {quanti - 3}" if quanti > 3 else "")
    return (
        f"{quanti} dat{'a' if quanti == 1 else 'e'} in attesa di conferma ({elenco}): "
        "nessun'altra fonte le conferma e cambiano agenda o scadenziario, il riquadro «Letture e verifiche» le chiede"
    )


def _letture_in_corso(archivio_letto: dict[str, Any], documenti_letti: dict[str, Any]) -> dict[str, Any]:
    stato = archivio_letto.get("lettura_automatica") or {}
    fonti = {
        (voce.get("tipo"), voce.get("oggetto_id") or voce.get("nome")): {
            "tipo": voce.get("tipo"), "id": voce.get("oggetto_id"),
            "nome": voce.get("nome"), "motivo": voce.get("motivo"),
        }
        for voce in stato.get("in_attesa") or [] if voce.get("nome")
    }
    totale = max(len(fonti), int(stato.get("da_leggere") or 0))
    if not archivio_letto.get("disponibile") and not totale:
        for voce in documenti_letti["non_indicizzati"]:
            fonti["documento", voce["id"]] = {
                "tipo": "documento", "id": voce["id"], "nome": voce["nome"],
                "motivo": "Testo non ancora disponibile nell’indice.",
            }
        totale = len(fonti)
    return {"totale": totale, "fonti": list(fonti.values())}


def costruisci_lettura(dati: DatiLettura) -> dict[str, Any]:
    """La lettura completa del fascicolo, come dati e come testo."""
    oggi = dati.oggi or datetime.now(ROME_TZ).date()
    testata = intestazione(dati.fascicolo, dati.parti, dati.catalogo)
    fonti_documenti = list((dati.archivio or {}).get("fonti_documenti", []) or [])
    if not testata.get("rg"):
        # Il numero di ruolo indicato nel deposito telematico dello studio (deposito integrativo) quando la scheda non lo porta.
        from pct.procedura_fasi.ruolo_dagli_atti import ruolo_dagli_atti

        if (rg_letto := ruolo_dagli_atti(fonti_documenti)):
            testata["rg"], testata["rg_fonte"] = rg_letto, "letto nel deposito telematico conservato nel fascicolo"
    documenti_letti = documenti(dati.documenti, dati.catalogo, rg=testata.get("rg", ""), fonti=fonti_documenti)
    depositi_letti = depositi(dati.depositi, pulisci(dati.fascicolo.get("canale_operativo")))
    notifiche_lette = notifiche(dati.notifiche, dati.attivita)
    notifiche_lette["prove_documentali"] = int((dati.archivio or {}).get("prove_notifica_documentali") or 0)
    pec_letto = pec(dati.pec)
    pec_letto["conteggio"] = conteggio_pec(pec_letto, dati.verifiche)
    economico_letto = economico(dati.economico, oggi)
    archivio_letto = archivio(dati.archivio) if getattr(dati, "archivio", None) else {}
    stato_documenti = (archivio_letto.get("lettura_automatica") or {}).get("documenti") or {}
    documenti_letti["errori_lettura"] = int(stato_documenti.get("errori") or 0)
    documenti_letti["da_leggere_lettura"] = int(stato_documenti["da_leggere"]) if "da_leggere" in stato_documenti else None
    eventi = cronologia(dati.attivita, depositi_letti["tutti"], notifiche_lette["tutte"], documenti_letti["tutti"], dati.appuntamenti, oggi, archivio_letto)
    fase_letta = fase(testata, documenti_letti, depositi_letti, notifiche_lette, eventi, dati.scadenze, oggi, pec_letto=pec_letto,
                      appuntamenti=dati.appuntamenti, fonti=fonti_documenti)
    passi, stato = prossimi_passi(
        intestazione=testata, fase_letta=fase_letta, depositi_letti=depositi_letti, notifiche_lette=notifiche_lette,
        documenti_letti=documenti_letti, scadenze=dati.scadenze, conformita=dati.conformita, regia=dati.regia,
        economico_letto=economico_letto, pec_letto=pec_letto, verifiche=dati.verifiche, oggi=oggi,
        appuntamenti=dati.appuntamenti, fascicolo_id=pulisci(dati.fascicolo.get("id")),
        ragionamento=dati.ragionamento or None,
    )
    # Le schede procedurali pertinenti: rito, canale di deposito, canali di notifica usati.
    conoscenza = schede_per_fascicolo(
        tipo=pulisci(dati.fascicolo.get("tipo")),
        tipo_procedimento=pulisci(dati.fascicolo.get("tipo_procedimento")),
        canale_operativo=pulisci(dati.fascicolo.get("canale_operativo")),
        canali_notifica=[voce.get("canale_codice", "") for voce in notifiche_lette["tutte"] if voce.get("canale_codice")],
        codice_oggetto=testata.get("codice_oggetto_pst", ""), oggetto=testata.get("oggetto", ""), area=testata.get("area", ""),
        etichette_atti=[voce["etichetta"] for voce in documenti_letti["tutti"] if voce.get("sezione") == "atti"],
    )
    # Ciò che il fascicolo cita e le schede non coprono: dichiarato, non inventato.
    conoscenza["lacune"] = lacune_conoscenza(
        tipo=pulisci(dati.fascicolo.get("tipo")),
        tipo_procedimento=pulisci(dati.fascicolo.get("tipo_procedimento")),
        canale_operativo=pulisci(dati.fascicolo.get("canale_operativo")),
        riferimenti=[f"{pulisci(voce.get('titolo'))} {pulisci(voce.get('descrizione'))}" for voce in dati.scadenze]
        + [pulisci(termine.get("norma")) for voce in pec_letto["tutte"] for termine in voce.get("termini", [])],
    )
    scadenze_aperte = [s for s in dati.scadenze if pulisci(s.get("stato")).upper() in {"APERTO", "APERTA", "IN_CORSO"}]
    giorni_scadenza = [d for s in scadenze_aperte if (d := data_da(s.get("data_scadenza") or s.get("data")))]
    riepilogo_scadenze = {
        "totale": len(scadenze_aperte),
        "scadute": sum(d < oggi for d in giorni_scadenza),
        "prossimi30": sum(0 <= (d - oggi).days <= 30 for d in giorni_scadenza),
        "successive": sum((d - oggi).days > 30 for d in giorni_scadenza),
    }
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
        "scadenze": riepilogo_scadenze,
        "conformita": dict(dati.conformita or {}),
        "economico": economico_letto,
        "fase": fase_letta,
        "prossimi_passi": passi,
        "stato_passi": stato,
        "conoscenza": conoscenza,
        "verifiche": dict(dati.verifiche or {}),
        "archivio": archivio_letto,
        "ragionamento": vista_ragionamento(dati.ragionamento) if dati.ragionamento else {},
    }
    if documenti_letti.get("sentenza"):
        from .percorso import percorso_dopo_sentenza

        lettura["percorso"] = percorso_dopo_sentenza(testata, documenti_letti)
    lettura["letture_in_corso"] = _letture_in_corso(archivio_letto, documenti_letti)
    inventario = (dati.archivio or {}).get("letture_documenti")
    if isinstance(inventario, dict):
        lettura["documenti_da_riallineare"] = [
            voce for voce in documenti_letti["non_indicizzati"]
            if voce["id"] and not (inventario.get(voce["id"]) or {}).get("presente")
        ]
    lettura["lacune"] = _lacune(lettura)
    lettura["narrativa"] = narrativa(lettura)
    return lettura


def lettura_come_payload(lettura: dict[str, Any]) -> dict[str, Any]:
    """La lettura senza gli oggetti interni, pronta per JSON."""
    return {chiave: valore for chiave, valore in lettura.items() if not chiave.startswith("_")}


__all__ = ["VERSIONE_LETTURA", "DatiLettura", "componi", "costruisci_lettura", "lettura_come_payload", "pulisci"]
