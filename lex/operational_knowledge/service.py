"""Application service for deterministic operational Lex answers."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .audit import OperationalAuditRecorder
from .models import OperationalAnswer, OperationalRoute, OperationalToolResult
from .permission_guard import resolve_query_context
from .query_router import OperationalQueryRouter
from .response_composer import OperationalResponseComposer
from .serializers import serialize_generic
from .settings import OperationalKnowledgeSettings
from .tools import OperationalKnowledgeTools, current_week_range


class OperationalKnowledgeService:
    def __init__(
        self,
        *,
        settings: OperationalKnowledgeSettings | None = None,
        router: OperationalQueryRouter | None = None,
        tools: OperationalKnowledgeTools | None = None,
        composer: OperationalResponseComposer | None = None,
        audit: OperationalAuditRecorder | None = None,
    ) -> None:
        self.settings = settings or OperationalKnowledgeSettings.from_env()
        self.router = router or OperationalQueryRouter()
        self.tools = tools or OperationalKnowledgeTools()
        self.composer = composer or OperationalResponseComposer()
        self.audit = audit or OperationalAuditRecorder(settings=self.settings)

    def answer(
        self,
        *,
        question: str,
        user: Any = None,
        studio: Any = None,
        tenant_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> OperationalAnswer | None:
        if not self.settings.enabled:
            return None

        metadata = dict(metadata or {})
        route = self.router.route(question, metadata=metadata)
        if route is None:
            return None

        context = resolve_query_context(user=user, studio=studio, tenant_id=tenant_id)
        if route.blocks_legal_action:
            answer = self.composer.compose(question=question, route=route, results=[], blocked_reason="legal_action_blocked")
            answer.audit_event_id = self._audit(context, question, route, answer, outcome="blocked")
            return answer

        results = self._execute_route(route, context, question, metadata)
        answer = self.composer.compose(question=question, route=route, results=results)
        outcome = "ok" if any(result.ok for result in results) else "blocked"
        answer.audit_event_id = self._audit(context, question, route, answer, outcome=outcome)
        return answer

    def _execute_route(self, route: OperationalRoute, context, question: str, metadata: dict[str, Any]) -> list[OperationalToolResult]:
        entity_query = route.entity_query or question
        fascicolo_id = str(metadata.get("fascicolo_id") or metadata.get("pratica_id") or "").strip()
        cliente_id = str(metadata.get("cliente_id") or metadata.get("client_id") or "").strip()

        if route.intent == "sources_overview":
            return [
                self.tools.search_legal_sources(entity_query or question, context, limit=3),
                self.tools.get_legal_intelligence_items(entity_query or question, context, limit=3),
            ]

        if route.intent in {"client_situation", "client_fascicoli", "client_economic_summary"}:
            return self._client_route(route, context, entity_query, cliente_id=cliente_id)

        if route.intent == "soggetti_lookup":
            return [self.tools.search_soggetti(entity_query, context, limit=self.settings.max_results)]

        if route.intent == "fascicolo_summary":
            return self._fascicolo_route(context, entity_query, fascicolo_id=fascicolo_id)

        if route.intent == "documenti_fascicolo":
            target = fascicolo_id or self._first_fascicolo_id(entity_query, context)
            if not target:
                return [self.tools.search_fascicoli(entity_query, context, limit=5)]
            if "riassumi" in question.lower() or "cerca" in question.lower():
                return [
                    self.tools.get_fascicolo(target, context),
                    self.tools.search_documenti_fascicolo(target, entity_query or question, context, limit=self.settings.max_results),
                ]
            return [self.tools.get_fascicolo(target, context), self.tools.get_documenti_fascicolo(target, context)]

        if route.intent == "deadlines_overview":
            if fascicolo_id:
                return [
                    self.tools.get_scadenze_by_fascicolo(fascicolo_id, context),
                    self.tools.get_agenda_range(context, start=date.today(), end=date.today() + timedelta(days=14), limit=20),
                ]
            if "cliente" in question.lower():
                if cliente_id:
                    return [
                        self.tools.get_cliente_by_id(cliente_id, context),
                        self.tools.get_scadenze_by_cliente(cliente_id, context),
                        self.tools.get_agenda_range(context, cliente_id=cliente_id, limit=20),
                    ]
                clienti = self.tools.search_clienti(entity_query, context, limit=5)
                results = [clienti]
                if clienti.ok and len(clienti.data or []) == 1:
                    cliente_id = str((clienti.data or [{}])[0].get("id") or "")
                    results.append(self.tools.get_scadenze_by_cliente(cliente_id, context))
                    results.append(self.tools.get_agenda_range(context, cliente_id=cliente_id, limit=20))
                return results
            start, end = current_week_range() if "settimana" in question.lower() else (date.today(), date.today() + timedelta(days=14))
            return [
                self.tools.get_agenda_range(context, start=start, end=end, limit=30),
                self._all_scadenze(context),
            ]

        if route.intent == "agenda_overview":
            start, end = current_week_range() if "settimana" in question.lower() else (date.today(), date.today() + timedelta(days=14))
            return [self.tools.get_agenda_range(context, start=start, end=end, limit=30)]

        if route.intent == "notifications_lookup":
            return [self.tools.get_notifiche_utente(context, limit=self.settings.max_results)]

        if route.intent == "preventivo_summary":
            return [
                self.tools.search_preventivi(entity_query, context, limit=self.settings.max_results),
                self.tools.search_conferimenti(entity_query, context, limit=self.settings.max_results),
            ]

        if route.intent == "conferimento_summary":
            return [
                self.tools.search_conferimenti(entity_query, context, limit=self.settings.max_results),
                self.tools.search_preventivi(entity_query, context, limit=self.settings.max_results),
            ]

        if route.intent == "tariffario_lookup":
            return [self.tools.get_tariffario_result(context)]

        if route.intent == "billing_summary":
            if "cliente" in question.lower():
                return self._client_route(route, context, entity_query, cliente_id=cliente_id)
            if fascicolo_id:
                return [
                    self.tools.get_parcelle_by_fascicolo(fascicolo_id, context),
                    self.tools.get_attivita_by_fascicolo(fascicolo_id, context),
                ]
            return [
                self.tools.search_preventivi(entity_query, context, limit=self.settings.max_results),
                self.tools.search_conferimenti(entity_query, context, limit=self.settings.max_results),
            ]

        if route.intent == "communications_lookup":
            return self._communications_route(context, entity_query, question, cliente_id=cliente_id, fascicolo_id=fascicolo_id)

        if route.intent == "template_lookup":
            return [self.tools.search_template_atti(entity_query or question, context, limit=self.settings.max_results)]

        if route.intent == "unbilled_activity":
            if fascicolo_id:
                return [self.tools.get_attivita_by_fascicolo(fascicolo_id, context)]
            return [self.tools.get_attivita_by_cliente(entity_query, context)]

        if route.intent in {"legal_update_overview", "official_sources_lookup"}:
            return [
                self.tools.get_legal_intelligence_items(entity_query or question, context, limit=6),
                self.tools.get_update_intelligence_items(entity_query or question, context, limit=6),
                self.tools.search_legal_sources(entity_query or question, context, limit=6),
            ]

        return []

    def _client_route(
        self,
        route: OperationalRoute,
        context,
        entity_query: str,
        *,
        cliente_id: str = "",
    ) -> list[OperationalToolResult]:
        clienti = (
            self.tools.get_cliente_by_id(cliente_id, context)
            if cliente_id
            else self.tools.search_clienti(entity_query, context, limit=self.settings.max_results)
        )
        results: list[OperationalToolResult] = [clienti]
        if not clienti.ok or len(clienti.data or []) != 1:
            return results
        cliente_id = str((clienti.data or [{}])[0].get("id") or "")
        if not cliente_id:
            return results
        results.append(self.tools.fascicoli_by_cliente(cliente_id, context))
        if route.intent == "client_fascicoli":
            return results
        results.append(self.tools.get_scadenze_by_cliente(cliente_id, context))
        results.append(self.tools.get_agenda_range(context, cliente_id=cliente_id, limit=20))
        results.append(self.tools.search_preventivi(cliente_id, context, limit=10))
        results.append(self.tools.search_conferimenti(cliente_id, context, limit=10))
        results.append(self.tools.get_parcelle_by_cliente(cliente_id, context))
        if route.intent == "client_economic_summary":
            results.append(self.tools.get_attivita_by_cliente(cliente_id, context))
        return results

    def _fascicolo_route(self, context, entity_query: str, *, fascicolo_id: str = "") -> list[OperationalToolResult]:
        target = fascicolo_id or self._first_fascicolo_id(entity_query, context)
        if not target:
            return [self.tools.search_fascicoli(entity_query, context, limit=self.settings.max_results)]
        return [
            self.tools.get_fascicolo(target, context),
            self.tools.get_documenti_fascicolo(target, context),
            self.tools.get_scadenze_by_fascicolo(target, context),
            self.tools.get_parcelle_by_fascicolo(target, context),
            self.tools.get_attivita_by_fascicolo(target, context),
        ]

    def _communications_route(
        self,
        context,
        entity_query: str,
        question: str,
        *,
        cliente_id: str = "",
        fascicolo_id: str = "",
    ) -> list[OperationalToolResult]:
        if fascicolo_id:
            return [self.tools.get_fascicolo(fascicolo_id, context), self.tools.get_messaggi_by_fascicolo(fascicolo_id, context)]
        if cliente_id:
            return [self.tools.get_cliente_by_id(cliente_id, context), self.tools.get_messaggi_by_cliente(cliente_id, context)]
        if "fascicolo" in question.lower() or "pratica" in question.lower():
            fascicoli = self.tools.search_fascicoli(entity_query, context, limit=2)
            results = [fascicoli]
            if fascicoli.ok and len(fascicoli.data or []) == 1:
                target = str((fascicoli.data or [{}])[0].get("id") or "")
                results.append(self.tools.get_messaggi_by_fascicolo(target, context))
            return results
        clienti = self.tools.search_clienti(entity_query, context, limit=2)
        results = [clienti]
        if clienti.ok and len(clienti.data or []) == 1:
            target = str((clienti.data or [{}])[0].get("id") or "")
            results.append(self.tools.get_messaggi_by_cliente(target, context))
        return results

    def _first_fascicolo_id(self, entity_query: str, context) -> str:
        result = self.tools.search_fascicoli(entity_query, context, limit=2)
        if result.ok and len(result.data or []) == 1:
            return str((result.data or [{}])[0].get("id") or "")
        return ""

    def _all_scadenze(self, context) -> OperationalToolResult:
        source_id = "scadenziario"
        decision = self.tools._decision(source_id, context)
        if not decision.allowed:
            return self.tools._blocked(source_id, decision)
        manager = self.tools._safe_manager(source_id, lambda: self.tools._manager(source_id, "get_scadenziario"))
        if manager is None:
            return self.tools._unavailable(source_id, "Scadenziario non disponibile.")
        try:
            rows = list(manager.tutte(solo_aperte=True))[: self.settings.max_results]
        except Exception as exc:
            return self.tools._unavailable(source_id, f"Scadenziario non interrogabile: {exc}")
        return self.tools._rows_result(source_id, context, rows, serialize_generic, "scadenza", decision)

    def _audit(self, context, question: str, route: OperationalRoute, answer: OperationalAnswer, *, outcome: str) -> str:
        return self.audit.record(
            context=context,
            question=question,
            route=route,
            sources=[source.source_id for source in answer.sources],
            objects=[obj.to_dict() for obj in answer.objects],
            outcome=outcome,
            blocked_reason=answer.blocked_reason,
        )
