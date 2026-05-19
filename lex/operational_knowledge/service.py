"""Application service for deterministic operational Lex answers."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from .audit import OperationalAuditRecorder
from .models import OperationalAnswer, OperationalRoute, OperationalToolResult
from .permission_guard import resolve_query_context
from .query_router import OperationalQueryRouter
from .reasoner import LexStudioReasoner
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
        reasoner: LexStudioReasoner | None = None,
        audit: OperationalAuditRecorder | None = None,
    ) -> None:
        self.settings = settings or OperationalKnowledgeSettings.from_env()
        self.router = router or OperationalQueryRouter()
        self.tools = tools or OperationalKnowledgeTools()
        self.composer = composer or OperationalResponseComposer()
        self.reasoner = reasoner or LexStudioReasoner(registry=self.tools.registry)
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
        plan = self.reasoner.build_plan(question=question, route=route)
        if route.blocks_legal_action:
            answer = self.composer.compose(question=question, route=route, results=[], blocked_reason="legal_action_blocked")
            report = self.reasoner.verify(plan=plan, results=[])
            self.reasoner.apply(answer, report)
            answer.audit_event_id = self._audit(context, question, route, answer, outcome="blocked")
            return answer

        results = self._execute_route(route, context, question, metadata)
        answer = self.composer.compose(
            question=question,
            route=route,
            results=results,
            blocked_reason=_policy_blocked_reason(results),
        )
        report = self.reasoner.verify(plan=plan, results=results)
        self.reasoner.apply(answer, report)
        outcome = "ok" if any(result.ok for result in results) else "blocked"
        answer.audit_event_id = self._audit(context, question, route, answer, outcome=outcome)
        return answer

    def _execute_route(self, route: OperationalRoute, context, question: str, metadata: dict[str, Any]) -> list[OperationalToolResult]:
        entity_query = route.entity_query or question
        fascicolo_id = str(metadata.get("fascicolo_id") or metadata.get("pratica_id") or "").strip()
        cliente_id = str(metadata.get("cliente_id") or metadata.get("client_id") or "").strip()
        active_context = dict(metadata.get("active_context") or {}) if isinstance(metadata.get("active_context"), dict) else {}
        context_type = str(active_context.get("context_type") or metadata.get("context_type") or "").strip().lower()
        pec_id = str(active_context.get("pec_id") or metadata.get("pec_id") or metadata.get("email_id") or "").strip()

        if route.intent == "sources_overview":
            return [
                self.tools.search_legal_sources(entity_query or question, context, limit=3),
                self.tools.get_legal_intelligence_items(entity_query or question, context, limit=3),
            ]

        if route.intent == "studio_context_overview":
            return self._studio_context_overview_route(context, entity_query or question)

        if route.intent in {"client_situation", "client_fascicoli", "client_economic_summary"}:
            return self._client_route(route, context, entity_query, cliente_id=cliente_id)

        if route.intent == "soggetti_lookup":
            return self._soggetti_route(context, entity_query, fascicolo_id=fascicolo_id)

        if route.intent == "fascicolo_summary":
            return self._fascicolo_route(context, entity_query, fascicolo_id=fascicolo_id)

        if route.intent == "build_case_timeline":
            target = fascicolo_id or self._first_fascicolo_id(entity_query, context)
            if not target:
                return [self.tools.search_fascicoli(entity_query, context, limit=5)]
            return [
                self.tools.get_fascicolo(target, context),
                self.tools.get_documenti_fascicolo(target, context),
                self.tools.get_scadenze_by_fascicolo(target, context),
                self.tools.get_agenda_range(context, limit=30),
                self.tools.list_pec_messages(context, query=entity_query, limit=self.settings.max_results),
                self.tools.list_ordinary_email_messages(context, query=entity_query, limit=self.settings.max_results),
                self.tools.get_parcelle_by_fascicolo(target, context),
            ]

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
            lowered = question.lower()
            if "udienz" in lowered and any(token in lowered for token in ("ultim", "recent", "passat", "precedent")):
                return [self.tools.search_agenda("udienza", context, limit=30, latest=True)]
            if "udienz" in lowered:
                return [self.tools.search_agenda("udienza", context, limit=30)]
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
                    self.tools.get_pagamenti_status(context, limit=self.settings.max_results),
                ]
            return [
                self.tools.search_preventivi(entity_query, context, limit=self.settings.max_results),
                self.tools.search_conferimenti(entity_query, context, limit=self.settings.max_results),
                self.tools.get_pagamenti_status(context, limit=self.settings.max_results),
            ]

        if route.intent == "communications_lookup":
            return self._communications_route(
                context,
                route.entity_query,
                question,
                cliente_id=cliente_id,
                fascicolo_id=fascicolo_id,
                pec_id=pec_id,
                context_type=context_type,
            )

        if route.intent == "template_lookup":
            results = [
                self.tools.search_template_atti(entity_query or question, context, limit=self.settings.max_results),
                self.tools.get_editor_ai_status(context),
            ]
            if fascicolo_id:
                results.append(self.tools.get_fascicolo(fascicolo_id, context))
                results.append(self.tools.get_documenti_fascicolo(fascicolo_id, context))
            return results

        if route.intent == "unbilled_activity":
            if fascicolo_id:
                return [self.tools.get_attivita_by_fascicolo(fascicolo_id, context)]
            return [self.tools.get_attivita_by_cliente(entity_query, context)]

        if route.intent in {"legal_update_overview", "official_sources_lookup"}:
            results = [
                self.tools.get_legal_intelligence_items(entity_query or question, context, limit=6),
                self.tools.get_update_intelligence_items(entity_query or question, context, limit=6),
                self.tools.search_legal_sources(entity_query or question, context, limit=6),
            ]
            if _should_integrate_free_web_articles(question):
                web_query = _free_web_article_query(question, results)
                results.append(self.tools.search_free_public_web(web_query, context, limit=3))
            return results

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
        results.append(self.tools.get_pagamenti_status(context, cliente_id=cliente_id, limit=10))
        if route.intent == "client_economic_summary":
            results.append(self.tools.get_attivita_by_cliente(cliente_id, context))
        return results

    def _studio_context_overview_route(self, context, entity_query: str) -> list[OperationalToolResult]:
        query = entity_query or ""
        return [
            self.tools.search_clienti(query, context, limit=4),
            self.tools.search_fascicoli(query, context, limit=4),
            self.tools.get_agenda_range(context, start=date.today(), end=date.today() + timedelta(days=14), limit=8),
            self._all_scadenze(context),
            self.tools.list_pec_messages(context, query=query, limit=5),
            self.tools.list_ordinary_email_messages(context, query=query, limit=5),
            self.tools.search_preventivi(query, context, limit=4),
            self.tools.search_conferimenti(query, context, limit=4),
            self.tools.get_pagamenti_status(context, limit=4),
        ]

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

    def _soggetti_route(self, context, entity_query: str, *, fascicolo_id: str = "") -> list[OperationalToolResult]:
        results: list[OperationalToolResult] = []
        if fascicolo_id:
            results.append(self.tools.parti_by_fascicolo(fascicolo_id, context))
            if not entity_query:
                return results
        soggetti = self.tools.search_soggetti(entity_query, context, limit=self.settings.max_results)
        results.append(soggetti)
        if soggetti.ok and len(soggetti.data or []) == 1:
            soggetto_id = str((soggetti.data or [{}])[0].get("id") or "")
            if soggetto_id:
                results.append(self.tools.parti_by_soggetto(soggetto_id, context))
        return results

    def _communications_route(
        self,
        context,
        entity_query: str,
        question: str,
        *,
        cliente_id: str = "",
        fascicolo_id: str = "",
        pec_id: str = "",
        context_type: str = "",
    ) -> list[OperationalToolResult]:
        lowered = question.lower()
        wants_pec = "pec" in lowered
        wants_ordinary = "posta ordinaria" in lowered or "email ordinaria" in lowered or "smtp" in lowered or "imap" in lowered
        wants_mailbox = wants_pec or wants_ordinary or "email" in lowered or "posta" in lowered
        if pec_id and (wants_pec or context_type == "pec"):
            return [self.tools.get_pec_message(pec_id, context), self.tools.list_pec_attachments(pec_id, context)]
        if pec_id and (wants_ordinary or context_type == "email"):
            return [self.tools.get_ordinary_email_message(pec_id, context), self.tools.list_ordinary_email_attachments(pec_id, context)]
        if fascicolo_id:
            results = [self.tools.get_fascicolo(fascicolo_id, context), self.tools.get_messaggi_by_fascicolo(fascicolo_id, context)]
            if wants_pec:
                results.append(self.tools.list_pec_messages(context, query=entity_query, limit=self.settings.max_results))
            if wants_ordinary:
                results.append(self.tools.list_ordinary_email_messages(context, query=entity_query, limit=self.settings.max_results))
            return results
        if cliente_id:
            results = [self.tools.get_cliente_by_id(cliente_id, context), self.tools.get_messaggi_by_cliente(cliente_id, context)]
            if wants_pec:
                results.append(self.tools.list_pec_messages(context, query=entity_query, limit=self.settings.max_results))
            if wants_ordinary:
                results.append(self.tools.list_ordinary_email_messages(context, query=entity_query, limit=self.settings.max_results))
            return results
        if wants_mailbox and not ("cliente" in lowered or "fascicolo" in lowered or "pratica" in lowered):
            results: list[OperationalToolResult] = []
            if wants_pec or not wants_ordinary:
                results.append(self.tools.list_pec_messages(context, query=entity_query, limit=self.settings.max_results))
            if wants_ordinary or not wants_pec:
                results.append(self.tools.list_ordinary_email_messages(context, query=entity_query, limit=self.settings.max_results))
            return results
        if "fascicolo" in question.lower() or "pratica" in question.lower():
            fascicoli = self.tools.search_fascicoli(entity_query, context, limit=2)
            results = [fascicoli]
            if fascicoli.ok and len(fascicoli.data or []) == 1:
                target = str((fascicoli.data or [{}])[0].get("id") or "")
                results.append(self.tools.get_messaggi_by_fascicolo(target, context))
                if wants_pec:
                    results.append(self.tools.list_pec_messages(context, query=entity_query, limit=self.settings.max_results))
                if wants_ordinary:
                    results.append(self.tools.list_ordinary_email_messages(context, query=entity_query, limit=self.settings.max_results))
            return results
        clienti = self.tools.search_clienti(entity_query, context, limit=2)
        results = [clienti]
        if clienti.ok and len(clienti.data or []) == 1:
            target = str((clienti.data or [{}])[0].get("id") or "")
            results.append(self.tools.get_messaggi_by_cliente(target, context))
            if wants_pec:
                results.append(self.tools.list_pec_messages(context, query=entity_query, limit=self.settings.max_results))
            if wants_ordinary:
                results.append(self.tools.list_ordinary_email_messages(context, query=entity_query, limit=self.settings.max_results))
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


def _policy_blocked_reason(results: list[OperationalToolResult]) -> str:
    policy_reasons = {"authentication_required", "tenant_context_required", "tenant_mismatch", "missing_permission"}
    for result in results:
        if result.blocked_reason in policy_reasons:
            return result.blocked_reason
    return ""


def _should_integrate_free_web_articles(question: str) -> bool:
    text = str(question or "").lower()
    return any(
        token in text
        for token in (
            "art.",
            "artt",
            "articolo",
            "articoli",
            "norme",
            "riferimenti normativi",
        )
    )


def _free_web_article_query(question: str, results: list[OperationalToolResult]) -> str:
    refs = _article_refs_from_results(results)
    if refs:
        return "testo articoli " + " ".join(refs[:8])
    return str(question or "").strip()


def _article_refs_from_results(results: list[OperationalToolResult]) -> list[str]:
    text_parts: list[str] = []
    for result in results:
        rows = result.data if isinstance(result.data, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            text_parts.extend(
                str(row.get(key) or "")
                for key in ("title", "titolo", "excerpt", "summary", "content", "text", "context")
            )
    text = " ".join(part for part in text_parts if part).lower()
    refs: list[str] = []

    def _push(label: str) -> None:
        clean = " ".join(str(label or "").split()).strip()
        if clean and clean not in refs:
            refs.append(clean)

    for match in re.finditer(r"\bartt?\.?\s+([^.;]{1,80}?)\s+cod\.?\s+proc\.?\s+pen\.?", text, flags=re.I):
        for article in re.split(r"\s+e\s+|,|;", match.group(1)):
            number = " ".join(article.split()).strip(" .")
            if re.match(r"^\d", number):
                _push(f"art. {number} c.p.p.")
    for match in re.finditer(r"\bartt?\.?\s+([^.;]{1,80}?)\s+cod\.?\s+pen\.?", text, flags=re.I):
        for article in re.split(r"\s+e\s+|;", match.group(1)):
            number = " ".join(article.split()).strip(" .")
            if re.match(r"^\d", number):
                _push(f"art. {number} c.p.")
    for match in re.finditer(r"\bex\s+art\.?\s+(\d+(?:-[a-z]+)?)\s+cod\.?\s+proc\.?\s+pen\.?", text, flags=re.I):
        _push(f"art. {match.group(1)} c.p.p.")
    return refs
