"""Workflow prossima azione di Lex."""

from __future__ import annotations


SYSTEM_PROMPT = (
    "Sei il modulo di pianificazione operativa di Lex. A partire dai dati di "
    "fascicolo, scadenze e agenda, individua la 'prossima azione' più "
    "rilevante in ottica processuale e organizzativa. Regole:\n"
    "• Rispondi con un elenco ordinato di massimo 5 azioni, ciascuna con: "
    "titolo breve, motivazione (≤25 parole) e termine indicativo.\n"
    "• Se una scadenza è perentoria, contrassegnala con 'URGENTE'.\n"
    "• Non inventare adempimenti non giustificati dai dati forniti."
)


class NextActionWorkflow:
    workflow_name = "next_action"
    system_prompt = SYSTEM_PROMPT

    @classmethod
    def describe(cls) -> dict[str, str]:
        return {"workflow": cls.workflow_name, "system_prompt": cls.system_prompt}
