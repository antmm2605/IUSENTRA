"""Regole operative per notifiche PEC L. 53/1994 e comunicazioni cliente.

Il modulo separa tre percorsi che non devono essere confusi:

- notifica legale alla controparte, con relata e prova PEC;
- deposito della prova della notifica nel fascicolo;
- comunicazione informativa al cliente, senza relata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


LEGAL_NOTIFICATION_SUBJECT = "notificazione ai sensi della legge n. 53 del 1994"

PUBLIC_PEC_REGISTERS: dict[str, str] = {
    "reginde": "ReGIndE",
    "ini_pec": "INI-PEC",
    "registro_imprese": "Registro Imprese",
    "registro_ppaa": "Registro PP.AA. / PST",
    "inad": "INAD",
    "anpr": "ANPR",
    "altro_pubblico_elenco": "Altro pubblico elenco ammesso",
}

LEGAL_RECIPIENT_ROLES = {
    "controparte",
    "difensore",
    "pa",
    "impresa",
    "professionista",
    "terzo",
}

CLIENT_RECIPIENT_ROLES = {"cliente", "assistito"}

DOCUMENT_ORIGIN_LABELS: dict[str, str] = {
    "originale": "originale informatico",
    "duplicato": "duplicato informatico",
    "copia_fascicolo": "copia informatica estratta dal fascicolo",
    "comunicazione_cancelleria": "copia da comunicazione di cancelleria",
    "scansione": "copia per immagine da originale analogico",
}

ORIGINS_REQUIRING_ATTESTATION = {
    "copia_fascicolo",
    "comunicazione_cancelleria",
    "scansione",
}


@dataclass(frozen=True)
class LegalWorkflowResult:
    ok: bool
    blockers: list[str]
    warnings: list[str]
    subject: str = ""
    body: str = ""
    relata_text: str = ""
    next_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "subject": self.subject,
            "body": self.body,
            "relataText": self.relata_text,
            "nextActions": list(self.next_actions),
        }


def text(value: Any, fallback: str = "") -> str:
    return " ".join(str(value if value is not None else fallback).split()).strip()


def boolish(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def normalise_role(value: Any) -> str:
    raw = text(value).lower().replace(" ", "_").replace("-", "_")
    if raw in {"pubblica_amministrazione", "amministrazione"}:
        return "pa"
    return raw


def is_legal_notification_subject(value: Any) -> bool:
    return LEGAL_NOTIFICATION_SUBJECT in text(value).lower()


def normalise_public_register(value: Any) -> str:
    raw = text(value).lower().replace("-", "_").replace(" ", "_").replace(".", "")
    aliases = {
        "reginde": "reginde",
        "registro_generale_indirizzi_elettronici": "reginde",
        "inipec": "ini_pec",
        "ini_pec": "ini_pec",
        "registro_imprese": "registro_imprese",
        "imprese": "registro_imprese",
        "registro_ppaa": "registro_ppaa",
        "registro_pst": "registro_ppaa",
        "pst": "registro_ppaa",
        "inad": "inad",
        "anpr": "anpr",
        "altro": "altro_pubblico_elenco",
        "altro_pubblico_elenco": "altro_pubblico_elenco",
    }
    return aliases.get(raw, raw)


def register_label(value: Any) -> str:
    key = normalise_public_register(value)
    return PUBLIC_PEC_REGISTERS.get(key, text(value))


def needs_attestazione(origin: Any) -> bool:
    return text(origin).lower() in ORIGINS_REQUIRING_ATTESTATION


def _documents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("documenti")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    single = {
        "nome_file": payload.get("nome_file") or payload.get("atto_file"),
        "descrizione": payload.get("descrizione_documento") or payload.get("atto_descrizione"),
        "origine": payload.get("origine_documento") or payload.get("origine"),
    }
    if any(text(value) for value in single.values()):
        return [single]
    return []


def validate_legal_notification(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Validate and prepare a controlled L. 53/1994 notification draft."""

    blockers: list[str] = []
    warnings: list[str] = []
    role = normalise_role(payload.get("ruolo_destinatario"))
    documents = _documents(payload)
    subject = LEGAL_NOTIFICATION_SUBJECT
    subject_input = text(payload.get("oggetto_pec") or payload.get("subject"))

    if subject_input and subject_input.lower() != LEGAL_NOTIFICATION_SUBJECT:
        blockers.append("L'oggetto PEC deve restare: notificazione ai sensi della legge n. 53 del 1994.")
    if not role:
        blockers.append("Seleziona il ruolo del destinatario della notifica.")
    if role in CLIENT_RECIPIENT_ROLES:
        blockers.append("Il cliente non va trattato come destinatario ordinario di una notifica: usa Comunicazione al cliente.")
    if role and role not in LEGAL_RECIPIENT_ROLES and role not in CLIENT_RECIPIENT_ROLES:
        warnings.append("Ruolo destinatario non ricondotto automaticamente: verifica che sia un soggetto notificabile.")

    required_fields = [
        ("avvocato_nome", "Indica l'avvocato notificante."),
        ("avvocato_cf", "Indica il codice fiscale dell'avvocato notificante."),
        ("avvocato_foro", "Indica l'Ordine o foro dell'avvocato."),
        ("mittente_pec", "Indica la PEC del notificante."),
        ("assistito_nome", "Indica la parte assistita."),
        ("assistito_cf", "Indica il codice fiscale o la partita IVA della parte assistita."),
        ("destinatario_nome", "Indica il destinatario della notifica."),
        ("destinatario_pec", "Indica la PEC del destinatario."),
    ]
    for field, message in required_fields:
        if not text(payload.get(field)):
            blockers.append(message)

    if not boolish(payload.get("mittente_pec_pubblico_elenco")) and not text(payload.get("fonte_pec_mittente")):
        blockers.append("La PEC del notificante deve risultare da un pubblico elenco.")

    source_key = normalise_public_register(payload.get("fonte_pec_destinatario"))
    if source_key not in PUBLIC_PEC_REGISTERS:
        blockers.append("La PEC del destinatario deve avere una fonte da pubblico elenco.")
    if not text(payload.get("data_verifica_pec")):
        blockers.append("Registra data e ora della verifica PEC del destinatario.")

    if not documents:
        blockers.append("Seleziona almeno un documento da notificare.")
    for index, document in enumerate(documents, start=1):
        name = text(document.get("nome_file") or document.get("file"))
        description = text(document.get("descrizione"))
        origin = text(document.get("origine")).lower()
        if not name:
            blockers.append(f"Documento {index}: indica il nome esatto del file.")
        if not description:
            blockers.append(f"Documento {index}: indica una descrizione riconoscibile.")
        if origin and origin not in DOCUMENT_ORIGIN_LABELS:
            blockers.append(f"Documento {index}: origine documento non riconosciuta.")
        if needs_attestazione(origin) and not text(payload.get("attestazione_conformita")):
            blockers.append(f"Documento {index}: serve attestazione di conformita per {DOCUMENT_ORIGIN_LABELS[origin]}.")
        if name and Path(name).suffix.lower() not in {".pdf", ".pdfa", ".p7m"}:
            blockers.append(f"Documento {index}: per la notifica guidata usa PDF/PDF-A o file firmato.")

    if boolish(payload.get("procedimento_pendente")):
        for field, message in (
            ("ufficio_giudiziario", "Per una notifica in corso di procedimento indica l'ufficio giudiziario."),
            ("sezione", "Per una notifica in corso di procedimento indica la sezione."),
            ("numero_rg", "Per una notifica in corso di procedimento indica il numero di ruolo."),
            ("anno_rg", "Per una notifica in corso di procedimento indica l'anno di ruolo."),
        ):
            if not text(payload.get(field)):
                blockers.append(message)

    if boolish(payload.get("invio_finale")):
        if not boolish(payload.get("relata_firmata")):
            blockers.append("Prima dell'invio la relata deve essere firmata digitalmente.")
        if not boolish(payload.get("ricevuta_completa")):
            blockers.append("Prima dell'invio va richiesta la ricevuta di avvenuta consegna completa.")
        if boolish(payload.get("destinatari_multipli")) and not boolish(payload.get("conferma_destinatari_multipli")):
            blockers.append("Per piu' destinatari nella stessa PEC serve una conferma esplicita.")
        if not boolish(payload.get("approvazione_avvocato")):
            blockers.append("L'invio richiede approvazione finale dell'avvocato.")

    relata_text = "" if blockers else render_relata(payload)
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=blockers,
        warnings=warnings,
        subject=subject,
        body="Si allegano atto, eventuale procura e relazione di notificazione firmata digitalmente.",
        relata_text=relata_text,
        next_actions=(
            "Firma digitalmente la relata separata.",
            "Invia una PEC distinta per destinatario con ricevuta completa.",
            "Conserva messaggio inviato, RAC e RdAC in originale digitale.",
        ),
    )


def render_relata(payload: dict[str, Any]) -> str:
    documents = _documents(payload)
    rows: list[str] = []
    for index, document in enumerate(documents, start=1):
        rows.append(
            f"{index}. {text(document.get('nome_file') or document.get('file'))} - "
            f"{text(document.get('descrizione'))}"
        )

    data_verifica = text(payload.get("data_verifica_pec"))
    luogo = text(payload.get("luogo"), text(payload.get("studio_citta"), ""))
    data_relata = text(payload.get("data_relata"), datetime.now().strftime("%d/%m/%Y"))
    lines = [
        "RELAZIONE DI NOTIFICAZIONE A MEZZO POSTA ELETTRONICA CERTIFICATA",
        "ai sensi dell'art. 3-bis Legge 21 gennaio 1994, n. 53",
        "",
        f"Io sottoscritto Avv. {text(payload.get('avvocato_nome'))},",
        f"C.F. {text(payload.get('avvocato_cf'))}, iscritto all'Ordine degli Avvocati di {text(payload.get('avvocato_foro'))},",
        f"con studio in {text(payload.get('studio_indirizzo')) or 'indirizzo indicato negli atti di studio'},",
        f"in qualita' di difensore di {text(payload.get('assistito_nome'))},",
        f"C.F./P.IVA {text(payload.get('assistito_cf'))},",
        "",
        "NOTIFICO",
        "",
        f"a {text(payload.get('destinatario_nome'))},",
        f"all'indirizzo PEC {text(payload.get('destinatario_pec'))},",
        f"estratto dal pubblico elenco {register_label(payload.get('fonte_pec_destinatario'))}",
        f" in data {data_verifica},",
        "",
        "i seguenti documenti informatici allegati al presente messaggio PEC:",
        "",
        *rows,
    ]

    if boolish(payload.get("procedimento_pendente")):
        lines.extend([
            "",
            "La presente notificazione viene eseguita in relazione al procedimento",
            f"pendente innanzi a {text(payload.get('ufficio_giudiziario'))},",
            f"Sezione {text(payload.get('sezione'))},",
            f"R.G. n. {text(payload.get('numero_rg'))}/{text(payload.get('anno_rg'))}.",
        ])

    attestazione = text(payload.get("attestazione_conformita"))
    if attestazione:
        lines.extend(["", "ATTESTO", attestazione])

    lines.extend([
        "",
        f"{luogo}, {data_relata}".strip(", "),
        "",
        f"Avv. {text(payload.get('avvocato_nome'))}",
        "[firma digitale]",
    ])
    return "\n".join(lines)


def build_client_communication(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Prepare an informative communication to the client, without relata."""

    blockers: list[str] = []
    warnings: list[str] = []
    if not text(payload.get("cliente_nome")):
        blockers.append("Seleziona il cliente destinatario della comunicazione.")
    if is_legal_notification_subject(payload.get("oggetto")):
        blockers.append("La comunicazione al cliente non deve usare l'oggetto della notifica L. 53/1994.")
    if boolish(payload.get("genera_relata")):
        blockers.append("La comunicazione al cliente non genera una relata di notificazione.")
    if not text(payload.get("provvedimento_descrizione")):
        warnings.append("Aggiungi una descrizione del provvedimento o documento trasmesso.")

    ufficio = text(payload.get("ufficio_giudiziario"))
    rg = text(payload.get("numero_rg"))
    anno = text(payload.get("anno_rg"))
    subject_parts = ["Comunicazione provvedimento"]
    if ufficio:
        subject_parts.append(ufficio)
    if rg or anno:
        subject_parts.append(f"R.G. {rg}/{anno}" if rg and anno else f"R.G. {rg or anno}")
    subject = " - ".join(subject_parts)
    body = (
        f"Gentile {text(payload.get('cliente_nome'), 'Cliente')},\n\n"
        "Le trasmettiamo in allegato o tramite link sicuro il provvedimento indicato dallo studio"
        f"{(' (' + text(payload.get('provvedimento_descrizione')) + ')') if text(payload.get('provvedimento_descrizione')) else ''}.\n"
        "Lo studio resta a disposizione per l'esame degli effetti e delle eventuali scadenze.\n\n"
        "Cordiali saluti"
    )
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=blockers,
        warnings=warnings,
        subject=subject,
        body=body,
        next_actions=("Invia al cliente via email ordinaria, PEC informativa o link sicuro.",),
    )


def validate_deposit_notification_proof(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Validate the evidence pack before deposit of notification proof."""

    blockers: list[str] = []
    warnings: list[str] = []
    if not text(payload.get("atto_notificato")):
        blockers.append("Inserisci l'atto notificato da depositare come prova.")
    if not text(payload.get("relata_firmata")):
        blockers.append("Allega la relata firmata digitalmente.")

    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "rac_file": payload.get("rac_file"),
            "rdac_file": payload.get("rdac_file"),
        }]
    if not recipients:
        blockers.append("Indica almeno un destinatario della notifica.")

    for index, recipient in enumerate(recipients, start=1):
        if not isinstance(recipient, dict):
            blockers.append(f"Destinatario {index}: dati ricevute non leggibili.")
            continue
        label = text(recipient.get("nome"), f"destinatario {index}")
        for field, human in (("rac_file", "ricevuta di accettazione"), ("rdac_file", "ricevuta di avvenuta consegna")):
            filename = text(recipient.get(field))
            if not filename:
                blockers.append(f"{label}: manca la {human}.")
                continue
            if Path(filename).suffix.lower() not in {".eml", ".msg"}:
                blockers.append(f"{label}: conserva la {human} in originale digitale .eml o .msg.")

    if not text(payload.get("dati_atto_ricevute")):
        warnings.append("Prepara l'indicizzazione delle ricevute in DatiAtto.xml prima della busta.")

    body = (
        "Prova notifica pronta per il controllo: atto notificato, relata firmata, "
        "messaggio PEC inviato, RAC e RdAC originali per ciascun destinatario."
    )
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=blockers,
        warnings=warnings,
        subject="Deposito prova notifica",
        body=body,
        next_actions=(
            "Inserisci atto notificato e ricevute nella busta telematica.",
            "Controlla che RAC e RdAC restino in originale digitale.",
            "Verifica i riferimenti ricevute in DatiAtto.xml.",
        ),
    )
