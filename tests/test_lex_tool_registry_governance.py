from __future__ import annotations

from lex.tools.registry import LEX_TOOL_REGISTRY_SCHEMA, LexToolRegistry


def test_tool_registry_espone_schema_governato_senza_rompere_tools_legacy():
    registry = LexToolRegistry()

    assert "operational_knowledge" in registry.tools
    assert "generate_editor_draft" in registry.tools

    tools = {row["tool_name"]: row for row in registry.list_tools()}

    assert set(tools) == set(registry.tools)
    assert tools["operational_knowledge"]["schema"] == LEX_TOOL_REGISTRY_SCHEMA
    assert tools["operational_knowledge"]["access_level"] == "read_only"
    assert tools["operational_knowledge"]["transport"] == "in_process"
    assert tools["operational_knowledge"]["mutates_state"] is False
    assert "studio:knowledge:read" in tools["operational_knowledge"]["permissions"]


def test_tool_registry_blocca_scrittura_senza_canale_applicativo():
    registry = LexToolRegistry()

    blocked = registry.validate_tool_call("generate_editor_draft")
    allowed = registry.validate_tool_call(
        "generate_editor_draft",
        allow_writes=True,
        user_permissions=["studio:atti:write"],
    )

    assert blocked["allowed"] is False
    assert blocked["reason"] == "strumento_di_scrittura_richiede_canale_applicativo_autorizzato"
    assert allowed["allowed"] is True
    assert allowed["descriptor"]["mutates_state"] is True


def test_tool_registry_web_libero_non_blocca_fonti_pubbliche_ma_isola_dati_studio():
    registry = LexToolRegistry()

    legal = registry.validate_tool_call(
        "legal_intelligence",
        mode="web_libero",
        user_permissions=["legal:sources:read"],
    )
    studio = registry.validate_tool_call(
        "fascicolo",
        mode="web_libero",
        user_permissions=["studio:fascicoli:read"],
    )

    assert legal["allowed"] is True
    assert legal["descriptor"]["allowed_in_free_web"] is True
    assert studio["allowed"] is False
    assert studio["reason"] == "strumento_studio_non_esposto_al_web_libero"


def test_tool_registry_segnala_permessi_insufficienti_quando_presenti():
    registry = LexToolRegistry()

    result = registry.validate_tool_call(
        "read_fascicolo_document",
        user_permissions=["studio:fascicoli:read"],
    )

    assert result["allowed"] is False
    assert result["reason"] == "permessi_insufficienti"
    assert result["missing_permissions"] == ["studio:documenti:read"]
