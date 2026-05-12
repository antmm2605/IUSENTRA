"""Motore parametrico per notifiche PEC L. 53/1994 e comunicazioni cliente.

Il modulo separa tre percorsi che non devono essere confusi:

- notifica legale alla controparte, con relata separata e prova PEC;
- deposito della prova della notifica nel fascicolo;
- comunicazione informativa al cliente, senza relata.
"""

from __future__ import annotations

import io
import json
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from jinja2 import ChainableUndefined, Environment


LEGAL_NOTIFICATION_SUBJECT = "notificazione ai sensi della legge n. 53 del 1994"
TEMPLATE_CATALOG_PATH = Path(__file__).with_name("data") / "notifiche_legali_templates.json"

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
    "originale_informatico": "originale informatico",
    "duplicato_informatico": "duplicato informatico",
    "copia_fascicolo_informatico": "copia informatica estratta dal fascicolo",
    "comunicazione_cancelleria": "copia da comunicazione di cancelleria",
    "scansione_analogico": "copia per immagine da originale analogico",
}

DOCUMENT_ORIGIN_ALIASES: dict[str, str] = {
    "originale": "originale_informatico",
    "originale_informatico": "originale_informatico",
    "documento_originale_informatico": "originale_informatico",
    "duplicato": "duplicato_informatico",
    "duplicato_informatico": "duplicato_informatico",
    "copia_fascicolo": "copia_fascicolo_informatico",
    "copia_fascicolo_informatico": "copia_fascicolo_informatico",
    "fascicolo_informatico": "copia_fascicolo_informatico",
    "provvedimento_da_fascicolo": "copia_fascicolo_informatico",
    "comunicazione_cancelleria": "comunicazione_cancelleria",
    "cancelleria": "comunicazione_cancelleria",
    "scansione": "scansione_analogico",
    "scansione_analogico": "scansione_analogico",
    "copia_immagine": "scansione_analogico",
}

ORIGINS_REQUIRING_ATTESTATION = {
    "copia_fascicolo_informatico",
    "comunicazione_cancelleria",
    "scansione_analogico",
}

_TEMPLATE_ENV = Environment(
    autoescape=False,
    undefined=ChainableUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True)
class LegalWorkflowResult:
    ok: bool
    blockers: list[str]
    warnings: list[str]
    subject: str = ""
    body: str = ""
    relata_text: str = ""
    next_actions: tuple[str, ...] = ()
    template_id: str = ""
    template_label: str = ""
    template_version: str = ""
    selected_blocks: tuple[str, ...] = ()
    checklist_text: str = ""
    log_json: dict[str, Any] | None = None
    output_plan: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "subject": self.subject,
            "body": self.body,
            "relataText": self.relata_text,
            "nextActions": list(self.next_actions),
            "templateId": self.template_id,
            "templateLabel": self.template_label,
            "templateVersion": self.template_version,
            "selectedBlocks": list(self.selected_blocks),
            "checklistText": self.checklist_text,
            "logJson": self.log_json or {},
            "outputPlan": self.output_plan or {},
        }


def text(value: Any, fallback: str = "") -> str:
    return " ".join(str(value if value is not None else fallback).split()).strip()


def boolish(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def normalise_role(value: Any) -> str:
    raw = text(value).lower().replace(" ", "_").replace("-", "_")
    if raw in {"pubblica_amministrazione", "amministrazione"}:
        return "pa"
    if raw in {"difensore_controparte", "avvocato_controparte"}:
        return "difensore"
    if raw in {"societa", "societa_impresa", "azienda"}:
        return "impresa"
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


def normalise_document_origin(value: Any) -> str:
    raw = text(value).lower().replace("-", "_").replace(" ", "_")
    return DOCUMENT_ORIGIN_ALIASES.get(raw, raw)


def needs_attestazione(origin: Any) -> bool:
    return normalise_document_origin(origin) in ORIGINS_REQUIRING_ATTESTATION


@lru_cache(maxsize=1)
def load_template_catalog() -> dict[str, Any]:
    payload = json.loads(TEMPLATE_CATALOG_PATH.read_text(encoding="utf-8"))
    templates = payload.get("templates")
    if not isinstance(templates, list) or not templates:
        raise RuntimeError("Catalogo modelli notifiche legali non valido.")
    return payload


def template_catalog_version() -> str:
    return text(load_template_catalog().get("catalog_version"), "2026.05.12")


def list_notification_templates(*, kind: str | None = None) -> list[dict[str, Any]]:
    templates = load_template_catalog()["templates"]
    if kind is None:
        return list(templates)
    return [item for item in templates if item.get("kind") == kind]


def _template_by_id() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for template in list_notification_templates():
        template_id = text(template.get("id"))
        if template_id:
            index[template_id] = template
        code = text(template.get("code"))
        if code:
            index[code.lower()] = template
        for alias in template.get("aliases") or []:
            index[text(alias).lower()] = template
    return index


def get_notification_template(template_id: Any) -> dict[str, Any] | None:
    raw = text(template_id).lower().strip()
    if not raw:
        return None
    normalised = raw.replace(" ", "_").replace("-", "_")
    if normalised.startswith("relata_pec_a_societa"):
        normalised = "relata_pec_a_impresa_societa"
    if normalised == "relata_a_societa_impresa":
        normalised = "relata_pec_a_impresa_societa"
    return _template_by_id().get(normalised) or _template_by_id().get(raw)


def _deep_get(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return None
    return current


def _template_fields(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("template_fields") or payload.get("campi_modello")
    return raw if isinstance(raw, dict) else {}


def _first(payload: dict[str, Any], *paths: str, fallback: Any = "") -> Any:
    extras = _template_fields(payload)
    for path in paths:
        value = _deep_get(payload, path)
        if text(value):
            return value
        snake = path.replace(".", "_")
        for source in (payload, extras):
            if isinstance(source, dict) and text(source.get(snake)):
                return source.get(snake)
            if isinstance(source, dict) and text(source.get(path)):
                return source.get(path)
    return fallback


def _first_bool(payload: dict[str, Any], *paths: str, fallback: bool = False) -> bool:
    for path in paths:
        value = _deep_get(payload, path)
        if value is not None and text(value) != "":
            return boolish(value)
        snake = path.replace(".", "_")
        if snake in payload:
            return boolish(payload.get(snake))
    return fallback


def _split_datetime(value: Any) -> tuple[str, str]:
    raw = text(value)
    if "T" in raw:
        date, hour = raw.split("T", 1)
        return date, hour[:5]
    if " " in raw:
        date, hour = raw.rsplit(" ", 1)
        return date, hour[:5]
    return raw, ""


def _documents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("documenti")
    if isinstance(raw, list):
        source = [item for item in raw if isinstance(item, dict)]
    else:
        source = []
    if not source:
        single = {
            "nome_file": payload.get("nome_file") or payload.get("atto_file"),
            "descrizione": payload.get("descrizione_documento") or payload.get("atto_descrizione"),
            "descrizione_breve_privacy": payload.get("descrizione_breve_privacy"),
            "origine": payload.get("origine_documento") or payload.get("origine"),
            "hash_sha256": payload.get("hash_sha256"),
            "data_comunicazione_cancelleria": payload.get("data_comunicazione_cancelleria"),
        }
        if any(text(value) for value in single.values()):
            source = [single]

    documents: list[dict[str, Any]] = []
    for index, item in enumerate(source, start=1):
        origin = normalise_document_origin(item.get("origine"))
        description = text(item.get("descrizione"))
        privacy_description = text(item.get("descrizione_breve_privacy"), description)
        documents.append({
            "index": index,
            "nome_file": text(item.get("nome_file") or item.get("file")),
            "descrizione": description,
            "descrizione_breve_privacy": privacy_description,
            "origine": origin,
            "origine_label": DOCUMENT_ORIGIN_LABELS.get(origin, text(item.get("origine"))),
            "necessita_attestazione": boolish(item.get("necessita_attestazione")) or origin in ORIGINS_REQUIRING_ATTESTATION,
            "hash_sha256": text(item.get("hash_sha256")),
            "data_comunicazione_cancelleria": text(
                item.get("data_comunicazione_cancelleria"),
                text(payload.get("data_comunicazione_cancelleria")),
            ),
        })
    return documents


def _build_context(payload: dict[str, Any], *, template: dict[str, Any] | None = None) -> dict[str, Any]:
    data_verifica, ora_verifica = _split_datetime(_first(payload, "destinatario.data_verifica_pec", "data_verifica_pec"))
    studio_citta = text(_first(payload, "avvocato.studio_citta", "studio_citta", fallback=""))
    notifica_data = text(_first(payload, "notifica.data", "data_relata", fallback=datetime.now().strftime("%d/%m/%Y")))
    notifica_luogo = text(_first(payload, "notifica.luogo", "luogo", fallback=studio_citta))
    role = normalise_role(_first(payload, "destinatario.tipo", "ruolo_destinatario"))
    source_key = normalise_public_register(_first(payload, "destinatario.fonte_pec", "fonte_pec_destinatario"))
    documents = _documents(payload)
    avvocato_nome = text(_first(payload, "avvocato.nome", "avvocato_nome"))
    avvocato_cognome = text(_first(payload, "avvocato.cognome", "avvocato_cognome"))
    avvocato_full = text(" ".join(part for part in (avvocato_nome, avvocato_cognome) if part), avvocato_nome)

    context = {
        "catalog_version": template_catalog_version(),
        "template": template or {},
        "pratica": {
            "codice": text(_first(payload, "pratica.codice", "pratica_codice")),
        },
        "avvocato": {
            "nome": avvocato_nome,
            "cognome": avvocato_cognome,
            "full_name": avvocato_full,
            "codice_fiscale": text(_first(payload, "avvocato.codice_fiscale", "avvocato_cf")),
            "foro": text(_first(payload, "avvocato.foro", "avvocato_foro")),
            "pec": text(_first(payload, "avvocato.pec", "mittente_pec")),
            "studio": text(_first(payload, "avvocato.studio", "studio_indirizzo")),
            "studio_citta": studio_citta,
            "fonte_pec": register_label(_first(payload, "avvocato.fonte_pec", "fonte_pec_mittente", fallback="reginde")),
        },
        "cliente": {
            "tipo": text(_first(payload, "cliente.tipo", "assistito_tipo")),
            "nome_denominazione": text(_first(payload, "cliente.nome_denominazione", "assistito_nome")),
            "codice_fiscale_piva": text(_first(payload, "cliente.codice_fiscale_piva", "assistito_cf")),
            "qualifica": text(_first(payload, "cliente.qualifica", "assistito_qualifica")),
        },
        "procedimento": {
            "presente": _first_bool(payload, "procedimento.presente", "procedimento_pendente", fallback=False),
            "ufficio": text(_first(payload, "procedimento.ufficio", "ufficio_giudiziario")),
            "sezione": text(_first(payload, "procedimento.sezione", "sezione")),
            "numero_rg": text(_first(payload, "procedimento.numero_rg", "numero_rg")),
            "anno_rg": text(_first(payload, "procedimento.anno_rg", "anno_rg")),
            "giudice": text(_first(payload, "procedimento.giudice", "giudice")),
            "tipo_procedimento": text(_first(payload, "procedimento.tipo_procedimento", "tipo_procedimento")),
        },
        "destinatario": {
            "tipo": role,
            "nome_denominazione": text(_first(payload, "destinatario.nome_denominazione", "destinatario_nome")),
            "codice_fiscale_piva": text(_first(payload, "destinatario.codice_fiscale_piva", "destinatario_cf", "destinatario_codice_fiscale_piva")),
            "pec": text(_first(payload, "destinatario.pec", "destinatario_pec")),
            "fonte_pec": PUBLIC_PEC_REGISTERS.get(source_key, text(_first(payload, "destinatario.fonte_pec", "fonte_pec_destinatario"))),
            "fonte_pec_key": source_key,
            "data_verifica_pec": data_verifica,
            "ora_verifica_pec": ora_verifica,
            "parte_rappresentata": text(_first(payload, "destinatario.parte_rappresentata", "destinatario_parte_rappresentata")),
            "qualifica": text(_first(payload, "destinatario.qualifica", "destinatario_qualifica")),
        },
        "documenti": documents,
        "notifica": {
            "tipo": text(_first(payload, "notifica.tipo", "tipo_notifica", fallback="pec_l53_1994")),
            "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT,
            "luogo": notifica_luogo,
            "data": notifica_data,
            "relata_firmata": boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")),
            "firma_tipo": text(_first(payload, "notifica.firma_tipo", "firma_tipo", fallback="PAdES")),
            "ricevuta_tipo": "completa" if boolish(payload.get("ricevuta_completa")) else text(payload.get("ricevuta_tipo")),
            "esito": text(_first(payload, "notifica.esito", "esito")),
            "note": text(_first(payload, "notifica.note", "note")),
        },
        "provvedimento": {
            "tipo": text(_first(payload, "provvedimento.tipo", "provvedimento_tipo")),
            "numero": text(_first(payload, "provvedimento.numero", "provvedimento_numero")),
            "anno": text(_first(payload, "provvedimento.anno", "provvedimento_anno")),
            "ufficio_origine": text(_first(payload, "provvedimento.ufficio_origine", "provvedimento_ufficio_origine")),
            "data": text(_first(payload, "provvedimento.data", "provvedimento_data")),
            "data_deposito": text(_first(payload, "provvedimento.data_deposito", "provvedimento_data_deposito")),
        },
        "notifica_precedente": {
            "data": text(_first(payload, "notifica_precedente.data", "notifica_precedente_data")),
            "esito": text(_first(payload, "notifica_precedente.esito", "notifica_precedente_esito")),
        },
        "provvedimento_rinnovo": {
            "presente": _first_bool(payload, "provvedimento_rinnovo.presente", "provvedimento_rinnovo_presente"),
            "data": text(_first(payload, "provvedimento_rinnovo.data", "provvedimento_rinnovo_data")),
            "nome_file": text(_first(payload, "provvedimento_rinnovo.nome_file", "provvedimento_rinnovo_nome_file")),
        },
        "riassunzione": {
            "causa": text(_first(payload, "riassunzione.causa", "riassunzione_causa")),
        },
        "sfratto": {
            "tipo_procedimento": text(_first(payload, "sfratto.tipo_procedimento", "sfratto_tipo_procedimento")),
            "immobile_indirizzo": text(_first(payload, "sfratto.immobile_indirizzo", "sfratto_immobile_indirizzo")),
        },
        "esecuzione": {
            "debitore": text(_first(payload, "esecuzione.debitore", "esecuzione_debitore")),
            "terzo_pignorato": text(_first(payload, "esecuzione.terzo_pignorato", "esecuzione_terzo_pignorato")),
        },
        "opposizione": {
            "tipo": text(_first(payload, "opposizione.tipo", "opposizione_tipo")),
        },
    }
    return context


def _context_lookup(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return ""
    return current


def _field_label(template: dict[str, Any], path: str) -> str:
    snake = path.replace(".", "_")
    for field in template.get("fields") or []:
        if isinstance(field, dict) and field.get("name") in {path, snake}:
            return text(field.get("label"), snake.replace("_", " "))
    return snake.replace("_", " ")


def _render_lines(lines: list[str], context: dict[str, Any]) -> list[str]:
    rendered: list[str] = []
    for line in lines:
        value = _TEMPLATE_ENV.from_string(line).render(**context).strip()
        if value or line == "":
            rendered.append(value)
    return rendered


def select_relata_template(payload: dict[str, Any]) -> dict[str, Any]:
    explicit = (
        payload.get("template_id")
        or payload.get("modello_relata")
        or _deep_get(payload, "template.id")
        or _deep_get(payload, "notifica.template_id")
    )
    template = get_notification_template(explicit)
    if template:
        return template

    role = normalise_role(_first(payload, "destinatario.tipo", "ruolo_destinatario"))
    documents = _documents(payload)
    origins = {document["origine"] for document in documents}

    if role in {"cliente", "assistito"}:
        return get_notification_template("comunicazione_cliente_non_notifica") or list_notification_templates(kind="communication")[0]
    if boolish(payload.get("rinnovo_notifica")):
        return get_notification_template("relata_rinnovo_notifica") or get_notification_template("relata_pec_base_l53")
    if boolish(payload.get("integrazione_contraddittorio")):
        return get_notification_template("relata_integrazione_contraddittorio") or get_notification_template("relata_pec_base_l53")
    if boolish(payload.get("chiamata_terzo")):
        return get_notification_template("relata_chiamata_terzo") or get_notification_template("relata_pec_base_l53")
    if boolish(payload.get("riassunzione")) or text(_first(payload, "riassunzione.causa", "riassunzione_causa")):
        return get_notification_template("relata_riassunzione") or get_notification_template("relata_pec_base_l53")
    if role == "difensore":
        return get_notification_template("relata_pec_a_difensore_costituito") or get_notification_template("relata_pec_base_l53")
    if role == "impresa":
        return get_notification_template("relata_pec_a_impresa_societa") or get_notification_template("relata_pec_base_l53")
    if role == "pa":
        return get_notification_template("relata_pec_a_pubblica_amministrazione") or get_notification_template("relata_pec_base_l53")
    if role == "professionista":
        return get_notification_template("relata_pec_a_professionista_inipec") or get_notification_template("relata_pec_base_l53")
    if "comunicazione_cancelleria" in origins:
        return get_notification_template("relata_pec_provvedimento_da_fascicolo") or get_notification_template("relata_provvedimento_giudice")
    if "copia_fascicolo_informatico" in origins:
        return get_notification_template("relata_pec_con_attestazione_fascicolo") or get_notification_template("relata_provvedimento_giudice")
    if "scansione_analogico" in origins:
        return get_notification_template("relata_pec_con_attestazione_scansione_analogica") or get_notification_template("relata_pec_base_l53")
    if boolish(payload.get("procedimento_pendente")) or boolish(_deep_get(payload, "procedimento.presente")):
        return get_notification_template("relata_pec_in_corso_di_causa") or get_notification_template("relata_pec_base_l53")
    return get_notification_template("relata_pec_base_l53") or list_notification_templates(kind="relata")[0]


def _validate_required_context(template: dict[str, Any], context: dict[str, Any], blockers: list[str]) -> None:
    for path in template.get("required_fields") or []:
        if not text(_context_lookup(context, path)):
            blockers.append(f"Completa il campo richiesto per il modello: {_field_label(template, path)}.")


def _validate_proceeding(context: dict[str, Any], blockers: list[str]) -> None:
    for path, message in (
        ("procedimento.ufficio", "Per una notifica in corso di procedimento indica l'ufficio giudiziario."),
        ("procedimento.sezione", "Per una notifica in corso di procedimento indica la sezione."),
        ("procedimento.numero_rg", "Per una notifica in corso di procedimento indica il numero di ruolo."),
        ("procedimento.anno_rg", "Per una notifica in corso di procedimento indica l'anno di ruolo."),
    ):
        if not text(_context_lookup(context, path)):
            blockers.append(message)


def _document_attestation_text(document: dict[str, Any], context: dict[str, Any]) -> str:
    origin = document["origine"]
    name = document["nome_file"]
    description = document["descrizione"]
    proceeding = context["procedimento"]
    if origin == "copia_fascicolo_informatico":
        return (
            f"Attesto che il file {name}, contenente {description}, e' copia informatica conforme "
            f"al corrispondente atto o provvedimento presente nel fascicolo informatico del procedimento "
            f"{proceeding['ufficio']}, R.G. n. {proceeding['numero_rg']}/{proceeding['anno_rg']}."
        )
    if origin == "comunicazione_cancelleria":
        return (
            f"Attesto che il file {name}, contenente {description}, e' copia informatica conforme "
            f"al documento allegato alla comunicazione telematica di cancelleria del "
            f"{document['data_comunicazione_cancelleria']} relativa al procedimento "
            f"R.G. n. {proceeding['numero_rg']}/{proceeding['anno_rg']}."
        )
    if origin == "scansione_analogico":
        return (
            f"Attesto che il file {name}, contenente {description}, e' copia informatica per immagine "
            "conforme all'originale analogico in possesso del sottoscritto difensore."
        )
    return ""


def _attestation_blocks(context: dict[str, Any]) -> list[str]:
    blocks: list[str] = []
    for document in context["documenti"]:
        if not document["necessita_attestazione"]:
            continue
        block = _document_attestation_text(document, context)
        if block:
            blocks.append(block)
    return blocks


def _document_rows(context: dict[str, Any], *, privacy: bool = False) -> list[str]:
    rows: list[str] = []
    for document in context["documenti"]:
        description = document["descrizione_breve_privacy"] if privacy else document["descrizione"]
        rows.append(f"{document['index']}. {document['nome_file']} - {description}")
    return rows


def validate_legal_notification(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Validate and prepare a controlled L. 53/1994 notification draft."""

    blockers: list[str] = []
    warnings: list[str] = []
    template = select_relata_template(payload)
    context = _build_context(payload, template=template)
    role = context["destinatario"]["tipo"]
    documents = context["documenti"]
    subject = LEGAL_NOTIFICATION_SUBJECT
    subject_input = text(payload.get("oggetto_pec") or payload.get("subject") or _deep_get(payload, "notifica.oggetto_pec"))

    if subject_input and subject_input.lower() != LEGAL_NOTIFICATION_SUBJECT:
        blockers.append("L'oggetto PEC deve restare: notificazione ai sensi della legge n. 53 del 1994.")
    if not role:
        blockers.append("Seleziona il ruolo del destinatario della notifica.")
    if role in CLIENT_RECIPIENT_ROLES:
        blockers.append("Il cliente non va trattato come destinatario ordinario di una notifica: usa Comunicazione al cliente.")
    if role and role not in LEGAL_RECIPIENT_ROLES and role not in CLIENT_RECIPIENT_ROLES:
        warnings.append("Ruolo destinatario non ricondotto automaticamente: verifica che sia un soggetto notificabile.")

    required_paths = [
        ("avvocato.full_name", "Indica l'avvocato notificante."),
        ("avvocato.codice_fiscale", "Indica il codice fiscale dell'avvocato notificante."),
        ("avvocato.foro", "Indica l'Ordine o foro dell'avvocato."),
        ("avvocato.pec", "Indica la PEC del notificante."),
        ("cliente.nome_denominazione", "Indica la parte assistita."),
        ("cliente.codice_fiscale_piva", "Indica il codice fiscale o la partita IVA della parte assistita."),
        ("destinatario.nome_denominazione", "Indica il destinatario della notifica."),
        ("destinatario.pec", "Indica la PEC del destinatario."),
        ("notifica.luogo", "Indica il luogo della relata."),
        ("notifica.data", "Indica la data della relata."),
    ]
    for path, message in required_paths:
        if not text(_context_lookup(context, path)):
            blockers.append(message)

    if not boolish(payload.get("mittente_pec_pubblico_elenco")) and not text(_first(payload, "avvocato.fonte_pec", "fonte_pec_mittente")):
        blockers.append("La PEC del notificante deve risultare da un pubblico elenco.")

    source_key = context["destinatario"]["fonte_pec_key"]
    if source_key not in PUBLIC_PEC_REGISTERS:
        blockers.append("La PEC del destinatario deve avere una fonte da pubblico elenco.")
    if not context["destinatario"]["data_verifica_pec"]:
        blockers.append("Registra data e ora della verifica PEC del destinatario.")

    if not documents:
        blockers.append("Seleziona almeno un documento da notificare.")
    for document in documents:
        name = document["nome_file"]
        description = document["descrizione"]
        origin = document["origine"]
        if not name:
            blockers.append(f"Documento {document['index']}: indica il nome esatto del file.")
        if not description:
            blockers.append(f"Documento {document['index']}: indica una descrizione riconoscibile.")
        if origin and origin not in DOCUMENT_ORIGIN_LABELS:
            blockers.append(f"Documento {document['index']}: origine documento non riconosciuta.")
        if name and Path(name).suffix.lower() not in {".pdf", ".pdfa", ".p7m"}:
            blockers.append(f"Documento {document['index']}: per la notifica guidata usa PDF/PDF-A o file firmato.")
        if document["necessita_attestazione"] and origin == "copia_fascicolo_informatico":
            _validate_proceeding(context, blockers)
        if document["necessita_attestazione"] and origin == "comunicazione_cancelleria":
            _validate_proceeding(context, blockers)
            if not document["data_comunicazione_cancelleria"]:
                blockers.append(f"Documento {document['index']}: indica la data della comunicazione di cancelleria.")

    if context["procedimento"]["presente"] or template.get("requires_proceeding"):
        context["procedimento"]["presente"] = True
        _validate_proceeding(context, blockers)

    _validate_required_context(template, context, blockers)

    if boolish(payload.get("invio_finale")):
        if not boolish(payload.get("relata_firmata")):
            blockers.append("Prima dell'invio la relata deve essere firmata digitalmente.")
        if not boolish(payload.get("ricevuta_completa")):
            blockers.append("Prima dell'invio va richiesta la ricevuta di avvenuta consegna completa.")
        if boolish(payload.get("destinatari_multipli")) and not boolish(payload.get("conferma_destinatari_multipli")):
            blockers.append("Per piu' destinatari nella stessa PEC serve una conferma esplicita.")
        if not boolish(payload.get("approvazione_avvocato")):
            blockers.append("L'invio richiede approvazione finale dell'avvocato.")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return LegalWorkflowResult(
            ok=False,
            blockers=blockers,
            warnings=warnings,
            subject=subject,
            template_id=text(template.get("id")),
            template_label=text(template.get("label")),
            template_version=template_catalog_version(),
        )

    relata_text = render_relata(payload, template=template)
    body = render_control_document("corpo_pec_standard", payload, template=template)
    checklist = render_control_document("checklist_pre_invio", payload, template=template)
    attestation_blocks = _attestation_blocks(_build_context(payload, template=template))
    selected_blocks = tuple(["procedimento"] if context["procedimento"]["presente"] else []) + tuple(
        f"attestazione:{document['origine']}" for document in context["documenti"] if document["necessita_attestazione"]
    )
    return LegalWorkflowResult(
        ok=True,
        blockers=[],
        warnings=warnings,
        subject=subject,
        body=body,
        relata_text=relata_text,
        next_actions=(
            "Rivedi la bozza con l'avvocato responsabile.",
            "Esporta la relata in PDF/PDF-A e firmala digitalmente.",
            "Invia una PEC distinta per destinatario con ricevuta completa.",
            "Conserva messaggio inviato, RAC e RdAC in originale digitale.",
        ),
        template_id=text(template.get("id")),
        template_label=text(template.get("label")),
        template_version=template_catalog_version(),
        selected_blocks=selected_blocks,
        checklist_text=checklist,
        log_json=build_generation_log(payload, template=template, attestation_blocks=attestation_blocks),
        output_plan=build_output_plan(payload),
    )


def render_relata(payload: dict[str, Any], *, template: dict[str, Any] | None = None) -> str:
    template = template or select_relata_template(payload)
    context = _build_context(payload, template=template)
    privacy = bool(template.get("privacy_description"))
    lines = [
        "RELAZIONE DI NOTIFICAZIONE A MEZZO POSTA ELETTRONICA CERTIFICATA",
        "ai sensi dell'art. 3-bis della Legge 21 gennaio 1994, n. 53",
        "",
        f"Io sottoscritto Avv. {context['avvocato']['full_name']},",
        f"C.F. {context['avvocato']['codice_fiscale']},",
        f"iscritto all'Ordine degli Avvocati di {context['avvocato']['foro']},",
        f"con studio in {context['avvocato']['studio'] or 'indirizzo indicato negli atti di studio'},",
        f"indirizzo PEC {context['avvocato']['pec']},",
        "",
        f"nella qualita' di difensore di {context['cliente']['nome_denominazione']},",
        f"C.F./P.IVA {context['cliente']['codice_fiscale_piva']},",
    ]
    if context["cliente"]["qualifica"]:
        lines.append(f"{context['cliente']['qualifica']},")
    lines.extend([
        "giusta procura alle liti in atti, allegata o rilasciata su separato documento,",
        "",
        "NOTIFICO",
        "",
        f"a {context['destinatario']['nome_denominazione']},",
    ])
    if context["destinatario"]["codice_fiscale_piva"]:
        lines.append(f"C.F./P.IVA {context['destinatario']['codice_fiscale_piva']},")
    if context["destinatario"]["parte_rappresentata"]:
        lines.append(f"quale difensore di {context['destinatario']['parte_rappresentata']},")
    if context["destinatario"]["qualifica"]:
        lines.append(f"in qualita' di {context['destinatario']['qualifica']},")
    lines.extend([
        f"all'indirizzo PEC {context['destinatario']['pec']},",
        f"estratto dal pubblico elenco {context['destinatario']['fonte_pec']}",
        f" in data {context['destinatario']['data_verifica_pec']}"
        f"{(' alle ore ' + context['destinatario']['ora_verifica_pec']) if context['destinatario']['ora_verifica_pec'] else ''},",
        "",
        "i seguenti documenti informatici allegati al presente messaggio PEC:",
        "",
        *_document_rows(context, privacy=privacy),
    ])

    if context["procedimento"]["presente"] or template.get("requires_proceeding"):
        lines.extend([
            "",
            "La presente notificazione viene eseguita in relazione al procedimento",
            f"pendente innanzi a {context['procedimento']['ufficio']},",
            f"Sezione {context['procedimento']['sezione']},",
            f"R.G. n. {context['procedimento']['numero_rg']}/{context['procedimento']['anno_rg']}.",
        ])

    purpose_lines = _render_lines(template.get("purpose_lines") or [], context)
    if purpose_lines:
        lines.extend(["", *purpose_lines])

    attestations = _attestation_blocks(context)
    manual_attestation = text(payload.get("attestazione_conformita"))
    if manual_attestation:
        attestations.append(manual_attestation)
    if attestations:
        lines.extend(["", "ATTESTAZIONE DI CONFORMITA", ""])
        for block in attestations:
            lines.extend([block, ""])

    lines.extend([
        f"{context['notifica']['luogo']}, {context['notifica']['data']}".strip(", "),
        "",
        f"Avv. {context['avvocato']['full_name']}",
        "Documento informatico separato sottoscritto con firma digitale.",
    ])
    return "\n".join(lines).strip() + "\n"


def render_control_document(template_id: str, payload: dict[str, Any], *, template: dict[str, Any] | None = None) -> str:
    control_template = get_notification_template(template_id)
    if not control_template:
        return ""
    context = _build_context(payload, template=template)
    return "\n".join(_render_lines(control_template.get("content_lines") or [], context)).strip()


def build_generation_log(
    payload: dict[str, Any],
    *,
    template: dict[str, Any] | None = None,
    attestation_blocks: list[str] | None = None,
) -> dict[str, Any]:
    template = template or select_relata_template(payload)
    context = _build_context(payload, template=template)
    return {
        "evento": "generazione_relata",
        "template_id": text(template.get("id")),
        "template_versione": template_catalog_version(),
        "data_generazione": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "utente_generatore": text(_first(payload, "utente.nome", "utente_generatore")),
        "avvocato_responsabile": context["avvocato"]["full_name"],
        "pratica": context["pratica"]["codice"],
        "procedimento": (
            f"{context['procedimento']['numero_rg']}/{context['procedimento']['anno_rg']}"
            if context["procedimento"]["numero_rg"] or context["procedimento"]["anno_rg"]
            else ""
        ),
        "destinatario": context["destinatario"]["nome_denominazione"],
        "pec_destinatario": context["destinatario"]["pec"],
        "fonte_pec": context["destinatario"]["fonte_pec"],
        "documenti": [
            {
                "nome_file": document["nome_file"],
                "descrizione": document["descrizione"],
                "origine": document["origine"],
                "hash_sha256": document["hash_sha256"],
                "attestazione": bool(document["necessita_attestazione"]),
            }
            for document in context["documenti"]
        ],
        "relata_firmata": boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")),
        "firma_tipo": text(_first(payload, "notifica.firma_tipo", "firma_tipo", fallback="PAdES")),
        "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT,
        "ricevuta_richiesta": "completa",
        "public_registry_checked": True,
        "attestazioni": attestation_blocks or [],
    }


def build_output_plan(payload: dict[str, Any]) -> dict[str, Any]:
    context = _build_context(payload, template=select_relata_template(payload))
    date = re.sub(r"[^0-9]", "-", context["notifica"]["data"]).strip("-") or datetime.now().strftime("%Y-%m-%d")
    recipient = re.sub(r"[^A-Za-z0-9]+", "_", context["destinatario"]["nome_denominazione"]).strip("_").lower() or "destinatario"
    folder = f"notifica_{date}_{recipient}"
    files = [
        "relata_notifica.pdf",
        "relata_notifica_firmata.pdf oppure relata_notifica.pdf.p7m",
        *[document["nome_file"] for document in context["documenti"] if document["nome_file"]],
        "pec_inviata.eml",
        "ricevuta_accettazione.eml",
        "ricevuta_consegna_completa.eml",
        "log_notifica.json",
        "distinta_prova_notifica.pdf",
    ]
    return {"folder": folder, "files": files}


def generate_relata_pdf_bytes(payload: dict[str, Any], *, pdfa: bool = False) -> bytes:
    result = validate_legal_notification(payload)
    if not result.ok:
        raise ValueError("; ".join(result.blockers))

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="Relata di notificazione",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "RelataBody",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=10.5,
        leading=15,
        spaceAfter=4,
    )
    title = ParagraphStyle(
        "RelataTitle",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=13,
        leading=17,
        spaceAfter=8,
    )
    story = []
    for index, line in enumerate(result.relata_text.splitlines()):
        if not line.strip():
            story.append(Spacer(1, 5))
            continue
        style = title if index < 2 else body
        story.append(Paragraph(escape(line), style))
    doc.build(story)
    data = buffer.getvalue()
    if not pdfa:
        return data

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = Path(tmp_dir) / "relata_notifica.pdf"
        pdfa_path = Path(tmp_dir) / "relata_notifica_pdfa.pdf"
        pdf_path.write_bytes(data)
        try:
            from pct.validazione import converti_pdfa

            conversion = converti_pdfa(str(pdf_path), str(pdfa_path))
            if conversion.get("ok") and pdfa_path.exists():
                return pdfa_path.read_bytes()
            raise RuntimeError(text(conversion.get("messaggio"), "Conversione PDF/A non completata."))
        except Exception as exc:  # pragma: no cover - dipende dagli strumenti locali PDF/A.
            raise RuntimeError("Conversione PDF/A non completata sul sistema corrente.") from exc


def build_client_communication(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Prepare an informative communication to the client, without relata."""

    blockers: list[str] = []
    warnings: list[str] = []
    if not text(payload.get("cliente_nome") or _deep_get(payload, "cliente.nome_denominazione")):
        blockers.append("Seleziona il cliente destinatario della comunicazione.")
    if is_legal_notification_subject(payload.get("oggetto")):
        blockers.append("La comunicazione al cliente non deve usare l'oggetto della notifica L. 53/1994.")
    if boolish(payload.get("genera_relata")):
        blockers.append("La comunicazione al cliente non genera una relata di notificazione.")
    if not text(payload.get("provvedimento_descrizione")):
        warnings.append("Aggiungi una descrizione del provvedimento o documento trasmesso.")

    ufficio = text(payload.get("ufficio_giudiziario") or _deep_get(payload, "procedimento.ufficio"))
    rg = text(payload.get("numero_rg") or _deep_get(payload, "procedimento.numero_rg"))
    anno = text(payload.get("anno_rg") or _deep_get(payload, "procedimento.anno_rg"))
    subject_parts = ["Comunicazione provvedimento"]
    if ufficio:
        subject_parts.append(ufficio)
    if rg or anno:
        subject_parts.append(f"R.G. {rg}/{anno}" if rg and anno else f"R.G. {rg or anno}")
    subject = " - ".join(subject_parts)
    cliente_nome = text(payload.get("cliente_nome") or _deep_get(payload, "cliente.nome_denominazione"), "Cliente")
    description = text(payload.get("provvedimento_descrizione"))
    body = (
        f"Gentile {cliente_nome},\n\n"
        "Le trasmettiamo in allegato o tramite link sicuro il provvedimento indicato dallo studio"
        f"{(' (' + description + ')') if description else ''}.\n"
        "Lo studio resta a disposizione per l'esame degli effetti e delle eventuali scadenze.\n\n"
        "Cordiali saluti"
    )
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=blockers,
        warnings=warnings,
        subject=subject,
        body=body,
        template_id="comunicazione_cliente_non_notifica",
        template_label="Comunicazione cliente",
        template_version=template_catalog_version(),
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
        template_id="distinta_prova_notifica",
        template_label="Distinta prova notifica",
        template_version=template_catalog_version(),
        next_actions=(
            "Inserisci atto notificato e ricevute nella busta telematica.",
            "Controlla che RAC e RdAC restino in originale digitale.",
            "Verifica i riferimenti ricevute in DatiAtto.xml.",
        ),
    )
