"""Test motore di priorità P0–P3 (tabella regole deterministica)."""

from datetime import date, datetime

from pct.daily_plan.clock import Clock
from pct.daily_plan.correlation import correlate
from pct.daily_plan.deduplication import merge_signals
from pct.daily_plan.models import OperationalSignal
from pct.daily_plan.priority_engine import decide_priority, rank_sort_key

TODAY = date(2026, 7, 11)
CLOCK = Clock(fixed_now=datetime(2026, 7, 11, 8, 0))


def _group(**overrides):
    base = dict(
        id="sig_1",
        tenant_id="studio-a",
        source_type="scadenziario",
        source_id="sc-1",
        kind="deadline_fulfill",
        title="Scadenza",
        dedupe_key="",
        fascicolo_id="fasc-1",
        due_at="2026-07-20",
    )
    base.update(overrides)
    segnale = OperationalSignal(**base)
    return merge_signals(correlate([segnale], clock=CLOCK))[0]


def test_perentoria_scaduta_aperta_p0():
    """Caso obbligatorio 1: scadenza perentoria scaduta ma aperta → P0."""
    decisione = decide_priority(_group(due_at="2026-07-08", peremptory=True), today=TODAY)
    assert decisione.priority == "P0"
    assert decisione.rule_id == "R1"
    assert "perentorio" in decisione.reason.lower()


def test_perentoria_oggi_p0():
    """Caso obbligatorio 2: scadenza perentoria oggi → P0."""
    decisione = decide_priority(_group(due_at="2026-07-11", peremptory=True), today=TODAY)
    assert decisione.priority == "P0"
    assert decisione.rule_id == "R1"


def test_scadenza_oggi_non_perentoria_p1():
    """Caso obbligatorio 2 (variante non perentoria): oggi → P1."""
    decisione = decide_priority(_group(due_at="2026-07-11"), today=TODAY)
    assert decisione.priority == "P1"
    assert decisione.rule_id == "R5"


def test_pec_rifiutata_p0():
    """Caso obbligatorio 3: PEC/PCT rifiutata → P0."""
    gruppo = _group(
        source_type="deposit",
        kind="deposit_outcome_check",
        due_at="",
        metadata={"esito": "rifiutato"},
    )
    decisione = decide_priority(gruppo, today=TODAY)
    assert decisione.priority == "P0"
    assert decisione.rule_id == "R2"


def test_udienza_oggi_p0():
    """Caso obbligatorio 7: udienza oggi → P0."""
    gruppo = _group(source_type="agenda", kind="hearing_attend", due_at="2026-07-11")
    decisione = decide_priority(gruppo, today=TODAY)
    assert decisione.priority == "P0"
    assert decisione.rule_id == "R3"


def test_attivita_bloccante_oggi_p0():
    gruppo = _group(blocking=True, due_at="2026-07-11")
    assert decide_priority(gruppo, today=TODAY).priority == "P0"


def test_perentoria_entro_tre_giorni_p1():
    decisione = decide_priority(_group(due_at="2026-07-13", peremptory=True), today=TODAY)
    assert decisione.priority == "P1"
    assert decisione.rule_id == "R4"


def test_udienza_entro_48_ore_p1():
    gruppo = _group(source_type="agenda", kind="hearing_attend", due_at="2026-07-12")
    decisione = decide_priority(gruppo, today=TODAY)
    assert decisione.priority == "P1"
    assert decisione.rule_id == "R6"


def test_scadenza_entro_14_giorni_p2():
    decisione = decide_priority(_group(due_at="2026-07-22"), today=TODAY)
    assert decisione.priority == "P2"
    assert decisione.rule_id == "R7"


def test_hint_presidio_rispettato():
    gruppo = _group(
        source_type="case_presidio",
        kind="document_review",
        due_at="",
        priority_hint="P1",
        reason="Documento con termine da confermare",
    )
    decisione = decide_priority(gruppo, today=TODAY)
    assert decisione.priority == "P1"
    assert decisione.rule_id == "R8"


def test_organizzativa_senza_scadenza_p3():
    decisione = decide_priority(_group(due_at="", kind="duplicate_reconciliation"), today=TODAY)
    assert decisione.priority == "P3"
    assert decisione.rule_id == "R9"


def test_override_perentorio_batte_hint_presidio():
    gruppo = _group(due_at="2026-07-08", peremptory=True, priority_hint="P3")
    assert decide_priority(gruppo, today=TODAY).rule_id == "R1"


def test_rank_deterministico_e_ordinato():
    scaduta = _group(due_at="2026-07-08", metadata={"scadenziario_id": "a"})
    futura = _group(due_at="2026-07-14", metadata={"scadenziario_id": "b"})
    dec_scaduta = decide_priority(scaduta, today=TODAY)
    dec_futura = decide_priority(futura, today=TODAY)
    key_scaduta = rank_sort_key(scaduta, dec_scaduta, today=TODAY)
    key_futura = rank_sort_key(futura, dec_futura, today=TODAY)
    assert key_scaduta < key_futura
    # stabilità: due chiamate producono la stessa chiave
    assert key_scaduta == rank_sort_key(scaduta, dec_scaduta, today=TODAY)


def test_ogni_decisione_ha_motivo_leggibile():
    for gruppo in (
        _group(due_at="2026-07-08", peremptory=True),
        _group(due_at="2026-07-11"),
        _group(due_at="2026-07-22"),
        _group(due_at=""),
    ):
        decisione = decide_priority(gruppo, today=TODAY)
        assert decisione.reason
        assert decisione.rule_id.startswith("R")
