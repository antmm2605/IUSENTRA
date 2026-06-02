"""Classificazione legale conservativa per PEC giudiziarie e SDI.

Le regole operative sono collegate a docs/LEGAL_NOTIFICATIONS_AND_TELEMATIC_REGISTRY.md
e alle specifiche ministeriali versionate in docs/specs/ministero. Il modulo non
scarica contenuti esterni: classifica solo dati PEC gia' disponibili nel flusso.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable


FORWARD_PREFIX_RE = re.compile(r"^\s*(?:fwd?|i|r|re|rif|inoltro)\s*:\s*", re.I)
ROLE_RE = re.compile(
    r"\b(?P<number>\d{1,7})\s*/\s*(?P<year>\d{4})\s*/\s*(?P<suffix>GDP|SIGP|CC|LAV|VG|FALL|ESM|ESIM|CASSCI|CASSPE|PENALE)\b",
    re.I,
)
RG_APP_RE = re.compile(r"\bn\.?\s*(?P<number>\d{1,7})[_/](?P<year>\d{4})\s*RG\s*APP\b", re.I)
RG_NR_RE = re.compile(r"\bn\.?\s*(?P<number>\d{1,7})[_/](?P<year>\d{4})\s*RG\s*NR\b", re.I)
GENERALE_CORTE_APPELLO_RE = re.compile(
    r"\bgenerale\s*/\s*(?P<year>\d{4})\s*/\s*0*(?P<number>\d{1,7})\s*/\s*Corte\s+di\s+Appello\b",
    re.I,
)


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
        suffix = match.group("suffix").upper()
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


def _classifica_evento(text: str, attachment_names: list[str]) -> dict[str, Any]:
    lower = _lower(text)
    has_video_link = bool(re.search(r"https?://\S+|teams\.microsoft|zoom\.us|meet\.google", lower))
    has_place = any(token in lower for token in ("aula", "piano", "sezione", "in presenza", "tribunale"))
    if "rifiuto deposito" in lower or "deposito rifiutato" in lower:
        return _event_payload("rifiuto_deposito", "Rifiuto deposito", "rossa", "Aprire attività urgente e predisporre verifica per eventuale rideposito.")
    if "accettazione deposito" in lower or "deposito accettato" in lower:
        return _event_payload("accettazione_deposito", "Accettazione deposito", "alta", "Collegare al deposito e chiudere il workflow solo se ricevute ed esiti sono completi.", closes_deposit=True)
    if "ricevuta di accettazione" in lower or "accettazione del messaggio" in lower:
        return _event_payload("ricevuta_accettazione_pec", "Ricevuta di accettazione PEC", "media", "Collegare alla notifica o al deposito senza chiudere il workflow se mancano consegna o esito.")
    if "avvenuta consegna" in lower or "ricevuta di consegna" in lower:
        return _event_payload("ricevuta_consegna_pec", "Ricevuta di avvenuta consegna", "alta", "Conservare la prova e collegarla al workflow notifiche/deposito.")
    if "mancata consegna" in lower:
        return _event_payload("mancata_consegna_pec", "Mancata consegna PEC", "rossa", "Creare alert immediato e coda di revisione.")
    if "sost. giudice" in lower or "sostituzione giudice" in lower:
        return _event_payload("sostituzione_giudice", "Sostituzione giudice", "media", "Aggiornare giudice del fascicolo, salvare precedente e attuale, verificare udienze future.")
    if "deposito ctu" in lower or re.search(r"\bctu\b", lower):
        return _event_payload("deposito_ctu", "Deposito CTU", "alta", "Archiviare CTU, avvisare responsabile e creare attività per verificare termini osservazioni.", creates_deadline=True)
    if any(token in lower for token in ("deposito sentenza", "pubblicazione sentenza", "deposito minuta", "pubblicazione minuta")):
        return _event_payload("deposito_sentenza", "Deposito sentenza o minuta", "alta", "Archiviare il provvedimento e creare attività per esame sentenza e valutazione impugnazione.", creates_deadline=True)
    if "decreto" in lower and "notificare" in lower or "ricorso da notificare" in lower:
        return _event_payload("decreto_o_ricorso_da_notificare", "Decreto o ricorso da notificare", "alta", "Preparare bozza notifica e relata; nessun invio senza approvazione umana.", creates_deadline=True)
    if "rinvio udienza" in lower or "udienza rinviata" in lower:
        return _event_payload("rinvio_udienza", "Rinvio udienza", "alta", "Aggiornare evento precedente, conservare vecchia data in timeline e creare nuova data.", creates_deadline=True)
    if "revoca udienza" in lower or "udienza revocata" in lower:
        return _event_payload("revoca_udienza", "Revoca udienza", "alta", "Sospendere l'evento e avvisare il responsabile senza cancellare la timeline.")
    if "conferma udienza" in lower:
        return _event_payload("conferma_udienza", "Conferma udienza", "media", "Aggiornare stato senza duplicare l'udienza.", creates_deadline=True)
    if "udienza online" in lower or has_video_link:
        return _event_payload("udienza_online", "Udienza online", "alta", "Salvare link, piattaforma, eventuale codice e creare promemoria tecnico.", creates_deadline=True)
    if "udienza in presenza" in lower or ("udienza" in lower and has_place):
        return _event_payload("udienza_in_presenza", "Udienza in presenza", "alta", "Estrarre aula, piano, sezione e creare promemoria operativo.", creates_deadline=True)
    if "udienza fissata" in lower or "avviso udienza" in lower or "fissazione udienza" in lower:
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
    if any(item.get("registro_normalizzato") == "SIGP" for item in registri):
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
    if "cancelleria" in lower or "giustiziacert" in sender_lower:
        return "comunicazione_cancelleria_civile", "Comunicazione cancelleria civile"
    if "controparte" in lower:
        return "pec_controparte", "PEC da controparte"
    return "pec_non_riconosciuta", "PEC non riconosciuta da revisione umana"


def _modalita_udienza(text: str) -> dict[str, str]:
    lower = _lower(text)
    link_match = re.search(r"https?://\S+", text or "")
    if link_match:
        return {"modalita": "online", "link": link_match.group(0), "luogo": "videoconferenza"}
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
) -> dict[str, Any]:
    normalized_subject = normalizza_oggetto_pec(subject)
    attachment_names = _attachment_names(attachments or [])
    text = "\n".join([normalized_subject, str(body or ""), str(sender or ""), " ".join(attachment_names)])
    registri = estrai_registri(text)
    family, family_label = _classifica_famiglia(text, sender, registri)
    event = _classifica_evento(text, attachment_names)
    if family == "fattura_sdi":
        event = _event_payload(
            "fattura_sdi_mancata_consegna" if "mancata consegna" in _lower(text) else "fattura_sdi",
            "Fattura SDI - mancata consegna" if "mancata consegna" in _lower(text) else "Fattura elettronica SDI",
            "media",
            "Archiviare nel flusso fatturazione; non creare scadenza processuale.",
            human_review=False,
        )
    modalita = _modalita_udienza(text)
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
