import pytest

from lex.agents.models import AgentStep
from lex.agents.policies import WorkflowAgentPolicyError, assert_step_executable, required_permissions_for_tool, validate_client_payload


def test_payload_client_non_puo_indicare_tenant_o_path():
    with pytest.raises(WorkflowAgentPolicyError) as exc:
        validate_client_payload({"tenant_id": "studio-b", "params": {"path": "/data/segreto.pdf"}})

    assert exc.value.code == "client_control_param"


def test_policy_blocca_azioni_vietate():
    step = AgentStep(
        step_key="pec",
        title="Invia PEC",
        tool_name="send_pec",
        mutates_state=True,
        approval_required=True,
        input_json={"oggetto": "invio"},
    )

    with pytest.raises(WorkflowAgentPolicyError) as exc:
        assert_step_executable(
            step,
            tenant_scope="studio-a",
            allow_writes=True,
            write_feature_enabled=True,
            approved=True,
            user_permissions=["messaggi.scrivi"],
        )

    assert exc.value.code == "forbidden_agent_action"


def test_policy_blocca_scrittura_senza_approvazione():
    step = AgentStep(
        step_key="task",
        title="Task",
        tool_name="create_task",
        mutates_state=True,
        approval_required=True,
        required_permissions=("agenda.scrivi",),
    )

    with pytest.raises(WorkflowAgentPolicyError) as exc:
        assert_step_executable(
            step,
            tenant_scope="studio-a",
            allow_writes=True,
            write_feature_enabled=True,
            approved=False,
            user_permissions=["agenda.scrivi"],
        )

    assert exc.value.code == "approval_required"


def test_policy_mappa_permessi_reali_per_letture_e_scritture_agentiche():
    assert required_permissions_for_tool("list_fascicolo_documents") == ("fascicoli.leggi",)
    assert required_permissions_for_tool("collect_fascicolo_context") == ("fascicoli.leggi", "ai.usa")
    assert required_permissions_for_tool("create_invoice_draft", mutates_state=True) == ("fatturazione.scrivi",)
