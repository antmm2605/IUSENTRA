from __future__ import annotations

from types import SimpleNamespace

from lex.operational_knowledge.audit import OperationalAuditRecorder
from lex.operational_knowledge.permission_guard import resolve_query_context
from lex.operational_knowledge.service import OperationalKnowledgeService
from lex.operational_knowledge.settings import OperationalKnowledgeSettings
from lex.operational_knowledge.tools import OperationalKnowledgeTools
from lex.tools.registry import LexToolRegistry


class _User:
    def __init__(self, permissions: set[str], *, tenant_slug: str = "tenant-a"):
        self.id = "user-a"
        self.username = "avvocato"
        self.tenant_slug = tenant_slug
        self._permissions = set(permissions)

    @property
    def permessi_effettivi(self):
        return sorted(self._permissions)

    def ha_permesso(self, permission: str) -> bool:
        return permission in self._permissions


class _ListManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def tutti(self, *args, **kwargs):
        return list(self.rows)

    def cerca(self, query: str = "", *args, **kwargs):
        needle = str(query or "").lower().strip()
        if not needle:
            return list(self.rows)
        return [row for row in self.rows if needle in _haystack(row)]

    def get(self, identifier: str):
        for row in self.rows:
            if str(getattr(row, "id", "") or getattr(row, "numero", "")) == str(identifier):
                return row
        return None


class _FascicoliManager(_ListManager):
    pass


class _PreventiviManager:
    def __init__(self, preventivi=None, conferimenti=None):
        self.preventivi = list(preventivi or [])
        self.conferimenti = list(conferimenti or [])

    def tutti_preventivi(self):
        return list(self.preventivi)

    def tutti_conferimenti(self):
        return list(self.conferimenti)

    def get_preventivo(self, identifier: str):
        return _get(self.preventivi, identifier)

    def get_conferimento(self, identifier: str):
        return _get(self.conferimenti, identifier)


class _FatturazioneManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def per_cliente(self, cliente_id: str):
        return [row for row in self.rows if getattr(row, "id_cliente", "") == cliente_id]

    def per_fascicolo(self, fascicolo_id: str):
        return [row for row in self.rows if getattr(row, "id_fascicolo", "") == fascicolo_id]


class _ScadenziarioManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def tutte(self, **kwargs):
        id_fascicolo = str(kwargs.get("id_fascicolo") or "")
        rows = [row for row in self.rows if not id_fascicolo or getattr(row, "id_fascicolo", "") == id_fascicolo]
        return rows


class _AgendaManager(_ListManager):
    def per_cliente(self, cliente_id: str):
        return [row for row in self.rows if getattr(row, "id_cliente", "") == cliente_id]


class _MessaggiManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def per_cliente(self, cliente_id: str):
        return [row for row in self.rows if getattr(row, "id_cliente", "") == cliente_id]

    def per_fascicolo(self, fascicolo_id: str):
        return [row for row in self.rows if getattr(row, "id_fascicolo", "") == fascicolo_id]


class _TemplateManager(_ListManager):
    def select_best_templates(self, query: str, limit: int = 12):
        return self.cerca(query)[:limit]


def _haystack(row) -> str:
    values = []
    for key in ("id", "nome", "cognome", "nome_completo", "titolo", "oggetto", "numero", "id_cliente"):
        values.append(str(getattr(row, key, "") or ""))
    return " ".join(values).lower()


def _get(rows, identifier: str):
    for row in rows:
        if str(getattr(row, "id", "")) == str(identifier):
            return row
    return None


def _service(*, user=None, repositories=None, audit_sink=None):
    settings = OperationalKnowledgeSettings(enabled=True, audit_enabled=False, strict_mode_enabled=True)
    tools = OperationalKnowledgeTools(repositories=repositories or {})
    audit = OperationalAuditRecorder(settings=settings, sink=audit_sink)
    return OperationalKnowledgeService(settings=settings, tools=tools, audit=audit), user or _User(_all_permissions())


def _all_permissions() -> set[str]:
    return {
        "ai.usa",
        "clienti.leggi",
        "fascicoli.leggi",
        "agenda.leggi",
        "scadenziario.leggi",
        "fatturazione.leggi",
        "messaggi.leggi",
        "telematico.leggi",
        "ai.audit",
    }


def _base_repositories():
    cliente = SimpleNamespace(id="cli-1", nome="Mario", cognome="Rossi", nome_completo="Mario Rossi", email="mario@example.test", tenant_id="tenant-a")
    fascicolo = SimpleNamespace(
        id="fas-1",
        numero="RG 10/2026",
        titolo="Rossi / Bianchi",
        oggetto="Opposizione",
        id_cliente="cli-1",
        nome_cliente="Mario Rossi",
        stato="APERTO",
        documenti=[
            SimpleNamespace(id="doc-1", nome="ricorso.pdf", tipo="ATTO", percorso="D:/segreto/ricorso.pdf", sha256="abc123"),
        ],
        tenant_id="tenant-a",
    )
    return {
        "clienti": _ListManager([cliente]),
        "fascicoli": _FascicoliManager([fascicolo]),
        "scadenziario": _ScadenziarioManager([SimpleNamespace(id="sca-1", titolo="Costituzione", id_fascicolo="fas-1", data_scadenza="2026-05-20")]),
        "agenda": _AgendaManager([SimpleNamespace(id="app-1", titolo="Udienza", id_cliente="cli-1", data_ora="2026-05-21T10:00:00")]),
        "preventivi": _PreventiviManager(
            preventivi=[SimpleNamespace(id="prev-1", oggetto="Opposizione", id_cliente="cli-1", id_pratica="fas-1", totale=1200.0)],
            conferimenti=[SimpleNamespace(id="conf-1", oggetto="Incarico opposizione", id_cliente="cli-1", id_pratica="fas-1", stato="ATTIVO")],
        ),
        "fatturazione": _FatturazioneManager([SimpleNamespace(id="par-1", numero="P-1", id_cliente="cli-1", id_fascicolo="fas-1", totale=500.0)]),
        "messaggi": _MessaggiManager([SimpleNamespace(id="msg-1", oggetto="Aggiornamento pratica", id_cliente="cli-1", id_fascicolo="fas-1", canale="PEC")]),
        "template_atti": _TemplateManager([SimpleNamespace(id="tpl-1", titolo="Ricorso opposizione", categoria="atti")]),
    }


def test_operational_knowledge_feature_flag_off_returns_none():
    service = OperationalKnowledgeService(settings=OperationalKnowledgeSettings(enabled=False))

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=_User(_all_permissions()), studio=SimpleNamespace(slug="tenant-a"))

    assert answer is None


def test_operational_knowledge_settings_default_on(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)

    settings = OperationalKnowledgeSettings.from_env()

    assert settings.enabled is True


def test_operational_knowledge_settings_explicit_off(monkeypatch):
    monkeypatch.setenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", "0")

    settings = OperationalKnowledgeSettings.from_env()

    assert settings.enabled is False


def test_client_retrieval_uses_real_repositories_and_sources():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Cliente: Mario Rossi" in answer.answer
    assert any(source.source_id == "clienti" for source in answer.sources)
    assert any(source.source_id == "fascicoli" for source in answer.sources)
    assert "clienti.leggi" in " ".join(answer.permissions_applied)


def test_client_context_id_resolves_this_client_without_guessing():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(
        question="Quali fascicoli ha questo cliente?",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        metadata={"cliente_id": "cli-1"},
    )

    assert answer is not None
    assert "Fascicoli collegati: 1" in answer.answer
    assert any(obj.object_id == "fas-1" for obj in answer.objects)


def test_tenant_isolation_excludes_other_tenant_records():
    repos = _base_repositories()
    repos["clienti"] = _ListManager([
        SimpleNamespace(id="cli-b", nome="Mario", cognome="Rossi", nome_completo="Mario Rossi", tenant_id="tenant-b"),
    ])
    service, user = _service(repositories=repos)

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"), tenant_id="tenant-a")

    assert answer is not None
    assert "Non ho trovato dati reali sufficienti" in answer.answer
    assert any("tenant diverso" in gap for gap in answer.coverage_gaps)


def test_rbac_blocks_client_without_permission():
    user = _User({"ai.usa", "fascicoli.leggi"})
    service, _ = _service(user=user, repositories=_base_repositories())

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Non ho trovato dati reali sufficienti" in answer.answer
    assert any("clienti" in gap for gap in answer.coverage_gaps)


def test_deadline_and_agenda_retrieval_are_structured():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Quali scadenze ho questa settimana?", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Scadenze consultabili" in answer.answer
    assert any(source.source_id in {"agenda", "scadenziario"} for source in answer.sources)


def test_preventivo_conferimento_and_billing_do_not_invent_amounts():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Preparami il riepilogo del preventivo opposizione", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Preventivi: 1" in answer.answer
    assert "1200" not in answer.answer or "EUR" not in answer.answer
    assert any(source.source_id == "preventivi" for source in answer.sources)


def test_tariffario_missing_parameters_returns_coverage_gap():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Quale tariffario si applica al preventivo?", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert any("materia" in gap and "grado" in gap for gap in answer.coverage_gaps)


def test_document_retrieval_does_not_expose_filesystem_paths():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Quali documenti mancano nel fascicolo Rossi?", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    payload = answer.to_dict()
    assert "D:/segreto" not in str(payload)
    assert any(source.source_id == "documenti_fascicolo" for source in answer.sources)


def test_message_retrieval_uses_tenant_internal_sources_only():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Mostrami i messaggi PEC del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert any(source.source_id == "messaggi" for source in answer.sources)
    assert "Aggiornamento pratica" in str(answer.to_dict())
    assert answer.metadata["operational_layer"] is True


def test_template_lookup_is_reported_as_template_source():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Cerca template ricorso opposizione", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert any(source.source_id == "template_atti" for source in answer.sources)


def test_legal_action_request_is_blocked():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Invia PEC al cliente Rossi e deposita l'atto", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert answer.blocked_reason == "legal_action_blocked"
    assert "Non posso eseguire direttamente" in answer.answer


def test_audit_event_is_recorded_to_in_memory_sink():
    sink = []
    service, user = _service(repositories=_base_repositories(), audit_sink=sink)

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert answer.audit_event_id == "memory:1"
    assert sink[0]["route"] == "client_situation"
    assert sink[0]["tenant"] == "tenant-a"


def test_internal_customer_query_does_not_call_legal_source_web(monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("fonti ufficiali non devono essere chiamate per dati cliente")

    monkeypatch.setattr("lex.legal_sources.tools.search_legal_sources", _forbidden)
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert answer.metadata["operational_layer"] is True


def test_permission_guard_requires_ai_usa():
    user = _User({"clienti.leggi"})
    context = resolve_query_context(user=user, studio=SimpleNamespace(slug="tenant-a"))
    tools = OperationalKnowledgeTools(repositories=_base_repositories())

    result = tools.search_clienti("Rossi", context)

    assert not result.ok
    assert result.permission is not None
    assert "ai.usa" in result.permission.missing_permissions


def test_tool_registry_exposes_operational_knowledge_tool_default_on(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    registry = LexToolRegistry()

    result = registry.tools["operational_knowledge"].run(
        question="Mostrami il cliente Rossi",
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
    )

    assert result["ok"] is True
    assert result["workflow"] == "operational_knowledge"


def test_tool_registry_can_disable_operational_knowledge(monkeypatch):
    monkeypatch.setenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", "0")
    registry = LexToolRegistry()

    result = registry.tools["operational_knowledge"].run(question="Mostrami il cliente Rossi")

    assert result == {"ok": False, "reason": "feature_flag_disabled"}


def test_http_bridge_operational_layer_handles_studio_data_by_default(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            return OperationalAnswer(
                handled=True,
                answer="Cliente: Mario Rossi.",
                route=OperationalRoute("client_situation", "client_situation", ("clienti",), "rossi"),
                sources=[
                    OperationalSourceReference(
                        source_id="clienti",
                        source_name="Clienti",
                        source_type="studio",
                        object_type="cliente",
                        object_id="cli-1",
                        title="Mario Rossi",
                        confidence=0.86,
                    )
                ],
                confidence=0.86,
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={},
        current_user_message="Mostrami la situazione del cliente Rossi",
        resolved_effective_question="Mostrami la situazione del cliente Rossi",
        studio_context={"focus_topic": "clienti", "request_profile": {"intent": "cliente_anagrafica"}},
    )

    assert payload is not None
    assert payload["workflow"] == "operational_knowledge"
    assert payload["provider"] == "deterministic"


def test_http_bridge_defers_specific_case_law_to_public_research(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"external_sources_reason": "riferimento giurisprudenziale esatto"},
        current_user_message="Mi puoi trovare questa Sentenza n. 7919 del 31/03/2026?",
        resolved_effective_question="Mi puoi trovare questa Sentenza n. 7919 del 31/03/2026?",
        studio_context={"focus_topic": "sentenze_web", "request_profile": {"intent": "giurisprudenza_specifica"}},
    )

    assert payload is None


def test_http_bridge_defers_without_permission_context(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload

    payload = build_operational_http_payload(
        user=SimpleNamespace(username="utente-senza-contesto-permessi"),
        studio=SimpleNamespace(slug="tenant-a"),
        data={},
        current_user_message="Che cosa devo fare oggi?",
        resolved_effective_question="Che cosa devo fare oggi?",
        studio_context={"request_profile": {"intent": ""}},
    )

    assert payload is None


def test_response_composer_reports_coverage_gap_for_absent_data():
    service, user = _service(repositories={"clienti": _ListManager([])})

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert answer.confidence < 0.55
    assert answer.coverage_gaps
