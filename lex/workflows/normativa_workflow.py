"""Workflow normativa / prassi / ricerca fonti di Lex.

Prima di questo modulo il workflow «normativa» non era registrato e usava il
system prompt della chat generica. Il prompt è quello giuridico fisso e unico
di Lex (`LEX_LEGAL_RAG_SYSTEM_PROMPT`): risposta solo dalle fonti numerate,
citazioni [n], astensione esplicita, vigenza quando nota.
"""

from __future__ import annotations

from lex.prompts.legal_rag_prompt import LEX_LEGAL_RAG_SYSTEM_PROMPT

SYSTEM_PROMPT = LEX_LEGAL_RAG_SYSTEM_PROMPT


class NormativaWorkflow:
    workflow_name = "normativa"
    system_prompt = SYSTEM_PROMPT

    @classmethod
    def describe(cls) -> dict[str, str]:
        return {"workflow": cls.workflow_name, "system_prompt": cls.system_prompt}
