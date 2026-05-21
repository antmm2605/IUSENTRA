from lex.agents.serialization import public_dict
from lex.agents.registry import WorkflowRecipeRegistry
from lex.agents.models import AgentPlan, AgentRun
from lex.agents.storage import WorkflowAgentStorage
from lex.tools.registry import LexToolRegistry


def test_registry_blocca_tool_mutante_senza_allow_writes_e_permessi():
    registry = LexToolRegistry()

    blocked = registry.validate_tool_call("create_task", allow_writes=False, user_permissions=["agenda.scrivi"])
    assert blocked["allowed"] is False
    assert blocked["reason"] == "strumento_di_scrittura_richiede_canale_applicativo_autorizzato"

    missing = registry.validate_tool_call("create_task", allow_writes=True, user_permissions=[])
    assert missing["allowed"] is False
    assert missing["reason"] == "permessi_insufficienti"


def test_registry_accetta_permessi_rbac_reali_senza_bypassare_policy():
    registry = LexToolRegistry()

    read = registry.validate_tool_call("fascicolo", user_permissions=["fascicoli.leggi"])
    write = registry.validate_tool_call(
        "generate_editor_draft",
        allow_writes=True,
        user_permissions=["ai.usa", "fascicoli.scrivi"],
    )

    assert read["allowed"] is True
    assert write["allowed"] is True


def test_ricette_non_generano_azioni_vietate_automatiche():
    registry = WorkflowRecipeRegistry()
    forbidden_tools = {"send_pec", "invia_pec", "deposito_telematico", "deposit_atto", "firma_digitale", "sign_document"}

    for recipe in registry.list_recipes():
        plan = recipe.builder({"workflow_code": recipe.code, "fascicolo_id": "F1", "params": {}, "input_text": "test"})
        assert plan.steps
        assert any(not step.mutates_state for step in plan.steps)
        assert any(step.mutates_state and step.approval_required for step in plan.steps)
        assert not {step.tool_name for step in plan.steps}.intersection(forbidden_tools)
        for step in plan.steps:
            if step.mutates_state:
                assert step.approval_required is True


def test_storage_non_espone_run_di_altro_tenant(tmp_path):
    runs_path = tmp_path / "runs.json"
    metrics_path = tmp_path / "metrics.json"
    plan = AgentPlan(workflow_code="triage_giornaliero", title="Triage", description="Test", steps=[])
    run = AgentRun(workflow_code="triage_giornaliero", created_by="pytest", tenant_scope="studio-a", plan=plan)

    WorkflowAgentStorage(runs_path, metrics_path, tenant_scope="studio-a").save_run(run)

    try:
        WorkflowAgentStorage(runs_path, metrics_path, tenant_scope="studio-b").get_run(run.id)
    except PermissionError as exc:
        assert "studio" in str(exc).lower()
    else:
        raise AssertionError("Il run di un altro tenant è stato letto.")


def test_output_pubblico_non_contiene_token_path_o_email():
    payload = public_dict(
        {
            "token": "abc",
            "path": "/data/tenants/studio/fascicoli/a.pdf",
            "note": "scrivere a cliente@example.it",
        }
    )

    text = str(payload)
    assert "abc" not in text
    assert "/data/tenants" not in text
    assert "cliente@example.it" not in text
