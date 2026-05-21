from lex.agents.serialization import public_dict
from lex.tools.registry import LexToolRegistry


def test_registry_blocca_tool_mutante_senza_allow_writes_e_permessi():
    registry = LexToolRegistry()

    blocked = registry.validate_tool_call("create_task", allow_writes=False, user_permissions=["agenda.scrivi"])
    assert blocked["allowed"] is False
    assert blocked["reason"] == "strumento_di_scrittura_richiede_canale_applicativo_autorizzato"

    missing = registry.validate_tool_call("create_task", allow_writes=True, user_permissions=[])
    assert missing["allowed"] is False
    assert missing["reason"] == "permessi_insufficienti"


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

