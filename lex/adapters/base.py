"""Helpers per trasformare il contesto Lex in facts ed eventi strutturati."""

from __future__ import annotations

from typing import Any

from lex.contracts import ContextRequest, LexEvent, LexFact, ModuleResultPack


def as_mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set)):
        return list(value)
    return []


def compact_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [], {}, ())
    }


def metadata_for_module(request, module: str) -> dict[str, Any]:
    metadata = dict(getattr(request, "metadata", {}) or {})
    direct = metadata.get(module)
    if isinstance(direct, dict):
        return dict(direct)
    module_payloads = metadata.get("module_payloads")
    if isinstance(module_payloads, dict) and isinstance(module_payloads.get(module), dict):
        return dict(module_payloads[module])
    lex_inputs = metadata.get("lex_module_inputs")
    if isinstance(lex_inputs, dict) and isinstance(lex_inputs.get(module), dict):
        return dict(lex_inputs[module])
    return {}


def preview_items(items: list[Any], *, limit: int = 3) -> list[str]:
    previews: list[str] = []
    for item in list(items or [])[:limit]:
        if isinstance(item, dict):
            label = item.get("titolo") or item.get("title") or item.get("nome") or item.get("name") or item.get("id")
        else:
            label = item
        text = str(label or "").strip()
        if text:
            previews.append(text)
    return previews


def make_fact(module: str, fact_type: str, value: Any, *, entity_id: str = "", kind: str = "fatto_certo", source: str = "", metadata: dict[str, Any] | None = None) -> LexFact:
    return LexFact(
        module=module,
        fact_type=fact_type,
        value=value,
        entity_id=entity_id,
        kind=kind,
        source=source or module,
        metadata=dict(metadata or {}),
    )


def make_event(module: str, event_type: str, *, entity_id: str = "", source: str = "", payload: dict[str, Any] | None = None, has_errors: bool = False) -> LexEvent:
    return LexEvent(
        module=module,
        event_type=event_type,
        entity_id=entity_id,
        source=source or module,
        payload=dict(payload or {}),
        has_errors=bool(has_errors),
    )


class BaseLexAdapter:
    module = "cabina"
    sections: tuple[str, ...] = ()

    def should_include(self, request, workflow: str, context: dict[str, Any], evidence: dict[str, Any]) -> bool:
        return True

    def build_context(self, request, workflow: str, context: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        payload = {section: context.get(section) for section in self.sections if context.get(section) not in (None, "", [], {})}
        metadata = metadata_for_module(request, self.module)
        if metadata:
            payload["input_metadata"] = metadata
        return compact_mapping(payload)

    def collect_facts(self, request, workflow: str, context: dict[str, Any], evidence: dict[str, Any]) -> list[LexFact]:
        return []

    def collect_events(self, request, workflow: str, context: dict[str, Any], evidence: dict[str, Any]) -> list[LexEvent]:
        return []

    def collect_warnings(self, request, workflow: str, context: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
        return []

    def build_pack(self, request, workflow: str, context: dict[str, Any], evidence: dict[str, Any]) -> ModuleResultPack:
        pack_context = self.build_context(request, workflow, context, evidence)
        facts = list(self.collect_facts(request, workflow, context, evidence))
        events = list(self.collect_events(request, workflow, context, evidence))
        warnings = [str(item).strip() for item in self.collect_warnings(request, workflow, context, evidence) if str(item).strip()]
        status = "ok"
        if not pack_context and not facts and not events:
            status = "empty"
        elif warnings:
            status = "warning"
        return ModuleResultPack(
            module=self.module,
            status=status,
            context_request=ContextRequest(
                module=self.module,
                workflow=workflow,
                query=str(getattr(request, "query", "") or ""),
                fascicolo_id=str(getattr(request, "fascicolo_id", "") or ""),
                document_id=str(getattr(request, "document_id", "") or ""),
                requested_sections=list(self.sections),
                metadata={
                    "tenant_id": str(getattr(request, "tenant_id", "") or ""),
                    "session_id": str(getattr(request, "session_id", "") or ""),
                },
            ),
            facts=facts,
            events=events,
            context=pack_context,
            warnings=warnings,
            metadata={"adapter": self.__class__.__name__},
        )