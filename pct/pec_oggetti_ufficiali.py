"""PEC con oggetto a formato fisso generato da un sistema: si riconoscono dall'oggetto, senza modelli.

Ogni regola corrisponde a un tracciato pubblicato o a un sistema che compone l'oggetto da solo:
- Sistema di Interscambio (fatture): ricevute e notifiche con l'identificativo SdI nell'oggetto
  (Specifiche tecniche FatturaPA, Agenzia delle Entrate, d.m. 55/2013);
- protocollo informatico degli enti: ricevuta di avvenuta protocollazione (d.P.R. 445/2000 art. 53;
  d.P.C.M. 3/12/2013, regole tecniche sul protocollo informatico);
- segreteria del giudice amministrativo: «Avviso <evento> per il ricorso … COD…tar…» e ricevute del deposito
  telematico «Registrazione …» / «Mancato deposito …» (art. 136 c.p.a.; d.P.C.M. 40/2016 e specifiche PAT);
- gestore PEC: casella piena (le PEC non consegnate per casella piena restano imputabili al titolare del
  domicilio digitale: art. 3-bis L. 53/1994; art. 149-bis c.p.c.).
Fail-closed: un oggetto che non coincide resta agli altri classificatori.
"""
from __future__ import annotations

import re
from typing import Any

_PREFISSO = r"^\s*(?:posta certificata:\s*)?(?:(?:r|re|i|rif|fwd?|inoltro)\s*:\s*)*"
_SDI = re.compile(_PREFISSO + r"(ricevuta di consegna|invio file|notifica di scarto|notifica di mancata consegna|"
                  r"notifica di esito|attestazione di avvenuta trasmissione|notifica decorrenza termini)\s+\d{6,}\b", re.I)
_PROTOCOLLO = re.compile(r"(ricevuta|notifica)\s+(?:di\s+)?avvenuta\s+(?:registrazione\s+)?protocoll|"
                         r"ricevuta\s+di\s+protocollazione|notifica\s+avvenuta\s+registrazione\s+protocollo|"
                         r"^\s*(?:posta certificata:\s*)?ricevuta\s+(?:di\s+)?protocollo\b", re.I)
_PROTOCOLLO_CORPO = re.compile(r"ricevuta automatica di protocollo", re.I)
_UNEP_DISPONIBILE = re.compile(r"avviso di disponibilit", re.I)
_DICHIARAZIONE_TERZO = re.compile(r"dichiarazione\s+(?:di|del)\s+terzo|dichiarazione\s+(?:resa\s+)?ex\s+art\.?\s*547|"
                                  r"nostra dichiarazione relativa al (?:pignoramento|procedimento)|dichiarazione ex art\.?\s*547", re.I)
_INEFFICACIA = re.compile(r"perdita di efficacia del pignoramento|inefficacia del pignoramento", re.I)
_NON_PRESA_IN_CARICO = re.compile(r"deve essere ritrasmessa|non verr[aà] presa in carico|non sar[aà] presa in carico|"
                                  r"casella [^.]{0,60}(?:dedicata|utilizzata)[^.]{0,40}esclusivamente|non saranno letti", re.I)
# Segnatura di protocollo di un ente (Area Organizzativa Omogenea): «Protocollo nr: 123 - del 01/02/2026 - AOO…»
_SEGNATURA_ENTE = re.compile(r"protocollo\s+nr:\s*\d+\s*-\s*del\s+\d{2}/\d{2}/\d{4}\s*-\s*AOO", re.I)
_TAR_AVVISO = re.compile(_PREFISSO + r"avviso\s+(?P<evento>.+?)\s+per il ricorso\s+\S+\s+cod\S*tar[a-z]{2}", re.I)
_PAT_RICEVUTA = re.compile(_PREFISSO + r"(?P<esito>registrazione|mancato deposito)\b", re.I)
_RICEVUTA_PEC = re.compile(r"^\s*(?:accettazione|consegna|avviso di (?:non )?accettazione|avviso di mancata consegna|"
                          r"mancata consegna|presa in carico|errore di consegna|anomalia messaggio)\s*:", re.I)
_CASELLA_PIENA = re.compile(r"terminato lo spazio|casella (?:pec )?piena|spazio (?:della casella )?esaurito", re.I)


def _evento(tipo: str, etichetta: str, priorita: str, azione: str, *, scadenza: bool = False,
            revisione: bool = True) -> dict[str, Any]:
    return {"event_type": tipo, "event_label": etichetta, "priority": priorita, "azione_proposta": azione,
            "creates_deadline": scadenza, "closes_deposit": False, "human_review_required": revisione}


def classifica_oggetto_ufficiale(oggetto: str, corpo: str = "") -> tuple[str, str, dict[str, Any]] | None:
    """(famiglia, etichetta famiglia, evento) per gli oggetti a formato fisso; None altrimenti.

    ``corpo`` serve solo per i testi fissi dei sistemi (ricevuta automatica di protocollo, avviso UNEP,
    dichiarazione del terzo, PEC non presa in carico)."""
    o = " ".join(str(oggetto or "").split())
    c = " ".join(str(corpo or "")[:20000].split())
    if _RICEVUTA_PEC.search(o):
        return None  # ricevuta PEC (accettazione, consegna, mancata consegna) del messaggio citato: resta tale
    m = _SDI.search(o)
    if m:
        tipo = m.group(1).lower()
        if "scarto" in tipo or "mancata consegna" in tipo:
            return "fattura_sdi", "Fattura elettronica SDI", _evento(
                "fattura_sdi_scarto" if "scarto" in tipo else "fattura_sdi_mancata_consegna",
                "Fattura SDI scartata" if "scarto" in tipo else "Fattura SDI - mancata consegna", "alta",
                "Correggere e ritrasmettere la fattura nel flusso fatturazione; nessuna scadenza processuale.")
        return "fattura_sdi", "Fattura elettronica SDI", _evento(
            "fattura_sdi", "Ricevuta del Sistema di Interscambio", "media",
            "Archiviare nel flusso fatturazione; non creare scadenza processuale.", revisione=False)
    if _PROTOCOLLO.search(o) or _PROTOCOLLO_CORPO.search(c):
        return "ente_pubblico", "Ente pubblico", _evento(
            "ricevuta_protocollazione", "Ricevuta di protocollazione dell'ente", "bassa",
            "Collegare alla PEC inviata all'ente e conservare il numero di protocollo; nessuna scadenza.", revisione=False)
    if _SEGNATURA_ENTE.search(o):
        return "ente_pubblico", "Ente pubblico", _evento(
            "comunicazione_ente_protocollata", "Comunicazione protocollata di un ente pubblico", "media",
            "Leggere l'atto allegato e collegarlo al fascicolo; scadenze solo se l'atto assegna un termine.")
    m = _TAR_AVVISO.search(o)
    if m:
        ev = m.group("evento").upper()
        famiglia = ("comunicazione_pat", "Comunicazione PAT (amministrativo)")
        if "FISSAZIONE UDIENZA" in ev or "UDIENZA" in ev and "FISSA" in ev:
            return (*famiglia, _evento("udienza_fissata", "Avviso di fissazione dell'udienza (TAR)", "alta",
                                       "Creare l'udienza in agenda dalla data dell'avviso allegato e verificare i termini "
                                       "per memorie e documenti (art. 73 c.p.a.).", scadenza=True))
        if "SENTENZA" in ev:
            return (*famiglia, _evento("deposito_sentenza", "Avviso di deposito della sentenza (TAR)", "alta",
                                       "Archiviare la sentenza e valutare l'impugnazione (artt. 92 e 94 c.p.a.).", scadenza=True))
        if "INVITO" in ev and "PAGAMENTO" in ev:
            return (*famiglia, _evento("invito_pagamento_contributo", "Invito al pagamento del contributo unificato (TAR)", "alta",
                                       "Verificare l'importo e pagare entro il termine dell'invito (art. 248 d.P.R. 115/2002).",
                                       scadenza=True))
        return (*famiglia, _evento("avviso_segreteria_tar", f"Avviso della segreteria TAR: {m.group('evento')[:80]}", "media",
                                   "Leggere l'avviso allegato e collegarlo al ricorso; scadenze solo se l'atto le assegna."))
    m = _PAT_RICEVUTA.search(o)
    if m and re.search(r"ricorso|istanza|deposito|adempimento|modulo", o, re.I):
        famiglia = ("comunicazione_pat", "Comunicazione PAT (amministrativo)")
        if m.group("esito").lower() == "mancato deposito":
            return (*famiglia, _evento("deposito_pat_non_riuscito", "Deposito PAT non riuscito", "rossa",
                                       "Verificare il motivo nel messaggio e ripetere il deposito prima della scadenza."))
        return (*famiglia, _evento("deposito_pat_registrato", "Deposito PAT registrato", "media",
                                   "Collegare la ricevuta al deposito del ricorso; nessuna nuova scadenza.", revisione=False))
    esecuzione = ("esecuzione", "Esecuzione (mobiliare/immobiliare)")
    if _UNEP_DISPONIBILE.search(o) and "unep" in c.lower():
        return (*esecuzione, _evento(
            "atto_unep_disponibile", "Atto notificato disponibile al ritiro presso l'UNEP", "alta",
            "Ritirare l'atto e depositare la nota di iscrizione a ruolo entro 30 giorni dalla consegna "
            "(artt. 543, 557 c.p.c.; art. 164-ter disp. att. c.p.c.), pena l'inefficacia del pignoramento.", scadenza=True))
    if _INEFFICACIA.search(o) or _INEFFICACIA.search(c[:3000]):
        return (*esecuzione, _evento(
            "inefficacia_pignoramento_segnalata", "Il terzo segnala l'inefficacia del pignoramento", "rossa",
            "Verificare subito iscrizione a ruolo e notifica dell'avviso al terzo (art. 543 c.p.c.; art. 164-ter disp. att.)."))
    if _DICHIARAZIONE_TERZO.search(o) or _DICHIARAZIONE_TERZO.search(c[:3000]):
        return (*esecuzione, _evento(
            "dichiarazione_terzo", "Dichiarazione del terzo pignorato", "alta",
            "Allegare la dichiarazione al fascicolo dell'esecuzione e valutarla prima dell'udienza (artt. 547-549 c.p.c.)."))
    if _NON_PRESA_IN_CARICO.search(c[:3000]):
        return "pec_da_reindirizzare", "PEC non presa in carico dal destinatario", _evento(
            "pec_non_presa_in_carico", "Il destinatario non prende in carico la PEC", "rossa",
            "Ritrasmettere all'indirizzo indicato nella risposta e verificare che termini e diffide non siano compromessi.")
    if _CASELLA_PIENA.search(o):
        return "gestore_pec", "Gestore PEC", _evento(
            "casella_pec_piena", "Casella PEC piena", "rossa",
            "Liberare spazio subito: le PEC non consegnate per casella piena restano imputabili allo studio.")
    return None
