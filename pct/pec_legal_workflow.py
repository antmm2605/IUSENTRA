"""Classificazione legale conservativa per PEC giudiziarie e SDI.

Le regole operative sono collegate a docs/LEGAL_NOTIFICATIONS_AND_TELEMATIC_REGISTRY.md
e alle specifiche ministeriali versionate in docs/specs/ministero. Il modulo non
scarica contenuti esterni: classifica solo dati PEC gia' disponibili nel flusso.
"""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any, Iterable
from urllib.parse import urlsplit

from pct.pec_oggetti_ufficiali import classifica_oggetto_ufficiale, classifica_ricevuta_pec, tipo_daticert


FORWARD_PREFIX_RE = re.compile(r"^\s*(?:fwd?|i|r|re|rif|inoltro)\s*:\s*", re.I)
ROLE_RE = re.compile(
    r"\b(?P<number>\d{1,7})\s*/\s*(?P<year>\d{4})\s*(?:/\s*(?P<suffix>GDP|SIGP|CC|LAV|VG|FALL|ESM|ESIM|CASSCI|CASSPE|PENALE)"
    # Ruolo del Giudice di Pace scritto «RG 1234/2025 GDP» (registro SIGP), senza la barra finale.
    r"|\s+(?P<gdp>GDP|SIGP))\b",
    re.I,
)
RG_APP_RE = re.compile(r"\bn\.?\s*(?P<number>\d{1,7})[_/](?P<year>\d{4})\s*RG\s*APP\b", re.I)
RG_NR_RE = re.compile(r"\bn\.?\s*(?P<number>\d{1,7})[_/](?P<year>\d{4})\s*RG\s*NR\b", re.I)
GENERALE_CORTE_APPELLO_RE = re.compile(
    r"\bgenerale\s*/\s*(?P<year>\d{4})\s*/\s*0*(?P<number>\d{1,7})\s*/\s*Corte\s+di\s+Appello\b",
    re.I,
)
TECHNICAL_URL_HOSTS = (
    "schemi.processotelematico.giustizia.it",
    "www.w3.org",
    "w3.org",
    "uri.etsi.org",
    "ca1.agid.gov.it",
    "ocsp.intesigroup.com",
    "ocsp2.infocert.it",
    "cacert.actalis.it",
    "ivaservizi.agenziaentrate.gov.it",
)
TECHNICAL_URL_MARKERS = (".dtd", ".xsd", "xmldsig", "signedproperties", "/ocsp", "ocsp0", "/crl", "fattura")


REGISTRY_MAP: dict[str, dict[str, str]] = {
    "CC": {
        "registro_normalizzato": "CC",
        "tabella_ministeriale": "SICID_CONTENZIOSO_CIVILE",
        "materia": "contenzioso civile",
        "canale": "PCT_SICID",
    },
    "LAV": {
        "registro_normalizzato": "LAV",
        "tabella_ministeriale": "SICID_LAVORO",
        "materia": "lavoro",
        "canale": "PCT_SICID",
    },
    "VG": {
        "registro_normalizzato": "VG",
        "tabella_ministeriale": "SICID_VOLONTARIA_GIURISDIZIONE",
        "materia": "volontaria giurisdizione",
        "canale": "PCT_SICID",
    },
    "GDP": {
        "registro_normalizzato": "SIGP",
        "tabella_ministeriale": "SIGP_GIUDICE_DI_PACE",
        "materia": "Giudice di Pace",
        "canale": "SIGP",
    },
    "SIGP": {
        "registro_normalizzato": "SIGP",
        "tabella_ministeriale": "SIGP_GIUDICE_DI_PACE",
        "materia": "Giudice di Pace",
        "canale": "SIGP",
    },
    "FALL": {
        "registro_normalizzato": "FALL",
        "tabella_ministeriale": "SIECIC_PROCEDURE_CONCORSUALI",
        "materia": "procedure concorsuali",
        "canale": "PCT_SIECIC",
    },
    "ESM": {
        "registro_normalizzato": "ESM",
        "tabella_ministeriale": "SIECIC_ESECUZIONI_MOBILIARI",
        "materia": "esecuzioni mobiliari",
        "canale": "PCT_SIECIC",
    },
    "ESIM": {
        "registro_normalizzato": "ESIM",
        "tabella_ministeriale": "SIECIC_ESECUZIONI_IMMOBILIARI",
        "materia": "esecuzioni immobiliari",
        "canale": "PCT_SIECIC",
    },
    "CASSCI": {
        "registro_normalizzato": "CASSCI",
        "tabella_ministeriale": "CASSAZIONE_CIVILE",
        "materia": "Cassazione civile",
        "canale": "CASSCI",
    },
    "CASSPE": {
        "registro_normalizzato": "CASSPE",
        "tabella_ministeriale": "CASSAZIONE_PENALE",
        "materia": "Cassazione penale",
        "canale": "CASSPE",
    },
    "PENALE": {
        "registro_normalizzato": "PENALE",
        "tabella_ministeriale": "PENALE_DEDICATO",
        "materia": "penale",
        "canale": "PDP_PENALE",
    },
}


def normalizza_oggetto_pec(subject: str) -> str:
    value = str(subject or "").strip()
    previous = ""
    while value and value != previous:
        previous = value
        value = FORWARD_PREFIX_RE.sub("", value).strip()
    return re.sub(r"\s+", " ", value)


def _lower(value: str) -> str:
    return str(value or "").lower()


def _host_matches(host: str, domain: str) -> bool:
    host = host.rstrip(".").lower()
    domain = domain.rstrip(".").lower()
    return host == domain or host.endswith(f".{domain}")


def _is_technical_process_url(url: str) -> bool:
    parsed = urlsplit(str(url or ""))
    host = (parsed.hostname or "").lower().rstrip(".")
    path = f"{parsed.path or ''}?{parsed.query or ''}".lower()
    return any(_host_matches(host, domain) for domain in TECHNICAL_URL_HOSTS) or any(
        marker in path for marker in TECHNICAL_URL_MARKERS
    )


def _has_remote_hearing_url(text: str) -> bool:
    for match in re.finditer(r"https?://\S+", str(text or ""), re.I):
        url = match.group(0).rstrip(").,;")
        if _is_technical_process_url(url):
            continue
        host = (urlsplit(url).hostname or "").lower()
        if any(_host_matches(host, domain) for domain in ("teams.microsoft.com", "zoom.us", "meet.google.com", "webex.com")):
            return True
    return bool(re.search(r"teams\.microsoft|zoom\.us|meet\.google|webex", str(text or ""), re.I))


def _is_decisive_judgment_text(text: str) -> bool:
    lower = _lower(text)
    if not lower:
        return False
    if "sentenza a verbale" in lower:
        return True
    if "definitivamente decidendo" in lower and "sentenza" in lower:
        return True
    if "decide la causa con sentenza" in lower:
        return True
    if re.search(r"\bsentenza\b.{0,100}\bart\.?\s*429\b", lower):
        return True
    if re.search(r"\bart\.?\s*429\b.{0,100}\bsentenza\b", lower):
        return True
    return False


def _attachment_names(attachments: Iterable[Any]) -> list[str]:
    names: list[str] = []
    for item in attachments or []:
        if isinstance(item, dict):
            name = str(item.get("filename") or item.get("nome") or item.get("nome_file") or "")
        else:
            name = str(getattr(item, "filename", "") or getattr(item, "nome", "") or "")
        if name:
            names.append(name)
    return names


def estrai_registri(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for match in ROLE_RE.finditer(text or ""):
        suffix = (match.group("suffix") or match.group("gdp") or "").upper()
        key = (match.group("number"), match.group("year"), suffix)
        if key in seen:
            continue
        seen.add(key)
        registry = dict(REGISTRY_MAP.get(suffix, REGISTRY_MAP["CC"]))
        results.append(
            {
                "numero": match.group("number"),
                "anno": match.group("year"),
                "suffisso": suffix,
                **registry,
            }
        )
    for label, pattern in (("RG_APP", RG_APP_RE), ("RG_NR", RG_NR_RE)):
        for match in pattern.finditer(text or ""):
            number = str(int(match.group("number")))
            key = (number, match.group("year"), label)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "numero": number,
                    "anno": match.group("year"),
                    "suffisso": label,
                    "registro_normalizzato": label,
                    "tabella_ministeriale": "PENALE_DEDICATO",
                    "materia": "penale",
                    "canale": "PDP_PENALE",
                }
            )
    for match in GENERALE_CORTE_APPELLO_RE.finditer(text or ""):
        number = str(int(match.group("number")))
        key = (number, match.group("year"), "RG_APP")
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "numero": number,
                "anno": match.group("year"),
                "suffisso": "RG_APP",
                "registro_normalizzato": "RG_APP",
                "tabella_ministeriale": "PENALE_DEDICATO",
                "materia": "penale",
                "canale": "PDP_PENALE",
                "fonte_ruolo": "generale_corte_appello",
            }
        )
    return results


def _event_payload(
    event_type: str,
    label: str,
    priority: str,
    action: str,
    *,
    creates_deadline: bool = False,
    closes_deposit: bool = False,
    human_review: bool = True,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "event_label": label,
        "priority": priority,
        "azione_proposta": action,
        "creates_deadline": creates_deadline,
        "closes_deposit": closes_deposit,
        "human_review_required": human_review,
    }


# Comunicazione.xml dei registri di cancelleria (Specifiche tecniche DGSIA, D.M. 44/2011 art. 34; art. 16 d.l.
# 179/2012): <Oggetto> e' l'evento registrato dalla cancelleria, dato certificato e non dedotto dal testo.
COMUNICAZIONE_OGGETTO_RE = re.compile(r"<Comunicazione\b.*?<Oggetto>\s*(.*?)\s*</Oggetto>", re.S | re.I)


BIGLIETTO_OGGETTO_RE = re.compile(r"Tipo Evento:.{0,120}?Oggetto:\s*(.+?)(?:\s+Descrizione:|\r?\n|$)", re.S)


def oggetto_comunicazione_cancelleria(text: str) -> str:
    match = COMUNICAZIONE_OGGETTO_RE.search(text or "")
    if not match and "notificazione di cancelleria" in _lower(text):
        # Biglietto di cancelleria (art. 16 d.l. 179/2012): «Data Evento … Tipo Evento … Oggetto: …»
        match = BIGLIETTO_OGGETTO_RE.search(text or "")
    if not match or "giustiziacert" not in _lower(text):
        return ""
    return " ".join(html.unescape(match.group(1)).split())


def _evento_da_comunicazione(oggetto: str, text: str) -> dict[str, Any] | None:
    """Evento dal registro della cancelleria; None per le sentenze, gia' riconosciute dal testo del provvedimento."""
    u = oggetto.upper()
    if not u or "SENTENZA" in u:
        return None
    if "NOTE IN SOST" in u:
        return _event_payload(
            "udienza_sostituita_da_note_scritte",
            f"Trattazione scritta (art. 127-ter c.p.c.): {oggetto}",
            "alta",
            "Leggere il provvedimento allegato, registrare il termine per il deposito delle note e la data che sostituisce "
            "l'udienza; aggiornare o revocare l'udienza precedente senza cancellarne la storia.",
            creates_deadline=True,
        )
    if "RINVIO" in u or "DIFFERIMENTO" in u:
        return _event_payload("rinvio_udienza", f"Rinvio udienza: {oggetto}", "alta",
                              "Aggiornare evento precedente, conservare vecchia data in timeline e creare nuova data.",
                              creates_deadline=True)
    if "FISSAZIONE UDIENZA" in u or "ANTICIPAZIONE UDIENZA" in u:
        if _has_remote_hearing_url(text):
            return _event_payload("udienza_online", f"Udienza online: {oggetto}", "alta",
                                  "Salvare link, piattaforma, eventuale codice e creare promemoria tecnico.", creates_deadline=True)
        return _event_payload("udienza_fissata", f"Udienza fissata: {oggetto}", "alta",
                              "Creare o aggiornare scadenziario; la modalita' (presenza, remoto, note) va letta dal provvedimento.",
                              creates_deadline=True)
    if "SOSTITUZIONE GIUDICE" in u:
        return _event_payload("sostituzione_giudice", "Sostituzione giudice", "media",
                              "Aggiornare giudice del fascicolo, salvare precedente e attuale, verificare udienze future.")
    if "DESIGNAZIONE GIUDICE" in u:
        return _event_payload("designazione_giudice", "Designazione del giudice", "media",
                              "Registrare il giudice designato nel fascicolo e verificare le udienze future.")
    return _event_payload("comunicazione_cancelleria", f"Comunicazione di cancelleria: {oggetto}", "media",
                          "Leggere comunicazione e allegato e collegarli al fascicolo; nessuna scadenza senza un termine nel provvedimento.")


# Ricevute PEC (d.P.R. 68/2005; d.m. 2/11/2005): l'etichetta viene dal classificatore unico
# (daticert.xml, X-Ricevuta, prefisso fisso dell'oggetto). Le ricevute negative restano
# «mancata_consegna_pec» (priorita' P0 a valle) con l'etichetta del tipo effettivo.
_EVENTI_RICEVUTA: dict[str, tuple[str, str, str, str]] = {
    "accettazione": ("ricevuta_accettazione_pec", "Ricevuta di accettazione PEC", "media",
                     "Collegare alla notifica o al deposito senza chiudere il workflow se mancano consegna o esito."),
    "presa_in_carico": ("ricevuta_accettazione_pec", "Ricevuta di presa in carico PEC", "media",
                        "Prova parziale: collegare alla notifica o al deposito e attendere la ricevuta di consegna."),
    "avvenuta_consegna": ("ricevuta_consegna_pec", "Ricevuta di avvenuta consegna", "alta",
                          "Conservare la prova e collegarla al workflow notifiche/deposito."),
    "mancata_consegna": ("mancata_consegna_pec", "Mancata consegna PEC", "rossa",
                         "Creare alert immediato e coda di revisione."),
    "preavviso_mancata_consegna": ("mancata_consegna_pec", "Preavviso di mancata consegna PEC (superati i tempi massimi)",
                                   "rossa", "Creare alert immediato e coda di revisione."),
    "non_accettazione": ("mancata_consegna_pec", "Avviso di non accettazione PEC", "rossa",
                         "Il messaggio non e' partito: creare alert immediato, correggere e ritrasmettere."),
    "rilevazione_virus": ("mancata_consegna_pec", "Rilevazione virus: messaggio PEC non consegnato", "rossa",
                          "Creare alert immediato, verificare gli allegati e ritrasmettere."),
}

# Rifiuto/non accettazione del deposito da parte della cancelleria: va letto PRIMA delle frasi di
# accettazione, che altrimenti vincerebbero su «il deposito non e' stato accettato».
_RIFIUTO_DEPOSITO_RE = re.compile(
    r"\brifiut\w*|\bnon\s+(?:[eè]|e['’])\s+stat[oa]\s+accettat\w*|\bnon\s+accettat\w*|"
    r"\bmancata\s+accettazione\s+(?:del\s+)?deposito\b|\bnon\s+accettazione\s+(?:del\s+)?deposito\b",
    re.I,
)
_RINVIO_UDIENZA_RE = re.compile(
    r"\budienza\b[^.;\n<>]{0,60}?\b(?:[eè]\s+(?:stata\s+)?|viene\s+|risulta\s+)?rinviat\w*|"
    r"\brinvio\b[^.;\n<>]{0,40}?\budienza\b",
    re.I,
)
_NOTE_SCRITTE_RE = re.compile(
    r"\b127[\s-]*ter\b|\btrattazione\s+scritta\b|\bnote\s+scritte\b|\bnote\s+in\s+sostituzione\b", re.I)
_DECRETO_171_BIS_RE = re.compile(r"\b171[\s-]*bis\b", re.I)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _testo_luogo(text: str) -> str:
    """Testo per luogo/modalita' dell'udienza: senza indirizzi email (il mittente
    «tribunale.x@…giustiziacert.it» non dice che l'udienza e' in presenza)."""
    return _EMAIL_RE.sub(" ", str(text or ""))


def _evento_ricevuta(etichetta: str) -> dict[str, Any] | None:
    if etichetta == "anomalia":
        return _event_payload("pec_non_riconosciuta", "Anomalia del messaggio PEC", "alta",
                              "Messaggio con anomalia del gestore: verificare mittente e contenuto prima di usarlo.")
    row = _EVENTI_RICEVUTA.get(etichetta)
    if row is None:
        return None
    event_type, label, priority, action = row
    return _event_payload(event_type, label, priority, action)


def _classifica_evento(text: str, attachment_names: list[str], *, place_text: str | None = None) -> dict[str, Any]:
    lower = _lower(text)
    has_video_link = _has_remote_hearing_url(text)
    place_lower = _lower(_testo_luogo(text if place_text is None else place_text))
    has_place = any(token in place_lower for token in ("aula", "piano", "sezione", "in presenza", "tribunale"))
    deposit_outcome = any(
        token in lower
        for token in ("esito intervento", "accettazione deposito", "accettazione del deposito", "deposito accettato",
                      "accettato dalla cancelleria", "rifiuto deposito", "deposito rifiutato")
    )
    if ("rifiuto deposito" in lower or "deposito rifiutato" in lower) or (
        deposit_outcome and _RIFIUTO_DEPOSITO_RE.search(lower)
    ):
        return _event_payload("rifiuto_deposito", "Rifiuto deposito", "rossa", "Aprire attività urgente e predisporre verifica per eventuale rideposito.")
    if "accettazione deposito" in lower or "deposito accettato" in lower:
        return _event_payload("accettazione_deposito", "Accettazione deposito", "alta", "Collegare al deposito e chiudere il workflow solo se ricevute ed esiti sono completi.", closes_deposit=True)
    if "esito controlli automatici" in lower:
        # Terza PEC del deposito telematico (Specifiche tecniche DGSIA, art. 34 D.M. 44/2011): l'esito e' in
        # EsitoAtto.xml; non e' un'udienza anche se l'oggetto riporta l'atto depositato «in vista dell'udienza».
        return _event_payload("esito_controlli", "Esito controlli automatici del deposito", "alta",
                              "Leggere EsitoAtto.xml, collegare al deposito e segnalare anomalie WARN/ERROR/FATAL; "
                              "non chiude il deposito senza l'esito dell'intervento della cancelleria.")
    dal_registro = _evento_da_comunicazione(oggetto_comunicazione_cancelleria(text), text)
    if dal_registro is not None:
        return dal_registro
    if "sost. giudice" in lower or "sostituzione giudice" in lower:
        return _event_payload("sostituzione_giudice", "Sostituzione giudice", "media", "Aggiornare giudice del fascicolo, salvare precedente e attuale, verificare udienze future.")
    if _is_decisive_judgment_text(text):
        return _event_payload(
            "sentenza_a_verbale",
            "Sentenza a verbale / provvedimento decisorio",
            "alta",
            "Archiviare la sentenza, estrarre dispositivo e spese, aprire presidio per valutare o preparare la notifica; non creare opposizione 127-ter dalla sentenza.",
            creates_deadline=True,
        )
    if "deposito ctu" in lower or re.search(r"\bctu\b", lower):
        return _event_payload("deposito_ctu", "Deposito CTU", "alta", "Archiviare CTU, avvisare responsabile e creare attività per verificare termini osservazioni.", creates_deadline=True)
    if any(token in lower for token in ("deposito sentenza", "pubblicazione sentenza", "deposito minuta", "pubblicazione minuta")):
        return _event_payload("deposito_sentenza", "Deposito sentenza o minuta", "alta", "Archiviare il provvedimento e creare attività per esame sentenza e valutazione impugnazione.", creates_deadline=True)
    if "decreto" in lower and "notificare" in lower or "ricorso da notificare" in lower:
        return _event_payload("decreto_o_ricorso_da_notificare", "Decreto o ricorso da notificare", "alta", "Preparare bozza notifica e relata; nessun invio senza approvazione umana.", creates_deadline=True)
    if _NOTE_SCRITTE_RE.search(lower) and "udienza" in lower:
        return _event_payload(
            "udienza_sostituita_da_note_scritte",
            "Trattazione scritta (art. 127-ter c.p.c.)",
            "alta",
            "Leggere il provvedimento allegato, registrare il termine per il deposito delle note e la data che sostituisce "
            "l'udienza; aggiornare o revocare l'udienza precedente senza cancellarne la storia.",
            creates_deadline=True,
        )
    if _DECRETO_171_BIS_RE.search(lower) and "decreto" in lower:
        return _event_payload(
            "decreto_171_bis",
            "Decreto di verifiche preliminari (art. 171-bis c.p.c.)",
            "alta",
            "Leggere il decreto: conferma o differimento della prima udienza e termini delle memorie integrative "
            "(art. 171-ter c.p.c.) da registrare dopo verifica.",
            creates_deadline=True,
        )
    if _RINVIO_UDIENZA_RE.search(lower):
        return _event_payload("rinvio_udienza", "Rinvio udienza", "alta", "Aggiornare evento precedente, conservare vecchia data in timeline e creare nuova data.", creates_deadline=True)
    if "revoca udienza" in lower or "udienza revocata" in lower:
        return _event_payload("revoca_udienza", "Revoca udienza", "alta", "Sospendere l'evento e avvisare il responsabile senza cancellare la timeline.")
    if "conferma udienza" in lower:
        return _event_payload("conferma_udienza", "Conferma udienza", "media", "Aggiornare stato senza duplicare l'udienza.", creates_deadline=True)
    if "udienza online" in lower or has_video_link:
        return _event_payload("udienza_online", "Udienza online", "alta", "Salvare link, piattaforma, eventuale codice e creare promemoria tecnico.", creates_deadline=True)
    if "udienza in presenza" in lower or ("udienza" in lower and has_place):
        return _event_payload("udienza_in_presenza", "Udienza in presenza", "alta", "Estrarre aula, piano, sezione e creare promemoria operativo.", creates_deadline=True)
    if ("udienza fissata" in lower or "avviso udienza" in lower or "fissazione udienza" in lower) and not re.search(
        r"(istanza|attesa|richiesta|in attesa)\s+(di\s+)?fissazione\s+(dell'?\s*)?udienza", lower
    ):
        return _event_payload("udienza_fissata", "Udienza fissata", "alta", "Creare o aggiornare scadenziario; se la modalità manca, segnare da verificare.", creates_deadline=True)
    if "deposito ricorso per cassazione" in lower and ("proc. pen" in lower or "rg app" in lower or "rg nr" in lower):
        return _event_payload("deposito_ricorso_cassazione_penale", "Deposito ricorso per Cassazione penale", "alta", "Classificare come penale/Cassazione, estrarre RG APP e RG NR, leggere messaggio originale allegato.")
    if "penale.ptel.giustiziacert.it" in lower or "notifichepenali" in lower:
        return _event_payload(
            "comunicazione_penale_pdp",
            "Comunicazione penale / PDP",
            "media",
            "Collegare al fascicolo penale e verificare il contenuto autorizzato prima di creare scadenze o chiudere workflow.",
        )
    if any(name.lower().endswith(".eml") for name in attachment_names) and "giustiziacert" in lower:
        return _event_payload("messaggio_originale_giustiziacert", "Messaggio giustiziacert con originale allegato", "media", "Leggere anche il messaggio originale allegato e conservare fonte.")
    return _event_payload("pec_non_riconosciuta", "PEC non riconosciuta", "media", "Conservare allegati e inviare in coda di revisione umana.")


def _classifica_famiglia(text: str, sender: str, registri: list[dict[str, Any]]) -> tuple[str, str]:
    lower = _lower(text)
    sender_lower = _lower(sender)
    if "fatturapa.it" in sender_lower or sender_lower.startswith("sdi") or "sistema di interscambio" in lower:
        return "fattura_sdi", "Fattura elettronica SDI"
    if ("cassazione" in lower or re.search(r"\bcass\b", lower)) and (
        "penale" in lower
        or "rg app" in lower
        or "rg nr" in lower
        or any(item.get("registro_normalizzato") in {"PENALE", "CASSPE"} for item in registri)
    ):
        return "cassazione_penale", "Cassazione penale"
    if "cassazione" in lower:
        return "cassazione_civile", "Cassazione civile"
    if any(item.get("registro_normalizzato") == "SIGP" for item in registri) or re.search(
        r"\bgiudice\s+di\s+pace\b", lower
    ):
        return "comunicazione_giudice_pace", "Comunicazione Giudice di Pace"
    if any(item.get("registro_normalizzato") == "LAV" for item in registri):
        return "comunicazione_lavoro", "Comunicazione lavoro"
    if any(item.get("registro_normalizzato") == "VG" for item in registri):
        return "volontaria_giurisdizione", "Volontaria giurisdizione"
    if "deposito telematico" in lower or "busta telematica" in lower or "datiatto.xml" in lower:
        return "deposito_pct_civile", "Deposito PCT civile"
    if (
        "deposito atti penali" in lower
        or "pdp" in lower
        or "proc. pen" in lower
        or "penale.ptel.giustiziacert.it" in sender_lower
        or "notifichepenali" in sender_lower
        or "depositoattipenali" in sender_lower
        or any(item.get("registro_normalizzato") in {"RG_APP", "RG_NR", "PENALE"} for item in registri)
    ):
        return "deposito_penale_pdp", "Deposito penale / PDP"
    if "notificazione ai sensi della legge n. 53" in lower or "l. 53/1994" in lower or "relata" in lower:
        return "notifica_avvocato", "Notifica avvocato"
    if any(item.get("registro_normalizzato") in {"FALL"} for item in registri) or any(
        token in lower for token in ("liquidazione giudiziale", "procedura concorsuale", "concordato preventivo", "falliment", "curatore", "giudice delegato")
    ):
        return "procedure_concorsuali", "Procedure concorsuali"
    if any(item.get("registro_normalizzato") in {"ESM", "ESIM"} for item in registri) or any(
        token in lower for token in ("esecuzione immobiliare", "esecuzione mobiliare", "pignoramento", "vendita all'asta", "custode giudiziario", "delega alla vendita")
    ):
        return "esecuzione", "Esecuzione (mobiliare/immobiliare)"
    if any(
        token in lower for token in ("tribunale per i minorenni", "responsabilita genitoriale", "affidamento dei figli", "473-bis", "curatore speciale del minore", "adozione")
    ):
        return "famiglia_minori", "Famiglia e minori"
    if "giustizia-amministrativa" in sender_lower or any(
        token in lower for token in ("tribunale amministrativo regionale", " tar ", "consiglio di stato", "processo amministrativo telematico", "p.a.t.")
    ):
        return "comunicazione_pat", "Comunicazione PAT (amministrativo)"
    if any(
        token in lower for token in ("corte di giustizia tributaria", "commissione tributaria", "processo tributario telematico", "sigit", "p.t.t.")
    ):
        return "comunicazione_ptt_sigit", "Comunicazione PTT/SIGIT (tributario)"
    if "cancelleria" in lower or "giustiziacert" in sender_lower:
        return "comunicazione_cancelleria_civile", "Comunicazione cancelleria civile"
    if "controparte" in lower:
        return "pec_controparte", "PEC da controparte"
    return "pec_non_riconosciuta", "PEC non riconosciuta da revisione umana"


def _modalita_udienza(text: str) -> dict[str, str]:
    text = _testo_luogo(text)
    lower = _lower(text)
    link_match = re.search(r"https?://\S+", text or "")
    if link_match:
        link = link_match.group(0).rstrip(").,;")
        if not _is_technical_process_url(link) and _has_remote_hearing_url(link):
            return {"modalita": "online", "link": link, "luogo": "videoconferenza"}
    if any(token in lower for token in ("aula", "piano", "in presenza", "tribunale")):
        aula = re.search(r"\baula\s+([A-Za-z0-9/-]+)", text or "", re.I)
        return {"modalita": "in presenza", "link": "", "luogo": f"Aula {aula.group(1)}" if aula else "ufficio giudiziario"}
    if "udienza" in lower:
        return {"modalita": "da verificare", "link": "", "luogo": "da verificare"}
    return {"modalita": "", "link": "", "luogo": ""}


def _correlation_key(
    normalized_subject: str,
    registri: list[dict[str, Any]],
    sender: str,
    attachment_names: list[str],
) -> str:
    registry_part = "|".join(
        f"{item.get('numero')}/{item.get('anno')}/{item.get('registro_normalizzato')}"
        for item in registri
    )
    attachments_part = "|".join(sorted(name.lower() for name in attachment_names))
    raw = "|".join([normalized_subject.lower(), registry_part, sender.lower(), attachments_part])
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def classifica_pec_legale(
    *,
    subject: str,
    body: str = "",
    sender: str = "",
    recipients: Iterable[str] | None = None,
    attachments: Iterable[Any] | None = None,
    message_id: str = "",
    receipt_type: str = "",
    receipt_type_known: bool = False,
) -> dict[str, Any]:
    normalized_subject = normalizza_oggetto_pec(subject)
    attachment_names = _attachment_names(attachments or [])
    text = "\n".join([normalized_subject, str(body or ""), str(sender or ""), " ".join(attachment_names)])
    registri = estrai_registri(text)
    family, family_label = _classifica_famiglia(text, sender, registri)
    if not receipt_type_known:
        # I messaggi del Sistema di Interscambio («Notifica di mancata consegna» della fattura) non sono
        # ricevute PEC: per loro valgono solo daticert e prefisso dell'oggetto, non le frasi del testo.
        receipt_type, _fonte = classifica_ricevuta_pec(
            subject,
            "\n".join([normalized_subject, str(body or "")]),
            daticert_tipo=tipo_daticert(body),
            usa_corpo=family != "fattura_sdi",
        )
    receipt_event = _evento_ricevuta(str(receipt_type or ""))
    event = receipt_event or _classifica_evento(
        text, attachment_names, place_text="\n".join([normalized_subject, str(body or "")])
    )
    ufficiale = None if receipt_event is not None else classifica_oggetto_ufficiale(subject, str(body or ""))
    if ufficiale is not None:
        family, family_label, event = ufficiale
    elif family == "fattura_sdi" and receipt_event is None:
        event = _event_payload(
            "fattura_sdi_mancata_consegna" if "mancata consegna" in _lower(text) else "fattura_sdi",
            "Fattura SDI - mancata consegna" if "mancata consegna" in _lower(text) else "Fattura elettronica SDI",
            "media",
            "Archiviare nel flusso fatturazione; non creare scadenza processuale.",
            human_review=False,
        )
    modalita = _modalita_udienza("\n".join([normalized_subject, str(body or "")]))
    audit_events = [
        "PEC legale analizzata",
        f"Famiglia PEC riconosciuta: {family_label}",
        f"Evento PEC riconosciuto: {event['event_label']}",
    ]
    if event["event_type"] == "pec_non_riconosciuta":
        audit_events.append("PEC non riconosciuta: inviata a revisione umana")
    return {
        "schema": "iusentra.pec.legal_workflow.v1",
        "message_id": message_id,
        "normalized_subject": normalized_subject,
        "family": family,
        "family_label": family_label,
        "event_type": event["event_type"],
        "event_label": event["event_label"],
        "priority": event["priority"],
        "azione_proposta": event["azione_proposta"],
        "registri": registri,
        "receipt_type": str(receipt_type or ""),
        "udienza": modalita,
        "documents": {
            "has_daticert": any(name.lower() in {"daticert.xml", "postacert.xml"} for name in attachment_names),
            "has_comunicazione_xml": any(name.lower() == "comunicazione.xml" for name in attachment_names),
            "has_original_eml": any(name.lower().endswith(".eml") for name in attachment_names),
            "has_pdf": any(name.lower().endswith(".pdf") for name in attachment_names),
            "has_p7m": any(name.lower().endswith(".p7m") for name in attachment_names),
            "attachment_names": attachment_names,
        },
        "receipt": {
            "closes_deposit": bool(event["closes_deposit"]),
            "does_not_close_deposit_reason": (
                "La ricevuta di accettazione PEC non chiude il deposito senza consegna ed esito cancelleria."
                if event["event_type"] == "ricevuta_accettazione_pec"
                else ""
            ),
        },
        "creates_deadline": bool(event["creates_deadline"]),
        "human_review_required": bool(event["human_review_required"]),
        "correlation_key": _correlation_key(normalized_subject, registri, sender, attachment_names),
        "correlation_inputs": {
            "message_id": message_id,
            "sender": sender,
            "recipients": list(recipients or []),
            "attachment_names": attachment_names,
        },
        "audit_events": audit_events,
    }
