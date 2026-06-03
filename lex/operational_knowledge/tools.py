"""Deterministic tools over IUSENTRA operational repositories."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
import re
from typing import Any

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
    serialize_parte_processuale,
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
            manager_factory=lambda: self._manager("clienti", "get_clienti", context),
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
            manager_factory=lambda: self._manager("clienti", "get_clienti", context),
            serializer=serialize_cliente,
            object_type="cliente",
        )

    def search_soggetti(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        return self._search(
            "soggetti",
            context,
            query=query,
            limit=limit,
            manager_factory=lambda: self._manager("soggetti", "get_soggetti", context),
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
            manager_factory=lambda: self._manager("soggetti", "get_soggetti", context),
            serializer=serialize_soggetto,
            object_type="soggetto",
        )

    def parti_by_fascicolo(self, fascicolo_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision("soggetti", context)
        if not decision.allowed:
            return self._blocked("soggetti", decision)
        manager = self._safe_manager("soggetti", lambda: self._manager("soggetti", "get_soggetti", context))
        if manager is None:
            return self._unavailable("soggetti", "Repository soggetti e parti non disponibile.")
        try:
            rows = list(_call(manager, "parti_fascicolo", fascicolo_id) or [])
        except Exception as exc:
            return self._unavailable("soggetti", f"Parti del fascicolo non interrogabili: {exc}")
        payload = [
            serialize_parte_processuale({"id_fascicolo": fascicolo_id, "parte": row[0], "soggetto": row[1]})
            for row in rows
            if self._party_belongs_to_tenant(context, row)
        ]
        result = self._plain_result("soggetti", context, payload, "parte")
        result.permission = decision
        if len(payload) < len(rows):
            result.coverage_gaps.append("Alcune parti sono state escluse per tenant diverso.")
        if not payload:
            result.coverage_gaps.append("Nessuna parte processuale reale collegata al fascicolo.")
        return result

    def parti_by_soggetto(self, soggetto_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision("soggetti", context)
        if not decision.allowed:
            return self._blocked("soggetti", decision)
        manager = self._safe_manager("soggetti", lambda: self._manager("soggetti", "get_soggetti", context))
        if manager is None:
            return self._unavailable("soggetti", "Repository soggetti e parti non disponibile.")
        try:
            fascicolo_ids = list(_call(manager, "fascicoli_con_soggetto", soggetto_id) or [])
            rows: list[dict[str, Any]] = []
            for fascicolo_id in fascicolo_ids:
                for parte, soggetto in list(_call(manager, "parti_fascicolo", fascicolo_id) or []):
                    current_id = clean_spaces(getattr(soggetto, "id", "") or _dict_get(soggetto, "id"))
                    if current_id == clean_spaces(soggetto_id):
                        rows.append({"id_fascicolo": fascicolo_id, "parte": parte, "soggetto": soggetto})
        except Exception as exc:
            return self._unavailable("soggetti", f"Ruoli del soggetto non interrogabili: {exc}")
        payload = [serialize_parte_processuale(row) for row in rows if self._party_belongs_to_tenant(context, (row.get("parte"), row.get("soggetto")))]
        result = self._plain_result("soggetti", context, payload, "parte")
        result.permission = decision
        if not payload:
            result.coverage_gaps.append("Nessun ruolo processuale reale collegato al soggetto.")
        return result

    def search_fascicoli(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        source_id = "fascicoli"
        decision = self._decision(source_id, context)
        if not decision.allowed:
            return self._blocked(source_id, decision)
        manager = self._safe_manager(source_id, lambda: self._manager("fascicoli", "get_fascicoli", context))
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
            manager_factory=lambda: self._manager("fascicoli", "get_fascicoli", context),
            serializer=serialize_fascicolo,
            object_type="fascicolo",
        )

    def get_scadenze_by_fascicolo(self, fascicolo_id: str, context: OperationalQueryContext, *, solo_aperte: bool = True) -> OperationalToolResult:
        decision = self._decision("scadenziario", context)
        if not decision.allowed:
            return self._blocked("scadenziario", decision)
        manager = self._safe_manager("scadenziario", lambda: self._manager("scadenziario", "get_scadenziario", context))
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
        manager = self._safe_manager("agenda", lambda: self._manager("agenda", "get_agenda", context))
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
        manager = self._safe_manager("agenda", lambda: self._manager("agenda", "get_agenda", context))
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
        manager = self._safe_manager("preventivi", lambda: self._manager("preventivi", "get_preventivi", context))
        if manager is None:
            return self._unavailable("preventivi", "Repository preventivi non disponibile.")
        rows = list(_call(manager, "tutti_preventivi") or [])
        return self._filter_text_rows("preventivi", context, rows, query, limit, decision, "preventivo")

    def get_preventivo(self, preventivo_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._get(
            "preventivi",
            context,
            identifier=preventivo_id,
            manager_factory=lambda: self._manager("preventivi", "get_preventivi", context),
            get_method="get_preventivo",
            serializer=serialize_generic,
            object_type="preventivo",
        )

    def search_conferimenti(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        decision = self._decision("conferimenti", context)
        if not decision.allowed:
            return self._blocked("conferimenti", decision)
        manager = self._safe_manager("conferimenti", lambda: self._manager("preventivi", "get_preventivi", context))
        if manager is None:
            return self._unavailable("conferimenti", "Repository conferimenti non disponibile.")
        rows = list(_call(manager, "tutti_conferimenti") or [])
        return self._filter_text_rows("conferimenti", context, rows, query, limit, decision, "conferimento")

    def get_conferimento(self, conferimento_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._get(
            "conferimenti",
            context,
            identifier=conferimento_id,
            manager_factory=lambda: self._manager("preventivi", "get_preventivi", context),
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

    def get_pagamenti_status(
        self,
        context: OperationalQueryContext,
        *,
        cliente_id: str = "",
        parcella_id: str = "",
        limit: int = 20,
    ) -> OperationalToolResult:
        decision = self._decision("pagamenti", context)
        if not decision.allowed:
            return self._blocked("pagamenti", decision)
        manager = self._safe_manager("pagamenti", lambda: self._manager("pagamenti", "get_pagamenti", context))
        if manager is None:
            return self._unavailable("pagamenti", "Repository pagamenti non disponibile.")
        try:
            if cliente_id and hasattr(manager, "link_per_cliente"):
                rows = list(manager.link_per_cliente(cliente_id))
            elif parcella_id and hasattr(manager, "link_per_parcella"):
                rows = list(manager.link_per_parcella(parcella_id))
            elif hasattr(manager, "tutti_link"):
                rows = list(manager.tutti_link())
            else:
                rows = []
        except Exception as exc:
            return self._unavailable("pagamenti", f"Pagamenti non interrogabili: {exc}")
        return self._rows_result("pagamenti", context, rows[: max(1, int(limit or 20))], serialize_generic, "pagamento", decision)

    def get_attivita_by_cliente(self, cliente_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_by_method("timesheet", context, "get_timesheet", "per_cliente", cliente_id, "attivita")

    def get_attivita_by_fascicolo(self, fascicolo_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        return self._list_by_method("timesheet", context, "get_timesheet", "per_fascicolo", fascicolo_id, "attivita")

    def fascicoli_by_cliente(self, cliente_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision("fascicoli", context)
        if not decision.allowed:
            return self._blocked("fascicoli", decision)
        manager = self._safe_manager("fascicoli", lambda: self._manager("fascicoli", "get_fascicoli", context))
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
        manager = self._safe_manager("fascicoli", lambda: self._manager("fascicoli", "get_fascicoli", context))
        fascicolo = getattr(manager, "get", lambda _id: None)(fascicolo_id) if manager is not None else None
        docs = list(getattr(fascicolo, "documenti", []) or [])
        rows = [serialize_documento(item) for item in docs]
        for index, row in enumerate(rows[:12]):
            if _document_ai_excerpt(row.get("anteprima") or row.get("summary") or row.get("content") or row.get("text")):
                continue
            extracted = self._document_file_row(manager, fascicolo_id, docs[index])
            if extracted:
                row.update(extracted)
        rows.extend(self._document_ai_rows(fascicolo_id, context))
        for row in rows:
            row.setdefault("id_fascicolo", fascicolo_id)
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

    def list_pec_audit_messages(self, context: OperationalQueryContext, *, query: str = "", limit: int = 20) -> OperationalToolResult:
        decision = self._decision("pec_audit", context)
        if not decision.allowed:
            return self._blocked("pec_audit", decision)
        repo = self._pec_audit_repository()
        if repo is None:
            return self._unavailable("pec_audit", "Controlli automatici PEC non ancora disponibili.")
        try:
            rows = [_serialize_pec_audit_detail(row) for row in repo.list_messages(limit=limit, q=query)]
        except Exception as exc:
            return self._unavailable("pec_audit", f"Controlli PEC non interrogabili: {exc}")
        result = self._plain_result("pec_audit", context, rows, "pec_audit")
        result.permission = decision
        if not rows:
            result.coverage_gaps.append("Nessun controllo PEC audit-grade disponibile.")
        return result

    def get_pec_audit_message(self, message_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision("pec_audit", context)
        if not decision.allowed:
            return self._blocked("pec_audit", decision)
        repo = self._pec_audit_repository()
        if repo is None:
            return self._unavailable("pec_audit", "Controlli automatici PEC non ancora disponibili.")
        try:
            row = _serialize_pec_audit_detail(repo.get_message_detail(message_id), include_fields=True)
        except Exception as exc:
            return self._unavailable("pec_audit", f"Controllo PEC non disponibile: {exc}")
        result = self._plain_result("pec_audit", context, [row], "pec_audit")
        result.permission = decision
        return result

    def get_pec_audit_for_email(self, email_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision("pec_audit", context)
        if not decision.allowed:
            return self._blocked("pec_audit", decision)
        repo = self._pec_audit_repository()
        if repo is None:
            return self._unavailable("pec_audit", "Controlli automatici PEC non ancora disponibili.")
        manager = self._safe_manager("email_pec", lambda: self._email_manager("email_pec", context))
        if manager is None:
            return self._unavailable("pec_audit", "Casella PEC non disponibile per collegare il controllo.")
        try:
            email_row = getattr(manager, "get", lambda _id: None)(email_id)
            message_id_header = clean_spaces(getattr(email_row, "message_id", "") if email_row is not None else "")
            detail = repo.find_by_header_message_id(message_id_header) if message_id_header else None
        except Exception as exc:
            return self._unavailable("pec_audit", f"Controllo PEC non collegabile: {exc}")
        if not detail:
            return OperationalToolResult(
                False,
                "pec_audit",
                coverage_gaps=["La PEC esiste in casella, ma non ha ancora un controllo audit-grade collegato."],
                permission=decision,
            )
        row = _serialize_pec_audit_detail(detail, include_fields=True)
        result = self._plain_result("pec_audit", context, [row], "pec_audit")
        result.permission = decision
        return result

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
            manager = self._manager("legal_intelligence", "get_legal_intelligence", context)
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
                rows = _filter_official_lookup_rows(query, rows)
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
            rows = _filter_specific_official_source_passages(query, rows)
        except Exception as exc:
            return self._unavailable("fonti_ufficiali", f"Fonti ufficiali non disponibili: {exc}")
        result = self._plain_result("fonti_ufficiali", context, rows, "fonte_ufficiale")
        if not rows:
            result.coverage_gaps.append("Nessuna fonte ufficiale citabile trovata nell'indice locale configurato.")
        return result

    def search_free_public_web(self, query: str, context: OperationalQueryContext, *, limit: int = 4) -> OperationalToolResult:
        decision = self._decision("web_libero", context)
        if not decision.allowed:
            return self._blocked("web_libero", decision)
        try:
            helper = self.repositories.get("web_libero")
            if helper is not None and hasattr(helper, "search_free_public_web"):
                rows = list(helper.search_free_public_web(query, limit=limit))
            else:
                from lex.retrieval.official_web import search_free_public_web

                rows = list(search_free_public_web(query, limit_results=limit))
        except Exception as exc:
            return self._unavailable("web_libero", f"Ricerca web libera non disponibile: {exc}")
        data = [serialize_generic(item) for item in rows[: max(1, int(limit or 1))]]
        result = self._plain_result("web_libero", context, data, "ricerca_web")
        result.permission = decision
        if not data:
            result.coverage_gaps.append("Ricerca web libera eseguita senza risultati utili per integrare gli articoli.")
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

    def _manager(self, source_id: str, helper_name: str, context: OperationalQueryContext | None = None) -> Any:
        if source_id in self.repositories:
            return self.repositories[source_id]
        tenant_manager = self._tenant_manager(source_id, context)
        if tenant_manager is not None:
            return tenant_manager
        if helper_name == "get_messaggi":
            from pct.messaggi import GestioneMessaggi
            paths = self._tenant_paths(context)
            if paths.get("MESSAGGI_DB"):
                return GestioneMessaggi(config=None, db_path=paths["MESSAGGI_DB"])
            from flask import current_app

            from web.services.tenant_paths import tenant_data_path

            db_path = tenant_data_path("MESSAGGI_DB", current_app.config.get("MESSAGGI_DB", ""), require_tenant=True)
            return GestioneMessaggi(config=None, db_path=db_path)
        if helper_name == "get_email_pec":
            return self._email_manager("email_pec", context)
        if helper_name == "get_email_ordinaria":
            return self._email_manager("email_ordinaria", context)
        from web import helpers

        helper = getattr(helpers, helper_name)
        return helper()

    def _tenant_paths(self, context: OperationalQueryContext | None) -> dict[str, str]:
        tenant_id = clean_spaces(getattr(context, "tenant_id", "") if context is not None else "")
        if not tenant_id:
            return {}
        try:
            from flask import current_app, has_app_context

            if not has_app_context():
                return {}
            from pct.tenant import GestioneTenant

            registry = current_app.config.get("TENANTS_REGISTRY", "")
            if not registry:
                return {}
            manager = GestioneTenant(registry_path=registry)
            if not manager.get(tenant_id):
                return {}
            return manager.percorsi_dati(tenant_id, reconcile_aliases=False)
        except Exception:
            return {}

    def _tenant_manager(self, source_id: str, context: OperationalQueryContext | None) -> Any | None:
        paths = self._tenant_paths(context)
        if not paths:
            return None
        try:
            if source_id == "clienti":
                from pct.clienti import GestioneClienti

                return GestioneClienti(db_path=paths["CLIENTI_DB"])
            if source_id == "soggetti":
                from pct.soggetti import GestioneSoggetti

                return GestioneSoggetti(paths["SOGGETTI_DB"], paths["SOGGETTI_PARTI_DB"])
            if source_id == "fascicoli":
                from pct.fascicoli import GestioneFascicoli

                return GestioneFascicoli(
                    db_path=paths["FASCICOLI_DB"],
                    documents_dir=paths["FASCICOLI_DOCS"],
                    archive_dir=paths["FASCICOLI_ARCH"],
                )
            if source_id == "agenda":
                from pct.agenda import Agenda

                return Agenda(db_path=paths["AGENDA_DB"])
            if source_id == "scadenziario":
                from pct.scadenziario import GestioneScadenziario

                return GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"])
            if source_id in {"preventivi", "conferimenti"}:
                from pct.preventivi import GestionePreventivi

                return GestionePreventivi(db_path=paths["PREVENTIVI_DB"])
            if source_id == "fatturazione":
                from pct.fatturazione import GestioneFatturazione

                return GestioneFatturazione(db_path=paths["FATTURAZIONE_DB"])
            if source_id == "timesheet":
                from pct.timesheet import GestioneTimesheet

                return GestioneTimesheet(db_path=paths["TIMESHEET_DB"])
            if source_id == "pagamenti":
                from pct.pagamenti import GestionePagamenti

                return GestionePagamenti(db_dir=paths["PAGAMENTI_DIR"])
        except Exception:
            return None
        return None

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
        manager = self._safe_manager(source_id, lambda: self._manager(source_id, helper_name, context))
        if manager is None:
            return self._unavailable(source_id, f"Repository {source_id} non disponibile.")
        try:
            rows = list(_call(manager, method_name, identifier) or [])
        except Exception as exc:
            return self._unavailable(source_id, f"Sorgente {source_id} non interrogabile: {exc}")
        return self._rows_result(source_id, context, rows, serialize_generic, object_type, decision)

    def _email_manager(self, source_id: str, context: OperationalQueryContext | None = None) -> Any:
        if source_id in self.repositories:
            return self.repositories[source_id]
        paths = self._tenant_paths(context)
        if paths:
            from pct.email_client import GestioneEmailRicevute

            key = "EMAIL_CASELLA_DB" if source_id == "email_pec" else "EMAIL_ORDINARIA_DB"
            db_path = paths.get(key, "")
            if db_path:
                return GestioneEmailRicevute(db_path=db_path)
        from flask import current_app

        from pct.email_client import GestioneEmailRicevute
        from web.services.tenant_paths import tenant_data_path

        key = "EMAIL_CASELLA_DB" if source_id == "email_pec" else "EMAIL_ORDINARIA_DB"
        db_path = tenant_data_path(key, current_app.config.get(key, ""), require_tenant=True)
        return GestioneEmailRicevute(db_path=db_path)

    def _pec_audit_repository(self) -> Any | None:
        if "pec_audit" in self.repositories:
            return self.repositories["pec_audit"]
        try:
            from pathlib import Path

            from flask import current_app, g

            from pct.pec_pipeline import PecAuditRepository
            from web.services.tenant_paths import tenant_data_path

            email_db = Path(tenant_data_path("EMAIL_CASELLA_DB", current_app.config.get("EMAIL_CASELLA_DB", ""), require_tenant=True))
            data_paths = getattr(g, "data_paths", {}) or {}
            db_path = Path(str(data_paths.get("PEC_AUDIT_DB") or email_db.parent / "pec_audit.sqlite"))
            if not db_path.exists():
                return None
            tenant_id = clean_spaces(getattr(g, "tenant_slug", "") or getattr(g, "auth_tenant_slug", "")) or "default"
            return PecAuditRepository(
                db_path,
                tenant_id=tenant_id,
                fascicoli_db_path=tenant_data_path("FASCICOLI_DB", current_app.config.get("FASCICOLI_DB", ""), require_tenant=True),
                fascicoli_docs_path=tenant_data_path("FASCICOLI_DOCS", current_app.config.get("FASCICOLI_DOCS", ""), require_tenant=True),
                scadenziario_db_path=tenant_data_path("SCADENZIARIO_DB", current_app.config.get("SCADENZIARIO_DB", ""), require_tenant=True),
            )
        except Exception:
            return None

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
        manager = self._safe_manager(source_id, lambda: self._email_manager(source_id, context))
        if manager is None:
            return self._unavailable(source_id, f"Casella {source_id} non disponibile.")
        try:
            rows = list(
                manager.tutte(
                    cartella=folder or None,
                    q=query,
                    con_allegati=con_allegati,
                )
            )
            rows = sorted(rows, key=_email_sort_key, reverse=True)[: max(1, int(limit or 20))]
        except Exception as exc:
            return self._unavailable(source_id, f"Casella {source_id} non interrogabile: {exc}")
        return self._rows_result(source_id, context, rows, serialize_email_message, "email", decision)

    def _get_email_message(self, source_id: str, email_id: str, context: OperationalQueryContext) -> OperationalToolResult:
        decision = self._decision(source_id, context)
        if not decision.allowed:
            return self._blocked(source_id, decision)
        manager = self._safe_manager(source_id, lambda: self._email_manager(source_id, context))
        if manager is None:
            return self._unavailable(source_id, f"Casella {source_id} non disponibile.")
        try:
            row = getattr(manager, "get", lambda _id: None)(email_id)
            if row is None:
                for candidate in list(manager.tutte()):
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
        manager = self._safe_manager(source_id, lambda: self._email_manager(source_id, context))
        if manager is None:
            return self._unavailable(source_id, f"Casella {source_id} non disponibile.")
        try:
            row = getattr(manager, "get", lambda _id: None)(email_id)
            if row is None:
                for candidate in list(manager.tutte()):
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
        data = [_with_action_links(source_id, object_type, dict(row)) for row in data]
        sources = [
            self._source_ref(
                source_id,
                context,
                object_type=object_type,
                object_id=clean_spaces(row.get("id") or row.get("numero") or row.get("number") or row.get("source_id") or ""),
                title=clean_spaces(
                    row.get("nome_completo")
                    or row.get("titolo")
                    or row.get("title")
                    or row.get("oggetto")
                    or row.get("numero")
                    or row.get("number")
                    or row.get("nome")
                    or row.get("name")
                    or ""
                ),
                confidence=0.82 if data else 0.35,
                action_url=clean_spaces(row.get("action_url")),
                record=_card_record(row),
            )
            for row in data[:20]
        ]
        objects = [
            OperationalObjectReference(
                object_type=object_type,
                object_id=clean_spaces(row.get("id") or row.get("numero") or row.get("number") or row.get("source_id") or ""),
                label=clean_spaces(
                    row.get("nome_completo")
                    or row.get("titolo")
                    or row.get("title")
                    or row.get("oggetto")
                    or row.get("numero")
                    or row.get("number")
                    or row.get("nome")
                    or row.get("name")
                    or ""
                ),
                source_id=source_id,
                action_url=clean_spaces(row.get("action_url")),
            )
            for row in data[:20]
        ]
        objects.extend(_email_attachment_objects(source_id, data[:20]))
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
        action_url: str = "",
        record: dict[str, Any] | None = None,
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
            metadata={"tenant_id": context.tenant_id, "action_url": clean_spaces(action_url), "record": _card_record(record or {})},
        )

    def _document_ai_rows(self, fascicolo_id: str, context: OperationalQueryContext) -> list[dict[str, Any]]:
        try:
            from pct.document_intelligence.repository import DocumentAIRepository
            from pct.document_intelligence.service import DocumentAIService
            paths = self._tenant_paths(context)
            if paths:
                fascicoli_db = paths["FASCICOLI_DB"]
                fascicoli_manager = self._tenant_manager("fascicoli", context)
            else:
                from flask import current_app
                from web.helpers import get_fascicoli
                from web.services.tenant_paths import tenant_data_path

                fascicoli_db = tenant_data_path("FASCICOLI_DB", current_app.config.get("FASCICOLI_DB", ""), require_tenant=True)
                fascicoli_manager = get_fascicoli()
            repository = self.repositories.get("documenti_ai") or DocumentAIRepository.from_fascicoli_db(fascicoli_db)
            service = DocumentAIService(repository, fascicoli_manager)
            rows = service.list_fascicolo_documents(context.tenant_id or "default", fascicolo_id, context.user)
            payload: list[dict[str, Any]] = []
            for row in rows:
                serialized = serialize_documento(row)
                if serialized.get("status") == "ready" and serialized.get("current_version_id"):
                    try:
                        extracted = service.get_fascicolo_document_text(
                            context.tenant_id or "default",
                            fascicolo_id,
                            str(serialized.get("id") or ""),
                            context.user,
                        )
                        excerpt = _document_ai_excerpt(getattr(extracted, "text", "") or "")
                        if excerpt:
                            serialized["anteprima"] = excerpt
                            serialized["summary"] = excerpt
                            serialized["content"] = excerpt
                            serialized["extraction_engine"] = getattr(extracted, "extraction_engine", "")
                            serialized["text_available"] = True
                    except Exception as exc:
                        serialized["text_available"] = False
                        serialized["text_read_warning"] = clean_spaces(str(exc))[:220]
                payload.append(serialized)
            return payload
        except Exception:
            return []

    def _document_file_row(self, manager: Any, fascicolo_id: str, document: Any) -> dict[str, Any]:
        if manager is None or document is None:
            return {}
        document_id = clean_spaces(getattr(document, "id", "") or _dict_get(document, "id"))
        if not document_id:
            return {}
        try:
            resolver = getattr(manager, "percorso_documento_lettura", None)
            if callable(resolver):
                path = resolver(fascicolo_id, document_id)
            else:
                from pathlib import Path

                root_raw = clean_spaces(str(getattr(manager, "documents_dir", "") or ""))
                relative = clean_spaces(getattr(document, "percorso", "") or _dict_get(document, "percorso")).replace("\\", "/")
                if not root_raw or not relative:
                    return {}
                root = Path(root_raw).resolve()
                rel_path = Path(relative)
                if rel_path.is_absolute():
                    return {}
                path = (root / rel_path).resolve()
                try:
                    path.relative_to(root)
                except ValueError:
                    return {}
            from pathlib import Path

            path = Path(path)
            if not path.exists() or not path.is_file():
                return {"text_available": False, "text_read_warning": "File del documento non trovato nel fascicolo."}
            from lex.tools._doc_extractor import extract_text_from_file

            text = extract_text_from_file(path)
            if text.startswith("[Impossibile leggere"):
                return {"text_available": False, "text_read_warning": _document_ai_excerpt(text, limit=220)}
            excerpt = _document_ai_excerpt(text)
            if not excerpt:
                return {"text_available": False, "text_read_warning": "Documento presente, ma senza testo estraibile in lettura rapida."}
            return {
                "anteprima": excerpt,
                "summary": excerpt,
                "content": excerpt,
                "text_available": True,
                "extraction_engine": "fascicolo_file",
            }
        except Exception as exc:
            return {"text_available": False, "text_read_warning": clean_spaces(str(exc))[:220]}

    def _party_belongs_to_tenant(self, context: OperationalQueryContext, row: Any) -> bool:
        if isinstance(row, (tuple, list)):
            return all(self.guard.record_belongs_to_tenant(context, item) for item in row[:2] if item is not None)
        if isinstance(row, dict) and ("parte" in row or "soggetto" in row):
            return all(
                self.guard.record_belongs_to_tenant(context, item)
                for item in (row.get("parte"), row.get("soggetto"))
                if item is not None
            )
        return self.guard.record_belongs_to_tenant(context, row)


def _with_action_links(source_id: str, object_type: str, row: dict[str, Any]) -> dict[str, Any]:
    action_url = clean_spaces(row.get("action_url")) or _action_url(source_id, object_type, row)
    if action_url:
        row["action_url"] = action_url
    if source_id == "pec_audit":
        message_id = clean_spaces(row.get("id"))
        if message_id:
            row.setdefault("mime_url", f"/api/pec/messages/{message_id}/mime")
    if source_id in {"email_pec", "email_ordinaria"}:
        message_url = _action_url(source_id, "email", row)
        if message_url:
            row["action_url"] = message_url
        attachments = []
        for attachment in list(row.get("allegati") or [])[:20]:
            if not isinstance(attachment, dict):
                continue
            enriched = dict(attachment)
            index = _int(enriched.get("index"))
            base = "/email/messaggio" if source_id == "email_pec" else "/email-ordinaria/messaggio"
            email_id = clean_spaces(row.get("id"))
            if email_id:
                enriched["view_url"] = f"{base}/{email_id}/allegato/{index}"
                enriched["download_url"] = f"{base}/{email_id}/allegato/{index}?download=1"
            attachments.append(enriched)
        row["allegati"] = attachments
    return row


def _document_ai_excerpt(value: Any, *, limit: int = 1200) -> str:
    text = clean_spaces(value)
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _action_url(source_id: str, object_type: str, row: dict[str, Any]) -> str:
    object_id = clean_spaces(row.get("id") or row.get("numero") or row.get("number") or row.get("source_id"))
    if not object_id:
        return ""
    if source_id == "clienti" or object_type == "cliente":
        return f"/clienti/{object_id}/cartella"
    if source_id == "soggetti" and object_type in {"soggetto", "parte"}:
        if object_type == "parte" and clean_spaces(row.get("id_fascicolo")):
            return f"/fascicoli/{clean_spaces(row.get('id_fascicolo'))}"
        return f"/soggetti/{object_id}"
    if source_id == "fascicoli" or object_type == "fascicolo":
        return f"/fascicoli/{object_id}"
    if source_id == "documenti_fascicolo" or object_type == "documento":
        fascicolo_id = clean_spaces(row.get("id_fascicolo") or row.get("fascicolo_id"))
        if fascicolo_id:
            return f"/fascicoli/{fascicolo_id}/documenti/{object_id}/editor"
    if source_id == "email_pec":
        return f"/email/messaggio/{object_id}"
    if source_id == "email_ordinaria":
        return f"/email-ordinaria/messaggio/{object_id}"
    if source_id == "pec_audit":
        return f"/email/?pec_audit={object_id}"
    if source_id == "agenda":
        return "/agenda"
    if source_id == "scadenziario":
        return "/scadenziario"
    if source_id == "preventivi":
        return f"/preventivi/p/{object_id}"
    if source_id == "conferimenti":
        return f"/preventivi/conferimento/{object_id}"
    if source_id == "pagamenti":
        return "/incassi-pagamenti"
    return ""


def _card_record(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    allowed = (
        "id",
        "numero",
        "number",
        "nome",
        "name",
        "nome_completo",
        "titolo",
        "title",
        "oggetto",
        "mittente",
        "destinatari",
        "data",
        "data_scadenza",
        "creato_il",
        "scade_il",
        "pagato_il",
        "stato",
        "stato_pct",
        "cartella",
        "origine",
        "allegati_count",
        "allegati",
        "id_cliente",
        "id_fascicolo",
        "id_parcella",
        "importo",
        "valuta",
        "descrizione",
        "action_url",
        "mime_url",
        "quality_status",
        "quality_label",
        "signature_status",
        "signature_label",
        "validation_severity",
        "event_type",
        "linked_fascicolo_id",
        "linked_fascicolo_score",
        "issues_count",
        "normative_references",
        "agent_questions",
        "recommended_actions",
    )
    payload = {key: row.get(key) for key in allowed if key in row and row.get(key) not in ("", None, [], {})}
    if "allegati" in payload and isinstance(payload["allegati"], list):
        payload["allegati"] = [dict(item) for item in payload["allegati"][:12] if isinstance(item, dict)]
    return payload


def _field_payload(raw: dict[str, Any], key: str) -> dict[str, Any]:
    fields = raw.get("fields") if isinstance(raw.get("fields"), dict) else {}
    value = fields.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _field_value(raw: dict[str, Any], key: str) -> Any:
    payload = _field_payload(raw, key)
    return payload.get("value") if payload else ""


def _serialize_pec_audit_detail(raw: dict[str, Any], *, include_fields: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    message = dict(raw.get("message") or raw)
    metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    headers = metadata.get("headers") if isinstance(metadata.get("headers"), dict) else {}
    parsed = raw.get("parsed") if isinstance(raw.get("parsed"), dict) else {}
    parsed_headers = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    report = raw.get("validation_report") if isinstance(raw.get("validation_report"), dict) else message.get("validation_report")
    report = dict(report) if isinstance(report, dict) else {}
    link = raw.get("fascicolo_link") if isinstance(raw.get("fascicolo_link"), dict) else message.get("fascicolo_link")
    link = dict(link) if isinstance(link, dict) else {}
    attachments = raw.get("attachments") if isinstance(raw.get("attachments"), list) else message.get("attachments")
    attachments = [dict(item) for item in list(attachments or []) if isinstance(item, dict)]
    fields = parsed.get("fields") if isinstance(parsed.get("fields"), dict) else raw.get("fields")
    fields = dict(fields) if isinstance(fields, dict) else {}
    semantic_context = report.get("semantic_context") if isinstance(report.get("semantic_context"), dict) else parsed.get("semantic_context")
    semantic_context = dict(semantic_context) if isinstance(semantic_context, dict) else {}
    issues = [dict(item) for item in list(report.get("issues") or []) if isinstance(item, dict)]
    subject = clean_spaces(headers.get("subject") or parsed_headers.get("subject") or message.get("subject") or "")
    sender_payload = _field_value({"fields": fields}, "mittente")
    sender = ""
    if isinstance(sender_payload, dict):
        sender = clean_spaces(sender_payload.get("email") or sender_payload.get("name"))
    elif sender_payload:
        sender = clean_spaces(sender_payload)
    if not sender:
        sender = clean_spaces(message.get("sender") or "")
    data = clean_spaces(_field_value({"fields": fields}, "data_consegna") or _field_value({"fields": fields}, "data_invio") or message.get("received_at"))
    quality_status = clean_spaces(message.get("quality_status"))
    signature_status = clean_spaces(message.get("signature_status"))
    row = {
        "id": clean_spaces(message.get("id")),
        "titolo": subject or "Controllo PEC",
        "oggetto": subject,
        "mittente": sender,
        "data": data,
        "quality_status": quality_status,
        "quality_label": _pec_quality_label(quality_status),
        "signature_status": signature_status,
        "signature_label": _pec_signature_label(signature_status),
        "validation_severity": clean_spaces(report.get("severity")),
        "event_type": clean_spaces(report.get("event_type")),
        "linked_fascicolo_id": clean_spaces(message.get("linked_fascicolo_id") or link.get("fascicolo_id")),
        "linked_fascicolo_score": message.get("linked_fascicolo_score") or link.get("score") or 0,
        "issues_count": len(issues),
        "issues": issues[:12],
        "allegati": attachments[:12],
        "deposit_lifecycle": report.get("deposit_lifecycle") if isinstance(report.get("deposit_lifecycle"), dict) else {},
        "deadline_proposal": report.get("deadline_proposal") if isinstance(report.get("deadline_proposal"), dict) else {},
        "normative_references": report.get("normative_references") or semantic_context.get("normative_references") or [],
        "agent_questions": report.get("agent_questions") or semantic_context.get("agent_questions") or [],
        "recommended_actions": report.get("recommended_actions") or semantic_context.get("recommended_actions") or [],
    }
    if include_fields:
        row["confidence"] = {
            key: {
                "value": payload.get("value"),
                "confidence": payload.get("confidence"),
                "motivation": payload.get("motivation"),
                "features": payload.get("features") or [],
            }
            for key, payload in fields.items()
            if isinstance(payload, dict)
        }
        row["candidates"] = list(link.get("candidates") or [])
        row["agent_policy"] = semantic_context.get("agent_policy") or {
            "stance": "presidio_non_bloccante",
            "must_do": [
                "segnalare anomalie e confidence",
                "preparare prossime azioni da confermare",
                "non sostituire la decisione dell'avvocato",
            ],
        }
    return {key: value for key, value in row.items() if value not in ("", None, [], {})}


def _pec_quality_label(value: str) -> str:
    raw = clean_spaces(value).lower()
    if raw == "verde":
        return "Qualita' verde"
    if raw == "giallo":
        return "Qualita' da presidiare"
    if raw == "rosso":
        return "Qualita' critica"
    return "Qualita' non disponibile"


def _pec_signature_label(value: str) -> str:
    raw = clean_spaces(value).lower()
    if raw == "valida":
        return "Firme valide"
    if raw == "assente":
        return "Firme assenti"
    if raw in {"non_valida", "errore", "scaduta"}:
        return "Firme da verificare"
    return "Firme non controllate"


def _email_attachment_objects(source_id: str, rows: list[dict[str, Any]]) -> list[OperationalObjectReference]:
    objects: list[OperationalObjectReference] = []
    if source_id not in {"email_pec", "email_ordinaria"}:
        return objects
    for row in rows:
        email_id = clean_spaces(row.get("id"))
        if not email_id:
            continue
        for attachment in list(row.get("allegati") or [])[:20]:
            if not isinstance(attachment, dict):
                continue
            index = _int(attachment.get("index"))
            label = clean_spaces(attachment.get("nome")) or f"Allegato {index + 1}"
            objects.append(
                OperationalObjectReference(
                    object_type="allegato_email",
                    object_id=f"{email_id}#{index}",
                    label=label,
                    source_id=source_id,
                    action_url=clean_spaces(attachment.get("view_url")),
                )
            )
    return objects


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


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


_OFFICIAL_LOOKUP_RE = re.compile(
    r"\b(?:r\.?\s*g\.?|rg)?\s*(?P<number>\d{2,7})\s*/\s*(?P<year>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)


def _reference_pairs(value: Any) -> list[str]:
    refs: list[str] = []
    for match in _OFFICIAL_LOOKUP_RE.finditer(clean_spaces(value)):
        ref = f"{match.group('number')}/{match.group('year')}"
        if ref not in refs:
            refs.append(ref)
    return refs


def _specific_official_lookup_identifiers(query: str) -> list[str]:
    text = clean_spaces(query)
    identifiers = list(_reference_pairs(text))
    for match in re.finditer(r"\bqsp\s*[-_/]?\s*\d+\b", text, re.IGNORECASE):
        value = clean_spaces(match.group(0)).lower().replace(" ", "")
        if value not in identifiers:
            identifiers.append(value)
    for match in re.finditer(r"\bcontentid\s*=\s*([a-z0-9_-]+)", text, re.IGNORECASE):
        value = match.group(1).lower()
        if value not in identifiers:
            identifiers.append(value)
    return identifiers


def _looks_like_official_lookup(query: str) -> bool:
    text = clean_spaces(query).lower()
    if _reference_pairs(text):
        return True
    return any(
        token in text
        for token in (
            "allegato ufficiale",
            "questione penale",
            "questione civile",
            "ordinanza di rimessione",
            "fonte ufficiale",
            "fonti ufficiali",
            "cassazione",
            "qsp",
            "contentid=",
        )
    )


def _row_lookup_text(row: dict[str, Any]) -> str:
    return clean_spaces(
        " ".join(
            str(row.get(key) or "")
            for key in (
                "title",
                "titolo",
                "excerpt",
                "summary",
                "content",
                "text",
                "query",
                "official_url",
                "source_url",
                "url",
                "attachment_url",
                "url_allegato",
                "source_name",
                "authority",
                "source_code",
                "origin",
                "attachment_type",
            )
        )
    )


def _row_score(row: dict[str, Any]) -> float:
    try:
        return float(row.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _filter_official_lookup_rows(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) <= 2 or not _looks_like_official_lookup(query):
        return rows
    refs = _reference_pairs(query)
    top_score = max((_row_score(row) for row in rows), default=0.0)
    score_threshold = max(1.25, top_score - 0.60) if top_score else 0.0
    filtered: list[dict[str, Any]] = []
    for row in rows:
        text = _row_lookup_text(row)
        normalized = text.lower()
        score = _row_score(row)
        has_exact_ref = any(ref in text for ref in refs)
        has_attachment = bool(clean_spaces(row.get("attachment_url") or row.get("url_allegato")))
        is_official_attachment = has_attachment and any(
            token in normalized
            for token in (
                "ordinanza",
                "rimessione",
                "allegato",
                "pdf",
                "cassazione",
                "corte suprema",
            )
        )
        if refs:
            keep = has_exact_ref or is_official_attachment
        else:
            keep = bool((score_threshold and score >= score_threshold) or is_official_attachment)
        if keep:
            filtered.append(row)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in filtered:
        key = (
            clean_spaces(row.get("title") or row.get("titolo")).lower(),
            clean_spaces(row.get("official_url") or row.get("source_url") or row.get("url")).lower(),
            clean_spaces(row.get("attachment_url") or row.get("url_allegato")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped or rows[:2]


def _filter_specific_official_source_passages(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    identifiers = _specific_official_lookup_identifiers(query)
    if not identifiers:
        return rows
    filtered = []
    for row in rows:
        text = _row_lookup_text(row).lower().replace(" ", "")
        if any(identifier.lower().replace(" ", "") in text for identifier in identifiers):
            filtered.append(row)
    return filtered


def _email_sort_key(row: Any) -> tuple[int, float | str]:
    for key in ("timestamp", "data", "ricevuta_il", "inviato_il", "creato_il"):
        value = getattr(row, key, "") if not isinstance(row, dict) else row.get(key)
        text = clean_spaces(value)
        if not text:
            continue
        parsed = _parse_datetime(text)
        if parsed is not None:
            return (1, parsed.timestamp())
        return (0, text)
    return (0, "")


def _parse_datetime(text: str) -> datetime | None:
    normalized = clean_spaces(text).replace("Z", "+00:00")
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized)
    except Exception:
        pass
    for pattern, length in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d", 10),
        ("%d/%m/%Y %H:%M", 16),
        ("%d/%m/%Y", 10),
    ):
        try:
            return datetime.strptime(normalized[:length], pattern)
        except Exception:
            continue
    return None


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
