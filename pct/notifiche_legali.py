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
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


LEGAL_NOTIFICATION_SUBJECT = "notificazione ai sensi della legge n. 53 del 1994"
LEGAL_NOTIFICATION_OPERATION = "notifica_pec_l53"
CLIENT_COMMUNICATION_OPERATION = "comunicazione_cliente_non_notifica"
TEMPLATE_CATALOG_PATH = Path(__file__).with_name("data") / "notifiche_legali_templates.json"
CLIENT_COMMUNICATION_CATALOG_PATH = Path(__file__).with_name("data") / "comunicazioni_cliente_templates.json"
SHA256_HEX_RE = re.compile(r"^[a-fA-F0-9]{64}$")

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
    "nativo_digitale": "documento nativo digitale",
    "firmato_digitalmente": "documento firmato digitalmente",
    "originale_informatico": "originale informatico",
    "duplicato_informatico": "duplicato informatico",
    "copia_fascicolo_informatico": "copia informatica estratta dal fascicolo",
    "comunicazione_cancelleria": "copia da comunicazione di cancelleria",
    "scansione_analogico": "copia per immagine da originale analogico",
}

DOCUMENT_ORIGIN_ALIASES: dict[str, str] = {
    "nativo": "nativo_digitale",
    "nativo_digitale": "nativo_digitale",
    "documento_nativo_digitale": "nativo_digitale",
    "firmato": "firmato_digitalmente",
    "firmato_digitalmente": "firmato_digitalmente",
    "documento_firmato": "firmato_digitalmente",
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

AVAILABLE_TEMPLATE_FIELDS: tuple[dict[str, str], ...] = (
    {"group": "Pratica", "label": "Codice pratica", "token": "{{ pratica.codice }}"},
    {"group": "Avvocato", "label": "Avvocato notificante", "token": "{{ avvocato.full_name }}"},
    {"group": "Avvocato", "label": "Codice fiscale avvocato", "token": "{{ avvocato.codice_fiscale }}"},
    {"group": "Avvocato", "label": "Foro", "token": "{{ avvocato.foro }}"},
    {"group": "Avvocato", "label": "PEC notificante", "token": "{{ avvocato.pec }}"},
    {"group": "Avvocato", "label": "Studio", "token": "{{ avvocato.studio }}"},
    {"group": "Assistito", "label": "Parte assistita", "token": "{{ cliente.nome_denominazione }}"},
    {"group": "Assistito", "label": "C.F. / P. IVA assistito", "token": "{{ cliente.codice_fiscale_piva }}"},
    {"group": "Procedimento", "label": "Ufficio giudiziario", "token": "{{ procedimento.ufficio }}"},
    {"group": "Procedimento", "label": "Sezione", "token": "{{ procedimento.sezione }}"},
    {"group": "Procedimento", "label": "Numero RG", "token": "{{ procedimento.numero_rg }}"},
    {"group": "Procedimento", "label": "Anno RG", "token": "{{ procedimento.anno_rg }}"},
    {"group": "Procedimento", "label": "Blocco procedimento", "token": "{{ blocco_procedimento }}"},
    {"group": "Destinatario", "label": "Destinatario", "token": "{{ destinatario.nome_denominazione }}"},
    {"group": "Destinatario", "label": "C.F. / P. IVA destinatario", "token": "{{ destinatario.codice_fiscale_piva }}"},
    {"group": "Destinatario", "label": "PEC destinatario", "token": "{{ destinatario.pec }}"},
    {"group": "Destinatario", "label": "Fonte PEC", "token": "{{ destinatario.fonte_pec }}"},
    {"group": "Destinatario", "label": "Data verifica PEC", "token": "{{ destinatario.data_verifica_pec }}"},
    {"group": "Destinatario", "label": "Ora verifica PEC", "token": "{{ destinatario.ora_verifica_pec }}"},
    {"group": "Documenti", "label": "Elenco documenti", "token": "{{ documenti_righe }}"},
    {"group": "Documenti", "label": "Elenco documenti riservato", "token": "{{ documenti_righe_privacy }}"},
    {"group": "Documenti", "label": "Attestazioni automatiche", "token": "{{ attestazioni_testo }}"},
    {"group": "Notifica", "label": "Luogo relata", "token": "{{ notifica.luogo }}"},
    {"group": "Notifica", "label": "Data relata", "token": "{{ notifica.data }}"},
    {"group": "Notifica", "label": "Oggetto PEC L. 53", "token": "{{ notifica.oggetto_pec }}"},
    {"group": "Provvedimento", "label": "Tipo provvedimento", "token": "{{ provvedimento.tipo }}"},
    {"group": "Provvedimento", "label": "Numero provvedimento", "token": "{{ provvedimento.numero }}"},
    {"group": "Provvedimento", "label": "Data provvedimento", "token": "{{ provvedimento.data }}"},
)

_OPERATIONAL_TEMPLATE_FIELDS = {
    "documenti_righe": "Elenco documenti",
    "documenti_righe_privacy": "Elenco documenti riservato",
    "attestazioni_testo": "Attestazioni automatiche",
    "blocco_procedimento": "Blocco procedimento",
}
_FORBIDDEN_TEMPLATE_TOKEN_CHARS = set("[]()")

CLIENT_COMMUNICATION_FIELDS: tuple[dict[str, str], ...] = (
    {"label": "Cliente", "token": "{{ cliente.nome }}"},
    {"label": "Codice pratica", "token": "{{ pratica.codice }}"},
    {"label": "Ufficio", "token": "{{ procedimento.ufficio }}"},
    {"label": "Numero RG", "token": "{{ procedimento.numero_rg }}"},
    {"label": "Anno RG", "token": "{{ procedimento.anno_rg }}"},
    {"label": "Riferimento procedimento", "token": "{{ procedimento.riferimento }}"},
    {"label": "Documento", "token": "{{ documento.descrizione }}"},
    {"label": "Studio", "token": "{{ studio.nome }}"},
    {"label": "Prossimi passi", "token": "{{ prossimi_passi }}"},
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


def multiline_text(value: Any, fallback: str = "") -> str:
    raw = str(value if value is not None else fallback).replace("\r\n", "\n").replace("\r", "\n").strip()
    return "\n".join(line.rstrip() for line in raw.split("\n"))


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


def block(code: str, message: str) -> str:
    return f"{code}: {message}"


def _document_attestation_declared(document: dict[str, Any], payload: dict[str, Any]) -> bool:
    return boolish(document.get("attestazione_presente")) or boolish(document.get("attestazione_conformita_presente")) or boolish(
        payload.get("attestazione_conformita_presente")
    ) or boolish(payload.get("attestazione_presente")) or boolish(payload.get("attestazione_multipla"))


def _document_attestation_text_present(document: dict[str, Any], payload: dict[str, Any]) -> bool:
    return bool(
        multiline_text(document.get("attestazione_conformita"))
        or multiline_text(payload.get("attestazione_conformita"))
        or multiline_text(payload.get("attestazione_multipla_testo"))
        or _document_attestation_declared(document, payload)
    )


@lru_cache(maxsize=1)
def load_template_catalog() -> dict[str, Any]:
    payload = json.loads(TEMPLATE_CATALOG_PATH.read_text(encoding="utf-8"))
    templates = payload.get("templates")
    if not isinstance(templates, list) or not templates:
        raise RuntimeError("Catalogo modelli notifiche legali non valido.")
    return payload


def template_catalog_version() -> str:
    return text(load_template_catalog().get("catalog_version"), "2026.05.12")


@lru_cache(maxsize=1)
def load_client_communication_catalog() -> dict[str, Any]:
    payload = json.loads(CLIENT_COMMUNICATION_CATALOG_PATH.read_text(encoding="utf-8"))
    templates = payload.get("templates")
    if not isinstance(templates, list) or not templates:
        raise RuntimeError("Catalogo modelli comunicazione cliente non valido.")
    return payload


def client_communication_templates_version() -> str:
    return text(load_client_communication_catalog().get("catalog_version"), "comunicazioni-cliente-1.0")


def list_notification_templates(*, kind: str | None = None) -> list[dict[str, Any]]:
    templates = load_template_catalog()["templates"]
    if kind is None:
        return list(templates)
    return [item for item in templates if item.get("kind") == kind]


def list_client_communication_templates() -> list[dict[str, Any]]:
    return list(load_client_communication_catalog()["templates"])


def get_client_communication_template(template_id: Any) -> dict[str, Any] | None:
    raw = text(template_id).lower().strip()
    if not raw:
        return None
    normalised = raw.replace(" ", "_").replace("-", "_")
    for template in list_client_communication_templates():
        if normalised == text(template.get("id")).lower():
            return template
    return None


def available_template_fields() -> list[dict[str, str]]:
    """Return the guided field tokens that can be inserted in custom models."""

    return [dict(item) for item in AVAILABLE_TEMPLATE_FIELDS]


def _token_name(raw_token: str) -> str:
    raw = raw_token.strip()
    if raw.startswith("{{") and raw.endswith("}}"):
        return raw[2:-2].strip()
    return ""


def _iter_template_tokens(content: str):
    index = 0
    while index < len(content):
        start = content.find("{{", index)
        if start < 0:
            break
        end = content.find("}}", start + 2)
        if end < 0:
            break
        yield content[start + 2:end].strip()
        index = end + 2


def _is_identifier_path(value: str) -> bool:
    if not value or value.startswith(".") or value.endswith("."):
        return False
    parts = [part for part in value.split(".") if part]
    return bool(parts) and all(part.replace("_", "a").isalnum() and not part[0].isdigit() for part in parts)


def _token_has_forbidden_chars(token: str) -> bool:
    return any(char in _FORBIDDEN_TEMPLATE_TOKEN_CHARS for char in token)


def _iter_simple_if_tokens(content: str):
    index = 0
    while index < len(content):
        start = content.find("{%", index)
        if start < 0:
            break
        end = content.find("%}", start + 2)
        if end < 0:
            break
        directive = content[start + 2:end].strip()
        if directive.startswith("if "):
            token = directive[3:].strip()
            if _is_identifier_path(token):
                yield token
        index = end + 2


def _allowed_custom_template_tokens() -> set[str]:
    tokens = {
        _token_name(item["token"])
        for item in AVAILABLE_TEMPLATE_FIELDS
        if _token_name(item["token"])
    }
    tokens.update(_OPERATIONAL_TEMPLATE_FIELDS)
    return tokens


def _custom_template_token_labels() -> dict[str, str]:
    labels = {
        _token_name(item["token"]): item["label"]
        for item in AVAILABLE_TEMPLATE_FIELDS
        if _token_name(item["token"])
    }
    labels.update(_OPERATIONAL_TEMPLATE_FIELDS)
    return labels


def validate_custom_template_body(body: Any) -> list[str]:
    """Validate a studio-authored relata model without allowing free Jinja."""

    content = multiline_text(body)
    blockers: list[str] = []
    if not content:
        blockers.append("Inserisci il testo del modello relata.")
        return blockers
    if "{%" in content or "%}" in content:
        blockers.append("I modelli personalizzati non possono contenere istruzioni Jinja.")
    if "{#" in content or "#}" in content:
        blockers.append("I modelli personalizzati non possono contenere commenti Jinja.")
    if content.count("{{") != content.count("}}"):
        blockers.append("Controlla le parentesi dei campi automatici del modello.")

    allowed_tokens = _allowed_custom_template_tokens()
    for token in _iter_template_tokens(content):
        if "|" in token:
            blockers.append(f"Il campo automatico {{{{ {token} }}}} contiene un filtro non consentito.")
            continue
        if _token_has_forbidden_chars(token):
            blockers.append(f"Il campo automatico {{{{ {token} }}}} contiene una chiamata o un accesso non consentito.")
            continue
        if "__" in token or token.startswith(".") or ".__" in token:
            blockers.append(f"Il campo automatico {{{{ {token} }}}} contiene un accesso riservato non consentito.")
            continue
        if token not in allowed_tokens:
            blockers.append(f"Campo automatico non consentito: {{{{ {token} }}}}.")
    return list(dict.fromkeys(blockers))


def normalise_custom_template(raw: dict[str, Any]) -> dict[str, Any]:
    template_id = text(raw.get("id") or raw.get("value"))
    body = multiline_text(
        raw.get("custom_body")
        or raw.get("body")
        or raw.get("previewText")
        or raw.get("preview_text")
        or raw.get("testo")
    )
    fields = raw.get("fields") if isinstance(raw.get("fields"), list) else []
    return {
        "id": template_id,
        "code": text(raw.get("code"), "PERS"),
        "kind": "relata",
        "label": text(raw.get("label") or raw.get("nome"), "Modello personalizzato"),
        "description": text(raw.get("description") or raw.get("descrizione"), "Modello relata personalizzato dallo studio."),
        "custom": True,
        "custom_body": body,
        "requires_proceeding": boolish(raw.get("requires_proceeding")),
        "privacy_description": boolish(raw.get("privacy_description")),
        "required_fields": raw.get("required_fields") if isinstance(raw.get("required_fields"), list) else [],
        "fields": [field for field in fields if isinstance(field, dict)],
        "purpose_lines": [],
        "created_at": text(raw.get("created_at")),
        "created_by": text(raw.get("created_by")),
    }


def template_preview_text(template: dict[str, Any]) -> str:
    """Build a readable model body for preview and customisation."""

    custom_body = multiline_text(template.get("custom_body"))
    if custom_body:
        return custom_body
    privacy = bool(template.get("privacy_description"))
    lines = [
        "RELAZIONE DI NOTIFICAZIONE A MEZZO POSTA ELETTRONICA CERTIFICATA",
        "ai sensi dell'art. 3-bis della Legge 21 gennaio 1994, n. 53",
        "",
        "Io sottoscritto Avv. {{ avvocato.full_name }},",
        "C.F. {{ avvocato.codice_fiscale }},",
        "iscritto all'Ordine degli Avvocati di {{ avvocato.foro }},",
        "con studio in {{ avvocato.studio }},",
        "indirizzo PEC {{ avvocato.pec }},",
        "",
        "nella qualita' di difensore di {{ cliente.nome_denominazione }},",
        "C.F./P.IVA {{ cliente.codice_fiscale_piva }},",
        "giusta procura alle liti in atti, allegata o rilasciata su separato documento,",
        "",
        "NOTIFICO",
        "",
        "a {{ destinatario.nome_denominazione }},",
        "C.F./P.IVA {{ destinatario.codice_fiscale_piva }},",
        "all'indirizzo PEC {{ destinatario.pec }},",
        "estratto dal pubblico elenco {{ destinatario.fonte_pec }} in data {{ destinatario.data_verifica_pec }} alle ore {{ destinatario.ora_verifica_pec }},",
        "",
        "i seguenti documenti informatici allegati al presente messaggio PEC:",
        "",
        "{{ documenti_righe_privacy }}" if privacy else "{{ documenti_righe }}",
        "",
        "{{ blocco_procedimento }}",
    ]
    purpose_lines = [multiline_text(line) for line in (template.get("purpose_lines") or []) if multiline_text(line)]
    if purpose_lines:
        lines.extend(["", *purpose_lines])
    lines.extend([
        "",
        "{{ attestazioni_testo }}",
        "",
        "{{ notifica.luogo }}, {{ notifica.data }}",
        "",
        "Avv. {{ avvocato.full_name }}",
        "Documento informatico separato sottoscritto con firma digitale.",
    ])
    return "\n".join(lines).strip()


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


def _format_italian_date(value: Any, fallback: str = "") -> str:
    raw = text(value, fallback)
    if not raw:
        return ""
    date_part = raw.split("T", 1)[0].rsplit(" ", 1)[0]
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_part, pattern).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return raw


def _split_datetime(value: Any) -> tuple[str, str]:
    raw = text(value)
    if "T" in raw:
        date, hour = raw.split("T", 1)
        return _format_italian_date(date), hour[:5]
    if " " in raw:
        date, hour = raw.rsplit(" ", 1)
        return _format_italian_date(date), hour[:5]
    return _format_italian_date(raw), ""


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
            "attestazione_conformita": payload.get("attestazione_conformita"),
            "attestazione_conformita_presente": payload.get("attestazione_conformita_presente"),
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
            "attestazione_conformita": multiline_text(item.get("attestazione_conformita")),
            "attestazione_conformita_presente": boolish(item.get("attestazione_conformita_presente") or item.get("attestazione_presente")),
            "data_comunicazione_cancelleria": _format_italian_date(
                item.get("data_comunicazione_cancelleria"),
                text(payload.get("data_comunicazione_cancelleria")),
            ),
        })
    return documents


def _build_context(payload: dict[str, Any], *, template: dict[str, Any] | None = None) -> dict[str, Any]:
    data_verifica, ora_verifica = _split_datetime(_first(payload, "destinatario.data_verifica_pec", "data_verifica_pec"))
    studio_citta = text(_first(payload, "avvocato.studio_citta", "studio_citta", fallback=""))
    notifica_data = _format_italian_date(_first(payload, "notifica.data", "data_relata", fallback=datetime.now().strftime("%d/%m/%Y")))
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
            "data": _format_italian_date(_first(payload, "provvedimento.data", "provvedimento_data")),
            "data_deposito": _format_italian_date(_first(payload, "provvedimento.data_deposito", "provvedimento_data_deposito")),
        },
        "notifica_precedente": {
            "data": _format_italian_date(_first(payload, "notifica_precedente.data", "notifica_precedente_data")),
            "esito": text(_first(payload, "notifica_precedente.esito", "notifica_precedente_esito")),
        },
        "provvedimento_rinnovo": {
            "presente": _first_bool(payload, "provvedimento_rinnovo.presente", "provvedimento_rinnovo_presente"),
            "data": _format_italian_date(_first(payload, "provvedimento_rinnovo.data", "provvedimento_rinnovo_data")),
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
        value, _ = _render_restricted_template_body(_render_supported_if_blocks(line, context), context)
        value = value.strip()
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
    custom_template = payload.get("template_personalizzato")
    if isinstance(custom_template, dict):
        custom = normalise_custom_template(custom_template)
        custom_id = text(custom.get("id"))
        if custom_id and (not text(explicit) or text(explicit) == custom_id):
            return custom

    inline_custom_body = multiline_text(
        payload.get("template_personalizzato_testo")
        or payload.get("testo_modello_personalizzato")
        or payload.get("custom_template_body")
    )
    if inline_custom_body:
        inline_id = text(explicit, "relata_personalizzata")
        return normalise_custom_template({
            "id": inline_id,
            "code": "PERS",
            "label": payload.get("template_personalizzato_nome") or payload.get("nome_modello_personalizzato") or "Modello personalizzato",
            "description": payload.get("template_personalizzato_descrizione") or "Modello compilato dai dati IUSENTRA disponibili.",
            "custom_body": inline_custom_body,
            "requires_proceeding": payload.get("template_personalizzato_procedimento"),
        })

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


def _proceeding_block(context: dict[str, Any]) -> str:
    if not context["procedimento"]["presente"]:
        return ""
    return "\n".join([
        "La presente notificazione viene eseguita in relazione al procedimento",
        f"pendente innanzi a {context['procedimento']['ufficio']},",
        f"Sezione {context['procedimento']['sezione']},",
        f"R.G. n. {context['procedimento']['numero_rg']}/{context['procedimento']['anno_rg']}.",
    ])


def _custom_render_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        **context,
        "documenti_righe": "\n".join(_document_rows(context, privacy=False)),
        "documenti_righe_privacy": "\n".join(_document_rows(context, privacy=True)),
        "blocco_procedimento": _proceeding_block(context),
        "attestazioni_testo": "\n\n".join(_attestation_blocks(context)),
    }


def _template_lookup_value(context: dict[str, Any], token: str) -> Any:
    render_context = _custom_render_context(context)
    if token in _OPERATIONAL_TEMPLATE_FIELDS:
        return context.get(token) if text(context.get(token)) else render_context.get(token)
    return _context_lookup(context, token)


def _render_supported_if_blocks(content: str, context: dict[str, Any]) -> str:
    output: list[str] = []
    index = 0
    while index < len(content):
        start = content.find("{%", index)
        if start < 0:
            output.append(content[index:])
            break
        directive_end = content.find("%}", start + 2)
        if directive_end < 0:
            output.append(content[index:])
            break
        directive = content[start + 2:directive_end].strip()
        if not directive.startswith("if "):
            output.append(content[index:start])
            index = directive_end + 2
            continue
        endif_start = content.find("{% endif %}", directive_end + 2)
        if endif_start < 0:
            output.append(content[index:start])
            index = directive_end + 2
            continue
        token = directive[3:].strip()
        output.append(content[index:start])
        if _is_identifier_path(token) and text(_template_lookup_value(context, token)):
            output.append(content[directive_end + 2:endif_start])
        index = endif_start + len("{% endif %}")
    return "".join(output)


def _render_restricted_template_body(
    body: str,
    context: dict[str, Any],
    *,
    placeholder_missing: bool = False,
) -> tuple[str, list[str]]:
    labels = _custom_template_token_labels()
    render_context = _custom_render_context(context)
    missing: list[str] = []

    def resolve_token(token: str) -> str:
        if _token_has_forbidden_chars(token) or "|" in token or "__" in token:
            return ""
        value = _template_lookup_value({**render_context, **context}, token)
        if not text(value):
            label = labels.get(token, token.replace(".", " ").replace("_", " "))
            if label not in missing:
                missing.append(label)
            return f"[dato mancante: {label}]" if placeholder_missing else ""
        return str(value)

    output: list[str] = []
    index = 0
    while index < len(body):
        start = body.find("{{", index)
        if start < 0:
            output.append(body[index:])
            break
        end = body.find("}}", start + 2)
        if end < 0:
            output.append(body[index:])
            break
        output.append(body[index:start])
        output.append(resolve_token(body[start + 2:end].strip()))
        index = end + 2
    return "".join(output).strip(), missing


def _assign_context_path(context: dict[str, Any], path: str, value: str) -> None:
    current: dict[str, Any] = context
    parts = [part for part in path.split(".") if part]
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    if parts:
        current[parts[-1]] = value


def _standard_preview_tokens(body: str) -> set[str]:
    tokens = {token for token in _iter_template_tokens(body)}
    tokens.update(_iter_simple_if_tokens(body))
    return {
        token
        for token in tokens
        if token and "|" not in token and "__" not in token and not _token_has_forbidden_chars(token)
    }


def _render_standard_template_preview(
    body: str,
    context: dict[str, Any],
    template: dict[str, Any],
) -> tuple[str, list[str]]:
    labels = _custom_template_token_labels()
    preview_context = deepcopy(_custom_render_context(context))
    missing: list[str] = []
    for token in sorted(_standard_preview_tokens(body)):
        value = preview_context.get(token) if token in _OPERATIONAL_TEMPLATE_FIELDS else _context_lookup(preview_context, token)
        if text(value):
            continue
        label = labels.get(token) or _field_label(template, token)
        if label not in missing:
            missing.append(label)
        placeholder = f"[dato mancante: {label}]"
        if token in _OPERATIONAL_TEMPLATE_FIELDS:
            preview_context[token] = placeholder
        else:
            _assign_context_path(preview_context, token, placeholder)
    rendered, _ = _render_restricted_template_body(
        _render_supported_if_blocks(body, preview_context),
        preview_context,
        placeholder_missing=True,
    )
    return rendered, missing


def preview_legal_relata(payload: dict[str, Any]) -> dict[str, Any]:
    """Render the selected model with current form data without final blocking checks."""

    template = select_relata_template(payload)
    body = template_preview_text(template)
    context = _build_context(payload, template=template)
    if multiline_text(template.get("custom_body")):
        blockers = validate_custom_template_body(body)
        if blockers:
            return {
                "ok": False,
                "previewText": "",
                "missingFields": [],
                "warnings": [],
                "blockers": blockers,
                "templateId": text(template.get("id")),
                "templateLabel": text(template.get("label")),
            }
        preview_text, missing = _render_restricted_template_body(body, context, placeholder_missing=True)
    else:
        preview_text, missing = _render_standard_template_preview(body, context, template)
    return {
        "ok": True,
        "previewText": preview_text,
        "missingFields": missing,
        "warnings": [f"Da completare nell'anteprima: {label}." for label in missing],
        "blockers": [],
        "templateId": text(template.get("id")),
        "templateLabel": text(template.get("label")),
    }


def _append_lawyer_addition(lines: list[str], payload: dict[str, Any]) -> None:
    addition = text(_first(payload, "notifica.note_integrative_relata", "note_integrative_relata", "integrazione_avvocato"))
    if addition:
        lines.extend(["", "INTEGRAZIONE DELL'AVVOCATO", "", addition])


def validate_legal_notification(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Validate and prepare a controlled L. 53/1994 notification draft."""

    blockers: list[str] = []
    warnings: list[str] = []
    template = select_relata_template(payload)
    context = _build_context(payload, template=template)
    custom_body = multiline_text(template.get("custom_body"))
    if custom_body:
        blockers.extend(validate_custom_template_body(custom_body))
    role = context["destinatario"]["tipo"]
    documents = context["documenti"]
    subject = LEGAL_NOTIFICATION_SUBJECT
    subject_input = text(payload.get("oggetto_pec") or payload.get("subject") or _deep_get(payload, "notifica.oggetto_pec"))

    operation = text(payload.get("operazione") or _deep_get(payload, "notifica.operazione"))
    if operation != LEGAL_NOTIFICATION_OPERATION:
        blockers.append(block("OPERATION_REQUIRED", "Il percorso deve essere notifica_pec_l53."))
    if not subject_input or subject_input.lower() != LEGAL_NOTIFICATION_SUBJECT:
        blockers.append(block("L53_SUBJECT_REQUIRED", "L'oggetto PEC deve essere esattamente: notificazione ai sensi della legge n. 53 del 1994."))
    if not role:
        blockers.append("Seleziona il ruolo del destinatario della notifica.")
    if role in CLIENT_RECIPIENT_ROLES:
        blockers.append(block("CLIENTE_NON_NOTIFICA", "Il cliente non va trattato come destinatario ordinario di una notifica: usa Comunicazione al cliente."))
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
        blockers.append(block("PEC_MITTENTE_FONTE_REQUIRED", "La PEC del notificante deve risultare da un pubblico elenco."))
    if not boolish(_first(payload, "avvocato.abilitato_notifiche", "mittente_avvocato_abilitato", "avvocato_abilitato")):
        blockers.append(block("AVVOCATO_ABILITATO_REQUIRED", "Il mittente deve essere avvocato abilitato alla notifica in proprio."))
    if not boolish(_first(payload, "avvocato.pec_validata", "mittente_pec_validata", "pec_mittente_validata")):
        blockers.append(block("PEC_MITTENTE_VALIDATA_REQUIRED", "La PEC del notificante deve essere presente e validata."))

    source_key = context["destinatario"]["fonte_pec_key"]
    if source_key not in PUBLIC_PEC_REGISTERS:
        blockers.append(block("PEC_DESTINATARIO_FONTE_REQUIRED", "La PEC del destinatario deve avere una fonte da pubblico elenco."))
    if not context["destinatario"]["data_verifica_pec"] or not context["destinatario"]["ora_verifica_pec"]:
        blockers.append(block("PEC_DESTINATARIO_VERIFICA_REQUIRED", "Registra data e ora della verifica PEC del destinatario."))
    if not boolish(_first(payload, "destinatario.pec_pubblico_elenco", "destinatario_pec_pubblico_elenco", fallback=True)):
        blockers.append(block("PEC_DESTINATARIO_PUBBLICO_ELENCO_REQUIRED", "La PEC destinatario deve essere estratta da pubblico elenco."))
    if not boolish(_first(payload, "notifica.relata_documento_separato", "relata_documento_separato")):
        blockers.append(block("RELATA_SEPARATA_REQUIRED", "La relata deve essere generata come documento separato."))
    if not boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")):
        blockers.append(block("RELATA_FIRMATA_REQUIRED", "La relata deve essere firmata digitalmente."))
    if not boolish(payload.get("ricevuta_completa")) or text(payload.get("ricevuta_tipo")).lower() in {"breve", "sintetica", "assente"}:
        blockers.append(block("RICEVUTA_COMPLETA_REQUIRED", "La notifica PEC L. 53/1994 richiede ricevuta di avvenuta consegna completa."))

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
        if document["necessita_attestazione"] and not _document_attestation_text_present(document, payload):
            blockers.append(block("ATTESTAZIONE_REQUIRED", f"Documento {document['index']}: attestazione di conformita' obbligatoria per l'origine indicata."))

    if context["procedimento"]["presente"] or template.get("requires_proceeding"):
        context["procedimento"]["presente"] = True
        _validate_proceeding(context, blockers)

    _validate_required_context(template, context, blockers)

    if boolish(payload.get("invio_finale")):
        if boolish(payload.get("destinatari_multipli")) and not boolish(payload.get("conferma_destinatari_multipli")):
            blockers.append("Per piu' destinatari nella stessa PEC serve una conferma esplicita.")
        if not boolish(payload.get("approvazione_avvocato")):
            blockers.append("L'invio richiede approvazione finale dell'avvocato.")

    relata_override_text = multiline_text(
        payload.get("relata_override_text")
        or payload.get("bozza_relata_testo")
        or payload.get("relata_text_override")
    )
    if relata_override_text and len(relata_override_text) > 30000:
        blockers.append("La bozza relata modificata e' troppo lunga.")

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

    relata_text = f"{relata_override_text}\n" if relata_override_text else render_relata(payload, template=template)
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
    custom_body = multiline_text(template.get("custom_body"))
    if custom_body:
        if validate_custom_template_body(custom_body):
            return ""
        rendered, _missing = _render_restricted_template_body(custom_body, context)
        lines = [rendered] if rendered else []
        _append_lawyer_addition(lines, payload)
        return "\n\n".join(part for part in lines if text(part)).strip() + "\n"

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

    _append_lawyer_addition(lines, payload)

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
        "eventuali_avvisi_errore.eml",
        "log_notifica.json",
        "distinta_prova_notifica.pdf",
        "scheda_esito_notifica.pdf",
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


def _client_communication_context(payload: dict[str, Any]) -> dict[str, Any]:
    cliente_nome = text(payload.get("cliente_nome") or _deep_get(payload, "cliente.nome_denominazione"), "Cliente")
    ufficio = text(payload.get("ufficio_giudiziario") or _deep_get(payload, "procedimento.ufficio"))
    rg = text(payload.get("numero_rg") or _deep_get(payload, "procedimento.numero_rg"))
    anno = text(payload.get("anno_rg") or _deep_get(payload, "procedimento.anno_rg"))
    riferimento = f"R.G. {rg}/{anno}" if rg and anno else (f"R.G. {rg or anno}" if rg or anno else "")
    documento = text(payload.get("provvedimento_descrizione") or payload.get("documento_descrizione") or _deep_get(payload, "documento.descrizione"))
    return {
        "cliente": {"nome": cliente_nome},
        "pratica": {"codice": text(payload.get("pratica_codice") or _deep_get(payload, "pratica.codice"))},
        "procedimento": {
            "ufficio": ufficio,
            "numero_rg": rg,
            "anno_rg": anno,
            "riferimento": " - ".join(part for part in (ufficio, riferimento) if part),
        },
        "documento": {"descrizione": documento},
        "studio": {"nome": text(payload.get("studio_nome") or _deep_get(payload, "studio.nome"), "lo Studio")},
        "prossimi_passi": text(payload.get("prossimi_passi"), "Lo studio resta a disposizione per concordare i prossimi passaggi."),
    }


def _client_token_labels() -> dict[str, str]:
    return {
        _token_name(item["token"]): item["label"]
        for item in CLIENT_COMMUNICATION_FIELDS
        if _token_name(item["token"])
    }


def _render_client_template_text(template_text: str, context: dict[str, Any]) -> str:
    labels = _client_token_labels()
    allowed = set(labels)
    output: list[str] = []
    index = 0

    while index < len(template_text):
        start = template_text.find("{{", index)
        if start < 0:
            output.append(template_text[index:])
            break
        end = template_text.find("}}", start + 2)
        if end < 0:
            output.append(template_text[index:])
            break
        output.append(template_text[index:start])
        token = template_text[start + 2:end].strip()
        if token in allowed and "|" not in token and "__" not in token and not _token_has_forbidden_chars(token):
            output.append(text(_context_lookup(context, token)))
        index = end + 2
    return "".join(output).strip()


def build_client_communication(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Prepare an informative communication to the client, without relata."""

    blockers: list[str] = []
    warnings: list[str] = []
    operation = text(payload.get("operazione") or _deep_get(payload, "comunicazione.operazione"))
    if operation != CLIENT_COMMUNICATION_OPERATION:
        blockers.append(block("CLIENT_COMMUNICATION_OPERATION_REQUIRED", "La comunicazione al cliente deve usare il percorso comunicazione_cliente_non_notifica."))
    if not text(payload.get("cliente_nome") or _deep_get(payload, "cliente.nome_denominazione")):
        blockers.append("Seleziona il cliente destinatario della comunicazione.")
    if is_legal_notification_subject(payload.get("oggetto")):
        blockers.append("La comunicazione al cliente non deve usare l'oggetto della notifica L. 53/1994.")
    if boolish(payload.get("genera_relata")):
        blockers.append("La comunicazione al cliente non genera una relata di notificazione.")
    if text(payload.get("relataText") or payload.get("relata_text") or payload.get("relata_override_text")):
        blockers.append("La comunicazione al cliente non deve contenere la relata.")
    template_id = text(payload.get("template_id") or payload.get("modello_cliente"), "aggiornamento_pratica")
    if template_id.startswith("relata_") or get_notification_template(template_id):
        blockers.append("Scegli un modello comunicazione cliente, non un modello relata.")
    template = get_client_communication_template(template_id) or get_client_communication_template("aggiornamento_pratica")
    if not template:
        blockers.append("Modello comunicazione cliente non disponibile.")
    if not text(payload.get("provvedimento_descrizione")):
        warnings.append("Aggiungi una descrizione del provvedimento o documento trasmesso.")

    context = _client_communication_context(payload)
    subject_override = text(payload.get("subject") or payload.get("oggetto"))
    if subject_override and is_legal_notification_subject(subject_override):
        blockers.append("La comunicazione al cliente non deve usare l'oggetto della notifica L. 53/1994.")
    subject_template = text((template or {}).get("subject"), "Aggiornamento pratica")
    subject = subject_override or _render_client_template_text(subject_template, context)
    body_override = multiline_text(payload.get("body_override") or payload.get("corpo") or payload.get("body"))
    if body_override and is_legal_notification_subject(body_override):
        blockers.append("Il corpo della comunicazione non deve riportare l'oggetto della notifica L. 53/1994.")
    body_template = "\n".join(str(line) for line in ((template or {}).get("body_lines") or []))
    body = body_override or _render_client_template_text(body_template, context)
    blockers = list(dict.fromkeys(blockers))
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=blockers,
        warnings=warnings,
        subject=subject,
        body=body,
        template_id=text((template or {}).get("id"), template_id),
        template_label=text((template or {}).get("label"), "Comunicazione cliente"),
        template_version=client_communication_templates_version(),
        next_actions=("Invia al cliente via email ordinaria, PEC informativa o link sicuro.",),
    )


def _hash_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload_hash(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = text(payload.get(key))
        if value:
            return value
    return ""


def _evidence_item(
    *,
    kind: str,
    label: str,
    filename: Any,
    sha256: str = "",
    required: bool = True,
    generated: bool = False,
) -> dict[str, Any]:
    file_text = text(filename)
    digest = text(sha256)
    return {
        "kind": kind,
        "label": label,
        "filename": file_text,
        "sha256": digest,
        "required": required,
        "generated": generated,
    }


def build_notification_evidence_pack(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the notification/deposit evidence inventory with SHA-256 checks."""

    items: list[dict[str, Any]] = []
    notified_documents = payload.get("atti_notificati")
    if isinstance(notified_documents, list) and notified_documents:
        for index, document in enumerate(notified_documents, start=1):
            row = document if isinstance(document, dict) else {"nome_file": document}
            items.append(_evidence_item(
                kind="atto" if index == 1 else f"allegato_{index}",
                label="Atto notificato" if index == 1 else f"Allegato notificato {index}",
                filename=row.get("nome_file") or row.get("filename") or row.get("file") or row.get("riferimento_portale"),
                sha256=text(row.get("hash_sha256") or row.get("sha256")),
            ))
    else:
        items.append(_evidence_item(
            kind="atto",
            label="Atto notificato",
            filename=payload.get("atto_notificato"),
            sha256=_payload_hash(payload, "atto_sha256", "atto_notificato_sha256"),
        ))

    items.extend([
        _evidence_item(
            kind="relata_firmata",
            label="Relata firmata",
            filename=payload.get("relata_firmata"),
            sha256=_payload_hash(payload, "relata_sha256", "relata_firmata_sha256"),
        ),
        _evidence_item(
            kind="pec_inviata",
            label="PEC inviata",
            filename=payload.get("pec_inviata") or payload.get("pec_inviata_file"),
            sha256=_payload_hash(payload, "pec_inviata_sha256", "pec_sha256"),
        ),
    ])

    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "rac_file": payload.get("rac_file"),
            "rac_sha256": payload.get("rac_sha256"),
            "rdac_file": payload.get("rdac_file"),
            "rdac_sha256": payload.get("rdac_sha256"),
        }]
    for index, recipient in enumerate(recipients, start=1):
        row = recipient if isinstance(recipient, dict) else {}
        label = text(row.get("nome"), f"destinatario {index}")
        items.append(_evidence_item(
            kind="rac",
            label=f"RAC {label}",
            filename=row.get("rac_file"),
            sha256=text(row.get("rac_sha256")),
        ))
        items.append(_evidence_item(
            kind="rdac_completa",
            label=f"RdAC completa {label}",
            filename=row.get("rdac_file"),
            sha256=text(row.get("rdac_sha256")),
        ))

    warnings = payload.get("avvisi_errore")
    if isinstance(warnings, list):
        for index, warning in enumerate(warnings, start=1):
            row = warning if isinstance(warning, dict) else {"file": warning}
            items.append(_evidence_item(
                kind="avviso_errore",
                label=f"Avviso errore {index}",
                filename=row.get("file") or row.get("filename"),
                sha256=text(row.get("sha256")),
                required=False,
            ))
    elif text(payload.get("avviso_mancata_consegna")):
        items.append(_evidence_item(
            kind="avviso_errore",
            label="Avviso mancata consegna",
            filename=payload.get("avviso_mancata_consegna"),
            sha256=_payload_hash(payload, "avviso_mancata_consegna_sha256", "avviso_sha256"),
            required=False,
        ))

    generated_log = json.dumps(
        {
            "evento": "evidence_pack_notifica",
            "data_generazione": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "atto_notificato": text(payload.get("atto_notificato")),
            "destinatario": text(payload.get("destinatario_nome")),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    items.extend([
        _evidence_item(
            kind="log_json",
            label="Log JSON",
            filename=text(payload.get("log_json_file"), "log_notifica.json"),
            sha256=_payload_hash(payload, "log_json_sha256") or _hash_text(generated_log),
            generated=True,
        ),
        _evidence_item(
            kind="distinta_prova_notifica",
            label="Distinta prova notifica",
            filename=text(payload.get("distinta_prova_notifica"), "distinta_prova_notifica.pdf"),
            sha256=_payload_hash(payload, "distinta_sha256") or _hash_text("distinta_prova_notifica"),
            generated=True,
        ),
        _evidence_item(
            kind="scheda_esito",
            label="Scheda esito",
            filename=text(payload.get("scheda_esito"), "scheda_esito_notifica.pdf"),
            sha256=_payload_hash(payload, "scheda_esito_sha256") or _hash_text("scheda_esito_notifica"),
            generated=True,
        ),
    ])

    missing: list[str] = []
    invalid_hashes: list[str] = []
    for item in items:
        if not item["required"]:
            continue
        if not item["filename"]:
            missing.append(f"{item['label']}: file mancante.")
        if not item["sha256"]:
            missing.append(f"{item['label']}: hash SHA-256 mancante.")
        elif not SHA256_HEX_RE.fullmatch(str(item["sha256"])):
            invalid_hashes.append(f"{item['label']}: hash SHA-256 non valido.")
    return {
        "items": items,
        "missing": missing,
        "invalid_hashes": invalid_hashes,
        "hashes": {item["kind"]: item["sha256"] for item in items if item["sha256"]},
    }


def prepare_pst_failed_notification_workflow(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Prepare the PST area web workflow after failed PEC delivery."""

    blockers: list[str] = []
    warnings: list[str] = []
    if not boolish(payload.get("pec_non_consegnata")):
        blockers.append(block("PEC_FAILED_REQUIRED", "Il workflow PST area web richiede una PEC non consegnata."))
    assessment = text(payload.get("valutazione_avvocato") or payload.get("causa_mancata_consegna"))
    if not assessment:
        blockers.append(block("LAWYER_ASSESSMENT_REQUIRED", "Serve la valutazione dell'avvocato sulla causa della mancata consegna."))
    attributable = boolish(payload.get("causa_imputabile_destinatario"))
    if assessment and not attributable:
        warnings.append("La causa non risulta imputabile al destinatario: prepara un canale alternativo e non dichiarare perfezionata la notifica.")

    evidence_pack = build_notification_evidence_pack(payload)
    if attributable:
        missing_notice = not text(payload.get("avviso_mancata_consegna"))
        if missing_notice:
            blockers.append(block("AVVISO_MANCATA_CONSEGNA_REQUIRED", "Allega l'avviso di mancata consegna."))
        blockers.extend(block("EVIDENCE_PACK_REQUIRED", item) for item in evidence_pack["missing"])
        blockers.extend(block("HASH_SHA256_INVALID", item) for item in evidence_pack.get("invalid_hashes", []))

    ok = not blockers
    return LegalWorkflowResult(
        ok=ok,
        blockers=list(dict.fromkeys(blockers)),
        warnings=warnings,
        subject="Workflow area web PST" if attributable else "Valutazione canale alternativo",
        body=(
            "Prepara deposito area web PST con atto, relata, RAC e avviso di mancata consegna."
            if attributable and ok
            else "Non dichiarare perfezionata la notifica; valuta nuovo invio o canale alternativo."
        ),
        template_id="workflow_deposito_area_web_pst" if attributable else "nota_mancata_consegna",
        template_label="Workflow deposito area web PST" if attributable else "Nota mancata consegna",
        template_version=template_catalog_version(),
        next_actions=(
            "Verifica la causa con l'avvocato responsabile.",
            "Prepara evidence pack per area web PST.",
            "Procedi solo con conferma manuale sul portale PST.",
        ) if attributable else (
            "Non considerare perfezionata la notifica.",
            "Scegli un canale alternativo o rinnova la notifica.",
        ),
        output_plan={"evidencePack": evidence_pack},
        log_json={"workflow": "pst_area_web_notifica_fallita", "evidencePack": evidence_pack},
    )


def validate_deposit_notification_proof(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Validate the evidence pack before deposit of notification proof."""

    blockers: list[str] = []
    warnings: list[str] = []
    notified_documents = payload.get("atti_notificati")
    has_notified_documents = isinstance(notified_documents, list) and bool(notified_documents)
    if not has_notified_documents and not text(payload.get("atto_notificato")):
        blockers.append("Inserisci l'atto notificato da depositare come prova.")
    if not text(payload.get("relata_firmata")):
        blockers.append("Allega la relata firmata digitalmente.")
    if not text(payload.get("pec_inviata") or payload.get("pec_inviata_file")):
        blockers.append("Allega il messaggio PEC inviato in originale digitale.")
    if not boolish(payload.get("ricevuta_completa")) and text(payload.get("rdac_tipo")).lower() != "completa":
        blockers.append(block("RICEVUTA_COMPLETA_REQUIRED", "La prova deposito richiede RdAC completa."))

    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "rac_file": payload.get("rac_file"),
            "rdac_file": payload.get("rdac_file"),
            "rac_sha256": payload.get("rac_sha256"),
            "rdac_sha256": payload.get("rdac_sha256"),
        }]
    if not recipients:
        blockers.append("Indica almeno un destinatario della notifica.")

    for index, recipient in enumerate(recipients, start=1):
        if not isinstance(recipient, dict):
            blockers.append(f"Destinatario {index}: dati ricevute non leggibili.")
            continue
        label = text(recipient.get("nome"), f"destinatario {index}")
        for field, human in (("rac_file", "ricevuta di accettazione"), ("rdac_file", "ricevuta di avvenuta consegna completa")):
            filename = text(recipient.get(field))
            if not filename:
                blockers.append(f"{label}: manca la {human}.")
                continue
            if Path(filename).suffix.lower() not in {".eml", ".msg"}:
                blockers.append(f"{label}: conserva la {human} in originale digitale .eml o .msg.")

    evidence_pack = build_notification_evidence_pack(payload)
    blockers.extend(block("EVIDENCE_PACK_REQUIRED", item) for item in evidence_pack["missing"])
    blockers.extend(block("HASH_SHA256_INVALID", item) for item in evidence_pack.get("invalid_hashes", []))

    if not text(payload.get("dati_atto_ricevute")):
        blockers.append(block("DATI_ATTO_RICEVUTE_REQUIRED", "Indica i riferimenti delle ricevute in DatiAtto.xml."))

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
        output_plan={"evidencePack": evidence_pack},
        log_json={"evento": "controllo_prova_notifica", "evidencePack": evidence_pack},
    )
