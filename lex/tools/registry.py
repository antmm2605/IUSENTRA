"""Registry governato dei tool del bounded context Lex."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

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
from .operational_knowledge_tool import OperationalKnowledgeTool
from .preventivi_tool import PreventiviTool
from .scadenziario_tool import ScadenziarioTool
from .telematico_tool import TelematicoTool
from .template_atti_tool import TemplateAttiTool
from .workflow_agent_tools import (
    CreateClientDraftTool,
    CreateDeadlineTool,
    CreateDocumentDraftTool,
    CreateFascicoloDraftTool,
    CreateInvoiceDraftTool,
    CreatePecDraftTool,
    CreateTaskTool,
    CreateTimesheetEntryTool,
    UpdateChecklistTool,
)


LEX_TOOL_REGISTRY_SCHEMA = "iusentra.lex_tool_registry.v1"

_FREE_WEB_MODES = frozenset({"web_libero", "web libero", "free_web", "ricerca_web_libera", "ricerca web libera"})

_PERMISSION_ALIASES: dict[str, tuple[str, ...]] = {
    "studio:fascicoli:read": ("fascicoli.leggi",),
    "studio:documenti:read": ("fascicoli.leggi",),
    "studio:telematico:read": ("telematico.leggi",),
    "studio:agenda:read": ("agenda.leggi",),
    "studio:scadenze:read": ("scadenziario.leggi",),
    "legal:sources:read": ("ai.usa",),
    "studio:knowledge:read": ("ai.usa",),
    "studio:template:read": ("ai.usa",),
    "studio:economico:read": ("fatturazione.leggi",),
    "studio:compliance:read": ("ai.usa",),
    "studio:atti:read": ("ai.usa", "fascicoli.leggi"),
    "studio:atti:write": ("ai.usa", "fascicoli.scrivi"),
    "studio:atti:export": ("ai.usa", "fascicoli.scrivi"),
}


def _expand_permissions(permissions: Iterable[str] | None) -> set[str]:
    expanded = {str(item).strip() for item in permissions or () if str(item).strip()}
    changed = True
    while changed:
        changed = False
        for canonical, aliases in _PERMISSION_ALIASES.items():
            family = {canonical, *aliases}
            if expanded.intersection(family) and not family.issubset(expanded):
                expanded.update(family)
                changed = True
    return expanded


@dataclass(frozen=True)
class LexToolDescriptor:
    tool_name: str
    category: str
    access_level: str
    transport: str
    permissions: tuple[str, ...]
    mutates_state: bool
    allowed_in_free_web: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": LEX_TOOL_REGISTRY_SCHEMA,
            "tool_name": self.tool_name,
            "category": self.category,
            "access_level": self.access_level,
            "transport": self.transport,
            "permissions": list(self.permissions),
            "mutates_state": self.mutates_state,
            "allowed_in_free_web": self.allowed_in_free_web,
            "description": self.description,
        }


def _descriptor(
    tool_name: str,
    *,
    category: str,
    access_level: str = "read_only",
    transport: str = "in_process",
    permissions: Iterable[str] = (),
    mutates_state: bool = False,
    allowed_in_free_web: bool = False,
    description: str,
) -> LexToolDescriptor:
    return LexToolDescriptor(
        tool_name=tool_name,
        category=category,
        access_level=access_level,
        transport=transport,
        permissions=tuple(dict.fromkeys(str(item).strip() for item in permissions if str(item).strip())),
        mutates_state=mutates_state,
        allowed_in_free_web=allowed_in_free_web,
        description=description,
    )


def _build_descriptors() -> dict[str, LexToolDescriptor]:
    rows = [
        _descriptor(
            "fascicolo",
            category="fascicolo",
            permissions=("studio:fascicoli:read",),
            description="Legge dati strutturati del fascicolo e li espone a Lex in sola lettura.",
        ),
        _descriptor(
            "documento",
            category="fascicolo",
            permissions=("studio:documenti:read",),
            description="Legge un documento interno gia' censito nello studio.",
        ),
        _descriptor(
            "list_fascicolo_documents",
            category="fascicolo",
            permissions=("studio:documenti:read",),
            description="Elenca i documenti disponibili nel fascicolo.",
        ),
        _descriptor(
            "read_fascicolo_document",
            category="fascicolo",
            permissions=("studio:documenti:read",),
            description="Rilegge un documento del fascicolo per risposta Lex o editor.",
        ),
        _descriptor(
            "find_in_fascicolo_document",
            category="fascicolo",
            permissions=("studio:documenti:read",),
            description="Cerca testo in un documento del fascicolo senza modificare dati.",
        ),
        _descriptor(
            "telematico",
            category="telematico",
            permissions=("studio:telematico:read",),
            description="Consulta stato e checklist telematiche in sola lettura.",
        ),
        _descriptor(
            "agenda",
            category="studio",
            permissions=("studio:agenda:read",),
            description="Consulta appuntamenti ed eventi dello studio.",
        ),
        _descriptor(
            "scadenziario",
            category="studio",
            permissions=("studio:scadenze:read",),
            description="Consulta scadenze e termini dello studio.",
        ),
        _descriptor(
            "giurisprudenza",
            category="fonti_pubbliche",
            permissions=("legal:sources:read",),
            allowed_in_free_web=True,
            description="Interroga giurisprudenza e fonti pubbliche disponibili.",
        ),
        _descriptor(
            "legal_intelligence",
            category="fonti_pubbliche",
            permissions=("legal:sources:read",),
            allowed_in_free_web=True,
            description="Consulta l'intelligence legale e gli aggiornamenti acquisiti.",
        ),
        _descriptor(
            "operational_knowledge",
            category="studio",
            permissions=("studio:knowledge:read",),
            description="Risponde su dati reali dello studio con policy tenant-aware.",
        ),
        _descriptor(
            "template_atti",
            category="redazione",
            permissions=("studio:template:read",),
            description="Consulta template atti disponibili.",
        ),
        _descriptor(
            "preventivi",
            category="economico",
            permissions=("studio:economico:read",),
            description="Consulta dati economici, preventivi e conferimenti.",
        ),
        _descriptor(
            "compliance",
            category="governance",
            permissions=("studio:compliance:read",),
            description="Consulta verifiche di conformita' gia' disponibili.",
        ),
        _descriptor(
            "list_template_atti",
            category="redazione",
            permissions=("studio:template:read",),
            description="Elenca template reali per la redazione assistita.",
        ),
        _descriptor(
            "read_template_atto",
            category="redazione",
            permissions=("studio:template:read",),
            description="Legge il contenuto di un template atto.",
        ),
        _descriptor(
            "collect_fascicolo_context",
            category="redazione",
            permissions=("studio:fascicoli:read", "studio:documenti:read"),
            description="Raccoglie il contesto fascicolo necessario per l'editor professionale.",
        ),
        _descriptor(
            "generate_editor_draft",
            category="redazione",
            access_level="write",
            permissions=("studio:atti:write",),
            mutates_state=True,
            description="Crea una bozza nell'editor professionale, non una risposta lunga in chat.",
        ),
        _descriptor(
            "read_editor_document",
            category="redazione",
            permissions=("studio:atti:read",),
            description="Rilegge il documento aperto nell'editor.",
        ),
        _descriptor(
            "propose_editor_edits",
            category="redazione",
            access_level="write",
            permissions=("studio:atti:write",),
            mutates_state=True,
            description="Propone modifiche tracciate da accettare nel flusso editor.",
        ),
        _descriptor(
            "export_editor_document",
            category="redazione",
            access_level="write",
            permissions=("studio:atti:export",),
            mutates_state=True,
            description="Prepara esportazione del documento editor nel formato richiesto.",
        ),
        _descriptor(
            "create_task",
            category="workflow_agents",
            access_level="write",
            permissions=("agenda.scrivi",),
            mutates_state=True,
            description="Crea o registra un'attivita' operativa approvata dalla regia agentica.",
        ),
        _descriptor(
            "create_deadline",
            category="workflow_agents",
            access_level="write",
            permissions=("scadenziario.scrivi",),
            mutates_state=True,
            description="Crea una scadenza o un promemoria approvato dalla regia agentica.",
        ),
        _descriptor(
            "create_document_draft",
            category="workflow_agents",
            access_level="write",
            permissions=("ai.usa", "fascicoli.scrivi"),
            mutates_state=True,
            description="Crea una bozza documento governata dopo approvazione.",
        ),
        _descriptor(
            "create_timesheet_entry",
            category="workflow_agents",
            access_level="write",
            permissions=("agenda.scrivi",),
            mutates_state=True,
            description="Crea una voce timesheet approvata.",
        ),
        _descriptor(
            "create_invoice_draft",
            category="workflow_agents",
            access_level="write",
            permissions=("fatturazione.scrivi",),
            mutates_state=True,
            description="Crea una parcella in bozza, mai definitiva.",
        ),
        _descriptor(
            "create_client_draft",
            category="workflow_agents",
            access_level="write",
            permissions=("clienti.scrivi",),
            mutates_state=True,
            description="Crea o recupera un cliente potenziale approvato.",
        ),
        _descriptor(
            "create_fascicolo_draft",
            category="workflow_agents",
            access_level="write",
            permissions=("fascicoli.scrivi",),
            mutates_state=True,
            description="Crea un fascicolo iniziale dopo approvazione e controllo.",
        ),
        _descriptor(
            "create_pec_draft",
            category="workflow_agents",
            access_level="write",
            permissions=("messaggi.scrivi",),
            mutates_state=True,
            description="Crea una bozza PEC senza invio automatico.",
        ),
        _descriptor(
            "update_checklist",
            category="workflow_agents",
            access_level="write",
            permissions=("telematico.valida",),
            mutates_state=True,
            description="Registra aggiornamenti checklist approvati.",
        ),
    ]
    return {row.tool_name: row for row in rows}


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
            "operational_knowledge": OperationalKnowledgeTool(),
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
            "create_task": CreateTaskTool(),
            "create_deadline": CreateDeadlineTool(),
            "create_document_draft": CreateDocumentDraftTool(),
            "create_timesheet_entry": CreateTimesheetEntryTool(),
            "create_invoice_draft": CreateInvoiceDraftTool(),
            "create_client_draft": CreateClientDraftTool(),
            "create_fascicolo_draft": CreateFascicoloDraftTool(),
            "create_pec_draft": CreatePecDraftTool(),
            "update_checklist": UpdateChecklistTool(),
        }
        self.descriptors = _build_descriptors()
        missing_descriptors = sorted(set(self.tools) - set(self.descriptors))
        extra_descriptors = sorted(set(self.descriptors) - set(self.tools))
        if missing_descriptors or extra_descriptors:
            raise RuntimeError(
                "Registry strumenti Lex non coerente: "
                f"mancano descrittori {missing_descriptors}, "
                f"descrittori senza tool {extra_descriptors}"
            )

    def list_tools(self) -> list[dict[str, Any]]:
        return [self.descriptors[name].to_dict() for name in sorted(self.descriptors)]

    def descriptor(self, tool_name: str) -> LexToolDescriptor | None:
        return self.descriptors.get(str(tool_name or "").strip())

    def validate_tool_call(
        self,
        tool_name: str,
        *,
        mode: str = "",
        allow_writes: bool = False,
        user_permissions: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        name = str(tool_name or "").strip()
        descriptor = self.descriptor(name)
        if descriptor is None:
            return {
                "schema": LEX_TOOL_REGISTRY_SCHEMA,
                "allowed": False,
                "reason": "strumento_non_registrato",
                "tool_name": name,
                "descriptor": None,
            }

        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode in _FREE_WEB_MODES and not descriptor.allowed_in_free_web:
            return {
                "schema": LEX_TOOL_REGISTRY_SCHEMA,
                "allowed": False,
                "reason": "strumento_studio_non_esposto_al_web_libero",
                "tool_name": name,
                "descriptor": descriptor.to_dict(),
            }

        if descriptor.mutates_state and not allow_writes:
            return {
                "schema": LEX_TOOL_REGISTRY_SCHEMA,
                "allowed": False,
                "reason": "strumento_di_scrittura_richiede_canale_applicativo_autorizzato",
                "tool_name": name,
                "descriptor": descriptor.to_dict(),
            }

        requested_permissions = _expand_permissions(descriptor.permissions)
        granted_permissions = _expand_permissions(user_permissions)
        if user_permissions is not None and not requested_permissions.issubset(granted_permissions):
            return {
                "schema": LEX_TOOL_REGISTRY_SCHEMA,
                "allowed": False,
                "reason": "permessi_insufficienti",
                "tool_name": name,
                "missing_permissions": sorted(requested_permissions - granted_permissions),
                "descriptor": descriptor.to_dict(),
            }

        return {
            "schema": LEX_TOOL_REGISTRY_SCHEMA,
            "allowed": True,
            "reason": "strumento_autorizzato",
            "tool_name": name,
            "descriptor": descriptor.to_dict(),
        }

    def run_tool(
        self,
        tool_name: str,
        *,
        mode: str = "",
        allow_writes: bool = False,
        user_permissions: Iterable[str] | None = None,
        **kwargs: Any,
    ) -> Any:
        validation = self.validate_tool_call(
            tool_name,
            mode=mode,
            allow_writes=allow_writes,
            user_permissions=user_permissions,
        )
        if not validation["allowed"]:
            return validation
        return self.tools[validation["tool_name"]].run(**kwargs)
