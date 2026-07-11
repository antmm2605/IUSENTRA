"""Test modelli puri del piano del giorno: serializzazione e redazione."""

from pct.daily_plan.models import (
    ITEM_STATUS_TRANSITIONS,
    DailyPlan,
    DailyWorkItem,
    OperationalSignal,
    SignalEvidence,
    SourceCoverage,
    redact_metadata,
    redact_text,
)


def _signal(**overrides):
    base = dict(
        id="sig_1",
        tenant_id="studio-a",
        source_type="scadenziario",
        kind="deadline_fulfill",
        title="Deposito memoria",
        dedupe_key="abc",
    )
    base.update(overrides)
    return OperationalSignal(**base)


def test_signal_roundtrip_serializzazione():
    sig = _signal(
        due_at="2026-07-12",
        peremptory=True,
        evidence=[SignalEvidence(source_type="scadenziario", source_id="sc-1", label="Scadenza")],
    )
    data = sig.to_dict()
    ricostruito = OperationalSignal.from_dict(data)
    assert ricostruito.dedupe_key == "abc"
    assert ricostruito.peremptory is True
    assert ricostruito.evidence[0].source_id == "sc-1"


def test_redazione_metadata_rimuove_chiavi_sensibili():
    out = redact_metadata(
        {
            "password": "segreta",
            "api_key": "xyz",
            "file_path": "/data/tenants/x/doc.pdf",
            "nota": "ok",
            "nested": {"token": "abc", "valore": 3},
        }
    )
    assert "password" not in out
    assert "api_key" not in out
    assert "file_path" not in out
    assert out["nota"] == "ok"
    assert "token" not in out["nested"]
    assert out["nested"]["valore"] == 3


def test_redazione_testo_iban_cf_percorsi():
    testo = redact_text(
        "Pagamento su IT60X0542811101000000123456 di RSSMRA85M01H501Z in /home/user/doc.pdf"
    )
    assert "IT60X0542811101000000123456" not in testo
    assert "RSSMRA85M01H501Z" not in testo
    assert "/home/user" not in testo


def test_signal_redige_titolo_e_metadata_alla_costruzione():
    sig = _signal(
        title="Verifica IBAN IT60X0542811101000000123456",
        metadata={"secret_token": "x", "fascicolo": "f-1"},
    )
    assert "IT60X05428" not in sig.title
    assert "secret_token" not in sig.metadata
    assert sig.metadata["fascicolo"] == "f-1"


def test_work_item_priorita_e_stato_normalizzati():
    item = DailyWorkItem(
        id="dpi_1",
        tenant_id="studio-a",
        target_date="2026-07-11",
        title="Attivita",
        action_kind="deadline_fulfill",
        dedupe_key="k1",
        priority="P9",
        status="stato_inventato",
    )
    assert item.priority == "P3"
    assert item.status == "proposed"


def test_work_item_roundtrip():
    item = DailyWorkItem(
        id="dpi_1",
        tenant_id="studio-a",
        target_date="2026-07-11",
        title="Attivita",
        action_kind="pec_review",
        dedupe_key="k1",
        priority="P0",
        blocking=True,
        source_signal_ids=["sig_1", "sig_2"],
        available_actions=["accept", "complete"],
    )
    data = item.to_dict()
    ricostruito = DailyWorkItem.from_dict(data)
    assert ricostruito.priority == "P0"
    assert ricostruito.blocking is True
    assert ricostruito.source_signal_ids == ["sig_1", "sig_2"]
    assert ricostruito.available_actions == ["accept", "complete"]


def test_state_machine_stati_finali_senza_uscite():
    assert ITEM_STATUS_TRANSITIONS["completed"] == ()
    assert ITEM_STATUS_TRANSITIONS["rejected"] == ()
    assert "accepted" in ITEM_STATUS_TRANSITIONS["proposed"]
    assert "rejected" in ITEM_STATUS_TRANSITIONS["needs_review"]


def test_daily_plan_coverage_complete():
    piano = DailyPlan(
        id="dp_1",
        tenant_id="studio-a",
        target_date="2026-07-11",
        coverage=[
            SourceCoverage(source_type="agenda", status="complete"),
            SourceCoverage(source_type="pec", status="stale"),
        ],
    )
    assert piano.coverage_complete is False
    data = piano.to_dict()
    assert data["coverage_complete"] is False
    assert len(data["coverage"]) == 2

    piano.coverage[1].status = "complete"
    assert piano.coverage_complete is True


def test_daily_plan_senza_coverage_non_dichiara_completo():
    piano = DailyPlan(id="dp_1", tenant_id="studio-a", target_date="2026-07-11")
    assert piano.coverage_complete is False
