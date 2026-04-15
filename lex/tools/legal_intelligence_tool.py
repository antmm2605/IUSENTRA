from __future__ import annotations

from .base import BaseLexTool


class LegalIntelligenceTool(BaseLexTool):
    tool_name = "legal_intelligence"

    def run(self, **kwargs):
        return {}
