from __future__ import annotations

from .base import BaseLexTool


class ComplianceTool(BaseLexTool):
    tool_name = "compliance"

    def run(self, **kwargs):
        return {}
