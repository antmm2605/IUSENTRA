"""Governed planning and source verification for Lex studio answers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .models import OperationalAnswer, OperationalRoute, OperationalToolResult
from .source_registry import OperationalSourceRegistry, build_default_registry


@dataclass(frozen=True, slots=True)
class StudioReasoningStep:
    step_id: str
    phase: str
    objective: str
    source_ids: tuple[str, ...] = ()
    status: str = "pending"
    evidence_count: int = 0
    verified: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StudioReasoningPlan:
    name: str
    mode: str
    question: str
    route_id: str
    intent: str
    required_sources: tuple[str, ...]
    steps: tuple[StudioReasoningStep, ...]
    answer_strategy: str
    confidence_floor: float = 0.55

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [step.to_dict() for step in self.steps]
        return payload


@dataclass(frozen=True, slots=True)
class StudioReasoningReport:
    plan: StudioReasoningPlan
    verified_internal_sources: tuple[str, ...] = ()
    excluded_sources: tuple[str, ...] = ()
    missing_sources: tuple[str, ...] = ()
    coverage_gaps: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence_count: int = 0
    object_count: int = 0
    object_links_count: int = 0
    evidence_sufficient: bool = False
    confidence_adjustment: float = 0.0
    entity_map: dict[str, Any] = field(default_factory=dict)
    fascicolo_timeline: list[dict[str, Any]] = field(default_factory=list)
    steps: tuple[StudioReasoningStep, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.plan.name,
            "mode": self.plan.mode,
            "plan": self.plan.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
            "verification": {
                "verified_internal_sources": list(self.verified_internal_sources),
                "excluded_sources": list(self.excluded_sources),
                "missing_sources": list(self.missing_sources),
                "coverage_gaps": list(self.coverage_gaps),
                "warnings": list(self.warnings),
                "evidence_count": self.evidence_count,
                "object_count": self.object_count,
                "object_links_count": self.object_links_count,
                "evidence_sufficient": self.evidence_sufficient,
                "confidence_adjustment": self.confidence_adjustment,
            },
            "entity_map": self.entity_map,
            "fascicolo_timeline": list(self.fascicolo_timeline),
            "rag_policy": {
                "tenant_aware": True,
                "internal_sources_only": True,
                "excludes_public_legal_sources": True,
                "no_legacy_aggregator": True,
                "no_raw_prompt_context": True,
            },
            "colleague_policy": {
                "conversation_style": "confronto professionale tra colleghi",
                "lawyer_position_is_default": True,
                "contradict_lawyer_min_confidence": 0.99,
                "contradict_lawyer_requires_verified_primary_source": True,
                "jurisprudence_practice_mode": "canary_web_governato_no_publish",
                "jurisprudence_practice_sources": [
                    "Cassazione",
                    "Corte costituzionale",
                    "Giustizia amministrativa",
                    "fonti ufficiali o archiviate",
                ],
                "jurisprudence_practice_publishes_without_review": False,
            },
        }


class LexStudioReasoner:
    """Builds a user-safe operational plan and verifies retrieved studio evidence."""

    def __init__(self, registry: OperationalSourceRegistry | None = None) -> None:
        self.registry = registry or build_default_registry()

    def build_plan(self, *, question: str, route: OperationalRoute) -> StudioReasoningPlan:
        required_sources = tuple(
            source_id
            for source_id in route.source_ids
            if self._is_internal_studio_source(source_id)
        )
        steps = (
            StudioReasoningStep(
                step_id="classifica",
                phase="classificazione",
                objective="Inquadrare la richiesta dell'avvocato e scegliere il workflow operativo Lex.",
                status="completed",
                verified=True,
                note=route.reason or route.intent,
            ),
            StudioReasoningStep(
                step_id="recupera_fonti_interne",
                phase="retrieval",
                objective="Interrogare solo sorgenti interne tenant-aware e autorizzate.",
                source_ids=required_sources,
            ),
            StudioReasoningStep(
                step_id="verifica_fonti_interne",
                phase="verifica",
                objective="Controllare che ogni evidenza provenga da una sorgente interna governata.",
                source_ids=required_sources,
            ),
            StudioReasoningStep(
                step_id="compone_risposta",
                phase="risposta",
                objective="Restituire fatti, lacune, limiti e oggetti apribili senza inventare dati.",
                source_ids=required_sources,
            ),
        )
        return StudioReasoningPlan(
            name="Lex Studio Reasoner",
            mode="llm_rag_governato",
            question=str(question or "").strip(),
            route_id=route.route_id,
            intent=route.intent,
            required_sources=required_sources,
            steps=steps,
            answer_strategy=_strategy_for_intent(route.intent),
        )

    def verify(self, *, plan: StudioReasoningPlan, results: list[OperationalToolResult]) -> StudioReasoningReport:
        verified: list[str] = []
        excluded: list[str] = []
        gaps: list[str] = []
        warnings: list[str] = []
        evidence_count = 0
        object_count = 0
        object_links_count = 0

        for result in results:
            source_id = str(result.source_id or "").strip()
            if self._is_internal_studio_source(source_id):
                if result.ok and _result_has_evidence(result):
                    _append_unique(verified, source_id)
                    evidence_count += _result_evidence_count(result)
                    object_count += len(result.objects or [])
                    object_links_count += sum(1 for obj in result.objects or [] if str(obj.action_url or "").strip())
                elif result.coverage_gaps:
                    gaps.extend(str(gap) for gap in result.coverage_gaps if str(gap or "").strip())
            else:
                _append_unique(excluded, source_id)
            warnings.extend(str(warning) for warning in result.warnings if str(warning or "").strip())

        missing = [source_id for source_id in plan.required_sources if source_id not in verified]
        confidence_adjustment = 0.0
        if missing:
            confidence_adjustment -= min(0.18, len(missing) * 0.03)
        if gaps:
            confidence_adjustment -= min(0.12, len(gaps) * 0.02)

        evidence_sufficient = bool(verified) and evidence_count > 0
        entity_map = _build_entity_map(results)
        fascicolo_timeline = _build_fascicolo_timeline(results)
        completed_steps = self._completed_steps(
            plan=plan,
            verified=tuple(verified),
            missing=tuple(missing),
            evidence_count=evidence_count,
            evidence_sufficient=evidence_sufficient,
        )
        return StudioReasoningReport(
            plan=plan,
            verified_internal_sources=tuple(verified),
            excluded_sources=tuple(excluded),
            missing_sources=tuple(missing),
            coverage_gaps=tuple(_unique(gaps)),
            warnings=tuple(_unique(warnings)),
            evidence_count=evidence_count,
            object_count=object_count,
            object_links_count=object_links_count,
            evidence_sufficient=evidence_sufficient,
            confidence_adjustment=round(confidence_adjustment, 4),
            entity_map=entity_map,
            fascicolo_timeline=fascicolo_timeline,
            steps=completed_steps,
        )

    def apply(self, answer: OperationalAnswer, report: StudioReasoningReport) -> OperationalAnswer:
        answer.metadata = dict(answer.metadata or {})
        answer.metadata["studio_reasoner"] = report.to_dict()
        answer.metadata["reasoner_mode"] = report.plan.mode
        answer.metadata["rag_governato"] = True
        if report.confidence_adjustment and answer.confidence:
            answer.confidence = round(max(0.1, min(0.92, answer.confidence + report.confidence_adjustment)), 4)
        return answer

    def _completed_steps(
        self,
        *,
        plan: StudioReasoningPlan,
        verified: tuple[str, ...],
        missing: tuple[str, ...],
        evidence_count: int,
        evidence_sufficient: bool,
    ) -> tuple[StudioReasoningStep, ...]:
        completed: list[StudioReasoningStep] = []
        for step in plan.steps:
            if step.step_id == "recupera_fonti_interne":
                completed.append(
                    StudioReasoningStep(
                        step_id=step.step_id,
                        phase=step.phase,
                        objective=step.objective,
                        source_ids=step.source_ids,
                        status="completed" if verified else "partial",
                        evidence_count=evidence_count,
                        verified=bool(verified),
                        note="Fonti interne recuperate: " + ", ".join(verified) if verified else "Nessuna evidenza interna recuperata.",
                    )
                )
                continue
            if step.step_id == "verifica_fonti_interne":
                completed.append(
                    StudioReasoningStep(
                        step_id=step.step_id,
                        phase=step.phase,
                        objective=step.objective,
                        source_ids=step.source_ids,
                        status="completed" if evidence_sufficient else "partial",
                        evidence_count=evidence_count,
                        verified=evidence_sufficient,
                        note="Fonti mancanti: " + ", ".join(missing) if missing else "Evidenze interne coerenti con il piano.",
                    )
                )
                continue
            if step.step_id == "compone_risposta":
                completed.append(
                    StudioReasoningStep(
                        step_id=step.step_id,
                        phase=step.phase,
                        objective=step.objective,
                        source_ids=step.source_ids,
                        status="completed",
                        evidence_count=evidence_count,
                        verified=evidence_sufficient,
                        note=plan.answer_strategy,
                    )
                )
                continue
            completed.append(step)
        return tuple(completed)

    def _is_internal_studio_source(self, source_id: str) -> bool:
        source = self.registry.get(source_id)
        if source is None:
            return False
        return bool(source.internal and not source.official_public_source and source.category != "fonti_pubbliche")


def _strategy_for_intent(intent: str) -> str:
    if intent == "communications_lookup":
        return "Risposta su PEC/email/messaggi con data, mittente, allegati e link operativi quando disponibili."
    if intent in {"fascicolo_summary", "documenti_fascicolo"}:
        return "Sintesi fascicolo con inventario documentale, scadenze, agenda e limiti espliciti."
    if intent == "studio_context_overview":
        return "Panoramica del database studio con fonti legali pubbliche escluse."
    if intent in {"client_situation", "client_fascicoli", "client_economic_summary"}:
        return "Scheda cliente basata su anagrafica, fascicoli, scadenze e dati economici autorizzati."
    return "Risposta operativa basata solo su evidenze interne verificate e lacune dichiarate."


def _result_has_evidence(result: OperationalToolResult) -> bool:
    if isinstance(result.data, list):
        return bool(result.data)
    return bool(result.data or result.sources or result.objects)


def _result_evidence_count(result: OperationalToolResult) -> int:
    if isinstance(result.data, list):
        return len(result.data)
    if result.data:
        return 1
    return len(result.sources or [])


def _build_entity_map(results: list[OperationalToolResult]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    node_keys: set[tuple[str, str]] = set()
    relation_keys: set[tuple[str, str, str]] = set()

    def add_node(node_type: str, node_id: str, label: str, source_id: str, action_url: str = "") -> None:
        key = (node_type, node_id)
        if not node_type or not node_id or key in node_keys:
            return
        node_keys.add(key)
        nodes.append(
            {
                "type": node_type,
                "id": node_id,
                "label": label or node_id,
                "source_id": source_id,
                "action_url": action_url,
            }
        )

    def add_relation(from_key: str, to_key: str, label: str) -> None:
        key = (from_key, to_key, label)
        if not from_key or not to_key or key in relation_keys:
            return
        relation_keys.add(key)
        relations.append({"from": from_key, "to": to_key, "label": label})

    for result in results:
        if not result.ok:
            continue
        for row in _result_rows(result):
            node_type = _node_type(result.source_id, row)
            node_id = _row_id(row)
            if not node_id:
                continue
            add_node(node_type, node_id, _row_label(row), result.source_id, _clean(row.get("action_url")))
            current_key = f"{node_type}:{node_id}"
            cliente_id = _clean(row.get("id_cliente") or row.get("cliente_id"))
            if cliente_id and node_type != "cliente":
                add_node("cliente", cliente_id, _clean(row.get("nome_cliente")) or cliente_id, "clienti")
                add_relation(f"cliente:{cliente_id}", current_key, "collegato")
            fascicolo_id = _clean(row.get("id_fascicolo") or row.get("fascicolo_id") or row.get("id_pratica"))
            if fascicolo_id and node_type != "fascicolo":
                add_node("fascicolo", fascicolo_id, fascicolo_id, "fascicoli", f"/fascicoli/{fascicolo_id}")
                add_relation(f"fascicolo:{fascicolo_id}", current_key, "contiene")
            soggetto_id = _clean(row.get("id_soggetto") or row.get("soggetto_id"))
            if soggetto_id and node_type != "soggetto":
                add_node("soggetto", soggetto_id, _clean(row.get("nome_completo")) or soggetto_id, "soggetti")
                add_relation(current_key, f"soggetto:{soggetto_id}", "riguarda")

    return {"nodes": nodes[:80], "relations": relations[:120]}


def _build_fascicolo_timeline(results: list[OperationalToolResult]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for result in results:
        if not result.ok:
            continue
        for row in _result_rows(result):
            when = _first_date(row)
            if not when:
                continue
            events.append(
                {
                    "date": when,
                    "type": _timeline_type(result.source_id),
                    "source_id": result.source_id,
                    "object_id": _row_id(row),
                    "label": _row_label(row),
                    "action_url": _clean(row.get("action_url")),
                    "fascicolo_id": _clean(row.get("id_fascicolo") or row.get("fascicolo_id") or row.get("id_pratica")),
                }
            )
    return sorted(events, key=lambda item: item["date"])[:80]


def _result_rows(result: OperationalToolResult) -> list[dict[str, Any]]:
    if isinstance(result.data, list):
        return [dict(item) for item in result.data if isinstance(item, dict)]
    if isinstance(result.data, dict):
        return [dict(result.data)]
    return []


def _node_type(source_id: str, row: dict[str, Any]) -> str:
    if source_id == "clienti":
        return "cliente"
    if source_id == "fascicoli":
        return "fascicolo"
    if source_id == "soggetti":
        return "parte" if _clean(row.get("record_kind")) == "parte" else "soggetto"
    if source_id == "documenti_fascicolo":
        return "documento"
    if source_id in {"email_pec", "email_ordinaria"}:
        return "email"
    if source_id == "messaggi":
        return "messaggio"
    if source_id == "scadenziario":
        return "scadenza"
    if source_id == "agenda":
        return "agenda"
    if source_id == "preventivi":
        return "preventivo"
    if source_id == "conferimenti":
        return "conferimento"
    if source_id == "fatturazione":
        return "parcella"
    return source_id


def _timeline_type(source_id: str) -> str:
    return {
        "fascicoli": "fascicolo",
        "documenti_fascicolo": "documento",
        "scadenziario": "scadenza",
        "agenda": "agenda",
        "email_pec": "pec",
        "email_ordinaria": "email",
        "messaggi": "messaggio",
        "fatturazione": "economico",
        "preventivi": "preventivo",
        "conferimenti": "conferimento",
    }.get(source_id, source_id)


def _row_id(row: dict[str, Any]) -> str:
    return _clean(row.get("id") or row.get("numero") or row.get("number") or row.get("source_id"))


def _row_label(row: dict[str, Any]) -> str:
    for key in ("nome_completo", "titolo", "title", "oggetto", "numero", "number", "nome", "name", "ragione_sociale", "id"):
        value = _clean(row.get(key))
        if value:
            return value
    return "Elemento"


def _first_date(row: dict[str, Any]) -> str:
    for key in (
        "data",
        "data_ora",
        "data_scadenza",
        "data_apertura",
        "data_caricamento",
        "ricevuta_il",
        "inviato_il",
        "creato_il",
        "modificato_il",
    ):
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _append_unique(items: list[str], value: str) -> None:
    clean = str(value or "").strip()
    if clean and clean not in items:
        items.append(clean)


def _unique(items: list[str]) -> list[str]:
    unique_items: list[str] = []
    for item in items:
        _append_unique(unique_items, item)
    return unique_items
