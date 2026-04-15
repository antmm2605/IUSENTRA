"""Registry dei tool del bounded context Lex."""

from __future__ import annotations

from .agenda_tool import AgendaTool
from .compliance_tool import ComplianceTool
from .document_tool import DocumentTool
from .fascicolo_tool import FascicoloTool
from .giurisprudenza_tool import GiurisprudenzaTool
from .legal_intelligence_tool import LegalIntelligenceTool
from .preventivi_tool import PreventiviTool
from .scadenziario_tool import ScadenziarioTool
from .telematico_tool import TelematicoTool
from .template_atti_tool import TemplateAttiTool


class LexToolRegistry:
    def __init__(self):
        self.tools = {
            "fascicolo": FascicoloTool(),
            "documento": DocumentTool(),
            "telematico": TelematicoTool(),
            "agenda": AgendaTool(),
            "scadenziario": ScadenziarioTool(),
            "giurisprudenza": GiurisprudenzaTool(),
            "legal_intelligence": LegalIntelligenceTool(),
            "template_atti": TemplateAttiTool(),
            "preventivi": PreventiviTool(),
            "compliance": ComplianceTool(),
        }
