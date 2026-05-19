"""Unified operational chat contract for Lex Studio Reasoner."""

from __future__ import annotations

import re
from typing import Any

from .models import OperationalAnswer
from .serializers import clean_spaces


_ACCOUNTING_SOURCE_IDS = {"fatturazione", "preventivi", "conferimenti", "pagamenti", "timesheet", "tariffario"}
_COMMUNICATION_SOURCE_IDS = {"email_pec", "email_ordinaria", "messaggi"}
_LEGAL_SOURCE_IDS = {"legal_intelligence", "update_intelligence", "fonti_ufficiali", "web_libero"}


class LexContextProvider:
    """Normalizes page/module context into one stable Lex chat context."""

    @classmethod
    def enrich_metadata(cls, metadata: dict[str, Any], studio_context: dict[str, Any] | None = None) -> dict[str, Any]:
        enriched = dict(metadata or {})
        active_context = cls.from_payload(enriched, studio_context or {})
        enriched["active_context"] = active_context
        if active_context.get("case_id") and not enriched.get("fascicolo_id"):
            enriched["fascicolo_id"] = active_context["case_id"]
        if active_context.get("linked_case_id") and not enriched.get("fascicolo_id"):
            enriched["fascicolo_id"] = active_context["linked_case_id"]
        if active_context.get("client_id") and not enriched.get("cliente_id"):
            enriched["cliente_id"] = active_context["client_id"]
        if active_context.get("linked_client_id") and not enriched.get("cliente_id"):
            enriched["cliente_id"] = active_context["linked_client_id"]
        if active_context.get("pec_id") and not enriched.get("pec_id"):
            enriched["pec_id"] = active_context["pec_id"]
        if active_context.get("document_id") and not enriched.get("document_id"):
            enriched["document_id"] = active_context["document_id"]
        return enriched

    @classmethod
    def from_payload(cls, metadata: dict[str, Any], studio_context: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = dict(metadata or {})
        studio_context = dict(studio_context or {})
        raw = metadata.get("active_context")
        active = dict(raw) if isinstance(raw, dict) else {}
        page_context = clean_spaces(active.get("page_context") or metadata.get("page_context") or metadata.get("page_section"))
        page_path = clean_spaces(active.get("page_path") or metadata.get("page_path"))
        context_type = clean_spaces(active.get("context_type") or active.get("contextType") or metadata.get("context_type")).lower()
        if not context_type:
            context_type = cls._infer_context_type(page_context=page_context, page_path=page_path)

        context = {
            "context_type": context_type or "global",
            "case_id": _first_clean(active, metadata, "case_id", "caseId", "fascicolo_id", "id_fascicolo", "pratica_id"),
            "client_id": _first_clean(active, metadata, "client_id", "clientId", "cliente_id", "id_cliente"),
            "pec_id": _first_clean(active, metadata, "pec_id", "pecId", "email_id", "message_id"),
            "document_id": _first_clean(active, metadata, "document_id", "documentId", "id_documento"),
            "linked_case_id": _first_clean(active, metadata, "linked_case_id", "linkedCaseId", "id_fascicolo_collegato"),
            "linked_client_id": _first_clean(active, metadata, "linked_client_id", "linkedClientId", "id_cliente_collegato"),
            "user_id": _first_clean(active, metadata, "user_id", "userId") or clean_spaces(studio_context.get("user_id")),
            "permissions_scope": _scope_list(active.get("permissions_scope") or active.get("permissionsScope") or metadata.get("permissions_scope")),
            "page_context": page_context,
            "page_path": page_path,
            "label": clean_spaces(active.get("label") or active.get("context_label") or metadata.get("context_label")),
        }
        cls._extract_ids_from_path(context)
        return {key: value for key, value in context.items() if value not in ("", [], None)}

    @staticmethod
    def _infer_context_type(*, page_context: str, page_path: str) -> str:
        haystack = f"{page_context} {page_path}".lower()
        if "/email/messaggio/" in haystack or "email-pec" in haystack or "pec" in haystack:
            return "pec"
        if "/email-ordinaria/messaggio/" in haystack or "ordinaria" in haystack:
            return "email"
        if "document" in haystack or "/documenti/" in haystack:
            return "document"
        if "fascicol" in haystack or "/fascicoli/" in haystack:
            return "case"
        if "client" in haystack or "/clienti/" in haystack:
            return "client"
        return "global"

    @staticmethod
    def _extract_ids_from_path(context: dict[str, Any]) -> None:
        path = clean_spaces(context.get("page_path"))
        if not path:
            return
        if not context.get("case_id"):
            match = re.search(r"/fascicoli/([^/?#]+)", path)
            if match:
                context["case_id"] = match.group(1)
        if not context.get("client_id"):
            match = re.search(r"/clienti/([^/?#]+)", path)
            if match:
                context["client_id"] = match.group(1)
        if not context.get("pec_id"):
            match = re.search(r"/email/messaggio/([^/?#]+)", path)
            if match:
                context["pec_id"] = match.group(1)
                context["context_type"] = "pec"
        if not context.get("document_id"):
            match = re.search(r"/documenti/([^/?#]+)/editor", path)
            if match:
                context["document_id"] = match.group(1)
                context.setdefault("context_type", "document")


class IntentRouter:
    """Maps deterministic operational routes to Lex operational chat intents."""

    @classmethod
    def detect(cls, answer: OperationalAnswer, question: str, active_context: dict[str, Any], sources: list[dict[str, Any]]) -> str:
        route_intent = clean_spaces(getattr(answer.route, "intent", "")).lower() if answer.route else ""
        text = clean_spaces(question).lower()
        context_type = clean_spaces(active_context.get("context_type")).lower()
        source_ids = {clean_spaces(source.get("source_id")) for source in sources}
        if route_intent == "communications_lookup":
            if context_type == "email" or ("email_ordinaria" in source_ids and "email_pec" not in source_ids and "pec" not in text):
                return "consult_email"
            return "consult_pec"
        if route_intent == "documenti_fascicolo":
            return "consult_document"
        if route_intent == "fascicolo_summary":
            return "summarize_case"
        if route_intent == "build_case_timeline":
            return "build_case_timeline"
        if route_intent in {"deadlines_overview", "agenda_overview"}:
            return "check_deadlines"
        if route_intent in {"billing_summary", "client_economic_summary", "preventivo_summary", "conferimento_summary", "unbilled_activity"}:
            return "check_payments"
        if route_intent == "template_lookup":
            return "draft_communication" if _looks_like_draft_request(text) else "consult_document"
        if route_intent in {"official_sources_lookup", "legal_update_overview"}:
            return "legal_strategy"
        return "unknown_or_ambiguous"


class StructuredContextBuilder:
    def build(
        self,
        *,
        answer: OperationalAnswer,
        question: str,
        active_context: dict[str, Any],
        detected_intent: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        rows = _rows_by_source(sources)
        latest_communications = _sort_records(
            rows.get("email_pec", []) + rows.get("email_ordinaria", []) + rows.get("messaggi", [])
        )[:8]
        reasoner = dict((answer.metadata or {}).get("studio_reasoner") or {})
        timeline = list(reasoner.get("fascicolo_timeline") or [])
        if not timeline and detected_intent == "build_case_timeline":
            timeline = _timeline_from_records(rows)
        return {
            "user_request": clean_spaces(question),
            "active_context": dict(active_context),
            "detected_intent": detected_intent,
            "client_card": _first_record(rows.get("clienti", [])),
            "case_card": _first_record(rows.get("fascicoli", [])),
            "timeline": timeline[:24],
            "latest_communications": latest_communications,
            "documents": rows.get("documenti_fascicolo", [])[:12],
            "deadlines": rows.get("scadenziario", [])[:12],
            "agenda": rows.get("agenda", [])[:12],
            "invoices": (rows.get("fatturazione", []) + rows.get("preventivi", []) + rows.get("conferimenti", []))[:12],
            "payments": rows.get("pagamenti", [])[:12],
            "retrieved_sources": [_source_summary(source) for source in sources[:60]],
            "missing_information": list(answer.coverage_gaps or []),
            "risk_flags": list(answer.warnings or []),
        }


class LexSourceVerifier:
    def verify(
        self,
        *,
        answer: OperationalAnswer,
        detected_intent: str,
        structured_context: dict[str, Any],
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        warnings = list(answer.warnings or [])
        missing = list(structured_context.get("missing_information") or [])
        source_ids = {clean_spaces(source.get("source_id")) for source in sources}
        ambiguous = []
        if answer.blocked_reason:
            warnings.append("Accesso non autorizzato o sorgente non consultabile con i permessi correnti.")
        if not sources and not answer.blocked_reason:
            missing.append("Nessuna fonte interna verificata ha restituito dati per questa richiesta.")
        if detected_intent == "check_payments" and not source_ids.intersection(_ACCOUNTING_SOURCE_IDS):
            missing.append("Nessuna fonte contabile autorizzata ha restituito fatture, parcelle o pagamenti.")
        client_options = [source for source in sources if source.get("source_id") == "clienti"]
        if len(client_options) > 1:
            ambiguous.append(
                {
                    "type": "client",
                    "message": "Più clienti compatibili: serve una scelta prima di usare i dati come certi.",
                    "options": [_source_summary(source) for source in client_options[:6]],
                }
            )
        allowed = not bool(answer.blocked_reason)
        return {
            "allowed": allowed,
            "verified": allowed and bool(sources),
            "requires_clarification": bool(ambiguous),
            "warnings": _unique(warnings),
            "missing_information": _unique(missing),
            "ambiguous_entities": ambiguous,
            "source_count": len(sources),
        }


class LexActions:
    def build(
        self,
        *,
        detected_intent: str,
        active_context: dict[str, Any],
        sources: list[dict[str, Any]],
        operational_links: list[dict[str, Any]],
        source_verification: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not source_verification.get("allowed", True):
            return []
        actions: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(key: str, label: str, *, url: str = "", prompt: str = "", icon: str = "arrow-up-right") -> None:
            token = clean_spaces(url) or clean_spaces(prompt) or key + label
            if not token or token in seen:
                return
            seen.add(token)
            action = {"key": key, "label": label, "icon": icon}
            if url:
                action["url"] = clean_spaces(url)
            if prompt:
                action["prompt"] = clean_spaces(prompt)
            actions.append(action)

        for link in list(operational_links or [])[:40]:
            label, key, icon = _action_label_for_link(link)
            add(key, label, url=link.get("url", ""), icon=icon)
        for source in sources[:20]:
            record = source.get("record") if isinstance(source.get("record"), dict) else {}
            for attachment in list(record.get("allegati") or [])[:8]:
                if not isinstance(attachment, dict):
                    continue
                add(
                    "open_attachment",
                    "Apri allegato",
                    url=clean_spaces(attachment.get("view_url") or attachment.get("download_url")),
                    icon="paperclip",
                )
        if detected_intent in {"consult_pec", "consult_email"} and any(source.get("source_id") in _COMMUNICATION_SOURCE_IDS for source in sources):
            add(
                "draft_reply",
                "Prepara bozza risposta",
                prompt="Prepara una bozza di risposta alla comunicazione selezionata usando solo le fonti interne citate.",
                icon="pencil-square",
            )
        if detected_intent in {"consult_pec", "consult_email", "summarize_case"} and (
            active_context.get("case_id") or active_context.get("linked_case_id") or any(source.get("source_id") == "fascicoli" for source in sources)
        ):
            add(
                "build_timeline",
                "Costruisci timeline",
                prompt="Costruisci la timeline del fascicolo con fonti e date interne verificabili.",
                icon="calendar-week",
            )
        if detected_intent == "check_payments":
            add(
                "verify_payments",
                "Verifica pagamenti",
                prompt="Verifica fatture, parcelle e pagamenti collegati usando solo fonti contabili interne.",
                icon="credit-card",
            )
        return actions[:10]


class LexMessageRenderer:
    def build_blocks(
        self,
        *,
        structured_context: dict[str, Any],
        actions: list[dict[str, Any]],
        source_verification: dict[str, Any],
    ) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        warnings = list(source_verification.get("warnings") or []) + list(source_verification.get("missing_information") or [])
        if warnings:
            blocks.append({"type": "warning", "title": "Controlli sui dati", "items": _unique(warnings)[:6]})
        if source_verification.get("ambiguous_entities"):
            blocks.append({"type": "warning", "title": "Dati da chiarire", "items": [item["message"] for item in source_verification["ambiguous_entities"]]})
        if structured_context.get("client_card"):
            blocks.append(_record_card("client_card", structured_context["client_card"], title="Cliente"))
        if structured_context.get("case_card"):
            blocks.append(_record_card("case_card", structured_context["case_card"], title="Fascicolo"))
        for communication in list(structured_context.get("latest_communications") or [])[:3]:
            card_type = "pec_card" if communication.get("_source_id") == "email_pec" else "email_card"
            blocks.append(_communication_card(card_type, communication))
            for attachment in list(communication.get("allegati") or [])[:6]:
                if isinstance(attachment, dict):
                    blocks.append(_attachment_card(attachment))
        if structured_context.get("timeline"):
            blocks.append({"type": "timeline", "title": "Timeline fascicolo", "items": list(structured_context["timeline"])[:12]})
        for document in list(structured_context.get("documents") or [])[:4]:
            blocks.append(_record_card("document_card", document, title="Documento"))
        for deadline in list(structured_context.get("deadlines") or [])[:4]:
            blocks.append(_record_card("deadline_card", deadline, title="Scadenza"))
        for invoice in list(structured_context.get("invoices") or [])[:4]:
            blocks.append(_record_card("invoice_card", invoice, title="Fattura o parcella"))
        for payment in list(structured_context.get("payments") or [])[:4]:
            blocks.append(_record_card("payment_card", payment, title="Pagamento"))
        if structured_context.get("retrieved_sources"):
            blocks.append({"type": "source_card", "title": "Fonti interne", "items": list(structured_context["retrieved_sources"])[:8]})
        if actions:
            blocks.append({"type": "actions", "title": "Azioni operative", "items": actions})
        return [block for block in blocks if block]


def build_lex_unified_chat(
    *,
    answer: OperationalAnswer,
    current_user_message: str,
    resolved_effective_question: str,
    studio_context: dict[str, Any],
    sources: list[dict[str, Any]],
    operational_links: list[dict[str, Any]],
) -> dict[str, Any]:
    metadata = dict(answer.metadata or {})
    active_context = dict(metadata.get("active_context") or LexContextProvider.from_payload(metadata, studio_context))
    detected_intent = IntentRouter.detect(answer, resolved_effective_question or current_user_message, active_context, sources)
    structured_context = StructuredContextBuilder().build(
        answer=answer,
        question=resolved_effective_question or current_user_message,
        active_context=active_context,
        detected_intent=detected_intent,
        sources=sources,
    )
    source_verification = LexSourceVerifier().verify(
        answer=answer,
        detected_intent=detected_intent,
        structured_context=structured_context,
        sources=sources,
    )
    actions = LexActions().build(
        detected_intent=detected_intent,
        active_context=active_context,
        sources=sources,
        operational_links=operational_links,
        source_verification=source_verification,
    )
    blocks = LexMessageRenderer().build_blocks(
        structured_context=structured_context,
        actions=actions,
        source_verification=source_verification,
    )
    return {
        "component": "LexUnifiedChat",
        "engine": "Lex Studio Reasoner",
        "surface": "operational_chat",
        "context_provider": "LexContextProvider",
        "intent_router": "IntentRouter",
        "retrieval": "GovernedRetrieval",
        "context_builder": "StructuredContextBuilder",
        "source_verifier": "LexSourceVerifier",
        "message_renderer": "LexMessageRenderer",
        "active_context": active_context,
        "detected_intent": detected_intent,
        "structured_context": structured_context,
        "source_verification": source_verification,
        "actions": actions,
        "renderer_blocks": blocks,
    }


def _first_clean(active: dict[str, Any], metadata: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = clean_spaces(active.get(key))
        if value:
            return value
        value = clean_spaces(metadata.get(key))
        if value:
            return value
    return ""


def _scope_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [clean_spaces(item) for item in value if clean_spaces(item)]
    if isinstance(value, str):
        return [clean_spaces(item) for item in value.split(",") if clean_spaces(item)]
    return []


def _looks_like_draft_request(text: str) -> bool:
    return any(token in text for token in ("scrivi", "redigi", "prepara", "bozza", "risposta"))


def _rows_by_source(sources: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        source_id = clean_spaces(source.get("source_id"))
        record = source.get("record") if isinstance(source.get("record"), dict) else {}
        if not record:
            record = {
                "id": source.get("object_id") or source.get("id"),
                "titolo": source.get("title"),
                "action_url": source.get("action_url"),
            }
        row = dict(record)
        row["_source_id"] = source_id
        row.setdefault("action_url", source.get("action_url"))
        row.setdefault("id", source.get("object_id") or source.get("id"))
        rows.setdefault(source_id, []).append(row)
    return rows


def _first_record(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return dict(rows[0]) if rows else {}


def _sort_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: clean_spaces(row.get("data") or row.get("creato_il") or row.get("date") or ""), reverse=True)


def _timeline_from_records(rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for source_id, label in (("email_pec", "PEC"), ("email_ordinaria", "Email"), ("documenti_fascicolo", "Documento"), ("scadenziario", "Scadenza"), ("agenda", "Agenda"), ("fatturazione", "Fattura")):
        for row in rows.get(source_id, [])[:12]:
            date_value = clean_spaces(row.get("data") or row.get("data_scadenza") or row.get("creato_il") or row.get("inizio"))
            if not date_value:
                continue
            events.append(
                {
                    "date": date_value,
                    "title": _record_label(row),
                    "source": label,
                    "url": clean_spaces(row.get("action_url")),
                }
            )
    return sorted(events, key=lambda row: clean_spaces(row.get("date")), reverse=True)[:24]


def _source_summary(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": clean_spaces(source.get("id")),
        "title": clean_spaces(source.get("title")),
        "source_id": clean_spaces(source.get("source_id")),
        "source_type": clean_spaces(source.get("source_type")),
        "object_type": clean_spaces(source.get("object_type")),
        "object_id": clean_spaces(source.get("object_id")),
        "url": clean_spaces(source.get("action_url")),
        "internal": bool(source.get("internal", True)),
    }


def _record_card(card_type: str, row: dict[str, Any], *, title: str) -> dict[str, Any]:
    fields = []
    for key, label in (
        ("numero", "Numero"),
        ("nome_completo", "Nome"),
        ("oggetto", "Oggetto"),
        ("stato", "Stato"),
        ("data", "Data"),
        ("data_scadenza", "Scadenza"),
        ("importo", "Importo"),
        ("id_cliente", "Cliente"),
        ("id_fascicolo", "Fascicolo"),
    ):
        value = clean_spaces(row.get(key))
        if value:
            fields.append({"label": label, "value": value})
    return {
        "type": card_type,
        "title": title,
        "subtitle": _record_label(row),
        "fields": fields[:8],
        "url": clean_spaces(row.get("action_url")),
        "source_id": clean_spaces(row.get("_source_id")),
    }


def _communication_card(card_type: str, row: dict[str, Any]) -> dict[str, Any]:
    title = "PEC" if card_type == "pec_card" else "Email"
    fields = []
    for key, label in (
        ("mittente", "Mittente"),
        ("destinatari", "Destinatari"),
        ("data", "Data"),
        ("oggetto", "Oggetto"),
        ("stato_pct", "Stato PCT"),
        ("allegati_count", "Allegati"),
    ):
        value = row.get(key)
        if isinstance(value, list):
            value = ", ".join(clean_spaces(item) for item in value if clean_spaces(item))
        value = clean_spaces(value)
        if value:
            fields.append({"label": label, "value": value})
    return {
        "type": card_type,
        "title": title,
        "subtitle": _record_label(row),
        "fields": fields,
        "url": clean_spaces(row.get("action_url")),
        "source_id": clean_spaces(row.get("_source_id")),
    }


def _attachment_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "attachment_card",
        "title": "Allegato",
        "subtitle": clean_spaces(row.get("nome")) or "Allegato email",
        "fields": [
            {"label": "Tipo", "value": clean_spaces(row.get("mime"))},
            {"label": "Dimensione", "value": clean_spaces(row.get("size"))},
        ],
        "url": clean_spaces(row.get("view_url") or row.get("download_url")),
    }


def _record_label(row: dict[str, Any]) -> str:
    for key in ("nome_completo", "titolo", "title", "oggetto", "numero", "number", "nome", "name", "descrizione", "id"):
        value = clean_spaces(row.get(key))
        if value:
            return value
    return "Elemento interno"


def _action_label_for_link(link: dict[str, Any]) -> tuple[str, str, str]:
    object_type = clean_spaces(link.get("object_type")).lower()
    source_id = clean_spaces(link.get("source_id")).lower()
    if object_type == "allegato_email":
        return "Apri allegato", "open_attachment", "paperclip"
    if source_id == "email_pec":
        return "Apri PEC", "open_pec", "envelope-check"
    if source_id == "email_ordinaria" or object_type == "email":
        return "Apri email", "open_email", "envelope"
    if object_type == "fascicolo":
        return "Apri fascicolo", "open_case", "folder2-open"
    if object_type == "cliente":
        return "Apri cliente", "open_client", "person-vcard"
    if object_type == "documento":
        return "Apri documento", "open_document", "file-earmark-text"
    if object_type == "scadenza":
        return "Apri scadenza", "open_deadline", "calendar-check"
    if object_type in {"pagamento", "parcella", "preventivo", "conferimento"} or source_id in _ACCOUNTING_SOURCE_IDS:
        return "Apri scheda economica", "open_accounting", "receipt"
    return clean_spaces(link.get("label")) or "Apri elemento", "open_item", "arrow-up-right"


def _unique(items: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for item in items:
        token = clean_spaces(item if isinstance(item, str) else repr(item))
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(item)
    return result
