from pathlib import Path


def test_nessun_mock_fallback_true_o_placeholder_regia():
    sources = [
        Path("pct/practice_engine"),
        Path("web/services/react_practice_engine_bridge.py"),
        Path("web/blueprints/api_v1_react.py"),
        Path("frontend/src/components/FascicoliPage.tsx"),
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8")
        if path.is_file()
        else "\n".join(child.read_text(encoding="utf-8") for child in path.glob("*.py"))
        for path in sources
    )
    assert "mock_fallback\": True" not in text
    assert "mock_fallback=true" not in text.lower()
    assert "sigp_infofascicolo.wp" not in text
    assert "BeautifulSoup" not in text
    assert "requests.get(\"https://pst" not in text
    assert "pass\n" not in "\n".join(child.read_text(encoding="utf-8") for child in Path("pct/practice_engine").glob("*.py"))
    assert "TODO" not in "\n".join(child.read_text(encoding="utf-8") for child in Path("pct/practice_engine").glob("*.py"))


def test_nessun_test_regia_skip_e_nessuna_busta_simulata_reale():
    for path in Path("tests").glob("test_regia*.py"):
        source = path.read_text(encoding="utf-8")
        assert "@pytest.mark." + "skip" not in source
        assert "pytest." + "skip" not in source
    deposit = Path("pct/practice_engine/deposit_orchestrator.py").read_text(encoding="utf-8")
    assert "simulated = False" in deposit
    assert "real_transport = False" in deposit
    assert "non_configurato" in deposit


def test_acquisito_solo_con_ricevuta_finale():
    state_machine = Path("pct/practice_engine/state_machine.py").read_text(encoding="utf-8")
    receipt_tracker = Path("pct/practice_engine/receipt_tracker.py").read_text(encoding="utf-8")
    assert "has_final_positive_receipt" in state_machine
    assert "target == PracticeState.ACQUISITO.value" in state_machine
    assert "ESITO_CANCELLERIA" in receipt_tracker
    assert "ACCETTAZIONE_PEC" in receipt_tracker
