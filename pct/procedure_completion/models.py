"""Modelli del Procedure Completion Engine (dataclass, stile repo)."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

CARD_STATUSES = ("draft", "needs_review", "approved", "published")
CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")
RISK_LEVELS = ("low", "medium", "high")
GAP_SEVERITIES = ("info", "warning", "blocking")
SOURCE_TYPES = ("official", "technical", "jurisprudence", "professional", "internal")
COPYRIGHT_POLICIES = ("full_text", "summary_only", "metadata_only")

# Le fonti professionali esterne non sono mai copiate estesamente.
MAX_PROFESSIONAL_EXCERPT_CHARS = 500


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str = "pce") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass(slots=True)
class ProcedureCompletionRequest:
    """Input dell'avvocato: mai trattato come verita' giuridica."""

    codice: str = ""
    denominazione: str = ""
    categoria: str = ""
    rito: str = ""
    competenza: str = ""
    template_code: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProcedureCompletionSource:
    """Fonte collegata alla scheda (ufficiale, tecnica, professionale, interna)."""

    id: str = field(default_factory=lambda: new_id("src"))
    source_type: str = "technical"
    title: str = ""
    url: str = ""
    authority: str = ""
    trust_class: str = ""           # "A" primaria, "B" istituzionale, "" non classificata
    copyright_policy: str = "metadata_only"
    excerpt: str = ""
    origin: str = ""                # catalogo_pst | xsd | template | lifecycle | normattiva | gazzetta | agenzia_entrate | fixture
    source_hash: str = ""
    last_checked_at: str = ""

    def __post_init__(self) -> None:
        if self.source_type == "professional":
            self.copyright_policy = "summary_only"
            if len(self.excerpt) > MAX_PROFESSIONAL_EXCERPT_CHARS:
                self.excerpt = self.excerpt[: MAX_PROFESSIONAL_EXCERPT_CHARS - 3] + "..."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def is_official_or_technical(self) -> bool:
        return self.source_type in {"official", "technical"}


@dataclass(slots=True)
class ProcedureCompletionCitation:
    """Citazione puntuale verificabile (atto + articolo + fonte)."""

    id: str = field(default_factory=lambda: new_id("cit"))
    riferimento: str = ""           # es. "art. 57 D.Lgs. 14/2019"
    atto_normativo: str = ""
    articolo: str = ""
    comma: str = ""
    versione: str = ""              # data versione/vigenza quando disponibile
    url: str = ""
    source_id: str = ""
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def verificabile(self) -> bool:
        return bool(self.riferimento and (self.source_id or self.url))


@dataclass(slots=True)
class ProcedureCompletionGap:
    """Lacuna dichiarata: il motore segnala, non inventa."""

    id: str = field(default_factory=lambda: new_id("gap"))
    codice_gap: str = ""
    descrizione: str = ""
    severita: str = "warning"
    azione_suggerita: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProcedureTemplateCandidate:
    template_id: str = ""
    titolo: str = ""
    score: int = 0
    canale: str = ""
    area: str = ""
    motivi: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProcedureCompletionValidationReport:
    """Esito macchina delle regole fail-closed."""

    valid: bool = True
    approvable: bool = False
    publishable: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    blocking_errors: List[str] = field(default_factory=list)
    privacy_review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProcedureCompletionCard:
    """Scheda operativa completa: sempre bozza finche' non revisionata e pubblicata."""

    id: str = field(default_factory=lambda: new_id("card"))
    run_id: str = ""
    tenant_id: str = ""
    codice: str = ""
    denominazione: str = ""
    categoria: str = ""
    rito: str = ""
    competenza: str = ""
    xsd_code: str = ""
    uffici_destinatari: List[str] = field(default_factory=list)
    fonte_catalogo: Dict[str, Any] = field(default_factory=dict)
    fonte_normativa: List[Dict[str, Any]] = field(default_factory=list)
    articoli_rilevanti: List[str] = field(default_factory=list)
    sintesi_articoli: List[Dict[str, str]] = field(default_factory=list)
    condizioni_procedibilita: List[Dict[str, str]] = field(default_factory=list)
    guida_pratica: List[str] = field(default_factory=list)
    adempimenti_fiscali: List[Dict[str, str]] = field(default_factory=list)
    termini_processuali: List[Dict[str, str]] = field(default_factory=list)
    allegati_obbligatori: List[Dict[str, str]] = field(default_factory=list)
    allegati_facoltativi: List[Dict[str, str]] = field(default_factory=list)
    avvertimenti_obbligatori: List[str] = field(default_factory=list)
    atto_principale: Dict[str, Any] = field(default_factory=dict)
    template_candidates: List[Dict[str, Any]] = field(default_factory=list)
    template_selected: Dict[str, Any] = field(default_factory=dict)
    checklist_operativa: List[Dict[str, Any]] = field(default_factory=list)
    lifecycle_steps: List[Dict[str, Any]] = field(default_factory=list)
    firma_digitale: Dict[str, Any] = field(default_factory=dict)
    deposito_telematico: Dict[str, Any] = field(default_factory=dict)
    ricevute_attese: List[str] = field(default_factory=list)
    notifiche: Dict[str, Any] = field(default_factory=dict)
    prova_notifica: Dict[str, Any] = field(default_factory=dict)
    rischi_operativi: List[str] = field(default_factory=list)
    gap_evidenza: List[Dict[str, Any]] = field(default_factory=list)
    confidence: str = "LOW"
    status: str = "draft"
    risk_level: str = "medium"
    review_avvocato: Dict[str, Any] = field(default_factory=dict)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    source_hashes: List[str] = field(default_factory=list)
    last_checked_at: str = ""
    generated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcedureCompletionCard":
        campi = {nome: data.get(nome) for nome in cls.__dataclass_fields__ if nome in data}
        card = cls(**{k: v for k, v in campi.items() if v is not None})
        return card

    @property
    def fonti_ufficiali_o_tecniche(self) -> list[dict[str, Any]]:
        return [src for src in self.sources if str(src.get("source_type")) in {"official", "technical"}]

    @property
    def citazioni_verificabili(self) -> list[dict[str, Any]]:
        return [
            cit for cit in self.citations
            if str(cit.get("riferimento") or "").strip() and (cit.get("source_id") or cit.get("url"))
        ]


def assign_confidence(card: ProcedureCompletionCard) -> str:
    """HIGH solo con fonti ufficiali + template + review; MEDIUM con fonti ma review pendente; LOW altrimenti."""
    blocking = [gap for gap in card.gap_evidenza if str(gap.get("severita")) == "blocking"]
    has_official = bool(card.fonti_ufficiali_o_tecniche)
    has_template = bool(card.template_selected.get("template_id"))
    reviewed = card.status in {"approved", "published"} and bool(card.review_avvocato.get("reviewer"))
    if has_official and has_template and reviewed and not blocking:
        return "HIGH"
    if has_official and not blocking:
        return "MEDIUM"
    return "LOW"


def card_summary(card: ProcedureCompletionCard) -> dict[str, Any]:
    """Riassunto compatto per liste/dashboard (senza payload completo)."""
    return {
        "id": card.id,
        "codice": card.codice,
        "denominazione": card.denominazione,
        "categoria": card.categoria,
        "status": card.status,
        "confidence": card.confidence,
        "riskLevel": card.risk_level,
        "gaps": len(card.gap_evidenza),
        "gapsBlocking": sum(1 for gap in card.gap_evidenza if str(gap.get("severita")) == "blocking"),
        "fontiUfficiali": len(card.fonti_ufficiali_o_tecniche),
        "citazioni": len(card.citazioni_verificabili),
        "templateSelezionato": str(card.template_selected.get("titolo") or ""),
        "generatedAt": card.generated_at,
    }


def empty_review() -> dict[str, Any]:
    return {"reviewer": "", "reviewed_at": "", "reason": "", "esito": ""}


__all__ = [
    "CARD_STATUSES",
    "CONFIDENCE_LEVELS",
    "RISK_LEVELS",
    "GAP_SEVERITIES",
    "SOURCE_TYPES",
    "COPYRIGHT_POLICIES",
    "MAX_PROFESSIONAL_EXCERPT_CHARS",
    "ProcedureCompletionRequest",
    "ProcedureCompletionCard",
    "ProcedureCompletionSource",
    "ProcedureCompletionCitation",
    "ProcedureCompletionGap",
    "ProcedureTemplateCandidate",
    "ProcedureCompletionValidationReport",
    "assign_confidence",
    "card_summary",
    "empty_review",
    "new_id",
    "now_iso",
]
