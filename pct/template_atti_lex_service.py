"""Servizi riusabili per Lex e Template Atti.

Il modulo collega Lex al catalogo/compilatore esistente senza passare dalle
route Flask. Le route possono comunque riusare queste funzioni iniettando le
dipendenze web necessarie per scrivere nell'editor professionale.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import html
import re
import unicodedata
from types import SimpleNamespace
from typing import Any, Callable


def clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean_spaces(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _tokens(value: Any) -> list[str]:
    return [token for token in normalize_text(value).split() if len(token) >= 2]


def _value(row: Any, *keys: str) -> Any:
    if row is None:
        return ""
    if isinstance(row, dict):
        for key in keys:
            if key in row and not _is_empty(row.get(key)):
                return row.get(key)
        return ""
    for key in keys:
        value = getattr(row, key, None)
        if not _is_empty(value):
            return value
    return ""


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _label(row: Any) -> str:
    return clean_spaces(
        _value(row, "nome_completo", "nome", "title", "titolo", "ragione_sociale", "label")
    )


def _id(row: Any) -> str:
    return clean_spaces(_value(row, "id", "value", "codice", "code"))


def _as_object(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _as_object(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_as_object(item) for item in value]
    return value


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    result: dict[str, Any] = {}
    for key in ("id", "nome", "cognome", "nome_completo", "titolo", "numero", "numero_rg", "anno_rg", "rg_completo", "controparte", "tribunale", "oggetto", "id_cliente", "email", "pec"):
        raw = getattr(value, key, None)
        if not _is_empty(raw):
            result[key] = raw
    return result


def _list_context_values(context: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = context.get(key)
        if isinstance(value, list):
            return list(value)
        if isinstance(value, dict):
            return list(value.values())
    structured = context.get("structured_context") if isinstance(context.get("structured_context"), dict) else {}
    for key in keys:
        value = structured.get(key)
        if isinstance(value, list):
            return list(value)
        if isinstance(value, dict):
            return list(value.values())
    anagrafica = structured.get("anagrafica") if isinstance(structured.get("anagrafica"), dict) else context.get("anagrafica")
    if isinstance(anagrafica, dict):
        for key in keys:
            value = anagrafica.get(key)
            if isinstance(value, list):
                return list(value)
    return []


def _find_record_by_id(records: list[Any], record_id: str) -> Any | None:
    needle = clean_spaces(record_id)
    if not needle:
        return None
    for row in records:
        if _id(row) == needle:
            return row
    return None


def _matches_query(row: Any, query: str) -> bool:
    haystack = normalize_text(
        " ".join(
            clean_spaces(_value(row, key))
            for key in (
                "nome_completo",
                "nome",
                "cognome",
                "ragione_sociale",
                "titolo",
                "numero",
                "numero_rg",
                "rg_completo",
                "controparte",
                "oggetto",
                "email",
                "pec",
            )
        )
    )
    if not haystack:
        return False
    query_norm = normalize_text(query)
    if haystack and haystack in query_norm:
        return True
    row_tokens = [token for token in haystack.split() if len(token) >= 3]
    query_tokens = set(_tokens(query_norm))
    if not row_tokens or not query_tokens:
        return False
    if any(token in query_tokens for token in row_tokens if len(token) >= 4):
        return True
    return len([token for token in row_tokens if token in query_tokens]) >= min(2, len(row_tokens))


def _field_list(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for field_item in fields:
        if not isinstance(field_item, dict):
            continue
        name = clean_spaces(field_item.get("name"))
        if not name:
            continue
        result.append(
            {
                "name": name,
                "label": clean_spaces(field_item.get("label")) or name,
                "type": clean_spaces(field_item.get("type")) or "text",
            }
        )
    return result


def _model_source_urls(model_code: str) -> dict[str, str]:
    code = clean_spaces(model_code)
    return {
        "compile_url": f"/template-atti/compila/{code}",
        "catalog_url": f"/template-atti/catalogo?scheda={code}",
        "source_url": f"/template-atti/compila/{code}",
    }


def template_metadata_for_model(model_code: str) -> dict[str, Any]:
    from pct.compilatore_atti import wizard_schema_modello

    schema = wizard_schema_modello(model_code)
    model = dict(schema.get("model") or {})
    urls = _model_source_urls(model_code)
    required_fields = list(schema.get("base_required_fields") or []) + list(model.get("required_extra_fields") or [])
    return {
        "model_code": clean_spaces(model.get("code") or model_code),
        "area": clean_spaces(model.get("area")),
        "name": clean_spaces(model.get("name")) or clean_spaces(model_code),
        "required_fields": required_fields,
        "base_fields": _field_list(list(schema.get("base_fields") or [])),
        "extra_fields": _field_list(list(schema.get("extra_fields") or [])),
        "suggested_attachments": list(schema.get("suggested_attachments") or []),
        "suggested_clauses": list(schema.get("suggested_clauses") or []),
        "validation_rules": list(schema.get("validation_rules") or []),
        "sections": list(schema.get("sections") or []),
        "renderer": clean_spaces(schema.get("renderer")),
        "compile_url": urls["compile_url"],
        "catalog_url": urls["catalog_url"],
        "prefill_capable": True,
        "source_url": urls["source_url"],
    }


@dataclass(slots=True)
class TemplateMatch:
    model_code: str = ""
    name: str = ""
    area: str = ""
    score: float = 0.0
    found: bool = False
    ambiguous: bool = False
    reason: str = ""
    options: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActContext:
    tenant_id: str = ""
    user_id: str = ""
    client_id: str = ""
    fascicolo_id: str = ""
    cliente: Any = None
    fascicolo: Any = None
    utente: Any = None
    config: dict[str, Any] = field(default_factory=dict)
    parti: list[Any] = field(default_factory=list)
    documents: list[Any] = field(default_factory=list)
    client_options: list[dict[str, Any]] = field(default_factory=list)
    case_options: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    forbidden: bool = False
    permissions_scope: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "client_id": self.client_id,
            "fascicolo_id": self.fascicolo_id,
            "cliente": _as_dict(self.cliente),
            "fascicolo": _as_dict(self.fascicolo),
            "utente": _as_dict(self.utente),
            "config": dict(self.config or {}),
            "parti": [_as_dict(item) for item in self.parti],
            "documents": [_as_dict(item) for item in self.documents],
            "client_options": list(self.client_options),
            "case_options": list(self.case_options),
            "missing": list(self.missing),
            "forbidden": bool(self.forbidden),
            "permissions_scope": list(self.permissions_scope),
            "sources": list(self.sources),
        }


@dataclass(slots=True)
class PrefillResult:
    model_code: str
    payload: dict[str, Any]
    filled_fields: list[dict[str, Any]] = field(default_factory=list)
    missing_fields: list[dict[str, Any]] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    base_fields: list[dict[str, Any]] = field(default_factory=list)
    extra_fields: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    errors: dict[str, str] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RenderResult:
    ok: bool
    text: str = ""
    title: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CreatedDocumentResult:
    ok: bool
    document_id: str = ""
    open_url: str = ""
    filename: str = ""
    message: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DIRECT_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...], float], ...] = (
    (("atto di citazione", "citazione"), ("CIV_CIT_001",), 0.55),
    (("crea diffida", "template diffida", "diffida"), ("STR_DIFF_001",), 0.52),
    (("opposizione a decreto ingiuntivo", "opposizione decreto ingiuntivo"), ("CIV_OPPDI_001",), 0.62),
    (("ricorso decreto ingiuntivo", "ricorso per decreto ingiuntivo"), ("CIV_RDI_001",), 0.62),
    (("decreto ingiuntivo",), ("CIV_RDI_001", "CIV_OPPDI_001"), 0.35),
    (("procura alle liti", "procura", "mandato difensivo"), ("CIV_PROCBASE_001",), 0.48),
    (("nomina difensore", "nomina del difensore", "penale nomina"), ("PEN_NOM_001",), 0.54),
    (("separazione",), ("FAM_SEPC_001", "FAM_SEPG_001"), 0.34),
)


def _model_search_text(model: dict[str, Any], metadata: dict[str, Any]) -> str:
    field_parts = []
    for field_item in list(metadata.get("base_fields") or []) + list(metadata.get("extra_fields") or []):
        if isinstance(field_item, dict):
            field_parts.append(clean_spaces(field_item.get("name")))
            field_parts.append(clean_spaces(field_item.get("label")))
    guidance = model.get("guidance") if isinstance(model.get("guidance"), dict) else {}
    return " ".join(
        [
            clean_spaces(model.get("code")),
            clean_spaces(model.get("name")),
            clean_spaces(model.get("area")),
            clean_spaces(model.get("summary")),
            clean_spaces(guidance.get("summary") if isinstance(guidance, dict) else ""),
            " ".join(clean_spaces(item) for item in list(model.get("tags") or [])),
            " ".join(clean_spaces(item) for item in list(metadata.get("suggested_attachments") or [])),
            " ".join(clean_spaces(item) for item in list(metadata.get("suggested_clauses") or [])),
            " ".join(field_parts),
        ]
    )


def search_template_models(query: str, *, limit: int = 8, model_code: str = "") -> list[TemplateMatch]:
    from pct.compilatore_atti import elenco_modelli

    query_norm = normalize_text(query)
    query_tokens = set(_tokens(query_norm))
    requested_code = clean_spaces(model_code).upper()
    matches: list[TemplateMatch] = []
    for model in elenco_modelli():
        code = clean_spaces(model.get("code")).upper()
        try:
            metadata = template_metadata_for_model(code)
        except Exception:
            metadata = {**_model_source_urls(code), "model_code": code, "name": clean_spaces(model.get("name")), "area": clean_spaces(model.get("area"))}
        haystack = normalize_text(_model_search_text(model, metadata))
        score = 0.0
        if requested_code and code == requested_code:
            score = max(score, 1.0)
        if normalize_text(code) and normalize_text(code) in query_norm:
            score = max(score, 0.98)
        name_norm = normalize_text(model.get("name"))
        if name_norm and name_norm in query_norm:
            score += 0.45
        if query_tokens:
            overlap = len(query_tokens.intersection(set(haystack.split())))
            score += min(0.32, overlap * 0.045)
            if overlap >= len(query_tokens):
                score += 0.12
        for phrases, codes, boost in _DIRECT_HINTS:
            if any(normalize_text(phrase) in query_norm for phrase in phrases) and code in codes:
                score += boost
        if score <= 0:
            continue
        score = min(round(score, 4), 0.99)
        matches.append(
            TemplateMatch(
                model_code=code,
                name=clean_spaces(model.get("name")),
                area=clean_spaces(model.get("area")),
                score=score,
                found=True,
                metadata=metadata,
            )
        )
    matches.sort(key=lambda item: (-item.score, item.model_code))
    return matches[: max(1, int(limit or 8))]


def resolve_template_for_query(query: str, context: dict[str, Any] | None = None) -> TemplateMatch:
    context = dict(context or {})
    active = context.get("active_context") if isinstance(context.get("active_context"), dict) else {}
    requested_code = clean_spaces(
        context.get("model_code")
        or active.get("model_code")
        or active.get("modelCode")
        or context.get("template_model_code")
    )
    matches = search_template_models(query, limit=8, model_code=requested_code)
    if not matches:
        return TemplateMatch(found=False, reason="Nessun modello reale del catalogo atti corrisponde alla richiesta.")
    top = matches[0]
    options = [match.to_dict() for match in matches[:5]]
    direct_codes: set[str] = set()
    query_norm = normalize_text(query)
    for phrases, codes, _boost in _DIRECT_HINTS:
        if any(normalize_text(phrase) in query_norm for phrase in phrases):
            direct_codes.update(codes)
    direct_single = len(direct_codes) == 1 and top.model_code in direct_codes
    if len(matches) > 1 and matches[1].score >= top.score - 0.06 and not requested_code and not direct_single:
        return TemplateMatch(
            model_code=top.model_code,
            name=top.name,
            area=top.area,
            score=top.score,
            found=True,
            ambiguous=True,
            reason="Più modelli del catalogo sono compatibili con la richiesta.",
            options=options,
            metadata=top.metadata,
        )
    top.options = options
    return top


def _live_records(context: dict[str, Any], key: str) -> list[Any]:
    records = _list_context_values(context, key, f"{key}_rows")
    if records:
        return records
    try:
        from web.helpers import get_clienti, get_fascicoli, get_soggetti, get_utenti

        if key in {"clienti", "clients"}:
            return list(get_clienti().tutti())
        if key in {"fascicoli", "cases"}:
            return list(get_fascicoli().tutti())
        if key in {"parti", "soggetti", "parties"}:
            return list(get_soggetti().tutti())
        if key in {"utenti", "users"}:
            return list(get_utenti().tutti(solo_attivi=True))
    except Exception:
        return []
    return []


def _case_belongs_to_client(fascicolo: Any, cliente: Any) -> bool:
    client_id = _id(cliente)
    if not client_id:
        return False
    return clean_spaces(_value(fascicolo, "id_cliente", "client_id", "cliente_id")) == client_id


def _option(row: Any, kind: str) -> dict[str, Any]:
    return {
        "id": _id(row),
        "label": _label(row) or _id(row),
        "kind": kind,
        "href": f"/clienti/{_id(row)}" if kind == "cliente" else f"/fascicoli/{_id(row)}",
    }


def _scope_allows(scope: list[str], required: str) -> bool:
    if not scope:
        return True
    normalized = {clean_spaces(item).lower() for item in scope}
    return required in normalized or "*" in normalized or "superadmin" in normalized or "admin" in normalized


def resolve_act_context(
    tenant_id: str,
    user_id: str,
    client_id: str | None,
    fascicolo_id: str | None,
    query: str,
    *,
    context: dict[str, Any] | None = None,
    permissions_scope: list[str] | None = None,
) -> ActContext:
    context = dict(context or {})
    scope = list(permissions_scope or [])
    result = ActContext(
        tenant_id=clean_spaces(tenant_id),
        user_id=clean_spaces(user_id),
        client_id=clean_spaces(client_id),
        fascicolo_id=clean_spaces(fascicolo_id),
        permissions_scope=scope,
    )
    if not result.tenant_id or not result.user_id:
        result.forbidden = True
        result.missing.append("tenant o utente non risolto")
        return result

    can_read_clients = _scope_allows(scope, "clienti.leggi")
    can_read_cases = _scope_allows(scope, "fascicoli.leggi")
    if not can_read_clients or not can_read_cases:
        result.forbidden = True
        if not can_read_clients:
            result.missing.append("permesso clienti.leggi")
        if not can_read_cases:
            result.missing.append("permesso fascicoli.leggi")
        return result

    clients = _live_records(context, "clienti") or _live_records(context, "clients")
    cases = _live_records(context, "fascicoli") or _live_records(context, "cases")
    parties = _live_records(context, "parti") or _live_records(context, "soggetti") or _live_records(context, "parties")
    documents = _list_context_values(context, "documenti", "documents")
    users = _live_records(context, "utenti") or _live_records(context, "users")

    structured = context.get("structured_context") if isinstance(context.get("structured_context"), dict) else {}
    active_case = structured.get("fascicolo") if isinstance(structured.get("fascicolo"), dict) else context.get("fascicolo")
    if isinstance(active_case, dict) and not _find_record_by_id(cases, _id(active_case)):
        cases.insert(0, active_case)
    anagrafica = structured.get("anagrafica") if isinstance(structured.get("anagrafica"), dict) else {}
    if isinstance(anagrafica, dict):
        for cliente in list(anagrafica.get("clienti") or []):
            if _id(cliente) and not _find_record_by_id(clients, _id(cliente)):
                clients.insert(0, cliente)
        for soggetto in list(anagrafica.get("soggetti") or []):
            parties.append(soggetto)

    result.cliente = _find_record_by_id(clients, result.client_id)
    result.fascicolo = _find_record_by_id(cases, result.fascicolo_id)
    if result.fascicolo and not result.cliente:
        linked_client_id = clean_spaces(_value(result.fascicolo, "id_cliente", "cliente_id", "client_id"))
        result.cliente = _find_record_by_id(clients, linked_client_id)
        result.client_id = _id(result.cliente) or linked_client_id
    if result.cliente and not result.fascicolo:
        linked_cases = [row for row in cases if _case_belongs_to_client(row, result.cliente)]
        if len(linked_cases) == 1:
            result.fascicolo = linked_cases[0]
            result.fascicolo_id = _id(result.fascicolo)
        elif len(linked_cases) > 1:
            result.case_options = [_option(row, "fascicolo") for row in linked_cases[:6]]

    if not result.cliente:
        client_matches = [row for row in clients if _matches_query(row, query)]
        if len(client_matches) == 1:
            result.cliente = client_matches[0]
            result.client_id = _id(result.cliente)
        elif len(client_matches) > 1:
            result.client_options = [_option(row, "cliente") for row in client_matches[:6]]
    if not result.fascicolo:
        case_matches = [row for row in cases if _matches_query(row, query)]
        if result.cliente:
            case_matches = [row for row in case_matches if _case_belongs_to_client(row, result.cliente)] or case_matches
        if len(case_matches) == 1:
            result.fascicolo = case_matches[0]
            result.fascicolo_id = _id(result.fascicolo)
        elif len(case_matches) > 1:
            result.case_options = [_option(row, "fascicolo") for row in case_matches[:6]]

    if not result.cliente:
        result.missing.append("cliente")
    if not result.fascicolo:
        result.missing.append("fascicolo")

    result.parti = list(parties or [])
    controparte = clean_spaces(_value(result.fascicolo, "controparte"))
    if controparte and not any(normalize_text(_label(row)) == normalize_text(controparte) for row in result.parti):
        result.parti.insert(0, {"id": "controparte", "nome_completo": controparte, "ruolo": "controparte"})
    result.documents = documents
    result.utente = users[0] if users else context.get("utente") or context.get("user")
    result.config = dict(context.get("config") or context.get("studio_config") or {})
    result.sources = [
        {"id": result.client_id, "title": _label(result.cliente), "kind": "cliente", "href": f"/clienti/{result.client_id}"}
        if result.cliente else {},
        {"id": result.fascicolo_id, "title": _label(result.fascicolo), "kind": "fascicolo", "href": f"/fascicoli/{result.fascicolo_id}"}
        if result.fascicolo else {},
    ]
    result.sources = [item for item in result.sources if item.get("id") or item.get("title")]
    return result


def build_prefill(
    model_code: str,
    fascicolo: Any,
    cliente: Any,
    utente: Any,
    config: dict[str, Any] | None,
    parti: list[Any] | None,
) -> PrefillResult:
    from pct.compilatore_atti import prefill_payload

    metadata = template_metadata_for_model(model_code)
    payload = prefill_payload(
        model_code,
        fascicolo=_as_object(fascicolo),
        cliente=_as_object(cliente),
        utente=_as_object(utente),
        config=dict(config or {}),
        studio_timbro=None,
        parti=parti or [],
    )
    required = list(metadata.get("required_fields") or [])
    missing: list[dict[str, Any]] = []
    filled: list[dict[str, Any]] = []
    field_labels = {
        field_item["name"]: field_item.get("label") or field_item["name"]
        for field_item in list(metadata.get("base_fields") or []) + list(metadata.get("extra_fields") or [])
        if isinstance(field_item, dict) and field_item.get("name")
    }
    for field_name in required:
        value = payload.get(field_name)
        row = {"name": field_name, "label": field_labels.get(field_name, field_name), "value": value}
        if _is_empty(value):
            missing.append({key: row[key] for key in ("name", "label")})
        else:
            filled.append(row)
    return PrefillResult(
        model_code=clean_spaces(model_code),
        payload=payload,
        filled_fields=filled,
        missing_fields=missing,
        required_fields=required,
        base_fields=list(metadata.get("base_fields") or []),
        extra_fields=list(metadata.get("extra_fields") or []),
        sources=[],
        metadata=metadata,
    )


def validate_template_payload(model_code: str, payload: dict[str, Any]) -> ValidationResult:
    from pct.compilatore_atti import validate_payload

    errors = dict(validate_payload(model_code, dict(payload or {})) or {})
    missing_fields = [field for field, message in errors.items() if "obbligatorio" in clean_spaces(message).lower()]
    return ValidationResult(ok=not errors, errors=errors, missing_fields=missing_fields, warnings=[])


def render_template_act(model_code: str, payload: dict[str, Any]) -> RenderResult:
    from pct.compilatore_atti import render_compiled_act

    try:
        text = render_compiled_act(model_code, dict(payload or {}))
        title = clean_spaces((payload or {}).get("title")) or clean_spaces(model_code)
        return RenderResult(ok=True, text=text, title=title)
    except Exception as exc:
        return RenderResult(ok=False, warnings=[str(exc)])


def _safe_editor_filename(title: str, model_code: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", clean_spaces(title).lower()).strip("._-")
    if not stem:
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", clean_spaces(model_code).lower()).strip("._-") or "atto"
    return f"{stem[:70]}_{date.today().strftime('%Y%m%d')}.html"


def _to_editor_html(text: str) -> str:
    paragraphs = [clean_spaces(part) for part in str(text or "").splitlines() if clean_spaces(part)]
    if not paragraphs:
        return "<p></p>"
    return "\n".join(f"<p>{html.escape(part)}</p>" for part in paragraphs)


def create_editor_draft(
    model_code: str,
    payload: dict[str, Any],
    fascicolo_id: str | None,
    user_id: str | None,
    *,
    rendered_text: str = "",
    model: dict[str, Any] | None = None,
    fascicoli_repo: Any = None,
    encrypt_func: Callable[[bytes], Any] | None = None,
    editor_html_builder: Callable[[str], str] | None = None,
    audit_callback: Callable[[str, str, str, str], None] | None = None,
    document_writer: Callable[..., Any] | None = None,
) -> CreatedDocumentResult:
    case_id = clean_spaces(fascicolo_id or (payload or {}).get("case_id"))
    if not case_id:
        return CreatedDocumentResult(ok=False, errors=["fascicolo mancante"], message="Seleziona prima il fascicolo.")
    model = dict(model or {})
    if not model:
        try:
            from pct.compilatore_atti import get_modello

            model = dict(get_modello(model_code) or {})
        except Exception:
            model = {}
    if not rendered_text:
        rendered = render_template_act(model_code, payload)
        if not rendered.ok:
            return CreatedDocumentResult(ok=False, errors=rendered.warnings, message="Non ho potuto renderizzare la bozza.")
        rendered_text = rendered.text
    title = clean_spaces((payload or {}).get("title") or model.get("name") or model_code or "Atto")
    filename = _safe_editor_filename(title, model_code)
    if document_writer is not None:
        try:
            result = document_writer(
                model_code=model_code,
                payload=payload,
                fascicolo_id=case_id,
                user_id=clean_spaces(user_id),
                rendered_text=rendered_text,
                filename=filename,
                title=title,
            )
            if isinstance(result, CreatedDocumentResult):
                return result
            result_dict = dict(result or {})
            return CreatedDocumentResult(
                ok=bool(result_dict.get("ok", True)),
                document_id=clean_spaces(result_dict.get("document_id")),
                open_url=clean_spaces(result_dict.get("open_url")),
                filename=clean_spaces(result_dict.get("filename") or filename),
                message=clean_spaces(result_dict.get("message")) or "Bozza creata nell'editor.",
                errors=list(result_dict.get("errors") or []),
            )
        except Exception as exc:
            return CreatedDocumentResult(ok=False, errors=[str(exc)], message="Creazione bozza non riuscita.")
    try:
        if fascicoli_repo is None:
            from web.helpers import get_fascicoli

            fascicoli_repo = get_fascicoli()
        if encrypt_func is None:
            from web.services.document_crypto import encrypt_doc

            encrypt_func = encrypt_doc
        from pct.fascicoli import TipoDocumento
    except Exception as exc:
        return CreatedDocumentResult(ok=False, errors=[str(exc)], message="Servizi editor non disponibili.")

    editor_html = (editor_html_builder or _to_editor_html)(rendered_text)
    try:
        documento = fascicoli_repo.aggiungi_documento(
            case_id,
            filename,
            TipoDocumento.ATTO_GIUDIZIARIO,
            encrypt_func(editor_html.encode("utf-8")),
            note=f"Bozza creata da Template Atti: {title}",
            tags=["template-atti", "bozza-editor", clean_spaces(model_code).lower()],
            caricato_da=clean_spaces(user_id),
            fonte_documento="TEMPLATE_ATTI_COMPILATORE",
            nome_originale=filename,
        )
    except Exception as exc:
        return CreatedDocumentResult(ok=False, errors=[str(exc)], message="Scrittura nel fascicolo non riuscita.")

    document_id = clean_spaces(getattr(documento, "id", ""))
    open_url = f"/fascicoli/{case_id}/documenti/{document_id}/editor"
    if audit_callback is not None:
        try:
            audit_callback(
                "template_atti.compilazione.importa_editor",
                "fascicolo",
                case_id,
                f"modello={model_code}; documento={document_id}",
            )
        except Exception:
            pass
    return CreatedDocumentResult(
        ok=True,
        document_id=document_id,
        open_url=open_url,
        filename=clean_spaces(getattr(documento, "nome", "")) or filename,
        message="Bozza creata nell'editor professionale.",
    )


def _is_explicit_editor_creation(query: str, metadata: dict[str, Any]) -> bool:
    text = normalize_text(query)
    if metadata.get("confirmed_action") == "create_editor_draft" or metadata.get("confirm_create_editor_draft") is True:
        return True
    return any(
        phrase in text
        for phrase in (
            "crea ora la bozza nell editor",
            "crea la bozza nell editor",
            "crea bozza nell editor",
            "genera ora nell editor",
        )
    )


def _is_lookup_only(query: str) -> bool:
    text = normalize_text(query)
    return any(token in text for token in ("quali atti", "mostrami template", "mostra template", "elenco template", "posso creare")) and not any(
        token in text for token in ("crea bozza", "compila", "prepara atto")
    )


def _field_names(rows: list[dict[str, Any]], *, limit: int = 12) -> list[str]:
    names: list[str] = []
    for row in rows[:limit]:
        label = clean_spaces(row.get("label") or row.get("name"))
        if label:
            names.append(label)
    return names


def _action(
    action_id: str,
    label: str,
    kind: str,
    *,
    href: str = "",
    endpoint: str = "",
    method: str = "GET",
    requires_confirmation: bool = False,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "kind": kind,
        "href": href,
        "endpoint": endpoint,
        "method": method,
        "requires_confirmation": requires_confirmation,
        "payload": dict(payload or {}),
    }


def build_template_actions(
    *,
    template: TemplateMatch,
    act_context: ActContext,
    prefill: PrefillResult | None,
    created: CreatedDocumentResult | None = None,
    explicit_create: bool = False,
) -> list[dict[str, Any]]:
    metadata = dict(template.metadata or {})
    code = clean_spaces(template.model_code or metadata.get("model_code"))
    payload = dict((prefill.payload if prefill else {}) or {})
    if act_context.client_id:
        payload.setdefault("id_cliente", act_context.client_id)
    if act_context.fascicolo_id:
        payload.setdefault("id_fascicolo", act_context.fascicolo_id)
        payload.setdefault("case_id", act_context.fascicolo_id)
    query = []
    if act_context.client_id:
        query.append(f"id_cliente={act_context.client_id}")
    if act_context.fascicolo_id:
        query.append(f"id_fascicolo={act_context.fascicolo_id}")
    suffix = ("?" + "&".join(query)) if query else ""
    actions = [
        _action("open_template_catalog", "Apri catalogo", "open", href=metadata.get("catalog_url") or f"/template-atti/catalogo?scheda={code}"),
        _action("open_template_compiler", "Apri compilatore", "open", href=(metadata.get("compile_url") or f"/template-atti/compila/{code}") + suffix),
    ]
    if prefill and prefill.missing_fields:
        actions.append(
            _action(
                "complete_missing_fields",
                "Completa dati mancanti",
                "open",
                href=(metadata.get("compile_url") or f"/template-atti/compila/{code}") + (suffix + ("&" if suffix else "?") + "intent=complete_missing"),
            )
        )
    if act_context.fascicolo_id:
        actions.append(_action("open_case", "Apri fascicolo", "open", href=f"/fascicoli/{act_context.fascicolo_id}"))
    if act_context.client_id:
        actions.append(_action("open_client", "Apri cliente", "open", href=f"/clienti/{act_context.client_id}"))
    if code and act_context.fascicolo_id:
        actions.append(
            _action(
                "create_editor_draft",
                "Crea bozza nell'editor",
                "mutation",
                endpoint=f"/template-atti/compila/{code}",
                method="POST",
                requires_confirmation=not explicit_create,
                payload=payload,
            )
        )
    if created and created.ok and created.open_url:
        actions.append(_action("open_created_document", "Apri documento creato", "open", href=created.open_url))
    return actions


def _source_rows(template: TemplateMatch, act_context: ActContext) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if template.found:
        meta = dict(template.metadata or {})
        rows.append(
            {
                "id": template.model_code,
                "title": template.name,
                "excerpt": "Modello reale del catalogo atti IUSENTRA.",
                "url": meta.get("source_url") or meta.get("compile_url") or "",
                "authority": "iusentra_template_atti",
                "verified_reference": True,
                "trust_class": "B",
            }
        )
    for source in act_context.sources:
        rows.append(
            {
                "id": source.get("id"),
                "title": source.get("title"),
                "excerpt": "Dato interno dello studio.",
                "url": source.get("href"),
                "authority": "iusentra_studio_db",
                "verified_reference": True,
                "trust_class": "B",
            }
        )
    return rows


def build_template_message_blocks(
    *,
    template: TemplateMatch,
    act_context: ActContext,
    prefill: PrefillResult | None,
    validation: ValidationResult | None,
    actions: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if template.found:
        blocks.append(
            {
                "type": "template_act_card",
                "title": template.name,
                "subtitle": template.model_code,
                "url": template.metadata.get("source_url") or template.metadata.get("compile_url"),
                "fields": [
                    {"label": "Area", "value": template.area},
                    {"label": "Precompilabile", "value": "Sì" if template.metadata.get("prefill_capable") else "No"},
                    {"label": "Campi richiesti", "value": len(template.metadata.get("required_fields") or [])},
                ],
            }
        )
    if act_context.cliente:
        blocks.append(
            {
                "type": "client_card",
                "title": _label(act_context.cliente),
                "subtitle": "Cliente risolto dai dati studio",
                "url": f"/clienti/{act_context.client_id}" if act_context.client_id else "",
            }
        )
    if act_context.fascicolo:
        blocks.append(
            {
                "type": "case_card",
                "title": _label(act_context.fascicolo),
                "subtitle": clean_spaces(_value(act_context.fascicolo, "rg_completo", "numero_rg", "oggetto")),
                "url": f"/fascicoli/{act_context.fascicolo_id}" if act_context.fascicolo_id else "",
                "fields": [{"label": "Controparte", "value": clean_spaces(_value(act_context.fascicolo, "controparte"))}],
            }
        )
    for party in act_context.parti[:3]:
        if _label(party):
            blocks.append(
                {
                    "type": "party_card",
                    "title": _label(party),
                    "subtitle": clean_spaces(_value(party, "ruolo", "tipo")) or "Parte collegata",
                }
            )
    missing_labels = _field_names(prefill.missing_fields if prefill else [], limit=14)
    if validation and validation.errors:
        missing_labels.extend([clean_spaces(message) for message in validation.errors.values()])
    missing_labels.extend(act_context.missing)
    if missing_labels:
        blocks.append({"type": "missing_fields_card", "title": "Dati mancanti", "items": missing_labels[:16]})
    if source_rows:
        blocks.append({"type": "source_card", "title": "Fonti interne", "items": source_rows})
    if actions:
        blocks.append({"type": "actions", "title": "Azioni operative", "items": actions})
    return blocks


def run_template_act_workflow(request: Any, context: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = dict(getattr(request, "metadata", {}) or {})
    active_context = metadata.get("active_context") if isinstance(metadata.get("active_context"), dict) else {}
    if not active_context and isinstance(metadata.get("lex_active_context"), dict):
        active_context = metadata.get("lex_active_context")
    query = clean_spaces(getattr(request, "query", ""))
    template_context = {**metadata, "active_context": active_context}
    template = resolve_template_for_query(query, template_context)
    items = list((evidence or {}).get("items") or [])
    template_items = [item for item in items if clean_spaces(getattr(item, "source_type", "")).lower() == "template_atto"]
    if template_items:
        item = template_items[0]
        item_meta = dict(getattr(item, "metadata", {}) or {})
        template = TemplateMatch(
            model_code=clean_spaces(item_meta.get("model_code") or getattr(item, "source_id", "")),
            name=clean_spaces(item_meta.get("name") or getattr(item, "title", "")),
            area=clean_spaces(item_meta.get("area")),
            score=float(getattr(item, "score", 0.0) or 0.0),
            found=True,
            ambiguous=template.ambiguous,
            reason=template.reason,
            options=template.options,
            metadata=item_meta,
        )
    explicit_create = _is_explicit_editor_creation(query, metadata)
    lookup_only = _is_lookup_only(query)
    case_id = clean_spaces(
        getattr(request, "fascicolo_id", "")
        or active_context.get("case_id")
        or active_context.get("caseId")
        or active_context.get("linked_case_id")
        or active_context.get("linkedCaseId")
    )
    client_id = clean_spaces(
        active_context.get("client_id")
        or active_context.get("clientId")
        or active_context.get("linked_client_id")
        or active_context.get("linkedClientId")
    )
    permissions_scope = active_context.get("permissions_scope") or active_context.get("permissionsScope") or metadata.get("permissionsScope")
    if not isinstance(permissions_scope, list):
        permissions_scope = []
    act_context = resolve_act_context(
        clean_spaces(getattr(request, "tenant_id", "")),
        clean_spaces(getattr(request, "user_id", "")),
        client_id,
        case_id,
        query,
        context=context,
        permissions_scope=permissions_scope,
    )
    prefill: PrefillResult | None = None
    validation: ValidationResult | None = None
    created: CreatedDocumentResult | None = None
    if template.found and not lookup_only and not act_context.forbidden and not act_context.client_options and not act_context.case_options:
        prefill = build_prefill(template.model_code, act_context.fascicolo, act_context.cliente, act_context.utente, act_context.config, act_context.parti)
        manual_payload = metadata.get("template_payload") if isinstance(metadata.get("template_payload"), dict) else {}
        if manual_payload:
            prefill.payload.update(manual_payload)
            refreshed_missing = []
            for row in prefill.missing_fields:
                if _is_empty(prefill.payload.get(row.get("name"))):
                    refreshed_missing.append(row)
            prefill.missing_fields = refreshed_missing
        validation = validate_template_payload(template.model_code, prefill.payload)
        if explicit_create and act_context.fascicolo_id and validation.ok:
            writer = context.get("template_act_document_writer")
            created = create_editor_draft(
                template.model_code,
                prefill.payload,
                act_context.fascicolo_id,
                act_context.user_id,
                document_writer=writer if callable(writer) else None,
            )
    elif template.found:
        validation = ValidationResult(ok=False, errors={}, missing_fields=list(act_context.missing), warnings=[])
    actions = build_template_actions(
        template=template,
        act_context=act_context,
        prefill=prefill,
        created=created,
        explicit_create=explicit_create,
    ) if template.found else []
    source_rows = _source_rows(template, act_context)
    blocks = build_template_message_blocks(
        template=template,
        act_context=act_context,
        prefill=prefill,
        validation=validation,
        actions=actions,
        source_rows=source_rows,
    )

    if not template.found:
        answer = (
            "Non ho trovato un modello reale del catalogo atti compatibile con la richiesta. "
            "Non genero un atto libero: apri il catalogo o indica il modello da usare."
        )
        confidence = 0.34
        answer_mode = "needs_review"
    elif lookup_only:
        options = template.options or [template.to_dict()]
        lines = ["Ho cercato nel catalogo atti. Modelli pertinenti:"]
        for option in options[:5]:
            lines.append(f"- {option.get('model_code')}: {option.get('name')}")
        lines.append("Nessuna bozza è stata creata.")
        answer = "\n".join(lines)
        confidence = 0.82
        answer_mode = "lookup"
    elif act_context.forbidden:
        answer = "Non posso usare il fascicolo o il cliente collegato con i permessi disponibili. Non creo alcuna bozza."
        confidence = 0.2
        answer_mode = "needs_review"
    elif act_context.client_options or act_context.case_options:
        choices = act_context.client_options or act_context.case_options
        lines = ["Ho trovato più dati compatibili e non scelgo al posto tuo."]
        for option in choices[:6]:
            lines.append(f"- {option.get('label')}")
        lines.append("Scegli il cliente o il fascicolo corretto prima della precompilazione.")
        answer = "\n".join(lines)
        confidence = 0.58
        answer_mode = "needs_review"
    else:
        filled_count = len(prefill.filled_fields if prefill else [])
        missing_labels = _field_names(prefill.missing_fields if prefill else [], limit=8)
        missing_labels.extend(act_context.missing)
        counterparty = clean_spaces(_value(act_context.fascicolo, "controparte"))
        lines = [
            f"Template individuato: {template.name} ({template.model_code}).",
            f"Cliente: {_label(act_context.cliente) or 'da indicare'}.",
            f"Fascicolo: {_label(act_context.fascicolo) or 'da indicare'}.",
            f"Controparte: {counterparty or 'da indicare'}.",
            f"Dati precompilati: {filled_count}.",
        ]
        if missing_labels:
            lines.append("Dati mancanti: " + ", ".join(missing_labels[:10]) + ".")
        else:
            lines.append("Controlli: i campi obbligatori risultano compilati.")
        if created and created.ok:
            lines.append("Bozza creata nell'editor professionale.")
        else:
            lines.append("Nessuna bozza è stata creata senza conferma esplicita.")
        lines.append("Fonti: catalogo atti IUSENTRA e dati interni dello studio.")
        answer = "\n".join(lines)
        confidence = 0.78 if missing_labels else 0.88
        answer_mode = "grounded" if not missing_labels else "needs_review"

    return {
        "answer": answer,
        "template": template.to_dict(),
        "act_context": act_context.to_dict(),
        "prefill": prefill.to_dict() if prefill else {},
        "validation": validation.to_dict() if validation else {},
        "created_document": created.to_dict() if created else {},
        "lex_actions": actions,
        "message_blocks": blocks,
        "source_rows": source_rows,
        "confidence": confidence,
        "answer_mode": answer_mode,
        "lookup_only": lookup_only,
        "explicit_create": explicit_create,
        "missing_fields": _field_names(prefill.missing_fields if prefill else [], limit=20) + list(act_context.missing),
        "evidence_sufficient": bool(template.found and not act_context.forbidden),
    }
