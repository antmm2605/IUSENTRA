"""Orchestratore del flusso Lex."""

from __future__ import annotations

from io import BytesIO
import json
from typing import Any

from flask import Response, current_app, send_file, stream_with_context

from .contracts import LexRequest as WorkflowLexRequest
from .exceptions import LexGuardError
from .context import LexContextBuilder
from .dependencies import LexDependencies
from .formatting.answer_builder import AnswerBuilder
from .formatting.ui_payloads import (
    direct_answer_payload,
    followup_resolution_payload,
    routing_payload,
    social_context_payload,
)
from .guards import AuthorizationGuard, GroundingGuard, OutputGuard, ScopeGuard
from .memory.conversation_state import (
    messages_with_effective_question,
    resolve_current_and_previous_user_messages,
)
from .providers.local_llm import LocalLLMProvider
from .retrieval import LexSearchRanker
from .telemetry.audit import audit_trace


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


class LexOrchestrator:
    def __init__(
        self,
        dependencies: LexDependencies | None = None,
        *,
        router=None,
        workflow_context_builder=None,
        retrieval_orchestrator=None,
        guard_orchestrator=None,
        provider_registry=None,
        formatter=None,
        telemetry=None,
        memory=None,
    ) -> None:
        self.dependencies = dependencies
        self.auth_guard = AuthorizationGuard()
        self.scope_guard = ScopeGuard()
        self.context_builder = LexContextBuilder()
        self.search_ranker = LexSearchRanker()
        self.grounding_guard = GroundingGuard()
        self.output_guard = OutputGuard()
        self.answer_builder = AnswerBuilder()
        self.llm_provider = LocalLLMProvider()
        self.workflow_router = router
        self.workflow_context_builder = workflow_context_builder or self.context_builder
        self.retrieval_orchestrator = retrieval_orchestrator
        self.guard_orchestrator = guard_orchestrator
        self.provider_registry = provider_registry
        self.response_formatter = formatter or self.answer_builder
        self.telemetry = telemetry
        self.memory = memory

    def run(self, request: WorkflowLexRequest):
        if self.workflow_router is None or self.retrieval_orchestrator is None or self.guard_orchestrator is None or self.provider_registry is None:
            raise RuntimeError("LexOrchestrator.run richiede i componenti applicativi del bounded context.")

        workflow = self.workflow_router.resolve_workflow(request)
        context = self.workflow_context_builder.build_request_context(request, workflow)

        pre = self.guard_orchestrator.run_pre(request, context, workflow)
        if not pre.allowed:
            raise LexGuardError("; ".join(pre.reasons or ["Request blocked by guards"]))

        evidence = self.retrieval_orchestrator.collect(request, context, workflow)
        provider = self.provider_registry.pick(request, context, workflow, evidence)
        draft = provider.generate(request=request, context=context, evidence=evidence, workflow=workflow)

        post = self.guard_orchestrator.run_post(request, context, workflow, evidence, draft)
        if not post.allowed:
            raise LexGuardError("; ".join(post.reasons or ["Response blocked by guards"]))

        response = self.response_formatter.build_response(
            request=request,
            context=context,
            workflow=workflow,
            evidence=evidence,
            draft=draft,
            verdict=post,
        )

        if self.telemetry is not None:
            self.telemetry.record(request, workflow, context, evidence, response)
        if self.memory is not None:
            self.memory.persist(request, workflow, context, response)

        return response

    def _build_context_payload(
        self,
        *,
        effective_question: str,
        history_messages: list[dict[str, object]],
        routing,
        pratica_id: str = "",
        fascicolo_id: str = "",
        mode: str = "general",
    ) -> dict[str, Any]:
        return self.context_builder.build(
            question=effective_question,
            mode=mode,
            pratica_id=pratica_id,
            fascicolo_id=fascicolo_id,
            history_messages=history_messages,
            routing=routing,
            build_studio_context=self.dependencies.build_studio_context,
            build_today_summary=self.dependencies.build_today_summary,
        )

    def _followup_prompt_block(self, followup) -> str:
        lines: list[str] = []
        if bool(getattr(followup, "reused_previous_topic", False)) and _clean_spaces(getattr(followup, "previous_user_text", "")):
            lines.append(
                "Follow-up conversazionale: il tema utile e' gia' emerso nel turno precedente e va ereditato senza chiedere di nuovo l'argomento."
            )
        if bool(getattr(followup, "is_web_request", False)):
            lines.append(
                "Richiesta web presa in carico: Lex deve controllare direttamente, usare fonti ufficiali pertinenti e riportare risultati concreti, non un elenco di siti da consultare."
            )
        if bool(getattr(followup, "needs_web_search", False)):
            lines.append(
                "In questa risposta il web va usato solo come supporto operativo mirato, dopo aver sfruttato il contesto interno utile."
            )
        return "\n".join(lines).strip()

    def _routing_prompt_block(self, routing, *, opening_line: str = "") -> str:
        lines: list[str] = []
        if bool(getattr(routing, "is_daily_overview", False)):
            lines.append(
                "Overview giornaliera: Lex deve costruire un quadro operativo di oggi ordinato per priorita', partendo da scadenze, udienze, agenda e fascicoli attivi."
            )
        if bool(getattr(routing, "is_followup", False)) and bool(getattr(routing, "reused_previous_topic", False)):
            lines.append("Follow-up breve: il contesto del turno precedente va riusato senza ripartire da zero.")
        clean_opening_line = _clean_spaces(opening_line)
        if clean_opening_line:
            lines.append(
                "L'apertura iniziale e' gia' stata resa all'utente: dopo quel testo Lex deve continuare direttamente con il contenuto operativo senza ripetere il saluto."
            )
        return "\n".join(lines).strip()

    def status_payload(self) -> tuple[dict[str, Any], int]:
        runtime = self.dependencies.resolved_runtime()
        api_base_url = str(runtime.get("api_base_url") or "").rstrip("/")
        base_url = str(runtime.get("base_url") or "").rstrip("/")
        chat_model = str(runtime.get("chat_model") or "mistral").strip() or "mistral"
        try:
            response = self.dependencies.requests_module.get(f"{api_base_url}/tags", timeout=3)
            models = [model["name"] for model in response.json().get("models", [])]
            return {
                "ok": True,
                "url": base_url,
                "modello_attivo": chat_model,
                "modelli": models,
            }, 200
        except self.dependencies.requests_module.exceptions.ConnectionError:
            return {
                "ok": False,
                "errore": "Ollama non raggiungibile",
                "suggerimento": "Avvia Ollama con: ollama serve",
                "modelli": [],
            }, 200
        except Exception as exc:
            return {"ok": False, "errore": str(exc), "modelli": []}, 200

    def build_context_response(
        self,
        *,
        user,
        studio,
        data: dict[str, Any],
    ) -> tuple[dict[str, Any], int]:
        self.auth_guard.ensure_can_access(
            user=user,
            studio=studio,
            pratica_id=str(data.get("pratica_id") or ""),
        )
        messages = list(data.get("messages", []) or [])[-12:]
        attachments = list(data.get("attachments") or [])
        fascicolo_id = _clean_spaces(data.get("fascicolo_id"))
        mode = _clean_spaces(data.get("mode")) or "general"
        current_user_message, previous_user_message, history_messages = resolve_current_and_previous_user_messages(
            explicit_question=_clean_spaces(data.get("question")),
            messages=messages,
        )
        if not current_user_message:
            return {"ok": False, "errore": "Domanda mancante.", "prompt": "", "sources": [], "citations": []}, 200

        routing = self.dependencies.resolve_social_and_operational_intent(
            current_user_message,
            previous_user_text=previous_user_message,
        )
        if routing.is_social_only:
            reply = self.dependencies.build_social_only_reply(routing.social_kind, routing.raw_text) or "Dimmi pure."
            payload = social_context_payload(current_user_message, reply)
            payload["routing"] = routing_payload(routing)
            payload["social_kind"] = routing.social_kind
            payload["social_prefix"] = routing.social_prefix
            return payload, 200

        base_question = str(routing.effective_query or current_user_message).strip() or current_user_message
        followup = self.dependencies.resolve_followup_query(
            base_question,
            previous_user_text=previous_user_message,
        )
        user_effective_question = str(followup.effective_query or base_question).strip() or base_question
        social_prefix = str(routing.social_prefix or "").strip() if routing.is_social_with_request else ""

        runtime = self.dependencies.resolved_runtime()
        studio_context = self._build_context_payload(
            effective_question=user_effective_question,
            history_messages=history_messages,
            routing=routing,
            pratica_id=str(data.get("pratica_id") or ""),
            fascicolo_id=fascicolo_id,
            mode=mode,
        )
        resolved_effective_question = str(studio_context.get("effective_question") or user_effective_question).strip() or user_effective_question
        direct_guard_reply = self.dependencies.build_unverified_pdf_reply(
            resolved_effective_question,
            studio_context.get("verified_legal_references") or studio_context.get("sources") or [],
        )
        if direct_guard_reply:
            payload = direct_answer_payload(
                current_user_message,
                direct_guard_reply,
                sources=studio_context.get("sources") or [],
                citations=studio_context.get("citations") or [],
                legal_reference_guard_active=True,
            )
            payload["routing"] = routing_payload(routing)
            payload["followup_resolution"] = followup_resolution_payload(followup)
            payload["effective_question"] = resolved_effective_question
            return payload, 200

        prompt_question = resolved_effective_question
        web_execution_requested = bool(studio_context.get("web_execution_requested")) or bool(followup.is_web_request)
        language_guidance = self.dependencies.build_language_guidance(
            question=prompt_question,
            social_prefix=social_prefix,
            research_strategy=str(studio_context.get("research_strategy") or "").strip(),
            focus_topic=str(studio_context.get("focus_topic") or "").strip(),
            web_execution_requested=web_execution_requested,
            is_daily_overview=bool(routing.is_daily_overview),
        )
        opening_line = str(language_guidance.opening_line or "").strip()
        prompt_social_prefix = "" if opening_line else social_prefix
        followup_block = self._followup_prompt_block(followup)
        routing_block = self._routing_prompt_block(routing, opening_line=opening_line)
        web_fallback_used = bool(studio_context.get("web_fallback_used")) or bool(
            followup.is_web_request and followup.needs_web_search
        )
        studio_prompt_block = str(studio_context.get("prompt_block", "") or "").strip()
        studio_prompt_block = "\n\n".join(
            block
            for block in [
                studio_prompt_block,
                routing_block,
                followup_block,
                str(language_guidance.prompt_block or "").strip(),
            ]
            if block
        )
        prompt = self.dependencies.build_prompt(
            question=prompt_question,
            fascicolo_id=fascicolo_id,
            messages=history_messages,
            studio_context=studio_prompt_block,
            include_conversation=True,
            social_prefix=prompt_social_prefix,
            social_kind=routing.social_kind,
            opening_line=opening_line,
        )
        if attachments:
            prompt += "\n\n" + self.dependencies.build_attachment_prompt_block(attachments)

        retrieval_sources = self.search_ranker.collect_and_rank(
            pratica_id=str(data.get("pratica_id") or ""),
            message=prompt_question,
            context=studio_context,
            mode=mode,
        )
        grounding = self.grounding_guard.evaluate(
            sources=studio_context.get("sources") or retrieval_sources
        )
        built = self.answer_builder.build_chat_payload(
            answer=self.output_guard.clean(answer="", grounding=grounding),
            sources=studio_context.get("sources") or retrieval_sources,
            grounding=grounding,
            mode=mode,
        )

        try:
            audit_trace(
                query=current_user_message,
                prompt_question=prompt_question,
                engine_ids=studio_context.get("engine_ids") or [],
                source_ids=studio_context.get("source_ids") or [],
                ai_model=runtime.get("chat_model") or "mistral",
                result_summary="Contesto assistente Lex preparato per il companion locale.",
                warning="La risposta finale viene generata sul dispositivo cliente tramite companion locale.",
            )
        except Exception:
            current_app.logger.exception("Errore audit assistente_context")

        built.update(
            {
                "query_type": "assistente_chat",
                "question": current_user_message,
                "effective_question": resolved_effective_question,
                "prompt": prompt,
                "attachments": attachments,
                "focus_label": str(studio_context.get("focus_label") or "").strip(),
                "focus_topic": str(studio_context.get("focus_topic") or "").strip(),
                "competence_labels": list(studio_context.get("competence_labels") or []),
                "web_fallback_used": web_fallback_used,
                "web_execution_requested": web_execution_requested,
                "social_kind": routing.social_kind,
                "social_prefix": str(social_prefix or "").strip(),
                "opening_line": opening_line,
                "daily_overview_lead": opening_line,
                "language_mode": str(language_guidance.mode or "").strip(),
                "legal_reference_guard_active": bool(studio_context.get("legal_reference_guard_active")),
                "verified_legal_references": studio_context.get("verified_legal_references") or [],
                "disable_exports": False,
                "execution_policy": studio_context.get("execution_policy") or {},
                "routing": routing_payload(routing),
                "followup_resolution": followup_resolution_payload(followup),
                "structured_context": studio_context.get("structured_context") or {},
                "retrieval_sources": retrieval_sources,
            }
        )
        return built, 200

    def warmup_response(self, *, question: str, context_label: str) -> tuple[dict[str, Any], int]:
        warmed = self.dependencies.warm_studio_context(question=question, context_label=context_label)
        runtime = self.dependencies.warm_runtime()
        return {
            "ok": True,
            "prewarmed": True,
            "sources_ready": len(warmed.get("sources") or []),
            "runtime": runtime,
        }, 200

    def attachments_response(self, *, files: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        attachments, errors = self.dependencies.parse_attachment_payloads(files or [])
        return {
            "ok": True,
            "attachments": attachments,
            "errors": errors,
            "prompt_block": self.dependencies.build_attachment_prompt_block(attachments),
        }, 200

    def document_response(self, *, data: dict[str, Any]):
        answer = _clean_spaces(data.get("answer"))
        if not answer:
            return {"ok": False, "errore": "Contenuto del documento mancante."}, 400
        title = self.dependencies.infer_export_title(
            title=str(data.get("title") or ""),
            question=str(data.get("question") or ""),
            answer=answer,
        )
        citations = data.get("citations") or []
        context_label = str(data.get("context_label") or "").strip()
        docx_bytes = self.dependencies.build_docx_bytes(
            title=title,
            question=str(data.get("question") or ""),
            answer=answer,
            citations=citations if isinstance(citations, list) else [],
            context_label=context_label,
        )
        file_name = self.dependencies.build_export_filename(title, "docx")
        return send_file(
            BytesIO(docx_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=file_name,
        )

    def chat_response(
        self,
        *,
        user,
        studio,
        data: dict[str, Any],
    ):
        self.auth_guard.ensure_can_access(
            user=user,
            studio=studio,
            pratica_id=str(data.get("pratica_id") or ""),
        )
        messages = list(data.get("messages", []) or [])[-12:]
        attachments = list(data.get("attachments") or [])
        fascicolo_id = str(data.get("fascicolo_id", "") or "")
        mode = _clean_spaces(data.get("mode")) or "general"
        current_user_message, previous_user_text, history_messages = resolve_current_and_previous_user_messages(
            explicit_question="",
            messages=messages,
        )
        routing = self.dependencies.resolve_social_and_operational_intent(
            current_user_message,
            previous_user_text=previous_user_text,
        )
        if routing.is_social_only:
            reply = self.dependencies.build_social_only_reply(routing.social_kind, routing.raw_text) or "Dimmi pure."

            def generate_social():
                yield f"data: {json.dumps({'token': reply})}\n\n"
                yield "data: [DONE]\n\n"

            return Response(
                stream_with_context(generate_social()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        base_question = str(routing.effective_query or current_user_message).strip() or "Richiesta operativa"
        followup = self.dependencies.resolve_followup_query(
            base_question,
            previous_user_text=previous_user_text,
        )
        user_effective_question = str(followup.effective_query or base_question).strip() or "Richiesta operativa"
        social_prefix = str(routing.social_prefix or "").strip() if routing.is_social_with_request else ""
        runtime = self.dependencies.resolved_runtime()
        api_base_url = str(runtime.get("api_base_url") or "").rstrip("/")
        base_url = str(runtime.get("base_url") or "").rstrip("/")
        studio_context = self._build_context_payload(
            effective_question=user_effective_question,
            history_messages=history_messages,
            routing=routing,
            pratica_id=str(data.get("pratica_id") or ""),
            fascicolo_id=fascicolo_id,
            mode=mode,
        )
        resolved_effective_question = str(studio_context.get("effective_question") or user_effective_question).strip() or "Richiesta operativa"
        direct_guard_reply = self.dependencies.build_unverified_pdf_reply(
            resolved_effective_question,
            studio_context.get("verified_legal_references") or studio_context.get("sources") or [],
        )
        if direct_guard_reply:
            def generate_direct():
                yield f"data: {json.dumps({'token': direct_guard_reply})}\n\n"
                yield "data: [DONE]\n\n"

            return Response(
                stream_with_context(generate_direct()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        prompt_question = resolved_effective_question
        language_guidance = self.dependencies.build_language_guidance(
            question=prompt_question,
            social_prefix=social_prefix,
            research_strategy=str(studio_context.get("research_strategy") or "").strip(),
            focus_topic=str(studio_context.get("focus_topic") or "").strip(),
            web_execution_requested=bool(studio_context.get("web_execution_requested")) or bool(followup.is_web_request),
            is_daily_overview=bool(routing.is_daily_overview),
        )
        stream_opening_line = str(language_guidance.opening_line or "").strip() or social_prefix
        rewrite_last_user_message = bool(followup.reused_previous_topic or routing.reused_previous_topic)
        llm_messages = (
            messages_with_effective_question(
                messages,
                effective_question=resolved_effective_question,
                original_question=current_user_message,
            )
            if rewrite_last_user_message
            else [dict(item or {}) for item in messages]
        )
        followup_block = self._followup_prompt_block(followup)
        routing_block = self._routing_prompt_block(routing, opening_line=stream_opening_line)
        studio_prompt_block = str(studio_context.get("prompt_block", "") or "").strip()
        studio_prompt_block = "\n\n".join(
            block
            for block in [
                studio_prompt_block,
                routing_block,
                followup_block,
                str(language_guidance.prompt_block or "").strip(),
            ]
            if block
        )

        system_content = self.dependencies.build_prompt(
            question=prompt_question,
            fascicolo_id=fascicolo_id,
            messages=history_messages,
            studio_context=studio_prompt_block,
            social_prefix="",
            social_kind=routing.social_kind,
            opening_line="",
        )
        if attachments:
            system_content += "\n\n" + self.dependencies.build_attachment_prompt_block(attachments)

        payload = self.llm_provider.build_chat_payload(
            runtime=runtime,
            llm_messages=llm_messages,
            system_content=system_content,
        )

        try:
            audit_trace(
                query=current_user_message or "Richiesta assistente PCT",
                prompt_question=prompt_question,
                engine_ids=studio_context.get("engine_ids") or [],
                source_ids=studio_context.get("source_ids") or [],
                ai_model=str(runtime.get("chat_model") or "mistral"),
                result_summary="Richiesta inviata all'assistente Lex.",
                warning="Risposta generativa locale: verificare sempre le fonti ufficiali prima dell'uso professionale.",
            )
        except Exception:
            current_app.logger.exception("Errore audit assistente_chat")

        generator = self.llm_provider.stream_chat(
            requests_module=self.dependencies.requests_module,
            api_base_url=api_base_url,
            payload=payload,
            base_url=base_url,
            opening_line=stream_opening_line,
        )
        return Response(
            stream_with_context(generator()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
