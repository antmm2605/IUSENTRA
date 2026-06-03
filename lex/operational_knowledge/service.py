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
from .serializers import clean_spaces, serialize_generic
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
        question_for_route, metadata = _apply_conversation_followup(question, metadata)
        route = self.router.route(question_for_route, metadata=metadata)
        if route is None:
            return None

        context = resolve_query_context(user=user, studio=studio, tenant_id=tenant_id)
        plan = self.reasoner.build_plan(question=question_for_route, route=route)
        if route.blocks_legal_action:
            answer = self.composer.compose(question=question_for_route, route=route, results=[], blocked_reason="legal_action_blocked")
            report = self.reasoner.verify(plan=plan, results=[])
            self.reasoner.apply(answer, report)
            answer.audit_event_id = self._audit(context, question, route, answer, outcome="blocked")
            return answer

        results = self._execute_route(route, context, question_for_route, metadata)
        answer = self.composer.compose(
            question=question_for_route,
            route=route,
            results=results,
            blocked_reason=_policy_blocked_reason(results),
        )
        answer.metadata["user_question"] = question
        if question_for_route != question:
            answer.metadata["conversation_effective_question"] = question_for_route
        report = self.reasoner.verify(plan=plan, results=results)
        self.reasoner.apply(answer, report)
        outcome = "ok" if any(result.ok for result in results) else "blocked"
        answer.audit_event_id = self._audit(context, question, route, answer, outcome=outcome)
        return answer

    def _execute_route(self, route: OperationalRoute, context, question: str, metadata: dict[str, Any]) -> list[OperationalToolResult]:
        entity_query = route.entity_query
        active_context = dict(metadata.get("active_context") or {}) if isinstance(metadata.get("active_context"), dict) else {}
        fascicolo_id = str(
            metadata.get("fascicolo_id")
            or metadata.get("pratica_id")
            or active_context.get("case_id")
            or active_context.get("linked_case_id")
            or ""
        ).strip()
        cliente_id = str(
            metadata.get("cliente_id")
            or metadata.get("client_id")
            or active_context.get("client_id")
            or active_context.get("linked_client_id")
            or ""
        ).strip()
        context_type = str(active_context.get("context_type") or metadata.get("context_type") or "").strip().lower()
        pec_id = str(active_context.get("pec_id") or metadata.get("pec_id") or metadata.get("email_id") or "").strip()

        if route.intent == "sources_overview":
            return [
                self.tools.search_legal_sources(entity_query or question, context, limit=3),
                self.tools.get_legal_intelligence_items(entity_query or question, context, limit=3),
            ]

        if route.intent == "studio_context_overview":
            return self._studio_context_overview_route(context, entity_query)

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

        if route.intent in {"communications_lookup", "draft_communication"}:
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
        query = "" if _is_generic_studio_overview_query(entity_query) else (entity_query or "")
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
        attachment_act_lookup = _looks_like_communication_attachment_question(question)
        wants_pec = "pec" in lowered or attachment_act_lookup
        wants_ordinary = "posta ordinaria" in lowered or "email ordinaria" in lowered or "smtp" in lowered or "imap" in lowered
        wants_mailbox = attachment_act_lookup or wants_pec or wants_ordinary or "email" in lowered or "posta" in lowered
        wants_audit = attachment_act_lookup or _wants_pec_audit(question)
        mail_query = "" if _should_ignore_mailbox_text_filter(question, entity_query, has_scope=bool(cliente_id or fascicolo_id or pec_id)) else entity_query
        if pec_id and (wants_pec or context_type == "pec"):
            results = [self.tools.get_pec_message(pec_id, context), self.tools.list_pec_attachments(pec_id, context)]
            if wants_audit:
                results.append(self.tools.get_pec_audit_for_email(pec_id, context))
            return results
        if pec_id and (wants_ordinary or context_type == "email"):
            return [self.tools.get_ordinary_email_message(pec_id, context), self.tools.list_ordinary_email_attachments(pec_id, context)]
        if fascicolo_id:
            fascicolo = self.tools.get_fascicolo(fascicolo_id, context)
            results = [fascicolo, self.tools.get_messaggi_by_fascicolo(fascicolo_id, context)]
            if not fascicolo.ok:
                return results
            if wants_pec:
                results.append(
                    _scope_communication_result(
                        self.tools.list_pec_messages(context, query=mail_query, limit=self.settings.max_results),
                        fascicolo_id=fascicolo_id,
                    )
                )
                if wants_audit:
                    results.append(self.tools.list_pec_audit_messages(context, query=mail_query, limit=self.settings.max_results))
            if wants_ordinary:
                results.append(
                    _scope_communication_result(
                        self.tools.list_ordinary_email_messages(context, query=mail_query, limit=self.settings.max_results),
                        fascicolo_id=fascicolo_id,
                    )
                )
            return results
        if cliente_id:
            cliente = self.tools.get_cliente_by_id(cliente_id, context)
            results = [cliente, self.tools.get_messaggi_by_cliente(cliente_id, context)]
            if not cliente.ok:
                return results
            if wants_pec:
                results.append(
                    _scope_communication_result(
                        self.tools.list_pec_messages(context, query=mail_query, limit=self.settings.max_results),
                        cliente_id=cliente_id,
                    )
                )
                if wants_audit:
                    results.append(self.tools.list_pec_audit_messages(context, query=mail_query, limit=self.settings.max_results))
            if wants_ordinary:
                results.append(
                    _scope_communication_result(
                        self.tools.list_ordinary_email_messages(context, query=mail_query, limit=self.settings.max_results),
                        cliente_id=cliente_id,
                    )
                )
            return results
        if wants_mailbox and not ("cliente" in lowered or "fascicolo" in lowered or "pratica" in lowered):
            results: list[OperationalToolResult] = []
            if wants_pec or not wants_ordinary:
                results.append(self.tools.list_pec_messages(context, query=mail_query, limit=self.settings.max_results))
                if wants_audit:
                    results.append(self.tools.list_pec_audit_messages(context, query=mail_query, limit=self.settings.max_results))
            if wants_ordinary or not wants_pec:
                results.append(self.tools.list_ordinary_email_messages(context, query=mail_query, limit=self.settings.max_results))
            return results
        if "fascicolo" in question.lower() or "pratica" in question.lower():
            fascicoli = self.tools.search_fascicoli(entity_query, context, limit=2)
            results = [fascicoli]
            if fascicoli.ok and len(fascicoli.data or []) == 1:
                target = str((fascicoli.data or [{}])[0].get("id") or "")
                results.append(self.tools.get_messaggi_by_fascicolo(target, context))
                if wants_pec:
                    results.append(
                        _scope_communication_result(
                            self.tools.list_pec_messages(context, query=mail_query, limit=self.settings.max_results),
                            fascicolo_id=target,
                        )
                    )
                    if wants_audit:
                        results.append(self.tools.list_pec_audit_messages(context, query=mail_query, limit=self.settings.max_results))
                if wants_ordinary:
                    results.append(
                        _scope_communication_result(
                            self.tools.list_ordinary_email_messages(context, query=mail_query, limit=self.settings.max_results),
                            fascicolo_id=target,
                        )
                    )
            return results
        clienti = self.tools.search_clienti(entity_query, context, limit=2)
        results = [clienti]
        if clienti.ok and len(clienti.data or []) == 1:
            target = str((clienti.data or [{}])[0].get("id") or "")
            results.append(self.tools.get_messaggi_by_cliente(target, context))
            if wants_pec:
                results.append(
                    _scope_communication_result(
                        self.tools.list_pec_messages(context, query=mail_query, limit=self.settings.max_results),
                        cliente_id=target,
                    )
                )
                if wants_audit:
                    results.append(self.tools.list_pec_audit_messages(context, query=mail_query, limit=self.settings.max_results))
            if wants_ordinary:
                results.append(
                    _scope_communication_result(
                        self.tools.list_ordinary_email_messages(context, query=mail_query, limit=self.settings.max_results),
                        cliente_id=target,
                    )
                )
        return results

    def _first_fascicolo_id(self, entity_query: str, context) -> str:
        for query in _fascicolo_resolution_queries(entity_query):
            result = self.tools.search_fascicoli(query, context, limit=2)
            if result.ok and len(result.data or []) == 1:
                return str((result.data or [{}])[0].get("id") or "")
        return ""

    def _all_scadenze(self, context) -> OperationalToolResult:
        source_id = "scadenziario"
        decision = self.tools._decision(source_id, context)
        if not decision.allowed:
            return self.tools._blocked(source_id, decision)
        manager = self.tools._safe_manager(source_id, lambda: self.tools._manager(source_id, "get_scadenziario", context))
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


_FASCICOLO_RESOLUTION_STOPWORDS = {
    "agenda",
    "analisi",
    "analizza",
    "aperti",
    "aperte",
    "atti",
    "attivo",
    "chiave",
    "documenti",
    "manca",
    "mancano",
    "passi",
    "prossimi",
    "punti",
    "rischi",
    "scadenze",
    "sintesi",
    "timeline",
}


def _fascicolo_resolution_queries(entity_query: str) -> list[str]:
    """Return progressively narrower queries to resolve a case from a long prompt."""

    original = clean_spaces(entity_query)
    if not original:
        return []
    tokens = [
        token
        for token in original.lower().split()
        if len(token) >= 2 and token not in _FASCICOLO_RESOLUTION_STOPWORDS
    ]
    queries: list[str] = [original]
    for size in (3, 2):
        for index in range(0, max(len(tokens) - size + 1, 0)):
            candidate = clean_spaces(" ".join(tokens[index : index + size]))
            if candidate and candidate not in queries:
                queries.append(candidate)
    for token in tokens:
        if token and token not in queries:
            queries.append(token)
    return queries


def _apply_conversation_followup(question: str, metadata: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    clean_question = clean_spaces(question)
    if not clean_question:
        return question, metadata
    reference = _conversation_reference(metadata)
    if not reference:
        return question, metadata
    text = clean_question.lower()
    if _looks_like_fresh_operational_question(text):
        return question, metadata
    active_context = dict(metadata.get("active_context") or {}) if isinstance(metadata.get("active_context"), dict) else {}
    effective = clean_question

    if reference.get("pec_id") and _is_short_followup(
        text,
        ("allegat", "mittent", "mandat", "arriv", "data", "oggett", "destinatar", "risposta", "rispondi", "bozza", "scrivi", "redigi", "spiega"),
    ):
        active_context.update({"context_type": "pec", "pec_id": reference["pec_id"]})
        metadata["pec_id"] = reference["pec_id"]
        if any(token in text for token in ("risposta", "rispondi", "bozza", "scrivi", "redigi", "prepara")):
            effective = "scrivi risposta alla PEC precedente"
        elif "allegat" in text:
            effective = "allegati della PEC precedente"
        else:
            effective = "spiegami la PEC precedente"

    elif reference.get("email_id") and _is_short_followup(
        text,
        ("allegat", "mittent", "mandat", "arriv", "data", "oggett", "destinatar", "risposta", "rispondi", "bozza", "scrivi", "redigi", "spiega"),
    ):
        active_context.update({"context_type": "email", "pec_id": reference["email_id"]})
        metadata["pec_id"] = reference["email_id"]
        if any(token in text for token in ("risposta", "rispondi", "bozza", "scrivi", "redigi", "prepara")):
            effective = "scrivi risposta alla email ordinaria precedente"
        elif "allegat" in text:
            effective = "allegati della email ordinaria precedente"
        else:
            effective = "spiegami la email ordinaria precedente"

    elif reference.get("case_id") and _is_short_followup(
        text,
        (
            "scadenz",
            "agenda",
            "timeline",
            "cronologia",
            "controparte",
            "soggett",
            "parti",
            "document",
            "pagament",
            "fattur",
            "riepilogo",
            "strateg",
            "risch",
            "critic",
            "azione",
            "azioni",
            "prossim",
            "priorit",
            "punto",
            "punti",
            "important",
        ),
    ):
        active_context.update({"context_type": "case", "case_id": reference["case_id"]})
        metadata["fascicolo_id"] = reference["case_id"]
        if any(token in text for token in ("controparte", "soggett", "parti")):
            effective = "quali soggetti sono collegati al fascicolo precedente"
        elif any(token in text for token in ("scadenz", "agenda")):
            effective = "scadenze e agenda del fascicolo precedente"
        elif any(token in text for token in ("pagament", "fattur")):
            effective = "pagamenti e fatture del fascicolo precedente"
        elif "timeline" in text or "cronologia" in text:
            effective = "costruisci timeline del fascicolo precedente"
        elif any(token in text for token in ("document", "punto", "punti", "important")):
            effective = "analizza i documenti del fascicolo precedente"
        else:
            effective = "fammi il riepilogo del fascicolo precedente"

    elif reference.get("document_id") and _is_short_followup(text, ("riassum", "spiega", "analizza", "punti", "important", "document", "atto")):
        active_context.update({"context_type": "document", "document_id": reference["document_id"]})
        if reference.get("case_id"):
            active_context["linked_case_id"] = reference["case_id"]
            metadata["fascicolo_id"] = reference["case_id"]
        metadata["document_id"] = reference["document_id"]
        effective = "analizza il documento precedente e indica i punti importanti"

    elif reference.get("client_id") and _is_short_followup(text, ("fascicol", "scadenz", "agenda", "pagament", "fattur", "recapit", "pec", "email", "situazione")):
        active_context.update({"context_type": "client", "client_id": reference["client_id"]})
        metadata["cliente_id"] = reference["client_id"]
        if "fascicol" in text:
            effective = "quali fascicoli ha il cliente precedente"
        elif any(token in text for token in ("pagament", "fattur")):
            effective = "verifica pagamenti e fatture del cliente precedente"
        elif any(token in text for token in ("pec", "email")):
            effective = "comunicazioni PEC/email del cliente precedente"
        elif any(token in text for token in ("scadenz", "agenda")):
            effective = "scadenze e agenda del cliente precedente"
        else:
            effective = "dammi la scheda cliente precedente"

    if active_context:
        metadata["active_context"] = active_context
    return effective, metadata


def _conversation_reference(metadata: dict[str, Any]) -> dict[str, str]:
    messages = list(metadata.get("messages") or [])
    if not messages:
        return {}
    reference: dict[str, str] = {}
    for message in reversed(messages[-8:]):
        if not isinstance(message, dict):
            continue
        content = clean_spaces(message.get("content"))
        if not content:
            continue
        reference.update(_extract_reference_from_text(content))
        if reference:
            return reference
    return reference


def _extract_reference_from_text(text: str) -> dict[str, str]:
    reference: dict[str, str] = {}
    pec_match = re.search(r"/email/messaggio/([^/\s)]+)", text)
    if pec_match:
        reference["pec_id"] = pec_match.group(1)
    email_match = re.search(r"/email-ordinaria/messaggio/([^/\s)]+)", text)
    if email_match:
        reference["email_id"] = email_match.group(1)
    document_match = re.search(r"/fascicoli/([^/\s)]+)/documenti/([^/\s)]+)/editor", text)
    if document_match:
        reference["case_id"] = document_match.group(1)
        reference["document_id"] = document_match.group(2)
    case_match = re.search(r"/fascicoli/([^/\s)]+)", text)
    if case_match and not reference.get("case_id"):
        reference["case_id"] = case_match.group(1)
    client_match = re.search(r"/clienti/([^/\s)]+)/cartella", text)
    if client_match:
        reference["client_id"] = client_match.group(1)
    return reference


def _is_short_followup(text: str, tokens: tuple[str, ...]) -> bool:
    if any(token in text for token in tokens):
        return True
    words = [word for word in re.split(r"\W+", text, flags=re.UNICODE) if word]
    return 0 < len(words) <= 4 and any(word in {"e", "poi", "anche", "quindi", "questo", "questa", "quello", "quella"} for word in words)


def _is_generic_studio_overview_query(entity_query: str) -> bool:
    text = re.sub(r"[^\w ]+", " ", str(entity_query or "").lower(), flags=re.UNICODE)
    tokens = [token for token in clean_spaces(text).split() if token]
    if not tokens:
        return True
    generic = {
        "contesto",
        "database",
        "studio",
        "memoria",
        "quadro",
        "situazione",
        "guardare",
        "oggi",
        "domani",
        "settimana",
        "devo",
        "cosa",
        "dimmi",
        "priorita",
        "priorità",
    }
    return all(token in generic for token in tokens)


def _looks_like_fresh_operational_question(text: str) -> bool:
    clean = clean_spaces(text).lower()
    if not clean:
        return False
    if any(token in clean for token in ("preventivo", "conferimento", "template", "modello atto", "modelli atto")):
        return True
    if "pec" in clean and ("fascicolo" in clean or "pratica" in clean):
        return True
    if ("ho in agenda" in clean or "cosa ho in agenda" in clean) and not clean.startswith(("e ", "anche ", "poi ")):
        return True
    return False


def _should_ignore_mailbox_text_filter(question: str, entity_query: str, *, has_scope: bool) -> bool:
    text = clean_spaces(question).lower()
    query = clean_spaces(entity_query).lower()
    if has_scope:
        return True
    if any(token in text for token in ("ultim", "ricevut", "inviat", "risposta", "rispondi", "scrivi", "redigi", "prepara", "bozza")):
        return True
    if _looks_like_communication_attachment_question(question):
        return True
    if "pec" in text and any(token in text for token in ("deposit", "controll", "verific", "presidi", "audit", "mime", "notific", "cancelleria")):
        return True
    return query in {"pec", "email", "posta", "messaggio", "messaggi"}


def _wants_pec_audit(question: str) -> bool:
    text = clean_spaces(question).lower()
    return any(
        token in text
        for token in (
            "controll",
            "valid",
            "firma",
            "firme",
            "confidence",
            "confidenza",
            "mancant",
            "mime",
            "audit",
            "deposito",
            "fascicolo",
            "collega",
            "qualita",
            "qualità",
            "semaforo",
            "notifica",
            "notificazione",
            "cancelleria",
            "giudice di pace",
            "d.l. 179",
            "legge 53",
            "l. 53",
            "snt",
            "pat",
            "ptt",
            "sigit",
            "siga",
            "termine",
            "scadenza",
        )
    )


def _looks_like_communication_attachment_question(question: str) -> bool:
    text = clean_spaces(question).lower()
    if not text:
        return False
    has_attachment = "allegat" in text
    has_act = any(token in text for token in ("atto", "atti", "notificat", "depositat", "comunicat"))
    has_mailbox = any(token in text for token in ("pec", "email", "mail", "messagg", "comunicazion"))
    has_question = any(token in text for token in ("quale", "quali", "che", "risulta", "risultano", "leggi", "dimmi"))
    return has_attachment and has_act and (has_mailbox or has_question)


def _scope_communication_result(
    result: OperationalToolResult,
    *,
    cliente_id: str = "",
    fascicolo_id: str = "",
) -> OperationalToolResult:
    if not result.ok or not isinstance(result.data, list):
        return result
    scoped_rows = []
    for row in result.data:
        if not isinstance(row, dict):
            continue
        row_cliente = clean_spaces(row.get("id_cliente") or row.get("cliente_id"))
        row_fascicolo = clean_spaces(row.get("id_fascicolo") or row.get("fascicolo_id") or row.get("id_pratica"))
        if cliente_id and row_cliente == clean_spaces(cliente_id):
            scoped_rows.append(row)
            continue
        if fascicolo_id and row_fascicolo == clean_spaces(fascicolo_id):
            scoped_rows.append(row)
    if scoped_rows:
        ids = {clean_spaces(row.get("id")) for row in scoped_rows if clean_spaces(row.get("id"))}
        result.data = scoped_rows
        result.sources = [source for source in result.sources if clean_spaces(source.object_id) in ids]
        result.objects = [
            obj
            for obj in result.objects
            if clean_spaces(obj.object_id) in ids
            or any(clean_spaces(obj.object_id).startswith(f"{item}#") for item in ids)
        ]
        return result
    result.ok = False
    result.data = []
    result.sources = []
    result.objects = []
    if fascicolo_id:
        result.coverage_gaps.append("Nessuna PEC/email collegata con certezza al fascicolo indicato.")
    elif cliente_id:
        result.coverage_gaps.append("Nessuna PEC/email collegata con certezza al cliente indicato.")
    return result


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
