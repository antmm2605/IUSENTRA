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


# ---------------------------------------------------------------------------
# Ricevute PEC: classificatore unico usato da pipeline, control tower e workflow.
#
# Base normativa: d.P.R. 68/2005 (artt. 6, 8, 9, 10, 11 e 12) e regole tecniche del d.m. 2/11/2005
# (allegato, §§ 2.1, 3.2-3.4): ogni ricevuta/avviso porta il tipo nell'attributo ``tipo`` di
# <postacert> in daticert.xml, nell'intestazione ``X-Ricevuta`` e un oggetto a prefisso fisso
# («ACCETTAZIONE:», «AVVISO DI NON ACCETTAZIONE:», «PRESA IN CARICO:», «CONSEGNA:»,
# «AVVISO DI MANCATA CONSEGNA:», «PROBLEMA DI SICUREZZA:», «ANOMALIA MESSAGGIO:»). Dopo il prefisso
# c'e' l'oggetto del messaggio originale: non va letto per decidere il tipo. ``posta-certificata``
# e' la busta di un messaggio in arrivo, non una ricevuta.
# Fail-safe: i tipi negativi si controllano prima di quelli positivi; un tipo sconosciuto non
# diventa mai accettazione o consegna.
# ---------------------------------------------------------------------------

RICEVUTE_NEGATIVE = frozenset({"non_accettazione", "mancata_consegna", "preavviso_mancata_consegna", "rilevazione_virus"})
RICEVUTE_PEC = frozenset({"accettazione", "presa_in_carico", "avvenuta_consegna", "anomalia", *RICEVUTE_NEGATIVE})

_TIPI_DATICERT = {
    "accettazione": "accettazione",
    "non_accettazione": "non_accettazione",
    "presa_in_carico": "presa_in_carico",
    "avvenuta_consegna": "avvenuta_consegna",
    "consegna": "avvenuta_consegna",
    "errore_consegna": "mancata_consegna",
    "mancata_consegna": "mancata_consegna",
    "preavviso_errore_consegna": "preavviso_mancata_consegna",
    "preavviso_mancata_consegna": "preavviso_mancata_consegna",
    "rilevazione_virus": "rilevazione_virus",
    "anomalia": "anomalia",
    "non_pec": "anomalia",
}
# Tipi che dicono con certezza "non e' una ricevuta": il testo non puo' trasformarli in ricevuta.
_TIPI_NON_RICEVUTA = frozenset({"posta_certificata"})

_PREFISSO_INOLTRO = r"^\s*(?:(?:r|re|i|rif|fwd?|inoltro)\s*:\s*)*"
_OGGETTO_RICEVUTA: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("non_accettazione", re.compile(r"avviso\s+di\s+non\s+accettazione\b[^:]{0,60}:", re.I)),
    ("preavviso_mancata_consegna", re.compile(
        r"avviso\s+di\s+mancata\s+consegna\s+per\s+sup(?:eramento|\.)?\s*(?:dei\s+)?t(?:empi|empo|\.)?\s*mass[^:]{0,30}:", re.I)),
    ("mancata_consegna", re.compile(r"(?:avviso\s+di\s+mancata\s+consegna|mancata\s+consegna|errore\s+di\s+consegna)\b[^:]{0,60}:", re.I)),
    ("rilevazione_virus", re.compile(r"(?:problema\s+di\s+sicurezza|avviso\s+di\s+rilevazione\s+virus)\s*:", re.I)),
    ("anomalia", re.compile(r"anomalia\s+messaggio\s*:", re.I)),
    ("presa_in_carico", re.compile(r"presa\s+in\s+carico\s*:", re.I)),
    ("avvenuta_consegna", re.compile(r"consegna\s*:", re.I)),
    ("accettazione", re.compile(r"accettazione\s*:", re.I)),
)
# Frasi standard dei gestori nel corpo della ricevuta (fallback quando mancano daticert e prefisso).
_CORPO_RICEVUTA: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("non_accettazione", re.compile(
        r"\bavviso\s+di\s+non\s+accettazione\b|\bnon[\s-]accettazione\b(?!\s+(?:del\s+|dell['’]\s*)?(?:deposito|atto|eredit))|\berrore\s+nell['’]\s*accettazione\b|"
        r"\bmancata\s+accettazione\b(?!\s+(?:del\s+|dell['’]\s*)?(?:deposito|atto|busta|eredit))|"
        r"\berrore\s+di\s+accettazione\b", re.I)),
    ("preavviso_mancata_consegna", re.compile(r"\bpreavviso[\s-]+(?:di\s+)?(?:errore|mancata)[\s-]+consegna\b", re.I)),
    ("mancata_consegna", re.compile(
        r"\bavviso\s+di\s+mancata\s+consegna\b|\bmancata\s+consegna\b|\berrore[\s-]+(?:di\s+|nella\s+)?consegna\b|"
        r"\bmessaggio\s+non\s+[eè]\s+stato\s+consegnato\b", re.I)),
    ("rilevazione_virus", re.compile(r"\brilevazione[\s-]+virus\b|\bproblema\s+di\s+sicurezza\b", re.I)),
    ("anomalia", re.compile(r"\banomalia\s+(?:nel\s+)?messaggio\b|\bbusta\s+di\s+anomalia\b", re.I)),
    ("presa_in_carico", re.compile(r"\bricevuta\s+di\s+presa\s+in\s+carico\b", re.I)),
    ("avvenuta_consegna", re.compile(
        r"\bricevuta\s+(?:(?:completa|breve|sintetica)\s+)?di\s+avvenuta\s+consegna\b|"
        r"\bstato\s+consegnato\s+nella\s+casella\s+di\s+destinazione\b", re.I)),
    ("accettazione", re.compile(r"\bricevuta\s+di\s+accettazione\b|\b[eè]\s+stato\s+accettato\s+dal\s+sistema\b", re.I)),
)
_DATICERT_TIPO_ATTR = re.compile(r"<(?:[\w-]+:)?postacert\b[^>]*?\btipo\s*=\s*[\"']([^\"']+)[\"']", re.I)
_DATICERT_TIPO_EL = re.compile(r"<(?:[\w-]+:)?tipo\b[^>]*>\s*([^<]+?)\s*</(?:[\w-]+:)?tipo>", re.I)


def _chiave(valore: Any) -> str:
    return re.sub(r"[\s-]+", "_", str(valore or "").strip().casefold())


def normalizza_tipo_ricevuta(valore: Any) -> str:
    """Valore di daticert/X-Ricevuta/etichetta interna → etichetta canonica ('' se non e' una ricevuta nota)."""
    chiave = _chiave(valore)
    if chiave in RICEVUTE_PEC:
        return chiave
    return _TIPI_DATICERT.get(chiave, "")


def tipo_daticert(xml_text: Any) -> str:
    """Attributo ``tipo`` di <postacert> (formato reale), con fallback sull'elemento <tipo>."""
    testo = str(xml_text or "")
    m = _DATICERT_TIPO_ATTR.search(testo)
    if m:
        return m.group(1).strip()
    if "postacert" in testo.casefold():
        m = _DATICERT_TIPO_EL.search(testo)
        if m:
            return m.group(1).strip()
    return ""


def tipo_ricevuta_da_oggetto(oggetto: Any, *, consenti_inoltro: bool = False) -> str:
    """Tipo dal SOLO prefisso fisso dell'oggetto; l'oggetto originale dopo i due punti e' ignorato.

    Con ``consenti_inoltro`` un prefisso «I:/Fwd:» e' tollerato solo per i tipi negativi: un avviso di
    mancata consegna inoltrato va comunque presidiato, una ricevuta positiva inoltrata non e' prova."""
    o = " ".join(str(oggetto or "").split())
    for inoltrato in ((False, True) if consenti_inoltro else (False,)):
        base = re.sub(_PREFISSO_INOLTRO, "", o, flags=re.I) if inoltrato else o
        if inoltrato and base == o:
            break
        for etichetta, pattern in _OGGETTO_RICEVUTA:
            if pattern.match(base.lstrip()):
                if inoltrato and etichetta not in RICEVUTE_NEGATIVE:
                    return ""
                return etichetta
    return ""


def classifica_ricevuta_pec(
    oggetto: Any = "",
    corpo: Any = "",
    *,
    x_ricevuta: Any = "",
    daticert_tipo: Any = "",
    x_trasporto: Any = "",
    usa_corpo: bool = True,
) -> tuple[str, str]:
    """(etichetta canonica, fonte) della ricevuta PEC; ("", fonte) se il messaggio non e' una ricevuta.

    Ordine: tipo in daticert.xml → intestazione X-Ricevuta → prefisso fisso dell'oggetto → frasi
    standard del corpo (negative prima delle positive, a parola intera)."""
    for fonte, valore in (("daticert", daticert_tipo), ("x-ricevuta", x_ricevuta)):
        chiave = _chiave(valore)
        if not chiave:
            continue
        if chiave in _TIPI_NON_RICEVUTA:
            return "", f"{fonte}:{chiave}"
        etichetta = normalizza_tipo_ricevuta(chiave)
        if etichetta:
            return etichetta, fonte
    trasporto = _chiave(x_trasporto)
    if trasporto == "errore":
        return "anomalia", "x-trasporto"
    if trasporto == "posta_certificata" and not _chiave(x_ricevuta):
        return "", "x-trasporto:posta_certificata"
    o = " ".join(str(oggetto or "").split())
    if _SDI.search(o):
        return "", "oggetto:sdi"
    etichetta = tipo_ricevuta_da_oggetto(o, consenti_inoltro=True)
    if etichetta:
        return etichetta, "oggetto"
    if re.match(r"^\s*posta\s+certificata\s*:", o, re.I):
        return "", "oggetto:posta_certificata"
    if usa_corpo:
        c = " ".join(str(corpo or "")[:20000].split())
        for etichetta, pattern in _CORPO_RICEVUTA:
            if pattern.search(c):
                return etichetta, "corpo"
    return "", ""
