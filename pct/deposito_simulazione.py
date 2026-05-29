"""Supporto per prove deposito senza invio PEC reale.

Le funzioni di questo modulo non implementano regole ministeriali nuove: servono
solo a marcare depositi di prova e a generare ricevute sintetiche per verificare
il percorso applicativo interno senza spedire messaggi PEC.
"""

from __future__ import annotations

import hashlib
import html
from datetime import datetime
from typing import Any

SIMULATED_DEPOSIT_NOTE_MARKER = "[PROVA SENZA INVIO REALE - nessun atto realmente inviato]"

_SIMULATION_MARKERS = (
    SIMULATED_DEPOSIT_NOTE_MARKER,
    "[SIMULAZIONE DEMO",
    "[DEMO]",
    "pec simulata",
    "invio pec è fittizio",
    "invio pec e' fittizio",
    "nessun atto realmente inviato",
    "nessun documento inviato",
)

_FINAL_STATES = {"ACCETTATO_CANCELLERIA", "RIFIUTATO_CANCELLERIA"}
_BLOCKING_STATES = {"ERRORE", "ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA"}
_RECEIPT_LABELS = {
    "accettazione": "accettazione PEC",
    "consegna": "avvenuta consegna",
    "controlli": "controlli automatici",
    "cancelleria": "conferma deposito",
}

_SUBJECT_LABELS = {
    "accettazione": "ACCETTAZIONE DEPOSITO TELEMATICO",
    "consegna": "AVVENUTA CONSEGNA DEPOSITO TELEMATICO",
    "controlli": "ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO",
    "cancelleria": "ESITO CANCELLERIA DEPOSITO TELEMATICO",
}


def simulated_deposit_note(note: str = "") -> str:
    """Restituisce una nota marcata come prova senza invio reale."""

    clean_note = str(note or "").strip()
    if SIMULATED_DEPOSIT_NOTE_MARKER in clean_note:
        return clean_note
    return f"{SIMULATED_DEPOSIT_NOTE_MARKER} {clean_note}".strip()


def is_simulated_deposit(deposito: Any) -> bool:
    """Riconosce depositi creati dal percorso di prova o da vecchie prove Demo."""

    text = " ".join(
        str(getattr(deposito, field, "") or "")
        for field in ("note", "messaggio", "pec_destinatario", "registrato_da")
    ).casefold()
    return any(marker.casefold() in text for marker in _SIMULATION_MARKERS)


def receipt_flags(deposito: Any) -> dict[str, bool]:
    return {
        "accettazione": bool(getattr(deposito, "ricevuta_accettazione", "")),
        "consegna": bool(getattr(deposito, "ricevuta_consegna", "")),
        "controlli": bool(getattr(deposito, "ricevuta_controlli_automatici", "")),
        "cancelleria": bool(getattr(deposito, "ricevuta_cancelleria", "")),
    }


def receipt_steps(deposito: Any) -> list[dict[str, Any]]:
    flags = receipt_flags(deposito)
    return [
        {
            "id": key,
            "label": label[:1].upper() + label[1:],
            "done": flags[key],
            "tone": "success" if flags[key] else "neutral",
        }
        for key, label in _RECEIPT_LABELS.items()
    ]


def next_receipt_phase(deposito: Any) -> str:
    flags = receipt_flags(deposito)
    for phase in ("accettazione", "consegna", "controlli", "cancelleria"):
        if not flags[phase]:
            return phase
    return "completo"


def build_simulated_receipt_text(
    *,
    deposito: Any,
    fase: str,
    fascicolo_ref: str = "",
    generated_at: str | None = None,
) -> str:
    label = _RECEIPT_LABELS.get(fase, fase)
    when = generated_at or datetime.now().isoformat(timespec="seconds")
    try:
        parsed = datetime.fromisoformat(when)
    except ValueError:
        parsed = datetime.now()
    day = parsed.strftime("%d/%m/%Y")
    iso_day = parsed.date().isoformat()
    time = parsed.strftime("%H:%M:%S")
    did = str(getattr(deposito, "id", "") or "PROVA").strip() or "PROVA"
    act = str(getattr(deposito, "tipo_atto", "") or "Atto").strip() or "Atto"
    ref_id = hashlib.sha1(f"{did}:{fase}".encode("utf-8")).hexdigest()[:12].upper()
    idbusta = int(hashlib.sha1(did.encode("utf-8")).hexdigest()[:8], 16) % 900000000 + 100000000
    message_id = f"PROVA-{ref_id}@iusentra.invalid"
    original_id = f"<jpec.prova.{ref_id.lower()}@pec.invalid>"
    subject = f"{_SUBJECT_LABELS.get(fase, label.upper())}: {act} [{did}] [RefID_PROVA_{ref_id}]"
    sender = "ufficio.telematico@civile.ptel.giustiziacert.invalid"
    recipient = "studio-legale@pec.invalid"
    role_number = html.escape(fascicolo_ref or "non indicato")
    subject_xml = html.escape(subject)
    act_xml = html.escape(act)
    sender_xml = html.escape(sender)
    recipient_xml = html.escape(recipient)
    original_id_xml = html.escape(original_id)
    message_id_xml = html.escape(message_id)
    if fase == "controlli":
        codice_esito = "-1"
        outcome = (
            "NOME FILE: documento_allegato.pdf\n"
            "Certificato firma scaduto!. Sono necessarie verifiche tecniche da parte dell'ufficio ricevente."
            "NOME FILE: DatiAtto.xml.p7m\n"
            "Atto non conforme alle specifiche. In attesa di conferma da parte della cancelleria: "
            "l'atto verrà comunque accettato, non è necessario effettuare nuovamente il deposito"
        )
    elif fase == "cancelleria":
        codice_esito = "2"
        outcome = "Accettazione manuale avvenuta con successo"
    else:
        codice_esito = "2"
        outcome = f"Ricevuta di {label} acquisita nella prova"
    daticert = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<postacert tipo="posta-certificata" errore="nessuno">'
        "<intestazione>"
        f"<mittente>{sender_xml}</mittente>"
        f'<destinatari tipo="certificato">{recipient_xml}</destinatari>'
        f"<risposte>{sender_xml}</risposte>"
        f"<oggetto>{subject_xml}</oggetto>"
        "</intestazione>"
        "<dati>"
        "<gestore-emittente>Gestore PEC di prova</gestore-emittente>"
        f'<data zona="+0200"><giorno>{day}</giorno><ora>{time}</ora></data>'
        f"<identificativo>{message_id_xml}</identificativo>"
        f"<msgid>{original_id_xml}</msgid>"
        '<ricevuta tipo="breve"/>'
        "</dati>"
        "</postacert>"
    )
    esito_atto = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE EsitoAtto SYSTEM "http://schemi.processotelematico.giustizia.it/Schemi/EsitoAtto.dtd">'
        "<EsitoAtto>"
        f"<IdMsgMitt>DEPOSITO TELEMATICO: {act_xml} [{did}] [RefID_PROVA_{ref_id}]</IdMsgMitt>"
        "<IdMsgPdA><CodicePdA></CodicePdA><Anno></Anno>"
        f"<IdMsg>{original_id_xml}</IdMsg>"
        "</IdMsgPdA>"
        "<DatiEsito>"
        '<Impronta algoritmo="SHA-1" codifica="base64" tipoImpronta="File">PROVA-SHA1-SANIFICATA</Impronta>'
        "<MsgEsito>"
        f"<NumeroRuolo>{role_number}</NumeroRuolo>"
        f"<CodiceEsito>{codice_esito}</CodiceEsito>"
        f"<DescrizioneEsito><![CDATA[\n--\nIDBUSTA: {idbusta}\n{outcome}\n]]></DescrizioneEsito>"
        "</MsgEsito>"
        f'<Tempo><Data>{iso_day}</Data><Ora zoneDesignator="+0200">{time}</Ora></Tempo>'
        "<RefId></RefId>"
        "</DatiEsito>"
        "</EsitoAtto>"
    )
    postacert = (
        "Received: from prova.iusentra.invalid by pec.invalid for studio-legale@pec.invalid; "
        f"{parsed.strftime('%a, %d %b %Y %H:%M:%S')} +0200\n"
        f"Date: {parsed.strftime('%a, %d %b %Y %H:%M:%S')} +0200\n"
        f"From: {sender}\n"
        f"To: {recipient}\n"
        f"Message-ID: <{message_id}>\n"
        f"Subject: {subject}\n"
        "MIME-Version: 1.0\n"
        "Content-Type: multipart/mixed; boundary=\"----=_Part_PROVA_IUSENTRA\"\n\n"
        "------=_Part_PROVA_IUSENTRA\n"
        "Content-Type: text/plain; charset=UTF-8\n\n"
        f"Codice esito: {codice_esito}.\n"
        f"Descrizione esito: --\nIDBUSTA: {idbusta}\n{outcome}.\n\n"
        "Si prega di non replicare a questo messaggio automatico.\n"
        "------=_Part_PROVA_IUSENTRA\n"
        "Content-Type: application/octet-stream; name=EsitoAtto.xml\n"
        "Content-Disposition: attachment; filename=EsitoAtto.xml\n\n"
        f"{esito_atto}\n"
        "------=_Part_PROVA_IUSENTRA--"
    )
    lines = [
        "Messaggio di posta certificata - prova senza invio reale",
        "",
        f'Il giorno {day} alle ore {time} (+0200) il messaggio "{subject}" è stato generato dal canale di prova "{sender}" indirizzato a:',
        recipient,
        "Il messaggio originale è incluso come allegato sintetico.",
        "",
        f"Identificativo messaggio: {message_id}",
        "",
        "Allegati attesi: postacert.eml, daticert.xml, EsitoAtto.xml, smime.p7s.",
        "Nessun messaggio PEC è stato spedito; questa evidenza serve solo a verificare il flusso interno.",
        "",
        "--- daticert.xml ---",
        daticert,
        "",
        "--- EsitoAtto.xml ---",
        esito_atto,
        "",
        "--- postacert.eml ---",
        postacert,
        "",
        "--- smime.p7s ---",
        "Firma S/MIME non generata nella prova locale; in produzione arriva come allegato del gestore PEC.",
    ]
    return "\n".join(lines)


def apply_simulated_receipt(
    deposito: Any,
    *,
    fase: str = "prossima",
    fascicolo_ref: str = "",
    generated_at: str | None = None,
) -> tuple[str, bool, str]:
    """Applica al deposito la prossima ricevuta sintetica e aggiorna lo stato."""

    requested = str(fase or "prossima").strip().casefold().replace("_", "-")
    if requested in {"next", "prossima", "avanza"}:
        phase = next_receipt_phase(deposito)
    else:
        phase = requested.replace("-", "_")
    phase = phase.replace("ricevuta-", "")
    if phase == "completo":
        return phase, False, "La prova deposito ha già tutte le ricevute previste."
    if phase not in _RECEIPT_LABELS:
        raise ValueError("Fase ricevuta non riconosciuta.")

    text = build_simulated_receipt_text(
        deposito=deposito,
        fase=phase,
        fascicolo_ref=fascicolo_ref,
        generated_at=generated_at,
    )
    updated = False
    stato = str(getattr(deposito, "stato", "") or "").upper()

    if phase == "accettazione":
        if not getattr(deposito, "ricevuta_accettazione", ""):
            deposito.ricevuta_accettazione = text
            updated = True
        if stato in {"", "INVIATO", "ACCETTATO"}:
            deposito.stato = "ACCETTATO_PEC"
            updated = True
    elif phase == "consegna":
        if not getattr(deposito, "ricevuta_consegna", ""):
            deposito.ricevuta_consegna = text
            updated = True
        if stato not in _FINAL_STATES | _BLOCKING_STATES | {"WARN_CONTROLLI"}:
            deposito.stato = "CONSEGNATO"
            updated = True
    elif phase == "controlli":
        if not getattr(deposito, "ricevuta_controlli_automatici", ""):
            deposito.ricevuta_controlli_automatici = text
            updated = True
        if str(getattr(deposito, "esito_controlli", "") or "").upper() not in {"OK", "WARN", "ERROR"}:
            deposito.esito_controlli = "WARN"
            updated = True
        if stato not in _FINAL_STATES | _BLOCKING_STATES:
            deposito.stato = "WARN_CONTROLLI"
            updated = True
    elif phase == "cancelleria":
        if not getattr(deposito, "ricevuta_cancelleria", ""):
            deposito.ricevuta_cancelleria = text
            updated = True
        if stato != "ACCETTATO_CANCELLERIA":
            deposito.stato = "ACCETTATO_CANCELLERIA"
            updated = True

    label = _RECEIPT_LABELS[phase]
    message = f"Ricevuta di {label} registrata nella prova deposito." if updated else f"Ricevuta di {label} già presente."
    return phase, updated, message
