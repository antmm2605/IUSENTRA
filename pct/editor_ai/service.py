"""Service applicativo per Generazione atti con Lex nell'editor."""

from __future__ import annotations

import hashlib
from typing import Any, Callable

from .audit import record_editor_ai_event
from .citations import build_atto_source
from .draft_planner import build_draft_plan
from .edit_proposals import apply_edit_proposal_to_html, build_edit_proposals
from .editor_renderer import create_editor_document, ensure_editor_html, read_editor_document_for_lex
from .models import (
    AttoAIDraftRequest,
    AttoAIExportResult,
    AttoAIGenerationResult,
    AttoAIRecord,
    AttoAISource,
    AttoAIVersion,
    FascicoloEditorAIContext,
    new_id,
    utc_now,
)
from .prompt_builder import EDITOR_AI_SYSTEM_PROMPT, build_generation_prompt
from .repository import EditorAIRepository
from .template_resolver import EditorAITemplateResolver
from .validators import (
    EditorAINotFound,
    EditorAIValidationError,
    assert_user_can_read,
    assert_user_can_write,
    clean_text,
    user_id_from_context,
    validate_italian_text,
)


class EditorAIService:
    def __init__(
        self,
        repository: EditorAIRepository,
        fascicoli_repository: Any,
        template_repository: Any = None,
        document_ai_service: Any = None,
        *,
        ai_generator: Callable[..., str] | None = None,
        central_audit: Callable[..., None] | None = None,
        encrypt_document: Callable[[bytes], bytes] | None = None,
        decrypt_document: Callable[[bytes], bytes] | None = None,
    ) -> None:
        self.repository = repository
        self.fascicoli_repository = fascicoli_repository
        self.template_repository = template_repository
        self.document_ai_service = document_ai_service
        self.template_resolver = EditorAITemplateResolver(template_repository)
        self.ai_generator = ai_generator
        self.central_audit = central_audit
        self.encrypt_document = encrypt_document
        self.decrypt_document = decrypt_document

    def bootstrap(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        user_context: object,
    ) -> dict[str, Any]:
        assert_user_can_read(user_context)
        fascicolo = self._get_fascicolo_or_raise(fascicolo_id)
        templates = self.template_resolver.list_available_templates_for_fascicolo(fascicolo)
        context = self.collect_fascicolo_context(tenant_id=tenant_id, fascicolo_id=fascicolo_id, user_context=user_context)
        return {
            "mock_fallback": False,
            "fascicolo_id": fascicolo_id,
            "templates": [
                {
                    "id": clean_text(item.get("id") or item.get("codice")),
                    "titolo": clean_text(item.get("titolo") or item.get("name")),
                    "area": clean_text(item.get("area") or item.get("materia")),
                    "canale_telematico": clean_text(item.get("canale_telematico") or item.get("canale_deposito")),
                    "link_compilatore_code": clean_text(item.get("link_compilatore_code")),
                }
                for item in templates
                if clean_text(item.get("id") or item.get("codice"))
            ],
            "documents": context.documents,
            "missing_fields": context.missing_fields,
            "capabilities": {
                "generate_draft": True,
                "propose_edits": True,
                "accept_reject_edits": True,
                "export_docx": True,
                "export_pdf": True,
            },
        }

    def generate_editor_draft(
        self,
        request: AttoAIDraftRequest,
        user_context: object,
    ) -> AttoAIGenerationResult:
        assert_user_can_write(user_context)
        fascicolo = self._get_fascicolo_or_raise(request.fascicolo_id)
        actor = user_id_from_context(user_context)
        atto_ai_id = new_id("attoai")
        record_editor_ai_event(
            self.repository,
            "editor_ai.generation.started",
            tenant_id=request.tenant_id,
            fascicolo_id=request.fascicolo_id,
            user_context=user_context,
            atto_ai_id=atto_ai_id,
            status="draft",
            central_audit=self.central_audit,
        )

        template = self.template_resolver.resolve_template_for_tipo_atto(
            tipo_atto=request.tipo_atto,
            template_id=request.template_id,
            fascicolo=fascicolo,
        )
        context_model = self.collect_fascicolo_context(
            tenant_id=request.tenant_id,
            fascicolo_id=request.fascicolo_id,
            user_context=user_context,
            document_ids=request.document_ids,
            include_document_text=request.use_fascicolo_context,
        )
        context = context_model.to_dict()
        context["missing_fields"] = sorted(
            set(context_model.missing_fields + self.template_resolver.validate_template_requirements(template, context)),
            key=str.casefold,
        )
        plan = build_draft_plan(
            tipo_atto=request.tipo_atto or clean_text(template.get("titolo")),
            template=template,
            context=context,
            document_ids=request.document_ids,
        )
        prompt = build_generation_prompt(request=request, template=template, context=context, plan=plan)
        content, generation_warning = self._generate_content(
            prompt=prompt,
            system_prompt=EDITOR_AI_SYSTEM_PROMPT,
            user_id=actor,
            plan=plan,
        )
        content_warnings = validate_italian_text(content, field_name="bozza atto")
        html_content = ensure_editor_html(content, plan)

        rendered = create_editor_document(
            fascicoli_repository=self.fascicoli_repository,
            fascicolo_id=request.fascicolo_id,
            title=plan.title,
            html_content=html_content,
            created_by=actor,
            encrypt=self.encrypt_document,
        )
        readback = self.read_editor_document_for_lex(
            tenant_id=request.tenant_id,
            fascicolo_id=request.fascicolo_id,
            editor_document_id=rendered["document_id"],
            user_context=user_context,
        )
        now = utc_now()
        record = AttoAIRecord(
            id=atto_ai_id,
            tenant_id=request.tenant_id,
            fascicolo_id=request.fascicolo_id,
            tipo_atto=plan.tipo_atto,
            template_id=plan.template_id,
            title=plan.title,
            status="draft",
            editor_document_id=rendered["document_id"],
            current_version_id=None,
            created_by=actor,
            created_at=now,
            updated_at=now,
        )
        self.repository.create_record(record)
        version = AttoAIVersion(
            id=new_id("veratto"),
            atto_ai_id=record.id,
            tenant_id=record.tenant_id,
            fascicolo_id=record.fascicolo_id,
            version_number=1,
            source="ai_generation",
            editor_document_snapshot=readback,
            docx_path=None,
            pdf_path=None,
            created_by=actor,
            created_at=utc_now(),
        )
        self.repository.create_version(version)
        record.current_version_id = version.id
        self.repository.update_record(record)

        sources = self._persist_sources(record.id, context_model.documents, plan.sources_to_use)
        warnings = sorted(
            set(plan.warnings + context_model.warnings + content_warnings + ([generation_warning] if generation_warning else [])),
            key=str.casefold,
        )
        record_editor_ai_event(
            self.repository,
            "editor_ai.version.created",
            tenant_id=record.tenant_id,
            fascicolo_id=record.fascicolo_id,
            user_context=user_context,
            atto_ai_id=record.id,
            version_id=version.id,
            editor_document_id=record.editor_document_id,
            status=record.status,
            payload={"version_number": version.version_number, "source": version.source},
            central_audit=self.central_audit,
        )
        record_editor_ai_event(
            self.repository,
            "editor_ai.readback.completed",
            tenant_id=record.tenant_id,
            fascicolo_id=record.fascicolo_id,
            user_context=user_context,
            atto_ai_id=record.id,
            version_id=version.id,
            editor_document_id=record.editor_document_id,
            status=record.status,
            payload={"filename": readback.get("filename", "")},
            central_audit=self.central_audit,
        )
        record_editor_ai_event(
            self.repository,
            "editor_ai.generation.completed",
            tenant_id=record.tenant_id,
            fascicolo_id=record.fascicolo_id,
            user_context=user_context,
            atto_ai_id=record.id,
            version_id=version.id,
            editor_document_id=record.editor_document_id,
            status=record.status,
            payload={"sources": len(sources), "missing_fields": len(context["missing_fields"])},
            central_audit=self.central_audit,
        )
        return AttoAIGenerationResult(
            record=record,
            version=version,
            sources=sources,
            plan=plan,
            open_url=rendered["open_url"],
            readback=readback,
            missing_fields=list(context["missing_fields"]),
            warnings=warnings,
        )

    def get_atto_ai(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        atto_ai_id: str,
        user_context: object,
    ) -> dict[str, Any]:
        assert_user_can_read(user_context)
        record = self._get_record_or_raise(tenant_id, fascicolo_id, atto_ai_id)
        return {
            "record": record,
            "versions": self.repository.list_versions(tenant_id, fascicolo_id, atto_ai_id),
            "sources": self.repository.list_sources(atto_ai_id),
            "edit_proposals": self.repository.list_edit_proposals(atto_ai_id),
        }

    def propose_editor_edits(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        atto_ai_id: str,
        instructions: str,
        user_context: object,
    ) -> list[Any]:
        assert_user_can_write(user_context)
        record = self._get_record_or_raise(tenant_id, fascicolo_id, atto_ai_id)
        current_version = self._current_version_or_raise(record)
        readback = self.read_editor_document_for_lex(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            editor_document_id=record.editor_document_id,
            user_context=user_context,
        )
        proposals = build_edit_proposals(
            atto_ai_id=record.id,
            version_id=current_version.id,
            instructions=instructions,
            current_html=str(readback.get("html") or ""),
            created_by=user_id_from_context(user_context),
        )
        for proposal in proposals:
            self.repository.create_edit_proposal(proposal)
        record.status = "in_review"
        self.repository.update_record(record)
        record_editor_ai_event(
            self.repository,
            "editor_ai.edit.proposed",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            user_context=user_context,
            atto_ai_id=record.id,
            version_id=current_version.id,
            editor_document_id=record.editor_document_id,
            status=record.status,
            payload={"count": len(proposals)},
            central_audit=self.central_audit,
        )
        return proposals

    def accept_edit(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        atto_ai_id: str,
        edit_id: str,
        user_context: object,
    ) -> dict[str, Any]:
        assert_user_can_write(user_context)
        record = self._get_record_or_raise(tenant_id, fascicolo_id, atto_ai_id)
        proposal = self.repository.get_edit_proposal(atto_ai_id, edit_id)
        if not proposal or proposal.status != "pending":
            raise EditorAINotFound("Proposta modifica non trovata o gia' risolta.")
        readback = self.read_editor_document_for_lex(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            editor_document_id=record.editor_document_id,
            user_context=user_context,
        )
        updated_html, warnings = apply_edit_proposal_to_html(str(readback.get("html") or ""), proposal)
        raw = updated_html.encode("utf-8")
        content = self.encrypt_document(raw) if callable(self.encrypt_document) else raw
        self.fascicoli_repository.sostituisci_documento(
            fascicolo_id,
            record.editor_document_id,
            nome_file=clean_text(readback.get("filename")) or f"{record.title}.html",
            contenuto=content,
            caricato_da=user_id_from_context(user_context),
            note="Modifica proposta da Lex accettata",
            preserve_version_snapshot=True,
            reuse_existing_path=True,
            hash_contenuto_sha256=hashlib.sha256(raw).hexdigest(),
        )
        new_readback = self.read_editor_document_for_lex(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            editor_document_id=record.editor_document_id,
            user_context=user_context,
        )
        version_number = len(self.repository.list_versions(tenant_id, fascicolo_id, atto_ai_id)) + 1
        version = AttoAIVersion(
            id=new_id("veratto"),
            atto_ai_id=record.id,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            version_number=version_number,
            source="ai_edit",
            editor_document_snapshot=new_readback,
            docx_path=None,
            pdf_path=None,
            created_by=user_id_from_context(user_context),
            created_at=utc_now(),
        )
        self.repository.create_version(version)
        record.current_version_id = version.id
        record.status = "in_review"
        self.repository.update_record(record)
        proposal.status = "accepted"
        proposal.resolved_by = user_id_from_context(user_context)
        proposal.resolved_at = utc_now()
        self.repository.update_edit_proposal(proposal)
        record_editor_ai_event(
            self.repository,
            "editor_ai.edit.accepted",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            user_context=user_context,
            atto_ai_id=record.id,
            version_id=version.id,
            editor_document_id=record.editor_document_id,
            status=record.status,
            payload={"edit_id": edit_id, "warnings": warnings},
            central_audit=self.central_audit,
        )
        return {"record": record, "version": version, "proposal": proposal, "warnings": warnings}

    def reject_edit(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        atto_ai_id: str,
        edit_id: str,
        user_context: object,
    ) -> Any:
        assert_user_can_write(user_context)
        record = self._get_record_or_raise(tenant_id, fascicolo_id, atto_ai_id)
        proposal = self.repository.get_edit_proposal(atto_ai_id, edit_id)
        if not proposal or proposal.status != "pending":
            raise EditorAINotFound("Proposta modifica non trovata o gia' risolta.")
        proposal.status = "rejected"
        proposal.resolved_by = user_id_from_context(user_context)
        proposal.resolved_at = utc_now()
        self.repository.update_edit_proposal(proposal)
        record_editor_ai_event(
            self.repository,
            "editor_ai.edit.rejected",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            user_context=user_context,
            atto_ai_id=record.id,
            version_id=record.current_version_id,
            editor_document_id=record.editor_document_id,
            status=record.status,
            payload={"edit_id": edit_id},
            central_audit=self.central_audit,
        )
        return proposal

    def export_editor_document(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        atto_ai_id: str,
        export_format: str,
        user_context: object,
    ) -> AttoAIExportResult:
        assert_user_can_read(user_context)
        record = self._get_record_or_raise(tenant_id, fascicolo_id, atto_ai_id)
        fmt = clean_text(export_format).lower()
        if fmt not in {"docx", "pdf"}:
            raise EditorAIValidationError("Formato export non valido.")
        record.status = "exported"
        self.repository.update_record(record)
        endpoint = "docx" if fmt == "docx" else "pdf"
        download_url = f"/api/editor/{fascicolo_id}/{record.editor_document_id}/{endpoint}"
        record_editor_ai_event(
            self.repository,
            "editor_ai.export.requested",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            user_context=user_context,
            atto_ai_id=record.id,
            version_id=record.current_version_id,
            editor_document_id=record.editor_document_id,
            status=record.status,
            payload={"format": fmt},
            central_audit=self.central_audit,
        )
        return AttoAIExportResult(
            atto_ai_id=record.id,
            editor_document_id=record.editor_document_id,
            format=fmt,
            download_url=download_url,
            version_id=record.current_version_id,
        )

    def read_editor_document_for_lex(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        editor_document_id: str,
        user_context: object,
    ) -> dict[str, Any]:
        assert_user_can_read(user_context)
        self._get_fascicolo_or_raise(fascicolo_id)
        return read_editor_document_for_lex(
            fascicoli_repository=self.fascicoli_repository,
            fascicolo_id=fascicolo_id,
            editor_document_id=editor_document_id,
            decrypt=self.decrypt_document,
        )

    def collect_fascicolo_context(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        user_context: object,
        document_ids: list[str] | None = None,
        include_document_text: bool = False,
    ) -> FascicoloEditorAIContext:
        assert_user_can_read(user_context)
        fascicolo = self._get_fascicolo_or_raise(fascicolo_id)
        facts = {
            "fascicolo_id": clean_text(getattr(fascicolo, "id", fascicolo_id)),
            "titolo": clean_text(getattr(fascicolo, "titolo", "")),
            "cliente": clean_text(getattr(fascicolo, "nome_cliente", "")),
            "ufficio": clean_text(getattr(fascicolo, "tribunale", "")),
            "numero_rg": clean_text(getattr(fascicolo, "numero_rg", "")),
            "oggetto": clean_text(getattr(fascicolo, "oggetto", "") or getattr(fascicolo, "titolo", "")),
            "tipo_fascicolo": clean_text(getattr(getattr(fascicolo, "tipo", ""), "value", getattr(fascicolo, "tipo", ""))),
            "stato": clean_text(getattr(getattr(fascicolo, "stato", ""), "value", getattr(fascicolo, "stato", ""))),
        }
        missing = [
            label
            for key, label in (
                ("cliente", "Cliente"),
                ("oggetto", "Oggetto"),
                ("ufficio", "Ufficio giudiziario"),
                ("numero_rg", "Numero RG"),
            )
            if not facts.get(key)
        ]
        documents = self._collect_indexed_documents(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            user_context=user_context,
            document_ids=document_ids or [],
            include_text=include_document_text,
        )
        activities = [
            {
                "id": clean_text(getattr(item, "id", "")),
                "tipo": clean_text(getattr(getattr(item, "tipo", ""), "value", getattr(item, "tipo", ""))),
                "data": clean_text(getattr(item, "data", "")),
                "titolo": clean_text(getattr(item, "titolo", "")),
                "descrizione": clean_text(getattr(item, "descrizione", "")),
            }
            for item in list(getattr(fascicolo, "attivita", []) or [])
        ]
        deadlines = [
            item for item in activities if clean_text(item.get("tipo")).upper() in {"TERMINE_SCADENZA", "UDIENZA"}
        ]
        warnings: list[str] = []
        not_ready = [doc for doc in documents if clean_text(doc.get("status")) != "ready"]
        if not_ready:
            warnings.append("Alcuni documenti del fascicolo non sono ancora indicizzati e non sono stati usati per il testo.")
        return FascicoloEditorAIContext(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            facts=facts,
            documents=documents,
            activities=activities,
            deadlines=deadlines,
            communications=[],
            missing_fields=missing,
            warnings=warnings,
        )

    def _collect_indexed_documents(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        user_context: object,
        document_ids: list[str],
        include_text: bool,
    ) -> list[dict[str, Any]]:
        if self.document_ai_service is None:
            return []
        wanted = {clean_text(item) for item in document_ids if clean_text(item)}
        rows = self.document_ai_service.list_fascicolo_documents(tenant_id, fascicolo_id, user_context)
        documents: list[dict[str, Any]] = []
        for doc in rows:
            doc_id = clean_text(getattr(doc, "id", ""))
            if wanted and doc_id not in wanted:
                continue
            item = {
                "document_id": doc_id,
                "filename": clean_text(getattr(doc, "original_filename", "")),
                "file_type": clean_text(getattr(doc, "file_type", "")),
                "status": clean_text(getattr(doc, "status", "")),
                "page_count": getattr(doc, "page_count", None),
                "sha256": clean_text(getattr(doc, "sha256", "")),
            }
            if include_text and item["status"] == "ready":
                try:
                    text = self.document_ai_service.get_fascicolo_document_text(tenant_id, fascicolo_id, doc_id, user_context)
                    item["text"] = text.text
                    item["pages"] = [page.to_dict() for page in text.pages]
                except Exception as exc:
                    item["warning"] = f"Testo non leggibile: {exc}"
            documents.append(item)
        return documents

    def _persist_sources(self, atto_ai_id: str, documents: list[dict[str, Any]], selected_ids: list[str]) -> list[AttoAISource]:
        selected = {clean_text(item) for item in selected_ids if clean_text(item)}
        sources: list[AttoAISource] = []
        for doc in documents:
            doc_id = clean_text(doc.get("document_id") or doc.get("id"))
            if selected and doc_id not in selected:
                continue
            if clean_text(doc.get("status")) != "ready":
                continue
            quote = ""
            pages = doc.get("pages") if isinstance(doc.get("pages"), list) else []
            if pages and isinstance(pages[0], dict):
                quote = clean_text(pages[0].get("text"))[:280]
            elif clean_text(doc.get("text")):
                quote = clean_text(doc.get("text"))[:280]
            source = build_atto_source(
                atto_ai_id=atto_ai_id,
                source_type="documento_fascicolo",
                source_id=doc_id,
                document_id=doc_id,
                page_number=(pages[0].get("page_number") if pages and isinstance(pages[0], dict) else None),
                quote=quote,
                sha256=clean_text(doc.get("sha256")),
                reason="Documento indicizzato del fascicolo usato per la bozza.",
            )
            self.repository.create_source(source)
            sources.append(source)
        return sources

    def _generate_content(
        self,
        *,
        prompt: str,
        system_prompt: str,
        user_id: str,
        plan: Any,
    ) -> tuple[str, str]:
        if callable(self.ai_generator):
            return str(self.ai_generator(prompt=prompt, system_prompt=system_prompt, user_id=user_id)), ""
        try:
            from lex.gateway.service import LexGateway

            response = LexGateway().ask(
                user_id=user_id,
                prompt=prompt,
                task="draft_act_support",
                allow_external=False,
                system_prompt=system_prompt,
            )
            return str(response.content or ""), ""
        except Exception:
            return self._fallback_structured_draft(plan), (
                "Runtime Lex non disponibile: creata bozza strutturata governata da completare e verificare."
            )

    def _fallback_structured_draft(self, plan: Any) -> str:
        parts = [f"<h1>{plan.title}</h1>"]
        for section in plan.sections:
            tag = f"h{min(max(section.level + 1, 2), 4)}"
            parts.append(f"<{tag}>{section.heading}</{tag}>")
            parts.append("<p>[DATO DA COMPLETARE: verificare e integrare questa sezione prima dell'uso.]</p>")
        return "\n".join(parts)

    def _get_fascicolo_or_raise(self, fascicolo_id: str) -> Any:
        getter = getattr(self.fascicoli_repository, "get", None)
        fascicolo = getter(fascicolo_id) if callable(getter) else None
        if not fascicolo:
            raise EditorAINotFound("Fascicolo non trovato.")
        return fascicolo

    def _get_record_or_raise(self, tenant_id: str, fascicolo_id: str, atto_ai_id: str) -> AttoAIRecord:
        record = self.repository.get_record(tenant_id, fascicolo_id, atto_ai_id)
        if not record:
            raise EditorAINotFound("Atto AI non trovato.")
        return record

    def _current_version_or_raise(self, record: AttoAIRecord) -> AttoAIVersion:
        versions = self.repository.list_versions(record.tenant_id, record.fascicolo_id, record.id)
        current = next((version for version in versions if version.id == record.current_version_id), None)
        if current:
            return current
        if versions:
            return versions[-1]
        raise EditorAINotFound("Versione atto AI non trovata.")
