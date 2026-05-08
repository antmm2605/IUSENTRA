"""Workflow applicativi di Lex."""

from .atto_workflow import AttoWorkflow
from .chat_workflow import ChatWorkflow
from .deposito_telematico_workflow import DepositoTelematicoWorkflow
from .fascicolo_workflow import FascicoloWorkflow
from .feedback_workflow import FeedbackWorkflow
from .giurisprudenza_specifica_workflow import GiurisprudenzaSpecificaWorkflow
from .giurisprudenza_workflow import GiurisprudenzaWorkflow
from .intelligence_workflow import IntelligenceWorkflow
from .lettera_workflow import LetteraWorkflow
from .next_action_workflow import NextActionWorkflow
from .telematico_workflow import TelematicoWorkflow
from .termini_processuali_workflow import TerminiProcessualiWorkflow
from .udienza_workflow import UdienzaWorkflow


WORKFLOW_REGISTRY = {
    # Redazione legale
    "drafting_legal_letter": LetteraWorkflow,
    "lettera": LetteraWorkflow,
    "bozza_lettera": LetteraWorkflow,
    "pec_comunicazioni": LetteraWorkflow,
    "atto": AttoWorkflow,
    "bozza_atto": AttoWorkflow,
    # Fascicolo e operativo
    "fascicolo": FascicoloWorkflow,
    "udienza": UdienzaWorkflow,
    "next_action": NextActionWorkflow,
    "cabina": NextActionWorkflow,
    # Giurisprudenza
    "giurisprudenza": GiurisprudenzaWorkflow,
    "giurisprudenza_specifica": GiurisprudenzaSpecificaWorkflow,
    "research_giurisprudenza": GiurisprudenzaWorkflow,
    # Telematico
    "telematico": TelematicoWorkflow,
    "telematico_status": TelematicoWorkflow,
    "deposito_telematico": DepositoTelematicoWorkflow,
    # Termini processuali
    "termini_processuali": TerminiProcessualiWorkflow,
    # Intelligence e chat
    "intelligence": IntelligenceWorkflow,
    "chat": ChatWorkflow,
    "question_answering": ChatWorkflow,
    # Feedback diagnostico
    "lex_feedback_diagnostico": FeedbackWorkflow,
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
    "DepositoTelematicoWorkflow",
    "FascicoloWorkflow",
    "FeedbackWorkflow",
    "GiurisprudenzaSpecificaWorkflow",
    "GiurisprudenzaWorkflow",
    "IntelligenceWorkflow",
    "LetteraWorkflow",
    "NextActionWorkflow",
    "TelematicoWorkflow",
    "TerminiProcessualiWorkflow",
    "UdienzaWorkflow",
    "WORKFLOW_REGISTRY",
    "system_prompt_for",
]
