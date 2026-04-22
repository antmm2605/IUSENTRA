"""Generazione draft con AI locale e retrieval interno per la coverage pipeline."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from pct.legal_platform_catalog import PROCEDURE_REGISTRY
from pct.legal_taxonomy_sql_generator import apply_presets, validate_spec
from pct.local_ai import OllamaHttpClient


PRESETS_PATH = Path(__file__).with_name("data") / "legal_coverage_presets.json"


def _sanitize_json_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def load_presets(path: Path | None = None) -> dict[str, Any]:
    target = path or PRESETS_PATH
    if not target.exists():
        return {"presets": {}, "subbranch_defaults": {}}
    return json.loads(target.read_text(encoding="utf-8"))


def build_retrieval_examples(subbranch_code: str, repository: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []

    direct = repository.list_procedure_examples(subbranch_code, limit=limit)
    for row in direct:
        examples.append({**row, "source": "db"})

    learning_rows = repository.list_learning_examples(subbranch_code, limit=limit)
    for row in learning_rows:
        payload = dict(row.get("signal_payload_json") or {})
        examples.append(
            {
                "code": row.get("procedure_code"),
                "subbranch_code": subbranch_code,
                "name": payload.get("name") or row.get("procedure_code"),
                "channel_code": payload.get("channel_code", ""),
                "complexity_level": payload.get("complexity_level", ""),
                "source": "learning",
            }
        )

    for proc in PROCEDURE_REGISTRY.values():
        if proc.subbranch_code == subbranch_code:
            examples.append(
                {
                    "code": proc.code,
                    "subbranch_code": proc.subbranch_code,
                    "name": proc.name,
                    "channel_code": proc.channel_code,
                    "complexity_level": proc.complexity_level,
                    "description": proc.to_dict().get("required_documents", []),
                    "source": "seed",
                }
            )

    if examples:
        unique: dict[str, dict[str, Any]] = {}
        for item in examples:
            key = str(item.get("code") or json.dumps(item, sort_keys=True, ensure_ascii=False))
            unique[key] = item
        return list(unique.values())[:limit]

    same_area: list[dict[str, Any]] = []
    for proc in PROCEDURE_REGISTRY.values():
        if proc.subbranch_code.split("_", 1)[0] == subbranch_code.split("_", 1)[0]:
            same_area.append(
                {
                    "code": proc.code,
                    "subbranch_code": proc.subbranch_code,
                    "name": proc.name,
                    "channel_code": proc.channel_code,
                    "complexity_level": proc.complexity_level,
                    "source": "seed-similar",
                }
            )
    return same_area[:limit]


def build_prompt(subbranch_code: str, gap_type: str, gap_payload: dict[str, Any], examples: list[dict[str, Any]]) -> str:
    example_block = json.dumps(examples[:3], ensure_ascii=False, indent=2)
    return (
        "Sei l'orchestratore AI di IUSENTRA per la copertura procedure legali.\n"
        "Genera SOLO JSON valido, senza markdown.\n"
        f"Subbranch: {subbranch_code}\n"
        f"Gap type: {gap_type}\n"
        f"Gap payload: {json.dumps(gap_payload, ensure_ascii=False)}\n"
        "Obiettivo: produrre uno spec v2 prudente, operational-ready, coerente con il dominio legale.\n"
        "Requisiti minimi:\n"
        "- chiavi: subbranch_profile, procedure, variants, phase_map, acts, documents, norms, checklists, requirements, deadlines, outcomes, rules, templates\n"
        "- almeno 3 fasi\n"
        "- almeno 1 atto\n"
        "- almeno 2 documenti\n"
        "- almeno 3 checklist\n"
        "- almeno 1 requirement\n"
        "- almeno 1 outcome\n"
        "- almeno 1 rule\n"
        "- almeno 1 template con variables\n"
        "- non inventare riferimenti normativi iper-specifici: se non sei certo usa placeholder prudente con review_required=true\n"
        "- usa una complexity_level tra LOW, MEDIUM, HIGH, SPECIALIST\n"
        "- se il subbranch e' telematico mantieni channel_code coerente\n"
        "Esempi interni di retrieval:\n"
        f"{example_block}\n"
        "Produci solo JSON."
    )


def query_ollama(base_url: str, model: str, prompt: str, *, timeout: int = 120) -> dict[str, Any]:
    payload = OllamaHttpClient(base_url, timeout=timeout).generate_completion(
        model,
        prompt,
        response_format="json",
        timeout=timeout,
    )
    content = _sanitize_json_text(str(payload.get("response") or ""))
    return json.loads(content)


def fallback_spec(subbranch_code: str, gap_type: str, examples: list[dict[str, Any]]) -> dict[str, Any]:
    example = examples[0] if examples else {}
    proc_code = str(example.get("code") or f"PROC_AUTO_{subbranch_code[:32]}")
    name = str(example.get("name") or f"Procedura auto-generata per {subbranch_code}")
    channel_code = str(example.get("channel_code") or "INTERNO_STUDIO")
    complexity_level = str(example.get("complexity_level") or "MEDIUM")
    return {
        "subbranch_profile": {
            "subbranch_code": subbranch_code,
            "coverage_mode": "OPERATIONAL_READY",
            "operational_priority": 60,
            "is_telematic": channel_code in {"PCT_CIVILE", "PDP_PENALE", "PAT_AMMINISTRATIVO", "PTT_TRIBUTARIO"},
            "requires_human_review": True,
            "default_channel_code": channel_code,
            "notes": f"Draft fallback prudente per gap {gap_type}",
        },
        "procedure": {
            "code": proc_code,
            "subbranch_code": subbranch_code,
            "phase_code": "PREPARAZIONE",
            "channel_code": channel_code,
            "act_type_code": "ISTANZA",
            "norm_source_code": "CODICE_CIVILE",
            "name": name,
            "description": f"Bozza prudente generata automaticamente per gap {gap_type}.",
            "workflow_code": f"WF_{proc_code}_V1",
            "estimated_duration_days": 30,
            "complexity_level": complexity_level,
            "mandatory_human_review": True,
            "requires_hearing": False,
            "requires_registry_enrollment": False,
            "allows_settlement": False,
            "default_output_bundle_code": f"BUNDLE_{proc_code}",
            "is_active": True,
        },
        "variants": [{"name": "Variante default", "is_default": True}],
        "phase_map": [
            {"phase_code": "PREPARAZIONE", "sort_order": 10, "is_required": True},
            {"phase_code": "DEPOSITO", "sort_order": 20, "is_required": True},
            {"phase_code": "CHIUSURA", "sort_order": 30, "is_required": True},
        ],
        "acts": [{"name": "Atto introduttivo", "act_type_code": "ISTANZA", "is_required": True, "is_active": True}],
        "documents": [
            {"name": "Documento principale", "document_type_code": "CERTIFICATO", "phase_code": "PREPARAZIONE", "is_required": True},
            {"name": "Documento di supporto", "document_type_code": "RICEVUTA", "phase_code": "PREPARAZIONE", "is_required": False},
        ],
        "norms": [{"norm_source_code": "CODICE_CIVILE", "notes": "Placeholder prudente da revisionare."}],
        "checklists": [
            {"item_text": "Verificare la documentazione minima.", "is_required": True},
            {"item_text": "Verificare competenza, canale e rito.", "is_required": True},
            {"item_text": "Verificare eventuali allegati e termini.", "is_required": False},
        ],
        "requirements": [
            {
                "requirement_type": "DOCUMENT",
                "requirement_key": "documento_principale",
                "requirement_value": "required",
                "is_required": True,
            }
        ],
        "deadlines": [
            {"label": "Verifica termini della procedura", "relative_to": "EVENTO", "days_offset": 0, "is_peremptory": False}
        ],
        "outcomes": [{"name": "Procedura completata", "is_positive": True}],
        "rules": [
            {
                "rule_type": "WARNING",
                "rule_key": "review_required",
                "rule_expression": "human_review_done == true",
                "user_message": "Completare la review umana prima della pubblicazione.",
            }
        ],
        "templates": [
            {
                "name": "Template base auto-generato",
                "body": "Atto relativo a {{ oggetto }}",
                "variables": [
                    {
                        "variable_name": "oggetto",
                        "variable_type": "STRING",
                        "source_scope": "MANUAL",
                        "is_required": True,
                    }
                ],
            }
        ],
    }


class CoverageAutofillEngine:
    """Motore AI + retrieval con fallback prudente e policy interne."""

    def __init__(
        self,
        *,
        ollama_url: str,
        ollama_model: str,
        presets: dict[str, Any] | None = None,
        timeout: int = 120,
    ):
        self.ollama_url = str(ollama_url or "").strip()
        self.ollama_model = str(ollama_model or "").strip() or "mistral"
        self.presets = presets or load_presets()
        self.timeout = timeout

    def generate_draft(self, repository: Any, gap: dict[str, Any]) -> dict[str, Any]:
        subbranch_code = str(gap["subbranch_code"])
        gap_payload = dict(gap.get("gap_payload_json") or {})
        examples = build_retrieval_examples(subbranch_code, repository)
        prompt = build_prompt(subbranch_code, str(gap["gap_type"]), gap_payload, examples)

        spec: dict[str, Any]
        try:
            if not self.ollama_url:
                raise RuntimeError("Ollama non configurato")
            spec = query_ollama(self.ollama_url, self.ollama_model, prompt, timeout=self.timeout)
        except Exception:
            spec = fallback_spec(subbranch_code, str(gap["gap_type"]), examples)

        if not isinstance(spec, dict) or "procedure" not in spec:
            spec = fallback_spec(subbranch_code, str(gap["gap_type"]), examples)

        spec = apply_presets(spec, self.presets)
        validation = validate_spec(spec, strict=False)
        return {
            "prompt_used": prompt,
            "retrieval_examples": examples,
            "spec_json": spec,
            "validation_report_json": validation,
            "procedure_code": str((spec.get("procedure") or {}).get("code") or ""),
            "risk_level": str((spec.get("procedure") or {}).get("complexity_level") or "MEDIUM"),
        }
