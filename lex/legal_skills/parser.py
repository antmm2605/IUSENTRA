"""Parser sicuro per skill pack Markdown."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml

from .models import LegalSkill, LegalSkillFrontmatter, TrustFinding


MAX_SKILL_CHARS = 48_000
HIDDEN_UNICODE_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")
LONG_BASE64_RE = re.compile(r"(?:[A-Za-z0-9+/]{80,}={0,2})")
ABSOLUTE_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/home/|/root/|/etc/|~/|\\\\)")
URL_RE = re.compile(r"https?://[^\s)>\"]+", re.IGNORECASE)
INJECTION_PHRASES = (
    "ignore previous instructions",
    "system override",
    "you are now",
    "developer message",
    "read ~/.ssh",
    "exfiltrate",
    "bypass",
)


@dataclass(slots=True)
class ParsedSkill:
    skill: LegalSkill
    findings: list[TrustFinding]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return [" ".join(str(item or "").split()).strip() for item in value if str(item or "").strip()]
    text = " ".join(str(value or "").split()).strip()
    return [text] if text else []


def _as_output_schema(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): raw for key, raw in value.items()}
    items = _as_list(value)
    if items:
        return {"sections": items}
    return {}


def _split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    text = str(markdown or "")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    raw_meta = parts[1].strip()
    body = parts[2].strip()
    parsed = yaml.safe_load(raw_meta) if raw_meta else {}
    if not isinstance(parsed, Mapping):
        parsed = {}
    return {str(key): value for key, value in parsed.items()}, body


def scan_skill_text(text: str, *, location: str = "skill") -> list[TrustFinding]:
    findings: list[TrustFinding] = []
    if len(text) > MAX_SKILL_CHARS:
        findings.append(
            TrustFinding(
                code="skill_too_large",
                severity="material_concern",
                message="La skill supera la dimensione massima ammessa.",
                location=location,
                action="refuse",
            )
        )
    if HIDDEN_UNICODE_RE.search(text):
        findings.append(
            TrustFinding(
                code="hidden_unicode",
                severity="concern",
                message="Rilevati caratteri invisibili o direzionali nel testo.",
                location=location,
            )
        )
    if LONG_BASE64_RE.search(text):
        findings.append(
            TrustFinding(
                code="long_encoded_blob",
                severity="material_concern",
                message="Rilevata una sequenza codificata troppo lunga per una skill leggibile.",
                location=location,
                action="refuse",
            )
        )
    lowered = text.lower()
    for phrase in INJECTION_PHRASES:
        if phrase in lowered:
            findings.append(
                TrustFinding(
                    code="prompt_injection_phrase",
                    severity="material_concern",
                    message="La skill contiene istruzioni di override o bypass non ammesse.",
                    location=location,
                    action="refuse",
                )
            )
            break
    if ABSOLUTE_PATH_RE.search(text):
        findings.append(
            TrustFinding(
                code="suspicious_path_reference",
                severity="warning",
                message="Rilevato riferimento a path locali o assoluti.",
                location=location,
            )
        )
    for raw_url in URL_RE.findall(text):
        host = urlparse(raw_url).netloc.lower()
        if host and not any(token in host for token in ("normattiva", "gazzettaufficiale", "garanteprivacy", "giustizia", "eur-lex")):
            findings.append(
                TrustFinding(
                    code="external_url_review",
                    severity="warning",
                    message="La skill cita una fonte esterna da verificare prima dell'uso.",
                    location=location,
                )
            )
            break
    return findings


def parse_skill_markdown(
    markdown: str,
    *,
    pack_id: str,
    skill_id: str,
    area: str,
    builtin: bool = True,
) -> ParsedSkill:
    metadata, body = _split_frontmatter(markdown)
    findings = scan_skill_text(markdown, location=f"{pack_id}/{skill_id}")
    missing = [field for field in ("name", "description") if not str(metadata.get(field) or "").strip()]
    for field in missing:
        findings.append(
            TrustFinding(
                code="missing_metadata",
                severity="material_concern",
                message=f"Metadato obbligatorio assente: {field}.",
                location=f"{pack_id}/{skill_id}",
                action="refuse",
            )
        )
    allowed_tools = _as_list(metadata.get("allowed-tools"))
    if any(tool not in {"lex_research", "source_policy", "document_context", "studio_profile"} for tool in allowed_tools):
        findings.append(
            TrustFinding(
                code="tool_not_allowed",
                severity="material_concern",
                message="La skill richiede strumenti non ammessi dal motore read-only.",
                location=f"{pack_id}/{skill_id}",
                action="refuse",
            )
        )
    source_mode = str(metadata.get("source-mode") or metadata.get("source_mode") or "balanced").strip().lower()
    if source_mode not in {"strict", "balanced", "broad"}:
        source_mode = "balanced"
    trust_status = "clean"
    if any(item.severity == "warning" for item in findings):
        trust_status = "warning"
    if any(item.severity == "concern" for item in findings):
        trust_status = "concern"
    if any(item.severity == "material_concern" for item in findings):
        trust_status = "material_concern"
    frontmatter = LegalSkillFrontmatter(
        name=str(metadata.get("name") or skill_id).strip(),
        description=str(metadata.get("description") or "").strip(),
        argument_hint=str(metadata.get("argument-hint") or "").strip(),
        user_invocable=bool(metadata.get("user-invocable", True)),
        allowed_tools=allowed_tools,
        references=_as_list(metadata.get("references")),
        required_context=_as_list(metadata.get("required-context")),
        output_schema=_as_output_schema(metadata.get("output-schema")),
    )
    skill = LegalSkill(
        pack_id=pack_id,
        skill_id=skill_id,
        name=frontmatter.name,
        description=frontmatter.description,
        area=area,
        body=body,
        argument_hint=frontmatter.argument_hint,
        user_invocable=frontmatter.user_invocable,
        allowed_tools=frontmatter.allowed_tools,
        references=frontmatter.references,
        required_context=frontmatter.required_context,
        output_schema=frontmatter.output_schema,
        source_mode=source_mode,
        builtin=builtin,
        read_only=True,
        trust_status=trust_status,
        trust_findings=findings,
        frontmatter=frontmatter,
    )
    return ParsedSkill(skill=skill, findings=findings)


__all__ = ["ParsedSkill", "parse_skill_markdown", "scan_skill_text"]
