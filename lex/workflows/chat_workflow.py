"""Workflow chat generico di Lex."""

from __future__ import annotations


SYSTEM_PROMPT = (
    "Stai operando in modalità conversazione generale per lo studio legale. "
    "Rispondi in italiano professionale, conciso e chiaro. Se la domanda è "
    "operativa (fascicoli, udienze, scadenze, atti) invita l'utente ad aprire "
    "la sezione dedicata o fornisci il percorso esatto nel gestionale. Non "
    "fornire pareri legali vincolanti: indica sempre le fonti da consultare."
)


class ChatWorkflow:
    workflow_name = "chat"
    system_prompt = SYSTEM_PROMPT

    @classmethod
    def describe(cls) -> dict[str, str]:
        return {"workflow": cls.workflow_name, "system_prompt": cls.system_prompt}
