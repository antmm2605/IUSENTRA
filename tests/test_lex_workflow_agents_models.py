from lex.agents.models import AgentPlan, AgentProposal, AgentRun, AgentStep
from lex.agents.serialization import public_dict


def test_modelli_agentici_serializzabili_e_redatti():
    step = AgentStep(
        step_key="lettura",
        title="Legge fascicolo",
        tool_name="fascicolo",
        input_json={"email": "cliente@example.it", "tenant_id": "non-accettato"},
    )
    plan = AgentPlan(workflow_code="triage_giornaliero", title="Triage", description="Test", steps=[step])
    run = AgentRun(workflow_code="triage_giornaliero", created_by="pytest", tenant_scope="studio-a", plan=plan)
    run.proposals.append(
        AgentProposal(
            run_id=run.id,
            step_id=step.id,
            tool_name="create_task",
            title="Task",
            payload={"codice_fiscale": "RSSMRA80A01H501U", "path": r"C:\data\studio\file.pdf"},
        )
    )

    payload = public_dict(run)

    assert payload["workflow_code"] == "triage_giornaliero"
    assert "tenant_id" not in str(payload)
    assert "cliente@example.it" not in str(payload)
    assert "RSSMRA80A01H501U" not in str(payload)
    assert r"C:\data\studio" not in str(payload)
