from __future__ import annotations

from .base import BaseLexTool


class AgendaTool(BaseLexTool):
    tool_name = "agenda"

    def run(self, **kwargs):
        return {}
