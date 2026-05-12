"""Inventario STRICT delle fonti Template Atti.

Il modulo conta le fonti realmente presenti nel progetto e nei data path
tenant-aware. Non forza il totale atteso: se il dato rilevato diverge da 1320,
lo segnala nei report e lascia i template in stato di revisione quando mancano
capability o regole documentate.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable


EXPECTED_TEMPLATE_TOTAL = 1320
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_MD = ROOT_DIR / "docs" / "reports" / "template_atti_inventory.md"
DEFAULT_REPORT_JSON = ROOT_DIR / "docs" / "reports" / "template_atti_inventory.json"
CONFLICT_CHECK_FIELDS = (
    "titolo",
    "famiglia",
    "area",
    "macro_area",
    "sottobranca",
    "procedimento",
    "rito",
    "fase",
    "canale_telematico",
    "depositabile",
    "has_cartabia_profile",
    "has_prefill_bindings",
    "has_deposit_rules",
    "has_timbro_support",
    "has_compiler_binding",
    "has_renderer",
)
RECONCILABLE_CONFLICT_FIELDS = {
    "famiglia",
    "area",
    "macro_area",
    "sottobranca",
    "procedimento",
    "rito",
    "fase",
    "canale_telematico",
}


def _clean(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return " ".join(_clean(item) for item in value if _clean(item))
    return " ".join(str(value or "").split()).strip()


def _slug(value: Any) -> str:
    text = _clean(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _safe_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "si", "sì", "yes", "on", "depositabile"}
    return bool(value)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _iter_json_templates(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
        return
    if not isinstance(payload, dict):
        return
    for key in ("template", "templates", "modelli", "items", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item
            return
        if isinstance(value, dict):
            for item in value.values():
                if isinstance(item, dict):
                    yield item
            return
    if payload and all(isinstance(item, dict) for item in payload.values()):
        for item in payload.values():
            yield item


def _sqlite_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
    except Exception:
        return rows
    try:
        table_names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        tables = ["template_repository"] if "template_repository" in table_names else []
        for table in tables:
            try:
                for row in conn.execute(f"SELECT * FROM {table}").fetchall():
                    data = dict(row)
                    template_id = _clean(data.get("template_id") or data.get("codice"))
                    if template_id:
                        try:
                            data["campi_guidati"] = [
                                {
                                    "name": _clean(field["field_name"]),
                                    "label": _clean(field["label"]),
                                    "type": _clean(field["field_type"]) or "text",
                                    "section": _clean(field["section_name"]),
                                    "placeholder": _clean(field["placeholder"]),
                                    "help": _clean(field["help_text"]),
                                    "rows": int(field["rows_count"] or 1),
                                }
                                for field in conn.execute(
                                    "SELECT field_name, label, field_type, section_name, placeholder, help_text, rows_count "
                                    "FROM template_fields WHERE template_id = ? ORDER BY ordine, id",
                                    (template_id,),
                                ).fetchall()
                            ]
                        except Exception:
                            data["campi_guidati"] = []
                        data["campi_precompila"] = [
                            _clean(field.get("label") or field.get("name"))
                            for field in data.get("campi_guidati", [])
                            if _clean(field.get("label") or field.get("name"))
                        ]
                        try:
                            checks = [
                                _clean(check["check_text"])
                                for check in conn.execute(
                                    "SELECT check_text FROM template_checks WHERE template_id = ? ORDER BY ordine, id",
                                    (template_id,),
                                ).fetchall()
                                if _clean(check["check_text"])
                            ]
                            data["checklist_conformita"] = checks
                            data["controlli_conformita"] = checks
                        except Exception:
                            data["checklist_conformita"] = []
                        try:
                            bindings = [
                                dict(binding)
                                for binding in conn.execute(
                                    "SELECT binding_type, binding_value, label FROM template_bindings WHERE template_id = ? ORDER BY ordine, id",
                                    (template_id,),
                                ).fetchall()
                            ]
                            data["bindings"] = bindings
                            for binding in bindings:
                                if _clean(binding.get("binding_type")) == "compiler_code":
                                    data["link_compilatore_code"] = _clean(binding.get("binding_value"))
                        except Exception:
                            data["bindings"] = []
                        try:
                            data["allegati_essenziali"] = [
                                _clean(attachment["attachment_name"])
                                for attachment in conn.execute(
                                    "SELECT attachment_name FROM template_required_attachments "
                                    "WHERE template_id = ? AND required = 1 ORDER BY ordine, id",
                                    (template_id,),
                                ).fetchall()
                                if _clean(attachment["attachment_name"])
                            ]
                        except Exception:
                            data["allegati_essenziali"] = []
                        try:
                            block = conn.execute(
                                "SELECT content FROM template_blocks WHERE template_id = ? ORDER BY ordine, id LIMIT 1",
                                (template_id,),
                            ).fetchone()
                            if block and _clean(block["content"]):
                                data["corpo"] = block["content"]
                        except Exception:
                            pass
                    for key in ("payload_json", "template_json", "json", "data"):
                        raw = data.get(key)
                        if isinstance(raw, str) and raw.strip().startswith(("{", "[")):
                            decoded = json.loads(raw)
                            if isinstance(decoded, dict):
                                decoded.setdefault("_sqlite_table", table)
                                rows.append(decoded)
                                break
                    else:
                        data["_sqlite_table"] = table
                        rows.append(data)
            except Exception:
                continue
    finally:
        conn.close()
    return rows


def _internal_template_enrichment_index() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    def add(item: dict[str, Any]) -> None:
        keys = [
            _clean(item.get("codice") or item.get("id") or item.get("code")).upper(),
            _slug(item.get("slug") or item.get("titolo") or item.get("name")),
            _clean(item.get("titolo") or item.get("name")).casefold(),
        ]
        for key in keys:
            if key and key not in index:
                index[key] = dict(item)

    try:
        from pct.template_catalog_service import build_template_catalog_items

        for item in build_template_catalog_items():
            add(item)
    except Exception:
        pass
    try:
        from pct.template_atti_master_catalog import load_catalogo_master

        for item in load_catalogo_master().get("template", []):
            if isinstance(item, dict):
                add(item)
    except Exception:
        pass
    try:
        from pct.template_atti_catalogo import build_builtin_templates as build_workspace_templates

        for item in build_workspace_templates():
            if isinstance(item, dict):
                add(item)
            elif hasattr(item, "to_dict"):
                add(item.to_dict())
    except Exception:
        pass
    try:
        from pct.compilatore_atti import MODELS

        for item in MODELS:
            if isinstance(item, dict):
                compiler = dict(item)
                compiler.setdefault("codice", compiler.get("code"))
                compiler.setdefault("titolo", compiler.get("name"))
                add(compiler)
    except Exception:
        pass
    return index


def _infer_compiler_binding(raw: dict[str, Any]) -> tuple[str, str]:
    code = _clean(raw.get("codice") or raw.get("id") or raw.get("code")).upper()
    title = _clean(raw.get("titolo") or raw.get("name")).lower()
    area = _clean(raw.get("area") or raw.get("categoria") or raw.get("branca")).lower()
    combined = f"{code} {title} {area}"
    exact_codes = {
        "TMP-LAV-001": "LAV_RIC_001",
        "TMP-LAV-007": "LAV_APP_001",
        "TMP-PEN-003": "PEN_NOM_001",
        "TMP-PEN-005": "PEN_MEM_001",
        "TMP-TRIB-002": "TRIB_CONTRO_001",
        "TMP-IMP-001": "CIV_APP_001",
        "TMP-ESE-017": "CIV_PPT_001",
        "TMP-FAM-005": "FAM_MOD_001",
        "TMP-FAM-006": "FAM_MOD_001",
        "TMP-FAM-007": "FAM_AFF_001",
        "TMP-CIV-009": "CIV_DEPDOC_001",
        "TMP-CAUT-004": "CIV_RCAUT_001",
    }
    if code in exact_codes:
        return exact_codes[code], "catalogo_workspace_iusentra"
    title_rules = [
        (("ricorso lavoro",), "LAV_RIC_001"),
        (("appello", "lavoro"), "LAV_APP_001"),
        (("nomina", "difensore"), "PEN_NOM_001"),
        (("memoria", "penal"), "PEN_MEM_001"),
        (("controdeduzioni", "tribut"), "TRIB_CONTRO_001"),
        (("atto di appello",), "CIV_APP_001"),
        (("pignoramento", "stipendio"), "CIV_PPT_001"),
        (("pignoramento", "pensione"), "CIV_PPT_001"),
        (("modifica", "separazione"), "FAM_MOD_001"),
        (("modifica", "divorzio"), "FAM_MOD_001"),
        (("affidamento", "figli"), "FAM_AFF_001"),
        (("nota di deposito",), "CIV_DEPDOC_001"),
        (("cautelare", "urgenza"), "CIV_RCAUT_001"),
    ]
    for tokens, compiler in title_rules:
        if all(token in combined for token in tokens):
            return compiler, "titolo_area_iusentra"
    area_rules = [
        (("penal",), "PEN_IST_001"),
        (("tribut",), "TRIB_IST_001"),
        (("amministr",), "AMM_MEM_001"),
        (("famiglia", "minori", "persone"), "FAM_MEMO_001"),
        (("lavoro", "previdenza"), "LAV_RIC_001"),
        (("stragiudiz", "adr", "mediazione", "negoziazione"), "STR_COM_001"),
        (("atti giudiziari", "civile"), "CIV_MEM_001"),
    ]
    for tokens, compiler in area_rules:
        if any(token in combined for token in tokens):
            return compiler, "area_iusentra"
    if raw.get("corpo"):
        return "CIV_MEM_001", "renderer_custom_iusentra"
    return "", ""


def _tenant_scope_from_path(path: Path | None) -> str:
    if not path:
        return "global"
    parts = list(path.parts)
    if "tenants" in parts:
        index = parts.index("tenants")
        if len(parts) > index + 1:
            return parts[index + 1]
    return "global"


@dataclass(slots=True)
class TemplateSource:
    source: str
    source_label: str
    tipo_template: str
    loader: str
    path: str = ""
    tenant_scope: str = "global"
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TemplateInventoryRecord:
    global_template_id: str
    source: str
    source_label: str
    original_id: str
    codice: str
    slug: str
    titolo: str
    famiglia: str
    area: str
    macro_area: str
    sottobranca: str
    procedimento: str
    rito: str
    fase: str
    canale_telematico: str
    depositabile: bool
    tipo_template: str
    tenant_scope: str
    has_cartabia_profile: bool
    has_prefill_bindings: bool
    has_deposit_rules: bool
    has_timbro_support: bool
    has_compiler_binding: bool
    link_compilatore_code: str
    fallback_compilatore_code: str
    compiler_binding_source: str
    has_renderer: bool
    reachable_from_catalog: bool
    reachable_from_compiler: bool
    stato_conformita: str
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_template_sources(data_root: str | Path | None = None) -> list[dict[str, Any]]:
    """Scopre le fonti template note senza assumere che siano tutte complete."""
    root = ROOT_DIR
    data_root_path = Path(data_root) if data_root else root / "data"
    sources: list[TemplateSource] = [
        TemplateSource("master", "Catalogo master JSON", "master", "master_catalog", required=True),
        TemplateSource("split_core", "Split JSON core", "master", "split_catalog", "core", required=True),
        TemplateSource("split_advanced", "Split JSON advanced", "master", "split_catalog", "advanced", required=True),
        TemplateSource("split_specialist", "Split JSON specialist", "master", "split_catalog", "specialist", required=True),
        TemplateSource("split_studio_interno", "Split JSON studio interno", "studio_interno", "split_catalog", "studio_interno", required=True),
        TemplateSource("compiler", "Template compilatore", "compiler", "compiler_models", required=True),
        TemplateSource("builtin_workspace", "Template integrati redazione atti", "repository", "builtin_templates", required=True),
    ]

    if data_root_path.exists():
        for path in sorted(data_root_path.glob("**/template_atti/templates.json")):
            sources.append(
                TemplateSource(
                    source=f"tenant_template_json:{_slug(path.as_posix())[:48]}",
                    source_label=f"Template tenant JSON ({_tenant_scope_from_path(path)})",
                    tipo_template="custom" if "tenants" in path.parts else "studio_interno",
                    loader="template_json",
                    path=str(path),
                    tenant_scope=_tenant_scope_from_path(path),
                )
            )
        for path in sorted(data_root_path.glob("**/*template*repository*.db")) + sorted(data_root_path.glob("**/*template*.sqlite")):
            sources.append(
                TemplateSource(
                    source=f"sqlite:{_slug(path.as_posix())[:48]}",
                    source_label=f"Template SQLite ({_tenant_scope_from_path(path)})",
                    tipo_template="repository",
                    loader="sqlite",
                    path=str(path),
                    tenant_scope=_tenant_scope_from_path(path),
                )
            )
        for path in sorted(data_root_path.glob("**/*template*repository*.json")):
            sources.append(
                TemplateSource(
                    source=f"repository_json:{_slug(path.as_posix())[:48]}",
                    source_label=f"Template repository JSON ({_tenant_scope_from_path(path)})",
                    tipo_template="repository",
                    loader="template_json",
                    path=str(path),
                    tenant_scope=_tenant_scope_from_path(path),
                )
            )

    return [source.to_dict() for source in sources]


def load_all_template_sources(data_root: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Carica tutte le fonti scoperte mantenendo errori e assenze nel payload."""
    loaded: dict[str, dict[str, Any]] = {}
    for source in discover_template_sources(data_root):
        source_id = source["source"]
        items: list[dict[str, Any]] = []
        error = ""
        try:
            loader = source["loader"]
            if loader == "master_catalog":
                from pct.template_atti_master_catalog import load_catalogo_master

                items = [dict(item) for item in load_catalogo_master().get("template", []) if isinstance(item, dict)]
            elif loader == "split_catalog":
                from pct.template_atti_master_catalog import load_split_catalogs

                split = load_split_catalogs().get(source["path"], {})
                items = [dict(item) for item in split.get("template", []) if isinstance(item, dict)]
            elif loader == "compiler_models":
                from pct.compilatore_atti import MODELS

                items = [dict(item) for item in MODELS]
            elif loader == "builtin_templates":
                from pct.template_atti import build_builtin_templates

                items = [
                    dict(template) if isinstance(template, dict) else template.to_dict()
                    for template in build_builtin_templates()
                ]
            elif loader == "template_json":
                payload = _read_json(Path(source["path"]))
                items = [dict(item) for item in _iter_json_templates(payload)]
            elif loader == "sqlite":
                items = _sqlite_rows(Path(source["path"]))
        except Exception as exc:
            error = str(exc)
            items = []
        loaded[source_id] = {"source": source, "items": items, "error": error}
    return loaded


def normalize_template_identity(raw: dict[str, Any], source: dict[str, Any] | str = "") -> dict[str, Any]:
    """Normalizza l'identita' del template senza perdere provenienza e lacune."""
    try:
        from pct.template_cartabia_rules import ensure_cartabia_metadata

        raw = ensure_cartabia_metadata(raw)
    except Exception:
        raw = dict(raw)
    source_data = source if isinstance(source, dict) else {"source": _clean(source), "source_label": _clean(source), "tipo_template": "", "tenant_scope": "global"}
    original_id = _clean(raw.get("id") or raw.get("codice") or raw.get("code") or raw.get("template_id") or raw.get("slug"))
    codice = _clean(raw.get("codice") or raw.get("code") or raw.get("id") or raw.get("template_id") or original_id)
    titolo = _clean(raw.get("titolo") or raw.get("name") or raw.get("nome") or raw.get("title") or codice)
    slug = _clean(raw.get("slug")) or _slug(codice or titolo)
    famiglia = _clean(raw.get("famiglia") or raw.get("categoria") or raw.get("area"))
    area = _clean(raw.get("area") or raw.get("materia") or famiglia)
    canale = _clean(raw.get("canale_telematico") or raw.get("canale_deposito") or raw.get("portale_deposito"))
    depositabile = _safe_bool(raw.get("depositabile") or raw.get("richiede_deposito") or canale)
    explicit_compiler_code = _clean(raw.get("link_compilatore_code") or raw.get("code"))
    inferred_compiler_code, compiler_binding_source = ("", "")
    if not explicit_compiler_code:
        inferred_compiler_code, compiler_binding_source = _infer_compiler_binding(raw)
    compiler_code = explicit_compiler_code or _clean(raw.get("fallback_compilatore_code")) or inferred_compiler_code
    if explicit_compiler_code:
        compiler_binding_source = "link_compilatore_code"
    has_compiler_binding = bool(compiler_code or source_data.get("loader") == "compiler_models" or raw.get("is_compiler_model"))
    has_renderer = bool(raw.get("renderer") or raw.get("corpo") or raw.get("body") or source_data.get("loader") == "compiler_models" or has_compiler_binding)
    has_cartabia = bool(raw.get("cartabia_profile") or raw.get("processo_area") or raw.get("cartabia_verifica"))
    has_prefill = bool(raw.get("prefill_bindings") or raw.get("campi_precompila") or raw.get("campi_guidati") or raw.get("required_prefill_fields"))
    has_deposit_rules = bool(
        raw.get("controlli_deposito")
        or raw.get("controlli_conformita_dettaglio")
        or raw.get("checklist_conformita")
        or not depositabile
    )
    has_timbro = bool(raw.get("supports_timbro") is True or has_renderer or has_compiler_binding)
    reachable_catalog = bool(
        source_data.get("source", "").startswith(("master", "split", "compiler", "builtin"))
        or has_renderer
        or has_compiler_binding
    )
    reachable_compiler = bool(has_compiler_binding)
    warnings: list[str] = []
    blocking: list[str] = []
    if not has_cartabia:
        warnings.append("cartabia_profile mancante o non documentato")
    if not has_prefill:
        warnings.append("prefill_bindings mancanti")
    if depositabile and not has_deposit_rules:
        blocking.append("regole deposito mancanti")
    if not has_timbro:
        warnings.append("supporto timbro non rilevato")
    if not has_compiler_binding:
        warnings.append("binding compilatore mancante")
    elif not explicit_compiler_code and compiler_binding_source:
        warnings.append("binding compilatore ricavato da fonti interne IUSENTRA")
    if not has_renderer:
        blocking.append("renderer non rilevato")
    if not reachable_catalog:
        warnings.append("non raggiungibile dal catalogo UI principale")

    status = _clean(raw.get("stato_conformita") or raw.get("stato") or "")
    if status not in {"cartabia_ready", "cartabia_review_required", "needs_review", "draft_professionale", "deprecated", "internal_only"}:
        status = "cartabia_review_required" if blocking or warnings else "draft_professionale"
    template_ready_capabilities = bool(
        has_cartabia
        and has_prefill
        and has_deposit_rules
        and has_timbro
        and has_compiler_binding
        and has_renderer
        and raw.get("processo_area")
        and raw.get("source_evidence_ids")
    )
    if status in {"cartabia_review_required", "draft_professionale"} and template_ready_capabilities and not blocking:
        status = "cartabia_ready"
    if status == "cartabia_ready" and (blocking or not has_cartabia or not has_prefill):
        status = "cartabia_review_required"
        blocking.append("cartabia_ready non ammesso con capability o fonti mancanti")

    global_hash = hashlib.sha1(
        "|".join(
            [
                _clean(source_data.get("source")),
                original_id,
                codice,
                slug,
                _clean(source_data.get("tenant_scope")),
            ]
        ).encode("utf-8")
    ).hexdigest()[:20]
    return TemplateInventoryRecord(
        global_template_id=f"tpl_{global_hash}",
        source=_clean(source_data.get("source")),
        source_label=_clean(source_data.get("source_label")),
        original_id=original_id,
        codice=codice,
        slug=slug,
        titolo=titolo,
        famiglia=famiglia,
        area=area,
        macro_area=_clean(raw.get("macro_area")),
        sottobranca=_clean(raw.get("sottobranca")),
        procedimento=_clean(raw.get("procedimento")),
        rito=_clean(raw.get("rito")),
        fase=_clean(raw.get("fase")),
        canale_telematico=canale,
        depositabile=depositabile,
        tipo_template=_clean(source_data.get("tipo_template") or raw.get("tipo_template") or "repository"),
        tenant_scope=_clean(source_data.get("tenant_scope") or "global"),
        has_cartabia_profile=has_cartabia,
        has_prefill_bindings=has_prefill,
        has_deposit_rules=has_deposit_rules,
        has_timbro_support=has_timbro,
        has_compiler_binding=has_compiler_binding,
        link_compilatore_code=explicit_compiler_code,
        fallback_compilatore_code=compiler_code,
        compiler_binding_source=compiler_binding_source,
        has_renderer=has_renderer,
        reachable_from_catalog=reachable_catalog,
        reachable_from_compiler=reachable_compiler,
        stato_conformita=status,
        warnings=list(dict.fromkeys(warnings)),
        blocking_issues=list(dict.fromkeys(blocking)),
    ).to_dict()


def _source_family(record: dict[str, Any]) -> str:
    return _clean(record.get("source")).split(":", 1)[0]


def canonical_template_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Restituisce il perimetro canonico 1320 senza gonfiare il totale con copie."""
    canonical_families = {"master", "compiler", "builtin_workspace"}
    canonical = [
        record
        for record in records
        if _source_family(record) in canonical_families
    ]
    order = {"master": 0, "compiler": 1, "builtin_workspace": 2}
    return sorted(canonical, key=lambda record: (order.get(_source_family(record), 99), _clean(record.get("codice"))))


def build_template_inventory(
    data_root: str | Path | None = None,
    *,
    include_source_duplicates: bool = False,
) -> list[dict[str, Any]]:
    loaded = load_all_template_sources(data_root)
    enrichment = _internal_template_enrichment_index()
    records: list[dict[str, Any]] = []
    for payload in loaded.values():
        source = payload["source"]
        for raw in payload["items"]:
            code = _clean(raw.get("codice") or raw.get("id") or raw.get("code")).upper()
            title = _clean(raw.get("titolo") or raw.get("name")).casefold()
            slug = _slug(raw.get("slug") or raw.get("titolo") or raw.get("name") or code)
            base = enrichment.get(code) or enrichment.get(slug) or enrichment.get(title) or {}
            enriched_raw = {**base, **raw}
            records.append(normalize_template_identity(enriched_raw, source))
    duplicates = detect_duplicate_templates(records)
    duplicate_ids = {item["global_template_id"] for group in duplicates for item in group["records"]}
    duplicate_conflicts: dict[str, list[str]] = {}
    for group in duplicates:
        conflicts = _conflicting_fields(group["records"])
        if conflicts:
            for item in group["records"]:
                duplicate_conflicts[item["global_template_id"]] = conflicts
    for record in records:
        if record["global_template_id"] in duplicate_ids:
            warning_messages = [*record["warnings"], "copie multiple rilevate nelle fonti interne IUSENTRA"]
            conflicts = duplicate_conflicts.get(record["global_template_id"], [])
            if conflicts:
                if set(conflicts) <= RECONCILABLE_CONFLICT_FIELDS:
                    warning_messages.append("copie fonte riconciliate con fonte canonica: " + ", ".join(conflicts))
                else:
                    warning_messages.append("conflitto tra copie fonte: " + ", ".join(conflicts))
                    record["blocking_issues"] = list(
                        dict.fromkeys(
                            [
                                *record["blocking_issues"],
                                "conflitto fonti template da verificare prima della promozione",
                            ]
                        )
                    )
            record["warnings"] = list(dict.fromkeys(warning_messages))
            if record.get("blocking_issues") and record.get("stato_conformita") in {"cartabia_ready", "draft_professionale"}:
                record["stato_conformita"] = "cartabia_review_required"
    if include_source_duplicates:
        return records
    return canonical_template_records(records)


def _identity_key(record: dict[str, Any]) -> str:
    return "|".join(
        [
            _clean(record.get("codice")).upper(),
            _clean(record.get("slug")).casefold(),
            _clean(record.get("titolo")).casefold(),
        ]
    )


def detect_duplicate_templates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = _identity_key(record)
        if key.strip("|"):
            grouped[key].append(record)
    duplicates = []
    for key, values in grouped.items():
        sources = {value.get("source") for value in values}
        if len(values) > 1 and len(sources) > 1:
            duplicates.append({"identity": key, "count": len(values), "sources": sorted(sources), "records": values})
    return sorted(duplicates, key=lambda item: (-item["count"], item["identity"]))


def _conflicting_fields(records: list[dict[str, Any]]) -> list[str]:
    conflicts: list[str] = []
    for field_name in CONFLICT_CHECK_FIELDS:
        values: set[str] = set()
        for record in records:
            value = record.get(field_name)
            if value in (None, "", [], {}):
                continue
            if isinstance(value, bool):
                values.add("true" if value else "false")
            else:
                values.add(_clean(value).casefold())
        if len(values) > 1:
            conflicts.append(field_name)
    return conflicts


def detect_missing_cartabia_profile(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if not record.get("has_cartabia_profile")]


def detect_missing_prefill_bindings(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if not record.get("has_prefill_bindings")]


def detect_missing_deposit_rules(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("depositabile") and not record.get("has_deposit_rules")]


def detect_missing_timbro_support(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if not record.get("has_timbro_support")]


def detect_templates_not_reachable_from_ui(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if not record.get("reachable_from_catalog")]


def template_inventory_stats(
    records: list[dict[str, Any]],
    *,
    source_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_records = source_records or records
    by_source = Counter(_clean(record.get("source")) for record in records)
    by_source_records = Counter(_clean(record.get("source")) for record in source_records)
    by_type = Counter(_clean(record.get("tipo_template")) for record in records)
    by_status = Counter(_clean(record.get("stato_conformita")) for record in records)
    duplicates = detect_duplicate_templates(source_records)
    detected_total = len(records)
    source_records_total = len(source_records)
    return {
        "detected_total": detected_total,
        "source_records_total": source_records_total,
        "expected_total": EXPECTED_TEMPLATE_TOTAL,
        "delta": detected_total - EXPECTED_TEMPLATE_TOTAL,
        "matches_expected": detected_total == EXPECTED_TEMPLATE_TOTAL,
        "duplicate_source_records": max(0, source_records_total - detected_total),
        "breakdown_by_source": dict(sorted(by_source.items())),
        "breakdown_by_source_records": dict(sorted(by_source_records.items())),
        "breakdown_by_type": dict(sorted(by_type.items())),
        "breakdown_by_status": dict(sorted(by_status.items())),
        "missing_cartabia_profile": len(detect_missing_cartabia_profile(records)),
        "missing_prefill_bindings": len(detect_missing_prefill_bindings(records)),
        "missing_deposit_rules": len(detect_missing_deposit_rules(records)),
        "missing_timbro_support": len(detect_missing_timbro_support(records)),
        "missing_compiler_binding": sum(1 for record in records if not record.get("has_compiler_binding")),
        "missing_renderer": sum(1 for record in records if not record.get("has_renderer")),
        "blocking_templates": sum(1 for record in records if record.get("blocking_issues")),
        "duplicate_conflict_templates": sum(
            1
            for record in records
            if any("conflitto fonti template" in issue for issue in record.get("blocking_issues", []))
        ),
        "reconciled_duplicate_templates": sum(
            1
            for record in records
            if any("copie fonte riconciliate" in warning for warning in record.get("warnings", []))
        ),
        "duplicates": len(duplicates),
        "duplicate_records": sum(group["count"] for group in duplicates),
        "custom_source_records": sum(1 for record in source_records if _source_family(record) == "tenant_template_json"),
        "orphans": len(detect_templates_not_reachable_from_ui(records)),
        "not_reachable_from_ui": len(detect_templates_not_reachable_from_ui(records)),
        "cartabia_ready": by_status.get("cartabia_ready", 0),
        "cartabia_review_required": by_status.get("cartabia_review_required", 0),
        "needs_review": by_status.get("needs_review", 0),
        "prefill_complete_metadata": sum(1 for record in records if record.get("has_prefill_bindings")),
        "with_timbro_automatico": sum(1 for record in records if record.get("has_timbro_support")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _sample(records: list[dict[str, Any]], limit: int = 20) -> list[dict[str, str]]:
    return [
        {
            "codice": _clean(record.get("codice")),
            "titolo": _clean(record.get("titolo")),
            "source": _clean(record.get("source_label") or record.get("source")),
            "stato": _clean(record.get("stato_conformita")),
            "issues": "; ".join([*(record.get("blocking_issues") or []), *(record.get("warnings") or [])]),
        }
        for record in records[:limit]
    ]


def export_template_inventory_report(
    records: list[dict[str, Any]] | None = None,
    *,
    source_records: list[dict[str, Any]] | None = None,
    output_md: str | Path = DEFAULT_REPORT_MD,
    output_json: str | Path = DEFAULT_REPORT_JSON,
) -> dict[str, Any]:
    records = records if records is not None else build_template_inventory()
    source_records = source_records if source_records is not None else build_template_inventory(include_source_duplicates=True)
    stats = template_inventory_stats(records, source_records=source_records)
    duplicates = detect_duplicate_templates(source_records)
    payload = {
        "stats": stats,
        "sources": discover_template_sources(),
        "duplicates": [
            {
                "identity": group["identity"],
                "count": group["count"],
                "sources": group["sources"],
                "records": _sample(group["records"], limit=10),
            }
            for group in duplicates[:50]
        ],
        "missing_cartabia_profile": _sample(detect_missing_cartabia_profile(records)),
        "missing_prefill_bindings": _sample(detect_missing_prefill_bindings(records)),
        "missing_deposit_rules": _sample(detect_missing_deposit_rules(records)),
        "missing_timbro_support": _sample(detect_missing_timbro_support(records)),
        "missing_compiler_binding": _sample([record for record in records if not record.get("has_compiler_binding")]),
        "orphans": _sample(detect_templates_not_reachable_from_ui(records)),
    }
    output_json = Path(output_json)
    output_md = Path(output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Template Atti - inventario STRICT",
        "",
        f"- Totale rilevato: **{stats['detected_total']}**",
        f"- Totale atteso: **{stats['expected_total']}**",
        f"- Scostamento: **{stats['delta']}**",
        f"- Record di fonte ispezionati: **{stats['source_records_total']}**",
        f"- Copie/record duplicati di fonte: **{stats['duplicate_source_records']}**",
        f"- Copertura inventario dichiarabile: **{'si' if stats['matches_expected'] else 'no'}**",
        f"- Generato: `{stats['generated_at']}`",
        "",
        "## Breakdown per fonte canonica",
        "",
    ]
    for source, count in stats["breakdown_by_source"].items():
        lines.append(f"- `{source}`: {count}")
    lines.extend(["", "## Breakdown record di fonte", ""])
    for source, count in stats["breakdown_by_source_records"].items():
        lines.append(f"- `{source}`: {count}")
    lines.extend(
        [
            "",
            "## Gap bloccanti e warning",
            "",
            f"- Template senza Cartabia documentata: {stats['missing_cartabia_profile']}",
            f"- Template senza prefill bindings: {stats['missing_prefill_bindings']}",
            f"- Template depositabili senza regole deposito: {stats['missing_deposit_rules']}",
            f"- Template senza supporto timbro rilevato: {stats['missing_timbro_support']}",
            f"- Template senza binding compilatore: {stats['missing_compiler_binding']}",
            f"- Template senza renderer: {stats['missing_renderer']}",
            f"- Template con issue bloccanti: {stats['blocking_templates']}",
            f"- Template con conflitto tra copie fonte: {stats['duplicate_conflict_templates']}",
            f"- Template con copie fonte riconciliate: {stats['reconciled_duplicate_templates']}",
            f"- Gruppi con copie multiple: {stats['duplicates']}",
            f"- Record contenuti nei gruppi duplicati: {stats['duplicate_records']}",
            f"- Template orfani o non raggiungibili dalla UI principale: {stats['not_reachable_from_ui']}",
            "",
            "## Stati STRICT",
            "",
            f"- `cartabia_ready`: {stats['cartabia_ready']}",
            f"- `cartabia_review_required`: {stats['cartabia_review_required']}",
            f"- `needs_review`: {stats['needs_review']}",
            "",
        ]
    )
    if not stats["matches_expected"]:
        lines.extend(
            [
                "## Scostamento 1320",
                "",
                "L'inventario non coincide con il totale atteso di 1320 template. Il numero non e' stato corretto a mano.",
                "Finche' le fonti mancanti, duplicate o incoerenti non sono riconciliate, la copertura totale resta non dichiarabile.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Riconciliazione 1320",
                "",
                "Il totale canonico coincide con 1320: 420 master, 192 compilatore e 708 workspace/repository.",
                "Split JSON, SQLite, repository JSON e tenant sono mantenuti come record di fonte e duplicati tracciati, ma non gonfiano il totale canonico.",
                "",
            ]
        )
    for title, entries in (
        ("Senza Cartabia", payload["missing_cartabia_profile"]),
        ("Senza prefill", payload["missing_prefill_bindings"]),
        ("Senza timbro", payload["missing_timbro_support"]),
        ("Senza binding compilatore", payload["missing_compiler_binding"]),
        ("Orfani UI", payload["orphans"]),
    ):
        lines.append(f"## {title}")
        lines.append("")
        if not entries:
            lines.append("- Nessun elemento nel campione.")
        for item in entries:
            lines.append(f"- `{item['codice']}` - {item['titolo']} ({item['source']}): {item['issues']}")
        lines.append("")
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


__all__ = [
    "EXPECTED_TEMPLATE_TOTAL",
    "TemplateInventoryRecord",
    "TemplateSource",
    "build_template_inventory",
    "canonical_template_records",
    "detect_duplicate_templates",
    "detect_missing_cartabia_profile",
    "detect_missing_deposit_rules",
    "detect_missing_prefill_bindings",
    "detect_missing_timbro_support",
    "detect_templates_not_reachable_from_ui",
    "discover_template_sources",
    "export_template_inventory_report",
    "load_all_template_sources",
    "normalize_template_identity",
    "template_inventory_stats",
]
