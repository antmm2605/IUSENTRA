"""Generatore SQL e validatore per draft spec v2 della coverage pipeline."""

from __future__ import annotations

import copy
import json
import re
from typing import Any


REQUIRED_OPERATIONAL_BLOCKS = (
    "variants",
    "phase_map",
    "acts",
    "documents",
    "norms",
    "checklists",
    "requirements",
    "outcomes",
    "rules",
    "templates",
)


def slugify(value: str) -> str:
    text = str(value or "").strip().lower()
    replacements = {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
        "Ã ": "a",
        "Ã¨": "e",
        "Ã©": "e",
        "Ã¬": "i",
        "Ã²": "o",
        "Ã¹": "u",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-") or "item"


def _sql_quote(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _sql_values(values: list[Any]) -> str:
    return "(" + ", ".join(_sql_quote(item) for item in values) + ")"


def _upsert_insert(
    table: str,
    columns: list[str],
    rows: list[list[Any]],
    *,
    conflict_col: str = "code",
) -> str:
    if not rows:
        return ""
    cols = ", ".join(columns)
    values = ",\n".join(f"    {_sql_values(row)}" for row in rows)
    return (
        f"INSERT INTO {table} (\n    {cols}\n) VALUES\n{values}\n"
        f"ON CONFLICT ({conflict_col}) DO NOTHING;\n"
    )


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data or data[key] in (None, ""):
        raise ValueError(f"Campo obbligatorio mancante: {key}")
    return data[key]


def _default_code(prefix: str, proc_code: str, index: int) -> str:
    return f"{prefix}_{proc_code}_{index:02d}"


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def apply_presets(spec: dict[str, Any], presets: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(spec)
    procedure = out.get("procedure", {})
    subbranch_code = str(procedure.get("subbranch_code") or "")
    preset_names: list[str] = []
    if procedure.get("preset"):
        preset_names.append(str(procedure["preset"]))
    default_name = (presets.get("subbranch_defaults") or {}).get(subbranch_code)
    if default_name:
        preset_names.append(str(default_name))

    merged: dict[str, Any] = {}
    for name in preset_names:
        preset = (presets.get("presets") or {}).get(name)
        if not preset:
            raise ValueError(f"Preset non trovato: {name}")
        merged = _merge_dict(merged, preset)
    if merged:
        out = _merge_dict(merged, out)
    return out


def completeness_score(spec: dict[str, Any]) -> tuple[int, list[str]]:
    missing = [block for block in REQUIRED_OPERATIONAL_BLOCKS if not spec.get(block)]
    return max(0, 100 - len(missing) * 10), missing


def validate_spec(spec: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    procedure = spec.get("procedure")
    if not isinstance(procedure, dict):
        return {
            "errors": ["Campo obbligatorio mancante: procedure"],
            "warnings": [],
            "score": 0,
            "missing_blocks": list(REQUIRED_OPERATIONAL_BLOCKS),
        }

    for field in (
        "code",
        "subbranch_code",
        "name",
        "channel_code",
        "act_type_code",
        "norm_source_code",
    ):
        if procedure.get(field) in (None, ""):
            errors.append(f"procedure.{field} mancante")

    score, missing_blocks = completeness_score(spec)
    for block in missing_blocks:
        warnings.append(f"Blocco mancante o vuoto: {block}")

    coverage_mode = str((spec.get("subbranch_profile") or {}).get("coverage_mode") or "OPERATIONAL_READY")
    if coverage_mode == "OPERATIONAL_READY":
        if len(spec.get("phase_map", [])) < 3:
            warnings.append("Per OPERATIONAL_READY servono almeno 3 fasi.")
        if len(spec.get("documents", [])) < 2:
            warnings.append("Per OPERATIONAL_READY servono almeno 2 documenti.")
        if len(spec.get("checklists", [])) < 3:
            warnings.append("Per OPERATIONAL_READY servono almeno 3 checklist item.")
        if len(spec.get("templates", [])) < 1:
            errors.append("Per OPERATIONAL_READY serve almeno 1 template.")

    if strict and warnings:
        errors.extend(f"[STRICT] {warning}" for warning in warnings)

    return {
        "errors": errors,
        "warnings": warnings,
        "score": score,
        "missing_blocks": missing_blocks,
    }


def build_subbranch_profile_sql(spec: dict[str, Any]) -> str:
    procedure = spec.get("procedure", {})
    profile = spec.get("subbranch_profile") or {
        "subbranch_code": procedure.get("subbranch_code"),
        "coverage_mode": "OPERATIONAL_READY",
        "operational_priority": 50,
        "is_telematic": False,
        "requires_human_review": True,
        "default_channel_code": procedure.get("channel_code"),
        "default_registry_code": None,
        "notes": None,
    }
    return _upsert_insert(
        "legal_subbranch_profiles",
        [
            "subbranch_code",
            "coverage_mode",
            "operational_priority",
            "is_telematic",
            "requires_human_review",
            "default_channel_code",
            "default_registry_code",
            "notes",
        ],
        [
            [
                _require(profile, "subbranch_code"),
                profile.get("coverage_mode", "OPERATIONAL_READY"),
                profile.get("operational_priority", 50),
                profile.get("is_telematic", False),
                profile.get("requires_human_review", True),
                profile.get("default_channel_code"),
                profile.get("default_registry_code"),
                profile.get("notes"),
            ]
        ],
        conflict_col="subbranch_code",
    )


def build_procedure_sql(spec: dict[str, Any]) -> str:
    procedure = spec["procedure"]
    proc_code = _require(procedure, "code")
    subbranch_code = _require(procedure, "subbranch_code")
    name = _require(procedure, "name")
    slug = procedure.get("slug", slugify(name))
    sql = _upsert_insert(
        "legal_procedures",
        [
            "code",
            "subbranch_code",
            "phase_code",
            "channel_code",
            "act_type_code",
            "norm_source_code",
            "name",
            "slug",
            "description",
            "workflow_code",
            "estimated_duration_days",
            "complexity_level",
            "mandatory_human_review",
            "requires_hearing",
            "requires_registry_enrollment",
            "allows_settlement",
            "default_output_bundle_code",
            "is_active",
        ],
        [
            [
                proc_code,
                subbranch_code,
                procedure.get("phase_code", "PREPARAZIONE"),
                procedure.get("channel_code", "INTERNO_STUDIO"),
                procedure.get("act_type_code", "ISTANZA"),
                procedure.get("norm_source_code", "CODICE_CIVILE"),
                name,
                slug,
                procedure.get("description"),
                procedure.get("workflow_code", f"WF_{proc_code}_V1"),
                procedure.get("estimated_duration_days", 30),
                procedure.get("complexity_level", "MEDIUM"),
                procedure.get("mandatory_human_review", True),
                procedure.get("requires_hearing", False),
                procedure.get("requires_registry_enrollment", False),
                procedure.get("allows_settlement", False),
                procedure.get("default_output_bundle_code", f"BUNDLE_{proc_code}"),
                procedure.get("is_active", True),
            ]
        ],
    )

    variants_rows: list[list[Any]] = []
    for index, variant in enumerate(spec.get("variants", []), start=1):
        variants_rows.append(
            [
                variant.get("code", _default_code("VAR", proc_code, index)),
                proc_code,
                _require(variant, "name"),
                variant.get("slug", slugify(variant["name"])),
                variant.get("is_default", index == 1),
                variant.get("notes"),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_variants",
        ["code", "procedure_code", "name", "slug", "is_default", "notes"],
        variants_rows,
    )

    phase_rows: list[list[Any]] = []
    for index, phase in enumerate(spec.get("phase_map", []), start=1):
        phase_rows.append(
            [
                phase.get("code", _default_code("PM", proc_code, index)),
                proc_code,
                _require(phase, "phase_code"),
                phase.get("sort_order", index * 10),
                phase.get("is_required", True),
                phase.get("notes"),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_phase_map",
        ["code", "procedure_code", "phase_code", "sort_order", "is_required", "notes"],
        phase_rows,
    )

    act_rows: list[list[Any]] = []
    for index, act in enumerate(spec.get("acts", []), start=1):
        act_rows.append(
            [
                act.get("code", _default_code("ACT", proc_code, index)),
                proc_code,
                act.get("act_type_code", procedure.get("act_type_code", "ISTANZA")),
                _require(act, "name"),
                act.get("slug", slugify(act["name"])),
                act.get("is_required", True),
                act.get("is_active", True),
                act.get("notes"),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_acts",
        ["code", "procedure_code", "act_type_code", "name", "slug", "is_required", "is_active", "notes"],
        act_rows,
    )

    documents_rows: list[list[Any]] = []
    document_map_rows: list[list[Any]] = []
    for index, document in enumerate(spec.get("documents", []), start=1):
        legacy_code = document.get("legacy_code", _default_code("DOC", proc_code, index))
        doc_name = _require(document, "name")
        doc_slug = document.get("slug", slugify(doc_name))
        documents_rows.append(
            [
                legacy_code,
                proc_code,
                doc_name,
                doc_slug,
                document.get("is_required", True),
                document.get("notes"),
            ]
        )
        document_map_rows.append(
            [
                document.get("code", _default_code("DM", proc_code, index)),
                proc_code,
                document.get("document_type_code", "CERTIFICATO"),
                doc_name,
                doc_slug,
                document.get("phase_code", "PREPARAZIONE"),
                document.get("is_required", True),
                document.get("is_user_upload", True),
                document.get("is_system_generated", False),
                document.get("notes"),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_documents",
        ["code", "procedure_code", "name", "slug", "is_required", "notes"],
        documents_rows,
    )
    sql += _upsert_insert(
        "legal_procedure_document_map",
        [
            "code",
            "procedure_code",
            "document_type_code",
            "name",
            "slug",
            "phase_code",
            "is_required",
            "is_user_upload",
            "is_system_generated",
            "notes",
        ],
        document_map_rows,
    )

    norms_rows: list[list[Any]] = []
    for index, norm in enumerate(spec.get("norms", []), start=1):
        norms_rows.append(
            [
                norm.get("code", _default_code("NRM", proc_code, index)),
                proc_code,
                _require(norm, "norm_source_code"),
                norm.get("notes"),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_norms",
        ["code", "procedure_code", "norm_source_code", "notes"],
        norms_rows,
    )

    checklist_rows: list[list[Any]] = []
    for index, item in enumerate(spec.get("checklists", []), start=1):
        checklist_rows.append(
            [
                item.get("code", _default_code("CHK", proc_code, index)),
                proc_code,
                item.get("sort_order", index * 10),
                _require(item, "item_text"),
                item.get("is_required", True),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_checklists",
        ["code", "procedure_code", "sort_order", "item_text", "is_required"],
        checklist_rows,
    )

    requirements_rows: list[list[Any]] = []
    for index, requirement in enumerate(spec.get("requirements", []), start=1):
        requirements_rows.append(
            [
                requirement.get("code", _default_code("REQ", proc_code, index)),
                proc_code,
                _require(requirement, "requirement_type"),
                _require(requirement, "requirement_key"),
                requirement.get("requirement_value"),
                requirement.get("is_required", True),
                requirement.get("notes"),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_requirements",
        [
            "code",
            "procedure_code",
            "requirement_type",
            "requirement_key",
            "requirement_value",
            "is_required",
            "notes",
        ],
        requirements_rows,
    )

    deadline_rows: list[list[Any]] = []
    for index, deadline in enumerate(spec.get("deadlines", []), start=1):
        deadline_rows.append(
            [
                deadline.get("code", _default_code("DDL", proc_code, index)),
                proc_code,
                deadline.get("phase_code"),
                _require(deadline, "label"),
                deadline.get("relative_to", "EVENTO"),
                deadline.get("days_offset"),
                deadline.get("business_days_only", False),
                deadline.get("is_peremptory", False),
                deadline.get("notes"),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_deadlines",
        [
            "code",
            "procedure_code",
            "phase_code",
            "label",
            "relative_to",
            "days_offset",
            "business_days_only",
            "is_peremptory",
            "notes",
        ],
        deadline_rows,
    )

    outcome_rows: list[list[Any]] = []
    for index, outcome in enumerate(spec.get("outcomes", []), start=1):
        outcome_rows.append(
            [
                outcome.get("code", _default_code("OUT", proc_code, index)),
                proc_code,
                _require(outcome, "name"),
                outcome.get("sort_order", index * 10),
                outcome.get("is_positive"),
                outcome.get("notes"),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_outcomes",
        ["code", "procedure_code", "name", "sort_order", "is_positive", "notes"],
        outcome_rows,
    )

    rule_rows: list[list[Any]] = []
    for index, rule in enumerate(spec.get("rules", []), start=1):
        rule_rows.append(
            [
                rule.get("code", _default_code("RUL", proc_code, index)),
                proc_code,
                rule.get("rule_type", "WARNING"),
                _require(rule, "rule_key"),
                _require(rule, "rule_expression"),
                _require(rule, "user_message"),
                rule.get("sort_order", index * 10),
                rule.get("is_active", True),
            ]
        )
    sql += _upsert_insert(
        "legal_procedure_rules",
        [
            "code",
            "procedure_code",
            "rule_type",
            "rule_key",
            "rule_expression",
            "user_message",
            "sort_order",
            "is_active",
        ],
        rule_rows,
    )

    template_rows: list[list[Any]] = []
    template_variables_sql = ""
    for index, template in enumerate(spec.get("templates", []), start=1):
        template_code = template.get("code", _default_code("TPL", proc_code, index))
        template_rows.append(
            [
                template_code,
                proc_code,
                template.get("act_type_code", procedure.get("act_type_code", "ISTANZA")),
                template.get("template_kind", "ACT"),
                template.get("version_label", "v1"),
                template.get("is_placeholder", False),
                template.get("jurisdiction_scope"),
                _require(template, "name"),
                template.get("slug", slugify(template["name"])),
                template.get("body"),
                template.get("is_active", True),
                template.get("notes"),
            ]
        )
        variable_rows: list[list[Any]] = []
        for var_index, variable in enumerate(template.get("variables", []), start=1):
            variable_rows.append(
                [
                    variable.get("code", f"TV_{template_code}_{var_index:02d}"),
                    template_code,
                    _require(variable, "variable_name"),
                    variable.get("variable_type", "STRING"),
                    variable.get("source_scope", "MANUAL"),
                    variable.get("source_key"),
                    variable.get("is_required", False),
                    variable.get("default_value"),
                    variable.get("notes"),
                ]
            )
        template_variables_sql += _upsert_insert(
            "legal_template_variables",
            [
                "code",
                "template_code",
                "variable_name",
                "variable_type",
                "source_scope",
                "source_key",
                "is_required",
                "default_value",
                "notes",
            ],
            variable_rows,
        )

    sql += _upsert_insert(
        "legal_templates",
        [
            "code",
            "procedure_code",
            "act_type_code",
            "template_kind",
            "version_label",
            "is_placeholder",
            "jurisdiction_scope",
            "name",
            "slug",
            "body",
            "is_active",
            "notes",
        ],
        template_rows,
    )
    sql += template_variables_sql
    return sql


def generate_sql(spec: dict[str, Any]) -> str:
    return "\n".join((build_subbranch_profile_sql(spec), build_procedure_sql(spec)))


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
