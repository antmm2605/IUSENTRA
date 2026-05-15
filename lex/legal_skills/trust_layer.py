"""Controlli di fiducia per skill integrate e custom."""

from __future__ import annotations

import re
from typing import Any, Mapping

from .models import TrustCheckResult, TrustFinding
from .parser import scan_skill_text


WRITE_OR_NETWORK_RE = re.compile(
    r"\b(?:write_file|delete_file|rm\s+-|curl|wget|socket|subprocess|powershell|cmd\.exe|os\.system|open\(|requests\.)\b",
    re.IGNORECASE,
)
HOOK_RE = re.compile(r"\b(?:pretooluse|posttooluse|hook|mcp)\b", re.IGNORECASE)
SPDX_RE = re.compile(r"\b(?:mit|apache-2\.0|bsd-3-clause|mpl-2\.0|unlicense)\b", re.IGNORECASE)


def _severity_rank(severity: str) -> int:
    return {"clean": 0, "warning": 1, "concern": 2, "material_concern": 3, "refuse": 4}.get(severity, 1)


class LegalSkillTrustLayer:
    """Esegue verifiche statiche senza eseguire codice della skill."""

    def check_raw_skill(self, raw_markdown: str, *, metadata: Mapping[str, Any] | None = None) -> TrustCheckResult:
        metadata = metadata or {}
        findings = scan_skill_text(raw_markdown, location=str(metadata.get("location") or "skill"))
        if WRITE_OR_NETWORK_RE.search(raw_markdown):
            findings.append(
                TrustFinding(
                    code="side_effect_capability",
                    severity="material_concern",
                    message="La skill contiene riferimenti a rete, shell o scrittura file.",
                    action="refuse",
                )
            )
        if HOOK_RE.search(raw_markdown):
            findings.append(
                TrustFinding(
                    code="runtime_hook_reference",
                    severity="material_concern",
                    message="La skill richiama hook o strumenti MCP non compatibili con il motore read-only.",
                    action="refuse",
                )
            )
        if not SPDX_RE.search(raw_markdown) and not metadata.get("builtin"):
            findings.append(
                TrustFinding(
                    code="license_missing",
                    severity="warning",
                    message="Licenza non dichiarata: installazione custom da sottoporre a revisione.",
                )
            )
        worst = max((_severity_rank(item.severity) for item in findings), default=0)
        verdict = ("clean", "warning", "concern", "material_concern", "refuse")[min(worst, 4)]
        refused = any(item.action == "refuse" for item in findings)
        if refused:
            verdict = "refuse"
        return TrustCheckResult(
            verdict=verdict,
            findings=findings,
            material_concern=worst >= 3,
            refused=refused,
            reviewer_note="Controllo statico completato. Le skill custom restano spente finche non approvate.",
        )


__all__ = ["LegalSkillTrustLayer"]
