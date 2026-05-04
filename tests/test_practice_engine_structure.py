from pathlib import Path


def test_practice_engine_struttura_modulare_e_migrazioni():
    root = Path("pct/practice_engine")
    expected = {
        "__init__.py",
        "models.py",
        "registry.py",
        "resolver.py",
        "profiles.py",
        "requirements.py",
        "checklist.py",
        "document_slots.py",
        "validators.py",
        "evaluator.py",
        "state_machine.py",
        "deadlines.py",
        "deposit_readiness.py",
        "deposit_orchestrator.py",
        "receipt_tracker.py",
        "evidence_pack.py",
        "repository.py",
        "audit.py",
        "messages.py",
    }
    assert root.is_dir()
    assert expected <= {path.name for path in root.glob("*.py")}
    for path in root.glob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 650, path
    sqlite = Path("pct/sql/20260504_practice_engine.sql").read_text(encoding="utf-8")
    postgres = Path("pct/sql/20260504_practice_engine_postgres.sql").read_text(encoding="utf-8")
    for table in (
        "practice_profiles",
        "practice_requirements",
        "practice_document_slots",
        "practice_checklist_items",
        "practice_validation_results",
        "practice_state_history",
        "deposit_sessions",
        "deposit_receipts",
        "deposit_timeline_events",
        "evidence_packs",
    ):
        assert table in sqlite
        assert table in postgres


def test_docs_api_bridge_e_ui_senza_mock_fallback_true():
    assert Path("docs/REGIA_OPERATIVA_FASCICOLO.md").exists()
    assert "Regia Operativa" in Path("docs/ARCHITETTURA.md").read_text(encoding="utf-8")
    assert "Regia Operativa" in Path("docs/STORAGE_MATRIX.md").read_text(encoding="utf-8")
    api = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    ui = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    assert "/fascicoli/<id_fasc>/regia" in api
    assert "mock_fallback\": True" not in api
    assert "Regia Operativa" in ui
    assert "href={item.href || '#'}" not in ui
    assert "Deposito acquisito correttamente" in Path("pct/practice_engine/messages.py").read_text(encoding="utf-8")
