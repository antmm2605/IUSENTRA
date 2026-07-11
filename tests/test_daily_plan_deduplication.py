"""Test deduplicazione e correlazione dei segnali operativi."""

from datetime import datetime

from pct.daily_plan.clock import Clock
from pct.daily_plan.correlation import correlate, normalize_rg
from pct.daily_plan.deduplication import (
    build_dedupe_key,
    merge_signals,
    normalize_due_date,
)
from pct.daily_plan.models import OperationalSignal, SignalEvidence

CLOCK = Clock(fixed_now=datetime(2026, 7, 11, 8, 0))


def _signal(source_type, source_id, **overrides):
    base = dict(
        id=f"sig_{source_type}_{source_id}",
        tenant_id="studio-a",
        source_type=source_type,
        source_id=source_id,
        kind="deadline_fulfill",
        title=f"Scadenza da {source_type}",
        dedupe_key="",
        fascicolo_id="fasc-1",
        due_at="2026-07-15",
        confidence=0.7,
    )
    base.update(overrides)
    return OperationalSignal(**base)


def test_stessa_scadenza_da_tre_fonti_un_solo_gruppo_tre_evidenze():
    """Caso obbligatorio 5: PEC + documento + scadenziario → 1 item, 3 evidenze."""
    segnali = [
        _signal("scadenziario", "sc-1", metadata={"scadenziario_id": "sc-1"}),
        _signal(
            "pec",
            "msg-1",
            metadata={"scadenziario_id": "sc-1"},
            evidence=[SignalEvidence(source_type="pec", source_id="msg-1", label="PEC Tribunale")],
        ),
        _signal(
            "case_presidio",
            "doc-1",
            metadata={"scadenziario_id": "sc-1"},
            evidence=[SignalEvidence(source_type="case_presidio", source_id="doc-1", label="Decreto PDF")],
        ),
    ]
    gruppi = merge_signals(correlate(segnali, clock=CLOCK))
    assert len(gruppi) == 1
    gruppo = gruppi[0]
    assert len(gruppo.signals) == 3
    assert len(gruppo.evidence) == 3
    assert gruppo.primary.source_type == "scadenziario"


def test_fascicoli_diversi_mai_fusi():
    """Caso obbligatorio 6: stesso giorno, fascicoli diversi → 2 item."""
    segnali = [
        _signal("scadenziario", "sc-1", fascicolo_id="fasc-1"),
        _signal("scadenziario", "sc-2", fascicolo_id="fasc-2"),
    ]
    gruppi = merge_signals(correlate(segnali, clock=CLOCK))
    assert len(gruppi) == 2


def test_scadenze_diverse_stesso_giorno_non_fuse():
    segnali = [
        _signal("scadenziario", "sc-1", metadata={"scadenziario_id": "sc-1"}),
        _signal("scadenziario", "sc-2", metadata={"scadenziario_id": "sc-2"}),
    ]
    gruppi = merge_signals(correlate(segnali, clock=CLOCK))
    assert len(gruppi) == 2


def test_confidence_cresce_solo_con_fonti_indipendenti():
    indipendenti = merge_signals(
        correlate(
            [
                _signal("scadenziario", "sc-1", confidence=0.6, metadata={"scadenziario_id": "s1"}),
                _signal("pec", "msg-1", confidence=0.6, metadata={"scadenziario_id": "s1"}),
            ],
            clock=CLOCK,
        )
    )[0]
    stessa_fonte = merge_signals(
        correlate(
            [
                _signal("pec", "msg-1", confidence=0.6, metadata={"scadenziario_id": "s2"}),
                _signal("pec", "msg-2", confidence=0.6, metadata={"scadenziario_id": "s2"}),
            ],
            clock=CLOCK,
        )
    )[0]
    assert indipendenti.confidence > 0.6
    assert stessa_fonte.confidence == 0.6


def test_conflitto_perentorieta_non_nascosto():
    segnali = [
        _signal("scadenziario", "sc-1", peremptory=True, metadata={"scadenziario_id": "s1"}),
        _signal("pec", "msg-1", peremptory=False, metadata={"scadenziario_id": "s1"}),
    ]
    gruppo = merge_signals(correlate(segnali, clock=CLOCK))[0]
    assert gruppo.needs_review is True
    assert gruppo.conflicts


def test_associazione_debole_va_in_revisione_e_non_si_fonde():
    """Caso obbligatorio 4: PEC con associazione incerta → needs_review."""
    certo = _signal("scadenziario", "sc-1", metadata={"scadenziario_id": "s1"})
    debole = _signal(
        "pec",
        "msg-9",
        confidence=0.9,
        metadata={"scadenziario_id": "s1", "fascicolo_match": "weak"},
    )
    gruppi = merge_signals(correlate([certo, debole], clock=CLOCK))
    # il link debole perde il fascicolo dalla chiave → non si fonde col certo
    assert len(gruppi) == 2
    gruppo_debole = next(g for g in gruppi if g.primary.source_type == "pec")
    assert gruppo_debole.needs_review is True
    assert gruppo_debole.confidence <= 0.6


def test_dedupe_key_stabile_e_normalizzazione_date():
    key1 = build_dedupe_key("studio-a", "fasc-1", "deadline_fulfill", "scadenziario:1", "2026-07-15")
    key2 = build_dedupe_key("Studio-A", "fasc-1", "deadline_fulfill", "scadenziario:1", "2026-07-15")
    assert key1 == key2  # tenant case-insensitive
    assert normalize_due_date("15/07/2026") == "2026-07-15"
    assert normalize_due_date("2026-07-15T23:30:00") == "2026-07-15"
    assert normalize_due_date("") == ""


def test_normalize_rg():
    assert normalize_rg("RG 123/2026") == "123/2026"
    assert normalize_rg("n. 0123/26") == "123/2026"
    assert normalize_rg("senza rg") == ""


def test_evidenze_duplicate_non_replicate():
    ev = SignalEvidence(source_type="pec", source_id="msg-1", label="PEC")
    segnali = [
        _signal("pec", "msg-1", evidence=[ev], metadata={"scadenziario_id": "s1"}),
        _signal("scadenziario", "sc-1", evidence=[ev], metadata={"scadenziario_id": "s1"}),
    ]
    gruppo = merge_signals(correlate(segnali, clock=CLOCK))[0]
    refs = [(e.source_type, e.source_id) for e in gruppo.evidence]
    assert refs.count(("pec", "msg-1")) == 1
