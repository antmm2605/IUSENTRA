"""Test tool Lex daily_plan, registrazione governata e sintesi item-aware."""

from types import SimpleNamespace

from lex.agents.policies import READ_PERMISSION_MAP, required_permissions_for_tool
from lex.tools.registry import LexToolRegistry


def _fake_plan(items, coverage_complete=True, warnings=()):
    return SimpleNamespace(
        work_items=items,
        coverage=[],
        coverage_complete=coverage_complete,
        summary={"totale": len(items)},
        warnings=list(warnings),
        plan_version="v1",
        target_date="2026-07-11",
    )


def _fake_item(key, priority="P0", **overrides):
    base = dict(
        id=f"dpi_{key}",
        title=f"Attivita {key}",
        priority=priority,
        status="proposed",
        sector="scadenze",
        action_kind="deadline_fulfill",
        reason="Motivo",
        priority_reason="Spiegazione",
        due_at="2026-07-11",
        blocking=False,
        peremptory=False,
        confidence=0.9,
        review_required=False,
        fascicolo_id="fasc-1",
        fascicolo_label="2026/10",
        cliente_label="Rossi",
        assigned_user_id="u1",
        assigned_lawyer_label="Mario Bianchi",
        scheduled_start="",
        in_backlog=False,
        evidence=[1],
        href="/scadenziario",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeService:
    def __init__(self, plan):
        self._plan = plan
        self.clock = SimpleNamespace(today=lambda: __import__("datetime").date(2026, 7, 11))

    def read_plan(self, *, user_id, target_date):
        return self._plan


def test_daily_plan_tool_registrato_con_descrittore_e_permessi():
    registry = LexToolRegistry()  # la guardia interna esplode se incoerente
    descriptor = registry.descriptor("daily_plan")
    assert descriptor is not None
    assert descriptor.mutates_state is False
    assert descriptor.access_level == "read_only"
    assert "daily_plan" in READ_PERMISSION_MAP
    assert required_permissions_for_tool("daily_plan") == ("agenda.leggi", "scadenziario.leggi")


def test_daily_plan_tool_rbac_fail_closed():
    registry = LexToolRegistry()
    esito = registry.validate_tool_call("daily_plan", user_permissions=["fascicoli.leggi"])
    assert esito["allowed"] is False
    assert esito["reason"] == "permessi_insufficienti"

    esito = registry.validate_tool_call(
        "daily_plan", user_permissions=["agenda.leggi", "scadenziario.leggi"]
    )
    assert esito["allowed"] is True


def test_daily_plan_tool_legge_snapshot(monkeypatch):
    from lex.tools import daily_plan_tool
    from lex.tools.daily_plan_tool import DailyPlanTool

    plan = _fake_plan([_fake_item("a"), _fake_item("b", priority="P2")])
    monkeypatch.setattr(daily_plan_tool, "_get_service", lambda: _FakeService(plan))

    result = DailyPlanTool().run()
    assert result["stato"] == "pronto"
    assert result["returned_count"] == 2
    assert result["items"][0]["priorita"] == "P0"
    assert result["items"][0]["peremptory"] is False
    assert result["coverage_complete"] is True

    solo_p0 = DailyPlanTool().run(priorita="P0")
    assert [i["id"] for i in solo_p0["items"]] == ["dpi_a"]


def test_daily_plan_tool_piano_non_generato(monkeypatch):
    from lex.tools import daily_plan_tool
    from lex.tools.daily_plan_tool import DailyPlanTool

    monkeypatch.setattr(daily_plan_tool, "_get_service", lambda: _FakeService(None))
    result = DailyPlanTool().run()
    assert result["stato"] == "non_generato"
    assert result["coverage_complete"] is False
    assert result["warnings"]


def test_daily_plan_tool_metadata_troncamento(monkeypatch):
    from lex.tools import daily_plan_tool
    from lex.tools.daily_plan_tool import DailyPlanTool

    plan = _fake_plan([_fake_item(f"k{i}") for i in range(5)])
    monkeypatch.setattr(daily_plan_tool, "_get_service", lambda: _FakeService(plan))
    result = DailyPlanTool().run(limit=2)
    assert result["returned_count"] == 2
    assert result["total_matching"] == 5
    assert result["truncated"] is True
    assert result["coverage_complete"] is False


def test_triage_giornaliero_legge_il_piano_del_giorno():
    from lex.agents.recipes.triage_giornaliero import build

    plan = build({})
    step_keys = [s.step_key for s in plan.steps]
    assert step_keys[0] == "piano_del_giorno"
    primo = plan.steps[0]
    assert primo.tool_name == "daily_plan"
    assert primo.mutates_state is False
    assert primo.required_permissions == ("agenda.leggi", "scadenziario.leggi")
    # restano i passi di verifica e le proposte approvabili
    assert "scadenze_14_giorni" in step_keys
    assert any(s.mutates_state and s.approval_required for s in plan.steps)


def test_synthesis_usa_priorita_strutturate():
    from lex.agents.models import AgentPlan, AgentRun, AgentStep
    from lex.agents.synthesis import build_run_result

    step = AgentStep(
        step_key="piano_del_giorno",
        title="Piano del giorno",
        tool_name="daily_plan",
        status="done",
    )
    run = AgentRun(
        workflow_code="triage_giornaliero",
        created_by="test",
        tenant_scope="studio-a",
        plan=AgentPlan(
            workflow_code="triage_giornaliero",
            title="Triage",
            description="",
            steps=[step],
        ),
        evidence_json={
            "piano_del_giorno": {
                "items": [
                    {
                        "titolo": "Deposita memoria",
                        "priorita": "P0",
                        "due_at": "2026-07-11",
                        "peremptory": True,
                        "blocking": True,
                        "confidence": 0.95,
                        "assigned_label": "Mario Bianchi",
                    },
                    {
                        "titolo": "Classifica documento",
                        "priorita": "P3",
                        "confidence": 0.7,
                    },
                ],
                "coverage_complete": False,
                "warnings": ["Presidio PEC: dati non aggiornati."],
            }
        },
    )
    result = build_run_result(run)
    priorita = result["priorita"]
    assert priorita[0]["title"] == "Deposita memoria"
    assert priorita[0]["level"] == "alta"
    assert priorita[0]["peremptory"] is True
    assert priorita[0]["due_at"] == "2026-07-11"
    assert priorita[0]["assigned_user"] == "Mario Bianchi"
    assert priorita[-1]["level"] == "bassa"
    warning_text = " ".join(result["warning"])
    assert "Copertura fonti incompleta" in warning_text


def test_synthesis_fallback_conteggi_per_tool_legacy():
    from lex.agents.models import AgentPlan, AgentRun, AgentStep
    from lex.agents.synthesis import build_run_result

    step = AgentStep(
        step_key="scadenze",
        title="Scadenze",
        tool_name="scadenziario",
        status="done",
    )
    run = AgentRun(
        workflow_code="triage_giornaliero",
        created_by="test",
        tenant_scope="studio-a",
        plan=AgentPlan(workflow_code="triage_giornaliero", title="T", description="", steps=[step]),
        evidence_json={"scadenze": {"items": [{"id": "s1"}, {"id": "s2"}]}},
    )
    result = build_run_result(run)
    assert result["priorita"][0]["level"] == "alta"
    assert "2 elementi" in result["priorita"][0]["title"]
