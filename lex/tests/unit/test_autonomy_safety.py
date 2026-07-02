from __future__ import annotations

import pytest

from lex.autonomy.models import ImprovementProposal
from lex.autonomy.safety import (
    HARD_LIMITS,
    AutonomyViolation,
    CycleConfigError,
    assert_no_autonomous_code_write,
    refuse_apply,
    validate_cycle_config,
)


def _base_config(**overrides):
    raw = {
        "mode": "offline",
        "allow_web": False,
        "limits": {"max_cycles": 2, "max_queries": 10},
        "sources": {"allowlist": ["normattiva.it"]},
        "politeness": {"min_interval_seconds": 2.0},
        "memory": {"dir": ""},
    }
    raw.update(overrides)
    return raw


def test_config_offline_valida():
    config = validate_cycle_config(_base_config())
    assert config.mode == "offline"
    assert config.require_official_sources is True
    assert config.respect_robots is True


def test_web_senza_allow_web_rifiutata():
    with pytest.raises(CycleConfigError):
        validate_cycle_config(_base_config(mode="web"))


def test_web_senza_allowlist_rifiutata():
    raw = _base_config(mode="web", allow_web=True)
    raw["sources"] = {"allowlist": []}
    with pytest.raises(CycleConfigError):
        validate_cycle_config(raw)


def test_web_richiede_robots_e_intervallo_minimo():
    raw = _base_config(mode="web", allow_web=True)
    raw["politeness"] = {"min_interval_seconds": 0.2}
    with pytest.raises(CycleConfigError):
        validate_cycle_config(raw)
    raw["politeness"] = {"min_interval_seconds": 2.0, "respect_robots": False}
    with pytest.raises(CycleConfigError):
        validate_cycle_config(raw)


def test_allow_web_con_mode_offline_incoerente():
    with pytest.raises(CycleConfigError):
        validate_cycle_config(_base_config(allow_web=True))


def test_hard_limits_fail_closed_senza_clamp():
    for key, ceiling in HARD_LIMITS.items():
        raw = _base_config()
        raw["limits"] = {key: ceiling + 1}
        with pytest.raises(CycleConfigError):
            validate_cycle_config(raw)


def test_limiti_non_numerici_o_nulli_rifiutati():
    raw = _base_config()
    raw["limits"] = {"max_cycles": "molti"}
    with pytest.raises(CycleConfigError):
        validate_cycle_config(raw)
    raw["limits"] = {"max_cycles": 0}
    with pytest.raises(CycleConfigError):
        validate_cycle_config(raw)


def test_refuse_apply_solleva_sempre():
    proposal = ImprovementProposal(kind="ontologia", title="Aggiungere concetto", description="...")
    with pytest.raises(AutonomyViolation):
        refuse_apply(proposal)


def test_azioni_vietate_bloccate():
    with pytest.raises(AutonomyViolation):
        assert_no_autonomous_code_write("test", requested_action="commit")
    assert_no_autonomous_code_write("test")  # nessuna azione: nessun errore


def test_proposta_sempre_in_revisione_umana():
    proposal = ImprovementProposal(kind="x", title="t", description="d", requires_human_review=False)
    assert proposal.requires_human_review is True
    assert proposal.to_dict()["requires_human_review"] is True
