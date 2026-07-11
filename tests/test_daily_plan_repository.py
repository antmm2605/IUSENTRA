"""Test repository materializzato del piano del giorno.

Copre: schema, upsert per dedupe_key, isolamento cross-tenant nello stesso
file, preservazione degli stati umani alla rigenerazione, obsolescenza,
watermark, job queue idempotente, dirty entities, action log idempotente.
"""

from datetime import datetime

import pytest

import pct.daily_plan.repository as daily_plan_repository
from pct.daily_plan.clock import Clock
from pct.daily_plan.models import DailyWorkItem, OperationalSignal, SignalEvidence
from pct.daily_plan.repository import (
    DailyPlanRepository,
    InvalidStatusTransition,
    TenantMismatchError,
    derive_daily_plan_db_path,
)

CLOCK = Clock(fixed_now=datetime(2026, 7, 11, 7, 30))
DATE = "2026-07-11"


@pytest.fixture()
def repo(tmp_path):
    return DailyPlanRepository(
        str(tmp_path / "daily_plan.db"), tenant_id="studio-a", clock=CLOCK
    )


def _signal(key, **overrides):
    base = dict(
        id="",
        tenant_id="studio-a",
        source_type="scadenziario",
        kind="deadline_fulfill",
        title=f"Scadenza {key}",
        dedupe_key=key,
        due_at="2026-07-12",
    )
    base.update(overrides)
    return OperationalSignal(**base)


def _item(key, **overrides):
    base = dict(
        id="",
        tenant_id="studio-a",
        target_date=DATE,
        title=f"Attivita {key}",
        action_kind="deadline_fulfill",
        dedupe_key=key,
        priority="P1",
        item_rank=1,
    )
    base.update(overrides)
    return DailyWorkItem(**base)


def test_derive_db_path():
    path = derive_daily_plan_db_path("/data/tenants/x/intelligence/quadro.json")
    assert path.endswith("daily_plan.db")
    assert "intelligence" in path


def test_riapertura_schema_pronto_non_riesegue_ddl(tmp_path, monkeypatch):
    db = str(tmp_path / "daily_plan.db")
    primo = DailyPlanRepository(db, tenant_id="studio-a", clock=CLOCK)
    primo.replace_items_for_date(DATE, [_item("stabile")], plan_version="v1")

    class SchemaNonLeggibile:
        @staticmethod
        def read_text(*_args, **_kwargs):
            raise AssertionError("lo schema completo non deve rieseguire DDL")

    monkeypatch.setattr(daily_plan_repository, "SCHEMA_DAILY_PLAN", SchemaNonLeggibile())
    riaperto = DailyPlanRepository(db, tenant_id="studio-a", clock=CLOCK)

    assert [item.dedupe_key for item in riaperto.list_items(DATE)] == ["stabile"]


def test_upsert_signals_idempotente_per_dedupe_key(repo):
    prima = repo.upsert_signals([_signal("k1"), _signal("k2")])
    assert prima == {"inserted": 2, "updated": 0}

    seconda = repo.upsert_signals([_signal("k1", title="Aggiornata")])
    assert seconda == {"inserted": 0, "updated": 1}

    segnali = repo.list_active_signals()
    assert len(segnali) == 2
    aggiornato = next(s for s in segnali if s.dedupe_key == "k1")
    assert aggiornato.title == "Aggiornata"


def test_isolamento_cross_tenant_stesso_file(tmp_path):
    db = str(tmp_path / "daily_plan.db")
    repo_a = DailyPlanRepository(db, tenant_id="studio-a", clock=CLOCK)
    repo_b = DailyPlanRepository(db, tenant_id="studio-b", clock=CLOCK)

    repo_a.upsert_signals([_signal("k1")])
    repo_b.upsert_signals([_signal("k9", tenant_id="studio-b")])

    assert {s.dedupe_key for s in repo_a.list_active_signals()} == {"k1"}
    assert {s.dedupe_key for s in repo_b.list_active_signals()} == {"k9"}

    repo_a.replace_items_for_date(DATE, [_item("i1")], plan_version="v1")
    assert repo_b.list_items(DATE) == []

    item_a = repo_a.list_items(DATE)[0]
    assert repo_b.get_item(item_a.id) is None


def test_rifiuta_segnali_di_altro_tenant(repo):
    with pytest.raises(TenantMismatchError):
        repo.upsert_signals([_signal("k1", tenant_id="studio-intruso")])


def test_replace_items_preserva_stati_umani(repo):
    repo.replace_items_for_date(DATE, [_item("k1"), _item("k2")], plan_version="v1")
    item = repo.list_items(DATE)[0]
    repo.update_item_status(item.id, "completed", actor="avv.rossi")

    stats = repo.replace_items_for_date(
        DATE, [_item("k1", title="Rigenerata"), _item("k2")], plan_version="v2"
    )
    assert stats["preserved_status"] >= 1

    ricaricato = repo.get_item(item.id)
    assert ricaricato.status == "completed"
    assert ricaricato.status_actor == "avv.rossi"
    assert ricaricato.plan_version == "v2"


def test_replace_items_marca_obsoleti_non_riemessi(repo):
    repo.replace_items_for_date(DATE, [_item("k1"), _item("k2")], plan_version="v1")
    stats = repo.replace_items_for_date(DATE, [_item("k1")], plan_version="v2")
    assert stats["obsoleted"] == 1

    attivi = repo.list_items(DATE)
    assert [i.dedupe_key for i in attivi] == ["k1"]

    tutti = repo.list_items(DATE, include_obsolete=True)
    assert len(tutti) == 2


def test_state_machine_blocca_transizioni_non_ammesse(repo):
    repo.replace_items_for_date(DATE, [_item("k1")], plan_version="v1")
    item = repo.list_items(DATE)[0]
    repo.update_item_status(item.id, "completed", actor="avv")
    with pytest.raises(InvalidStatusTransition):
        repo.update_item_status(item.id, "accepted", actor="avv")


def test_backlog_paginato_keyset(repo):
    items = [
        _item(f"k{i}", priority="P2", item_rank=i, in_backlog=True) for i in range(7)
    ]
    repo.replace_items_for_date(DATE, items, plan_version="v1")

    pagina1 = repo.list_backlog_page(DATE, limit=3)
    assert len(pagina1["items"]) == 3
    assert pagina1["total_matching"] == 7
    assert pagina1["truncated"] is True
    assert pagina1["next_cursor"]

    pagina2 = repo.list_backlog_page(DATE, cursor=pagina1["next_cursor"], limit=3)
    ids1 = {i.dedupe_key for i in pagina1["items"]}
    ids2 = {i.dedupe_key for i in pagina2["items"]}
    assert not ids1 & ids2


def test_snapshot_upsert_e_cache_sintesi_lex(repo):
    base = dict(
        target_date=DATE,
        user_id="u1",
        generation_mode="full",
        freshness={},
        coverage={"agenda": "complete"},
        summary={"p0": 1},
        fixed_agenda=[],
        warnings=[],
    )
    repo.save_snapshot(plan_version="v1", **base)
    repo.save_lex_summary(target_date=DATE, user_id="u1", plan_version="v1", summary="Sintesi v1")

    snap = repo.get_snapshot(DATE, "u1")
    assert snap["lex_summary"] == "Sintesi v1"

    # stessa versione → la sintesi resta
    repo.save_snapshot(plan_version="v1", **base)
    assert repo.get_snapshot(DATE, "u1")["lex_summary"] == "Sintesi v1"

    # versione nuova → la sintesi viene invalidata
    repo.save_snapshot(plan_version="v2", **base)
    snap = repo.get_snapshot(DATE, "u1")
    assert snap["lex_summary"] == ""
    assert snap["plan_version"] == "v2"

    # la sintesi per una versione superata non viene salvata
    salvata = repo.save_lex_summary(
        target_date=DATE, user_id="u1", plan_version="v1", summary="vecchia"
    )
    assert salvata is False


def test_watermarks(repo):
    repo.set_watermark("pec", watermark="2026-07-11T07:00:00", status="ok")
    repo.set_watermark("agenda", status="error", error="fonte non raggiungibile in /opt/x")

    marks = repo.get_watermarks()
    assert marks["pec"]["last_status"] == "ok"
    assert marks["pec"]["watermark"] == "2026-07-11T07:00:00"
    assert marks["agenda"]["last_status"] == "error"
    assert "/opt" not in marks["agenda"]["last_error"]


def test_job_queue_idempotente(repo):
    primo = repo.enqueue_job("incremental_refresh", idempotency_key="idem-1")
    assert primo["replayed"] is False

    replay = repo.enqueue_job("incremental_refresh", idempotency_key="idem-1")
    assert replay["replayed"] is True
    assert replay["job_id"] == primo["job_id"]

    # job dello stesso tipo già in coda → non si accoda un doppione
    doppione = repo.enqueue_job("incremental_refresh")
    assert doppione["replayed"] is True

    claimed = repo.claim_next_job("incremental_refresh")
    assert claimed["id"] == primo["job_id"]
    assert claimed["status"] == "running"

    repo.finish_job(primo["job_id"], status="done", report={"items": 3})
    assert repo.claim_next_job("incremental_refresh") is None


def test_job_queue_distingue_le_date_del_piano(repo):
    oggi = repo.enqueue_job(
        "incremental_refresh",
        payload={"target_date": "2026-07-11"},
    )
    dopodomani = repo.enqueue_job(
        "incremental_refresh",
        payload={"target_date": "2026-07-13"},
    )
    replay = repo.enqueue_job(
        "incremental_refresh",
        payload={"target_date": "2026-07-13"},
    )

    assert oggi["replayed"] is False
    assert dopodomani["replayed"] is False
    assert dopodomani["job_id"] != oggi["job_id"]
    assert replay["replayed"] is True
    assert replay["job_id"] == dopodomani["job_id"]

    claimed = [
        repo.claim_next_job("incremental_refresh"),
        repo.claim_next_job("incremental_refresh"),
    ]
    assert {job["payload"]["target_date"] for job in claimed if job} == {
        "2026-07-11",
        "2026-07-13",
    }


def test_dirty_entities_marcatura_e_consumo(repo):
    assert repo.mark_dirty("fascicolo", ["f1", "f2", ""]) == 2
    assert repo.pending_dirty_count() == 2

    consumati = repo.consume_dirty(limit=10)
    assert {c["entity_id"] for c in consumati} == {"f1", "f2"}
    assert repo.pending_dirty_count() == 0

    # rimarcare dopo il consumo riapre l'entità
    repo.mark_dirty("fascicolo", ["f1"])
    assert repo.pending_dirty_count() == 1


def test_action_log_replay_idempotente(repo):
    repo.replace_items_for_date(DATE, [_item("k1")], plan_version="v1")
    item = repo.list_items(DATE)[0]

    repo.record_action(
        item_id=item.id,
        action="accept",
        actor="avv",
        idempotency_key="act-1",
        result={"ok": True, "status": "accepted"},
    )
    replay = repo.get_action_by_idempotency("act-1")
    assert replay["result"]["status"] == "accepted"
    assert repo.get_action_by_idempotency("act-mai-vista") is None


def test_resolve_signals_not_in(repo):
    repo.upsert_signals([_signal("k1"), _signal("k2"), _signal("k3")])
    rimossi = repo.resolve_signals_not_in("scadenziario", ["k1"])
    assert rimossi == 2
    assert {s.dedupe_key for s in repo.list_active_signals()} == {"k1"}


def test_evidence_persistite_sul_segnale(repo):
    sig = _signal(
        "k1",
        evidence=[
            SignalEvidence(source_type="pec", source_id="msg-1", label="PEC Tribunale"),
            SignalEvidence(source_type="scadenziario", source_id="sc-1", label="Scadenza"),
        ],
    )
    repo.upsert_signals([sig])
    ricaricato = repo.list_active_signals()[0]
    assert len(ricaricato.evidence) == 2
    assert ricaricato.evidence[0].source_id == "msg-1"


def test_storage_stats(repo):
    repo.upsert_signals([_signal("k1")])
    repo.replace_items_for_date(DATE, [_item("k1")], plan_version="v1")
    stats = repo.storage_stats()
    assert stats["backend_kind"] == "sqlite"
    assert stats["operational_signals"] == 1
    assert stats["daily_plan_items"] == 1
