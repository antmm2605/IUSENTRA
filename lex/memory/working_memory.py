"""Assembler dello snapshot di working memory di Lex."""

from __future__ import annotations

from lex.contracts import WorkingMemorySnapshot


class WorkingMemoryAssembler:
    def build(self, *, session_facts, case_facts, timeline, profiles, economic_facts, research_index, module_packs):
        return WorkingMemorySnapshot(
            session_facts=list(session_facts or []),
            case_facts=list(case_facts or []),
            timeline=list(timeline or []),
            profiles=dict(profiles or {}),
            economic_facts=list(economic_facts or []),
            research_index=list(research_index or []),
            module_packs=list(module_packs or []),
        )