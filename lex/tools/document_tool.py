from __future__ import annotations

from .base import BaseLexTool


class DocumentTool(BaseLexTool):
    tool_name = "documento"

    def run(self, **kwargs):
        return {}
