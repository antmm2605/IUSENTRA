"""Workflow applicativi di Lex."""

from .atto_workflow import AttoWorkflow
from .chat_workflow import ChatWorkflow
from .fascicolo_workflow import FascicoloWorkflow
from .giurisprudenza_workflow import GiurisprudenzaWorkflow
from .intelligence_workflow import IntelligenceWorkflow
from .lettera_workflow import LetteraWorkflow
from .next_action_workflow import NextActionWorkflow
from .telematico_workflow import TelematicoWorkflow
from .udienza_workflow import UdienzaWorkflow


WORKFLOW_REGISTRY = {
    "chat": ChatWorkflow,
    "atto": AttoWorkflow,
    "bozza_atto": AttoWorkflow,
    "udienza": UdienzaWorkflow,
    "fascicolo": FascicoloWorkflow,
    "giurisprudenza": GiurisprudenzaWorkflow,
    "research_giurisprudenza": GiurisprudenzaWorkflow,
    "telematico": TelematicoWorkflow,
    "next_action": NextActionWorkflow,
    "intelligence": IntelligenceWorkflow,
    "drafting_legal_letter": LetteraWorkflow,
    "lettera": LetteraWorkflow,
    "bozza_lettera": LetteraWorkflow,
}


def system_prompt_for(workflow: str) -> str:
    """Ritorna il system prompt specializzato per il workflow richiesto."""

    cls = WORKFLOW_REGISTRY.get(str(workflow or "").strip().lower())
    if cls is None:
        cls = ChatWorkflow
    prompt = getattr(cls, "system_prompt", "")
    return str(prompt or "").strip()


__all__ = [
    "AttoWorkflow",
    "ChatWorkflow",
    "FascicoloWorkflow",
    "GiurisprudenzaWorkflow",
    "IntelligenceWorkflow",
    "LetteraWorkflow",
    "NextActionWorkflow",
    "TelematicoWorkflow",
    "UdienzaWorkflow",
    "WORKFLOW_REGISTRY",
    "system_prompt_for",
]
