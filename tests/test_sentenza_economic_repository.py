from __future__ import annotations

import json
import re
from pathlib import Path

from pct.sentenza_economic_repository import (
    SCHEMA_SENTENZA_ECONOMIC_POSTGRES,
    SCHEMA_SENTENZA_ECONOMIC_SQLITE,
    SENTENZA_ECONOMIC_TABLES,
    SentenzaEconomicRepository,
)


def _tables(sql: str) -> set[str]:
    return set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+([a-z0-9_]+)", sql, flags=re.I))


def test_schema_sqlite_postgres_parity():
    sqlite_tables = _tables(SCHEMA_SENTENZA_ECONOMIC_SQLITE.read_text(encoding="utf-8"))
    postgres_tables = _tables(SCHEMA_SENTENZA_ECONOMIC_POSTGRES.read_text(encoding="utf-8"))
    assert sqlite_tables == postgres_tables == set(SENTENZA_ECONOMIC_TABLES)


def test_schema_created_and_tenant_scoped(tmp_path: Path):
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    assert repo.schema_table_names() == set(SENTENZA_ECONOMIC_TABLES)

    repo.save_sentenza_audit("studio-a", fascicolo_id="F1", rg_numero_rilevato="1234", status="to_review", audit={"x": 1})
    repo.save_sentenza_audit("studio-b", fascicolo_id="F9", rg_numero_rilevato="9", audit={"y": 2})

    a = repo.list_sentenza_audits("studio-a")
    b = repo.list_sentenza_audits("studio-b")
    assert [r["fascicolo_id"] for r in a] == ["F1"]
    assert [r["fascicolo_id"] for r in b] == ["F9"]
    assert a[0]["audit"] == {"x": 1}
    assert a[0]["safe_to_attach"] is False


def test_economic_events_roundtrip_and_status(tmp_path: Path):
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    ev = repo.add_economic_event(
        "studio-a",
        fascicolo_id="F1",
        event_type="apri_credito_cliente",
        amount=4200.0,
        beneficiary_type="cliente",
        evidence=[{"k": "v"}],
    )
    assert ev["amount"] == 4200.0
    assert ev["evidence"] == [{"k": "v"}]

    repo.update_event_status("studio-a", ev["id"], status="confirmed", reviewed_by="avv")
    rows = repo.list_economic_events("studio-a", fascicolo_id="F1")
    assert rows[0]["status"] == "confirmed"
    assert rows[0]["reviewed_by"] == "avv"
    # isolamento tenant
    assert repo.list_economic_events("studio-b", fascicolo_id="F1") == []


def test_signed_decision_register_detects_tamper(tmp_path: Path):
    decisions = tmp_path / "dec.jsonl"
    repo = SentenzaEconomicRepository(tmp_path / "se.db", decisions_path=decisions)
    repo.record_decision(tenant_id="studio-a", actor_id="avv", kind="attach_verified", subject_ref="F1", decision="approvato", rationale="RG combacia")
    repo.record_decision(tenant_id="studio-a", actor_id="avv", kind="credit_confirmed", subject_ref="F1", decision="approvato", rationale="Spese distratte")

    assert len(repo.list_decisions(tenant_id="studio-a")) == 2
    assert repo.list_decisions(tenant_id="studio-b") == []
    assert repo.verify_decisions() is True

    lines = decisions.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[0])
    obj["decision"] = "manomesso"
    lines[0] = json.dumps(obj)
    decisions.write_text("\n".join(lines) + "\n", encoding="utf-8")

    repo_after = SentenzaEconomicRepository(tmp_path / "se.db", decisions_path=decisions)
    assert repo_after.verify_decisions() is False
