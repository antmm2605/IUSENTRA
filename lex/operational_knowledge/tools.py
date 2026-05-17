"""Deterministic tools over IUSENTRA operational repositories."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable

from .models import (
    OperationalObjectReference,
    OperationalQueryContext,
    OperationalSourceReference,
    OperationalToolResult,
)
from .permission_guard import OperationalPermissionGuard
from .serializers import (
    clean_spaces,
    serialize_cliente,
    serialize_documento,
    serialize_email_attachment,
    serialize_email_message,
    serialize_fascicolo,
    serialize_generic,
    serialize_soggetto,
)
from .source_registry import OperationalSourceRegistry, build_default_registry


class OperationalKnowledgeTools:
    def __init__(
        self,
        *,
        registry: OperationalSourceRegistry | None = None,
        guard: OperationalPermissionGuard | None = None,
        repositories: dict[str, Any] | None = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.guard = guard or OperationalPermissionGuard()
        self.repositories = repositories or {}

    # ------------------------------------------------------------------
    # Public deterministic tool surface
    # ------------------------------------------------------------------

    def search_clienti(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        return self._search(
            "clienti",
            context,
            query=query,
            limit=limit,
            manager_factory=lambda: self._manager("clienti", "get_clienti"),
            search_method="cerca",
            all_method="tutti",
            serializer=serialize_cliente,
            object_type="cliente",
        )

    def get_cliente_by_id(self, cliente_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._get(
            "clienti",
            context,
            identifier=cliente_id,
            manager_factory=lambda: self._manager("clienti", "get_clienti"),
            serializer=serialize_cliente,
            object_type="cliente",
        )

    def search_soggetti(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        return self._search(
            "soggetti",
            context,
            query=query,
            limit=limit,
            manager_factory=lambda: self._manager("soggetti", "get_soggetti"),
            search_method="cerca",
            all_method="tutti",
            serializer=serialize_soggetto,
            object_type="soggetto",
        )

    def get_soggetto(self, soggetto_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._get(
            "soggetti",
            context,
            identifier=soggetto_id,
            manager_factory=lambda: self._manager("soggetti", "get_soggetti"),
            serializer=serialize_soggetto,
            object_type="soggetto",
        )

    def search_fascicoli(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        source_id = "fascicoli"
        decision = self._decision(source_id, context)
        if not decision.allowed:
            return self._blocked(source_id, decision)
        manager = self._safe_manager(source_id, lambda: self._manager("fascicoli", "get_fascicoli"))
        if manager is None:
            return self._unavailable(source_id, "Repository fascicoli non disponibile.")
        try:
            if clean_spaces(query) and hasattr(manager, "cerca"):
                rows = list(manager.cerca(query))
                if not rows:
                    try:
                        candidate_rows = list(manager.tutti(archiviati=True))
                    except TypeError:
                        candidate_rows = list(manager.tutti())
                    rows = [row for row in candidate_rows if _row_matches(serialize_fascicolo(row), query)]
            elif hasattr(manager, "tutti"):
                try:
                    rows = list(manager.tutti(archiviati=True))
                except TypeError:
                    rows = list(manager.tutti())
            else:
                rows = []
        except Exception as exc:
            return self._unavailable(source_id, f"Fascicoli non interrogabili: {exc}")
        return self._rows_result(source_id, context, rows[:limit], serialize_fascicolo, "fascicolo", decision)

    def get_fascicolo(self, fascicolo_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._get(
            "fascicoli",
            context,
            identifier=fascicolo_id,
            manager_factory=lambda: self._manager("fascicoli", "get_fascicoli"),
            serializer=serialize_fascicolo,
            object_type="fascicolo",
        )

    def get_scadenze_by_fascicolo(self, fascicolo_id: str, context: OperationalQueryContext, *, solo_aperte: bool = True) -> OperationalToolResult:
        decision = self._decision("scadenziario", context)
        if not decision.allowed:
            return self._blocked("scadenziario", decision)
        manager = self._safe_manager("scadenziario", lambda: self._manager("scadenziario", "get_scadenziario"))
        if manager is None:
            return self._unavailable("scadenziario", "Scadenziario non disponibile.")
        try:
            rows = list(manager.tutte(id_fascicolo=fascicolo_id, solo_aperte=solo_aperte))
        except Exception as exc:
            return self._unavailable("scadenziario", f"Scadenziario non interrogabile: {exc}")
        return self._rows_result("scadenziario", context, rows, serialize_generic, "scadenza", decision)

    def get_scadenze_by_cliente(self, cliente_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        fascicoli = self.fascicoli_by_cliente(cliente_id, context)
        if not fascicoli.ok:
            return fascicoli
        all_rows: list[Any] = []
        gaps = list(fascicoli.coverage_gaps)
        for fascicolo in list(fascicoli.data or []):
            result = self.get_scadenze_by_fascicolo(str(fascicolo.get("id") or ""), context)
            if result.ok:
                all_rows.extend(result.data or [])
            gaps.extend(result.coverage_gaps)
        result = self._plain_result("scadenziario", context, all_rows, "scadenza")
        result.coverage_gaps.extend(gaps)
        return result

    def get_agenda_range(
        self,
        context: OperationalQueryContext,
        *,
        start: date | None = None,
        end: date | None = None,
        cliente_id: str = "",
        limit: int = 30,
    ) -> OperationalToolResult:
        decision = self._decision("agenda", context)
        if not decision.allowed:
            return self._blocked("agenda", decision)
        manager = self._safe_manager("agenda", lambda: self._manager("agenda", "get_agenda"))
        if manager is None:
            return self._unavailable("agenda", "Agenda non disponibile.")
        try:
            if cliente_id and hasattr(manager, "per_cliente"):
                rows = list(manager.per_cliente(cliente_id))
            elif start and end:
                rows = [row for row in list(manager.tutti()) if _date_in_range(_row_date(row), start, end)]
            else:
                rows = list(manager.tutti())
        except Exception as exc:
            return self._unavailable("agenda", f"Agenda non interrogabile: {exc}")
        rows = sorted(rows, key=lambda row: _row_date(row) or date.max)[:limit]
        return self._rows_result("agenda", context, rows, serialize_generic, "appuntamento", decision)

    def search_agenda(
        self,
        query: str,
        context: OperationalQueryContext,
        *,
        limit: int = 30,
        latest: bool = False,
    ) -> OperationalToolResult:
        decision = self._decision("agenda", context)
        if not decision.allowed:
            return self._blocked("agenda", decision)
        manager = self._safe_manager("agenda", lambda: self._manager("agenda", "get_agenda"))
        if manager is None:
            return self._unavailable("agenda", "Agenda non disponibile.")
        try:
            rows = list(manager.tutti())
        except Exception as exc:
            return self._unavailable("agenda", f"Agenda non interrogabile: {exc}")

        text = clean_spaces(query).lower()
        wants_udienze = "udienz" in text
        filtered = []
        for row in rows:
            payload = serialize_generic(row)
            row_type = clean_spaces(payload.get("tipo")).lower()
            haystack = clean_spaces(" ".join(str(value) for value in payload.values())).lower()
            if wants_udienze and ("udienz" in row_type or "udienz" in haystack):
                filtered.append(row)
                continue
            if not wants_udienze and _row_matches(payload, query):
                filtered.append(row)
        filtered.sort(key=lambda row: _row_date(row) or date.min, reverse=latest)
        return self._rows_result("agenda", context, filtered[:limit], serialize_generic, "appuntamento", decision)

    def search_preventivi(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        decision = self._decision("preventivi", context)
        if not decision.allowed:
            return self._blocked("preventivi", decision)
        manager = self._safe_manager("preventivi", lambda: self._manager("preventivi", "get_preventivi"))
        if manager is None:
            return self._unavailable("preventivi", "Repository preventivi non disponibile.")
        rows = list(_call(manager, "tutti_preventivi") or [])
        return self._filter_text_rows("preventivi", context, rows, query, limit, decision, "preventivo")

    def get_preventivo(self, preventivo_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._get(
            "preventivi",
            context,
            identifier=preventivo_id,
            manager_factory=lambda: self._manager("preventivi", "get_preventivi"),
            get_method="get_preventivo",
            serializer=serialize_generic,
            object_type="preventivo",
        )

    def search_conferimenti(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        decision = self._decision("conferimenti", context)
        if not decision.allowed:
            return self._blocked("conferimenti", decision)
        manager = self._safe_manager("conferimenti", lambda: self._manager("preventivi", "get_preventivi"))
        if manager is None:
            return self._unavailable("conferimenti", "Repository conferimenti non disponibile.")
        rows = list(_call(manager, "tutti_conferimenti") or [])
        return self._filter_text_rows("conferimenti", context, rows, query, limit, decision, "conferimento")

    def get_conferimento(self, conferimento_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._get(
            "conferimenti",
            context,
            identifier=conferimento_id,
            manager_factory=lambda: self._manager("preventivi", "get_preventivi"),
            get_method="get_conferimento",
            serializer=serialize_generic,
            object_type="conferimento",
        )

    def get_tariffario_result(self, context: OperationalQueryContext, **filters: Any) -> OperationalToolResult:
        decision = self._decision("tariffario", context)
        if not decision.allowed:
            return self._blocked("tariffario", decision)
        materia = clean_spaces(filters.get("materia"))
        grado = clean_spaces(filters.get("grado"))
        valore = filters.get("valore")
        if not (materia and grado and valore):
            return OperationalToolResult(
                False,
                "tariffario",
                data={"required_fields": ["materia", "grado", "valore"]},
                sources=[self._source_ref("tariffario", context, object_type="tariffario", title="Tariffario forense", confidence=0.74)],
                coverage_gaps=["Per calcolare il compenso servono almeno materia, grado e valore/scaglione."],
                permission=decision,
            )
        try:
            from pct.tariffario import calcola_compenso

            result = calcola_compenso(materia=materia, grado=grado, valore=valore, fasi=filters.get("fasi") or None)
            payload = result.to_dict() if hasattr(result, "to_dict") else serialize_generic(result)
            return OperationalToolResult(
                True,
                "tariffario",
                data=payload,
                sources=[self._source_ref("tariffario", context, object_type="tariffario", title="Calcolo tariffario forense", confidence=0.82)],
                permission=decision,
            )
        except Exception as exc:
            return self._unavailable("tariffario", f"Calcolo tariffario non disponibile: {exc}")

    def get_parcelle_by_cliente(self, cliente_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_by_method("fatturazione", context, "get_fatturazione", "per_cliente", cliente_id, "parcella")

    def get_parcelle_by_fascicolo(self, fascicolo_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_by_method("fatturazione", context, "get_fatturazione", "per_fascicolo", fascicolo_id, "parcella")

    def get_attivita_by_cliente(self, cliente_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_by_method("timesheet", context, "get_timesheet", "per_cliente", cliente_id, "attivita")

    def get_attivita_by_fascicolo(self, fascicolo_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_by_method("timesheet", context, "get_timesheet", "per_fascicolo", fascicolo_id, "attivita")

    def fascicoli_by_cliente(self, cliente_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision("fascicoli", context)
        if not decision.allowed:
            return self._blocked("fascicoli", decision)
        manager = self._safe_manager("fascicoli", lambda: self._manager("fascicoli", "get_fascicoli"))
        if manager is None:
            return self._unavailable("fascicoli", "Repository fascicoli non disponibile.")
        try:
            try:
                rows = list(manager.tutti(archiviati=True))
            except TypeError:
                rows = list(manager.tutti())
            rows = [row for row in rows if clean_spaces(getattr(row, "id_cliente", "") or _dict_get(row, "id_cliente")) == clean_spaces(cliente_id)]
        except Exception as exc:
            return self._unavailable("fascicoli", f"Fascicoli non interrogabili: {exc}")
        return self._rows_result("fascicoli", context, rows, serialize_fascicolo, "fascicolo", decision)

    def get_documenti_fascicolo(self, fascicolo_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision("documenti_fascicolo", context)
        if not decision.allowed:
            return self._blocked("documenti_fascicolo", decision)
        fascicolo_result = self.get_fascicolo(fascicolo_id, context)
        if not fascicolo_result.ok or not fascicolo_result.data:
            return OperationalToolResult(
                False,
                "documenti_fascicolo",
                coverage_gaps=["Fascicolo non trovato o non accessibile."],
                permission=decision,
            )
        manager = self._safe_manager("fascicoli", lambda: self._manager("fascicoli", "get_fascicoli"))
        fascicolo = getattr(manager, "get", lambda _id: None)(fascicolo_id) if manager is not None else None
        docs = list(getattr(fascicolo, "documenti", []) or [])
        rows = [serialize_documento(item) for item in docs]
        rows.extend(self._document_ai_rows(fascicolo_id, context))
        result = self._plain_result("documenti_fascicolo", context, rows, "documento")
        if not rows:
            result.coverage_gaps.append("Nessun documento collegato o indicizzato per il fascicolo.")
        return result

    def search_documenti_fascicolo(
        self,
        fascicolo_id: str,
        query: str,
        context: OperationalQueryContext,
        *,
        limit: int = 12,
    ) -> OperationalToolResult:
        docs = self.get_documenti_fascicolo(fascicolo_id, context)
        if not docs.ok:
            return docs
        terms = _terms(query)
        rows = []
        for row in list(docs.data or []):
            haystack = clean_spaces(" ".join(str(value) for value in dict(row).values())).lower()
            if not terms or all(term in haystack for term in terms):
                rows.append(row)
        docs.data = rows[:limit]
        if not rows:
            docs.coverage_gaps.append("Nessun documento citabile contiene i termini richiesti.")
        return docs

    def get_messaggi_by_cliente(self, cliente_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_by_method("messaggi", context, "get_messaggi", "per_cliente", cliente_id, "messaggio")

    def get_messaggi_by_fascicolo(self, fascicolo_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_by_method("messaggi", context, "get_messaggi", "per_fascicolo", fascicolo_id, "messaggio")

    def list_pec_messages(
        self,
        context: OperationalQueryContext,
        *,
        query: str = "",
        folder: str = "",
        con_allegati: bool = False,
        limit: int = 20,
    ) -> OperationalToolResult:
        return self._list_email_messages(
            "email_pec",
            context,
            query=query,
            folder=folder,
            con_allegati=con_allegati,
            limit=limit,
        )

    def get_pec_message(self, email_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._get_email_message("email_pec", email_id, context)

    def list_pec_attachments(self, email_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_email_attachments("email_pec", email_id, context)

    def list_ordinary_email_messages(
        self,
        context: OperationalQueryContext,
        *,
        query: str = "",
        folder: str = "",
        con_allegati: bool = False,
        limit: int = 20,
    ) -> OperationalToolResult:
        return self._list_email_messages(
            "email_ordinaria",
            context,
            query=query,
            folder=folder,
            con_allegati=con_allegati,
            limit=limit,
        )

    def get_ordinary_email_message(self, email_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._get_email_message("email_ordinaria", email_id, context)

    def list_ordinary_email_attachments(self, email_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_email_attachments("email_ordinaria", email_id, context)

    def get_notifiche_utente(self, context: OperationalQueryContext, *, limit: int = 20) -> OperationalToolResult:
        decision = self._decision("notifiche", context)
        if not decision.allowed:
            return self._blocked("notifiche", decision)
        try:
            from web.services.notifications_runtime import build_notification_repository

            repo = self.repositories.get("notifiche") or build_notification_repository()
            rows = repo.list_notifications(context.tenant_id or "default", context.user_id, limit=limit)
        except Exception as exc:
            return self._unavailable("notifiche", f"Notifiche non disponibili: {exc}")
        return self._rows_result("notifiche", context, rows, serialize_generic, "notifica", decision)

    def search_template_atti(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        decision = self._decision("template_atti", context)
        if not decision.allowed:
            return self._blocked("template_atti", decision)
        manager = self._safe_manager("template_atti", self._template_manager)
        if manager is None:
            return self._unavailable("template_atti", "Repository template atti non disponibile.")
        try:
            rows = list(_call(manager, "select_best_templates", query, limit=limit) or [])
            if not rows:
                rows = list(_call(manager, "tutti") or [])
        except Exception as exc:
            return self._unavailable("template_atti", f"Template atti non interrogabili: {exc}")
        return self._filter_text_rows("template_atti", context, rows, query, limit, decision, "template_atto")

    def get_editor_ai_status(self, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision("editor_ai", context)
        if not decision.allowed:
            return self._blocked("editor_ai", decision)
        row = {
            "id": "editor_ai",
            "titolo": "Editor normale e professionale con Lex",
            "stato": "attivo",
            "capabilities": [
                "bootstrap contestuale sul fascicolo",
                "selezione template reali",
                "generazione bozza nell'editor professionale",
                "rilettura documento editor",
                "proposte di modifica pending",
                "export governato",
            ],
            "tools": [
                "list_template_atti",
                "read_template_atto",
                "collect_fascicolo_context",
                "generate_editor_draft",
                "read_editor_document",
                "propose_editor_edits",
                "export_editor_document",
            ],
            "warnings": [
                "Lex non deve presentare la bozza come conforme automaticamente.",
                "Le modifiche restano in attesa finche' l'utente non le accetta o rifiuta.",
            ],
        }
        return self._plain_result("editor_ai", context, [row], "editor_ai")

    def get_legal_intelligence_items(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        decision = self._decision("legal_intelligence", context)
        if not decision.allowed:
            return self._blocked("legal_intelligence", decision)
        try:
            manager = self._manager("legal_intelligence", "get_legal_intelligence")
            alerts = list(_call(manager, "recent_alerts", limit=limit) or [])
            fonti = list(_call(manager, "catalogo_fonti") or [])[:limit]
            rows = [{"kind": "alert", **serialize_generic(item)} for item in alerts]
            rows.extend({"kind": "fonte", **serialize_generic(item)} for item in fonti)
        except Exception as exc:
            return self._unavailable("legal_intelligence", f"Legal intelligence non disponibile: {exc}")
        return self._plain_result("legal_intelligence", context, rows[:limit], "legal_intelligence")

    def get_update_intelligence_items(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        decision = self._decision("update_intelligence", context)
        if not decision.allowed:
            return self._blocked("update_intelligence", decision)
        try:
            from web.helpers import get_legal_update_pipeline

            pipeline = self.repositories.get("update_intelligence") or get_legal_update_pipeline()
            repo = getattr(pipeline, "repo", None) or getattr(pipeline, "repository", None)
            if repo is not None and hasattr(repo, "search_lex_sources"):
                rows = list(repo.search_lex_sources(query, limit=limit))
            else:
                snapshot = _call(pipeline, "dashboard_snapshot") or {}
                rows = list((snapshot if isinstance(snapshot, dict) else {}).get("recent_news") or [])[:limit]
        except Exception as exc:
            return self._unavailable("update_intelligence", f"Update intelligence non disponibile: {exc}")
        return self._plain_result("update_intelligence", context, [serialize_generic(item) for item in rows], "update_intelligence")

    def search_legal_sources(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        decision = self._decision("fonti_ufficiali", context)
        if not decision.allowed:
            return self._blocked("fonti_ufficiali", decision)
        try:
            from lex.legal_sources.tools import search_legal_sources

            payload = search_legal_sources(query, limit=limit)
            rows = list(((payload.get("data") or {}).get("passages")) or [])
        except Exception as exc:
            return self._unavailable("fonti_ufficiali", f"Fonti ufficiali non disponibili: {exc}")
        result = self._plain_result("fonti_ufficiali", context, rows, "fonte_ufficiale")
        if not rows:
            result.coverage_gaps.append("Nessuna fonte ufficiale citabile trovata nell'indice locale configurato.")
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _decision(self, source_id: str, context: OperationalQueryContext):
        source = self.registry.get(source_id)
        if source is None:
            from .models import PermissionDecision

            return PermissionDecision(False, source_id, reason="source_not_registered")
        return self.guard.check_source(context, source)

    def _blocked(self, source_id: str, decision) -> OperationalToolResult:
        return OperationalToolResult(
            False,
            source_id,
            coverage_gaps=[f"Accesso a {source_id} non consentito."],
            permission=decision,
            blocked_reason=decision.reason,
        )

    def _unavailable(self, source_id: str, message: str) -> OperationalToolResult:
        return OperationalToolResult(False, source_id, coverage_gaps=[message], blocked_reason="source_unavailable")

    def _manager(self, source_id: str, helper_name: str) -> Any:
        if source_id in self.repositories:
            return self.repositories[source_id]
        if helper_name == "get_messaggi":
            from flask import current_app
            from pct.messaggi import GestioneMessaggi
            from web.services.tenant_paths import tenant_data_path

            db_path = tenant_data_path("MESSAGGI_DB", current_app.config.get("MESSAGGI_DB", ""), require_tenant=True)
            return GestioneMessaggi(config=None, db_path=db_path)
        if helper_name == "get_email_pec":
            return self._email_manager("email_pec")
        if helper_name == "get_email_ordinaria":
            return self._email_manager("email_ordinaria")
        from web import helpers

        helper = getattr(helpers, helper_name)
        return helper()

    def _safe_manager(self, source_id: str, factory: Callable[[], Any]) -> Any | None:
        if source_id in self.repositories:
            return self.repositories[source_id]
        try:
            return factory()
        except Exception:
            return None

    def _template_manager(self) -> Any:
        if "template_atti" in self.repositories:
            return self.repositories["template_atti"]
        try:
            from flask import current_app
            from pct.template_atti import GestioneTemplateAtti
            from web.services.tenant_paths import tenant_data_path

            db_path = tenant_data_path("TEMPLATE_ATTI_DB", current_app.config.get("TEMPLATE_ATTI_DB", ""), require_tenant=True)
            return GestioneTemplateAtti(db_path=db_path)
        except Exception:
            return None

    def _list_by_method(
        self,
        source_id: str,
        context: OperationalQueryContext,
        helper_name: str,
        method_name: str,
        identifier: str,
        object_type: str,
    ) -> OperationalToolResult:
        decision = self._decision(source_id, context)
        if not decision.allowed:
            return self._blocked(source_id, decision)
        manager = self._safe_manager(source_id, lambda: self._manager(source_id, helper_name))
        if manager is None:
            return self._unavailable(source_id, f"Repository {source_id} non disponibile.")
        try:
            rows = list(_call(manager, method_name, identifier) or [])
        except Exception as exc:
            return self._unavailable(source_id, f"Sorgente {source_id} non interrogabile: {exc}")
        return self._rows_result(source_id, context, rows, serialize_generic, object_type, decision)

    def _email_manager(self, source_id: str) -> Any:
        if source_id in self.repositories:
            return self.repositories[source_id]
        from flask import current_app
        from pct.email_client import GestioneEmailRicevute
        from web.services.tenant_paths import tenant_data_path

        key = "EMAIL_CASELLA_DB" if source_id == "email_pec" else "EMAIL_ORDINARIA_DB"
        db_path = tenant_data_path(key, current_app.config.get(key, ""), require_tenant=True)
        return GestioneEmailRicevute(db_path=db_path)

    def _list_email_messages(
        self,
        source_id: str,
        context: OperationalQueryContext,
        *,
        query: str = "",
        folder: str = "",
        con_allegati: bool = False,
        limit: int = 20,
    ) -> OperationalToolResult:
        decision = self._decision(source_id, context)
        if not decision.allowed:
            return self._blocked(source_id, decision)
        manager = self._safe_manager(source_id, lambda: self._email_manager(source_id))
        if manager is None:
            return self._unavailable(source_id, f"Casella {source_id} non disponibile.")
        try:
            rows = list(
                manager.tutte(
                    cartella=folder or None,
                    q=query,
                    con_allegati=con_allegati,
                )
            )[: max(1, int(limit or 20))]
        except Exception as exc:
            return self._unavailable(source_id, f"Casella {source_id} non interrogabile: {exc}")
        return self._rows_result(source_id, context, rows, serialize_email_message, "email", decision)

    def _get_email_message(self, source_id: str, email_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision(source_id, context)
        if not decision.allowed:
            return self._blocked(source_id, decision)
        manager = self._safe_manager(source_id, lambda: self._email_manager(source_id))
        if manager is None:
            return self._unavailable(source_id, f"Casella {source_id} non disponibile.")
        try:
            row = getattr(manager, "get", lambda _id: None)(email_id)
            if row is None:
                for candidate in list(getattr(manager, "tutte")()):
                    if clean_spaces(getattr(candidate, "id", "") or _dict_get(candidate, "id")) == clean_spaces(email_id):
                        row = candidate
                        break
        except Exception as exc:
            return self._unavailable(source_id, f"Casella {source_id} non interrogabile: {exc}")
        if row is None:
            return OperationalToolResult(False, source_id, coverage_gaps=["Email non trovata nella casella autorizzata."], permission=decision)
        return self._rows_result(
            source_id,
            context,
            [row],
            lambda item: serialize_email_message(item, include_body=True),
            "email",
            decision,
        )

    def _list_email_attachments(self, source_id: str, email_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision(source_id, context)
        if not decision.allowed:
            return self._blocked(source_id, decision)
        manager = self._safe_manager(source_id, lambda: self._email_manager(source_id))
        if manager is None:
            return self._unavailable(source_id, f"Casella {source_id} non disponibile.")
        try:
            row = getattr(manager, "get", lambda _id: None)(email_id)
            if row is None:
                for candidate in list(getattr(manager, "tutte")()):
                    if clean_spaces(getattr(candidate, "id", "") or _dict_get(candidate, "id")) == clean_spaces(email_id):
                        row = candidate
                        break
            if row is None:
                return OperationalToolResult(False, source_id, coverage_gaps=["Email non trovata nella casella autorizzata."], permission=decision)
            attachments = []
            for index, attachment in enumerate(list(getattr(row, "allegati", []) or [])):
                available = bool(getattr(manager, "allegato_disponibile", lambda *_args: False)(row, index))
                attachments.append(serialize_email_attachment(attachment, index=index, available=available))
        except Exception as exc:
            return self._unavailable(source_id, f"Allegati {source_id} non interrogabili: {exc}")
        result = self._plain_result(source_id, context, attachments, "allegato_email")
        result.permission = decision
        if not attachments:
            result.coverage_gaps.append("Nessun allegato disponibile per questa email.")
        return result

    def _search(
        self,
        source_id: str,
        context: OperationalQueryContext,
        *,
        query: str,
        limit: int,
        manager_factory: Callable[[], Any],
        search_method: str,
        all_method: str,
        serializer: Callable[[Any], dict[str, Any]],
        object_type: str,
    ) -> OperationalToolResult:
        decision = self._decision(source_id, context)
        if not decision.allowed:
            return self._blocked(source_id, decision)
        manager = self._safe_manager(source_id, manager_factory)
        if manager is None:
            return self._unavailable(source_id, f"Repository {source_id} non disponibile.")
        try:
            if clean_spaces(query) and hasattr(manager, search_method):
                rows = list(getattr(manager, search_method)(query))
                if not rows and hasattr(manager, all_method):
                    rows = [
                        row
                        for row in list(getattr(manager, all_method)())
                        if _row_matches(serializer(row), query)
                    ]
            else:
                rows = list(getattr(manager, all_method)())
        except Exception as exc:
            return self._unavailable(source_id, f"Sorgente {source_id} non interrogabile: {exc}")
        return self._rows_result(source_id, context, rows[:limit], serializer, object_type, decision)

    def _get(
        self,
        source_id: str,
        context: OperationalQueryContext,
        *,
        identifier: str,
        manager_factory: Callable[[], Any],
        serializer: Callable[[Any], dict[str, Any]],
        object_type: str,
        get_method: str = "get",
    ) -> OperationalToolResult:
        decision = self._decision(source_id, context)
        if not decision.allowed:
            return self._blocked(source_id, decision)
        manager = self._safe_manager(source_id, manager_factory)
        if manager is None:
            return self._unavailable(source_id, f"Repository {source_id} non disponibile.")
        try:
            row = getattr(manager, get_method)(identifier)
        except Exception as exc:
            return self._unavailable(source_id, f"Sorgente {source_id} non interrogabile: {exc}")
        if row is None:
            return OperationalToolResult(
                False,
                source_id,
                data=None,
                coverage_gaps=[f"Nessun {object_type} trovato per l'identificativo indicato."],
                permission=decision,
            )
        return self._rows_result(source_id, context, [row], serializer, object_type, decision)

    def _rows_result(
        self,
        source_id: str,
        context: OperationalQueryContext,
        rows: list[Any],
        serializer: Callable[[Any], dict[str, Any]],
        object_type: str,
        decision,
    ) -> OperationalToolResult:
        allowed_rows = [row for row in rows if self.guard.record_belongs_to_tenant(context, row)]
        data = [serializer(row) for row in allowed_rows]
        result = self._plain_result(source_id, context, data, object_type)
        result.permission = decision
        if len(allowed_rows) < len(rows):
            result.coverage_gaps.append("Alcuni risultati sono stati esclusi per tenant diverso.")
        if not data:
            result.coverage_gaps.append(f"Nessun dato reale disponibile dalla sorgente {source_id}.")
        return result

    def _plain_result(self, source_id: str, context: OperationalQueryContext, data: list[dict[str, Any]], object_type: str) -> OperationalToolResult:
        sources = [
            self._source_ref(
                source_id,
                context,
                object_type=object_type,
                object_id=clean_spaces(row.get("id") or row.get("numero") or ""),
                title=clean_spaces(row.get("nome_completo") or row.get("titolo") or row.get("oggetto") or row.get("numero") or row.get("nome") or ""),
                confidence=0.82 if data else 0.35,
            )
            for row in data[:20]
        ]
        objects = [
            OperationalObjectReference(
                object_type=object_type,
                object_id=clean_spaces(row.get("id") or row.get("numero") or ""),
                label=clean_spaces(row.get("nome_completo") or row.get("titolo") or row.get("oggetto") or row.get("numero") or row.get("nome") or ""),
                source_id=source_id,
            )
            for row in data[:20]
        ]
        return OperationalToolResult(bool(data), source_id, data=data, sources=sources, objects=objects)

    def _filter_text_rows(
        self,
        source_id: str,
        context: OperationalQueryContext,
        rows: list[Any],
        query: str,
        limit: int,
        decision,
        object_type: str,
    ) -> OperationalToolResult:
        terms = _terms(query)
        filtered = []
        for row in rows:
            payload = serialize_generic(row)
            if not terms or _row_matches(payload, query):
                filtered.append(row)
        return self._rows_result(source_id, context, filtered[:limit], serialize_generic, object_type, decision)

    def _source_ref(
        self,
        source_id: str,
        context: OperationalQueryContext,
        *,
        object_type: str,
        object_id: str = "",
        title: str = "",
        confidence: float = 0.0,
    ) -> OperationalSourceReference:
        source = self.registry.get(source_id)
        permission = ""
        if source and source.required_permissions:
            permission = ", ".join(source.required_permissions)
        return OperationalSourceReference(
            source_id=source_id,
            source_name=source.display_name if source else source_id,
            source_type=source.source_type if source else source_id,
            object_type=object_type,
            object_id=object_id,
            title=title,
            confidence=confidence,
            internal=bool(source.internal if source else True),
            permission_applied=permission or "ai.usa",
            metadata={"tenant_id": context.tenant_id},
        )

    def _document_ai_rows(self, fascicolo_id: str, context: OperationalQueryContext) -> list[dict[str, Any]]:
        try:
            from flask import current_app
            from pct.document_intelligence.repository import DocumentAIRepository
            from pct.document_intelligence.service import DocumentAIService
            from web.helpers import get_fascicoli
            from web.services.tenant_paths import tenant_data_path

            fascicoli_db = tenant_data_path("FASCICOLI_DB", current_app.config.get("FASCICOLI_DB", ""), require_tenant=True)
            repository = self.repositories.get("documenti_ai") or DocumentAIRepository.from_fascicoli_db(fascicoli_db)
            service = DocumentAIService(repository, get_fascicoli())
            rows = service.list_fascicolo_documents(context.tenant_id or "default", fascicolo_id, context.user)
            return [serialize_documento(row) for row in rows]
        except Exception:
            return []


def _call(obj: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(obj, method_name, None)
    if not callable(method):
        return None
    return method(*args, **kwargs)


def _dict_get(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return ""


def _terms(query: str) -> list[str]:
    return [term for term in clean_spaces(query).lower().split() if len(term) >= 2][:8]


def _row_matches(payload: dict[str, Any], query: str) -> bool:
    terms = _terms(query)
    haystack = clean_spaces(" ".join(str(value) for value in payload.values())).lower()
    return not terms or all(term in haystack for term in terms)


def _row_date(row: Any) -> date | None:
    for key in ("data_ora", "inizio", "quando", "data", "data_scadenza", "scadenza"):
        value = getattr(row, key, "") if not isinstance(row, dict) else row.get(key)
        text = clean_spaces(value)
        if not text:
            continue
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except Exception:
            pass
        for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(text[:10], pattern).date()
            except Exception:
                continue
    return None


def _date_in_range(value: date | None, start: date, end: date) -> bool:
    if value is None:
        return False
    return start <= value <= end


def current_week_range() -> tuple[date, date]:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)
