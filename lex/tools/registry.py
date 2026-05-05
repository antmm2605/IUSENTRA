"""Registry dei tool del bounded context Lex."""

from __future__ import annotations

from .agenda_tool import AgendaTool
from .compliance_tool import ComplianceTool
from .document_tool import DocumentTool
from .editor_ai import (
    CollectFascicoloContextTool,
    ExportEditorDocumentTool,
    GenerateEditorDraftTool,
    ListTemplateAttiTool,
    ProposeEditorEditsTool,
    ReadEditorDocumentTool,
    ReadTemplateAttoTool,
)
from .fascicolo_documents import (
    FindInFascicoloDocumentTool,
    ListFascicoloDocumentsTool,
    ReadFascicoloDocumentTool,
)
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
            "list_fascicolo_documents": ListFascicoloDocumentsTool(),
            "read_fascicolo_document": ReadFascicoloDocumentTool(),
            "find_in_fascicolo_document": FindInFascicoloDocumentTool(),
            "telematico": TelematicoTool(),
            "agenda": AgendaTool(),
            "scadenziario": ScadenziarioTool(),
            "giurisprudenza": GiurisprudenzaTool(),
            "legal_intelligence": LegalIntelligenceTool(),
            "template_atti": TemplateAttiTool(),
            "preventivi": PreventiviTool(),
            "compliance": ComplianceTool(),
            "list_template_atti": ListTemplateAttiTool(),
            "read_template_atto": ReadTemplateAttoTool(),
            "collect_fascicolo_context": CollectFascicoloContextTool(),
            "generate_editor_draft": GenerateEditorDraftTool(),
            "read_editor_document": ReadEditorDocumentTool(),
            "propose_editor_edits": ProposeEditorEditsTool(),
            "export_editor_document": ExportEditorDocumentTool(),
        }
