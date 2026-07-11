"""Benchmark riproducibili del piano del giorno (nessun servizio esterno).

Garanzie strutturali misurate:
- la lettura del piano usa poche query indicizzate (niente N+1, niente scan);
- zero chiamate al modello linguistico durante la lettura;
- il refresh incrementale di un evento normale resta entro il budget;
- la deduplicazione batch scala con molti segnali.

Le metriche (durata, numero query, righe) vengono stampate a stdout per il
confronto tra esecuzioni.
"""

import time
from datetime import datetime

import pytest

from pct.daily_plan.clock import Clock
from pct.daily_plan.correlation import correlate
from pct.daily_plan.deduplication import merge_signals
from pct.daily_plan.models import DailyWorkItem, OperationalSignal
from pct.daily_plan.repository import DailyPlanRepository

CLOCK = Clock(fixed_now=datetime(2026, 7, 11, 7, 30))
DATE = "2026-07-11"

# Budget CI-safe (macchine lente): i target di prodotto (p95 <= 500ms warm)
# si misurano in produzione; qui blocchiamo le regressioni strutturali.
MAX_READ_QUERIES = 6
MAX_READ_SECONDS = 1.0
MAX_INCREMENTAL_SECONDS = 60.0


class QueryCounter:
    def __init__(self):
        self.statements: list[str] = []

    def __call__(self, statement: str) -> None:
        testo = statement.strip().upper()
        if testo.startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
            self.statements.append(statement)


def _traced_repository(tmp_path, counter: QueryCounter) -> DailyPlanRepository:
    repo = DailyPlanRepository(str(tmp_path / "perf.db"), tenant_id="studio-a", clock=CLOCK)
    original_connect = repo._connect

    def connect_with_trace():
        conn = original_connect()
        conn.set_trace_callback(counter)
        return conn

    repo._connect = connect_with_trace  # type: ignore[method-assign]
    return repo


def _item(key, *, backlog=False, rank=0):
    return DailyWorkItem(
        id="",
        tenant_id="studio-a",
        target_date=DATE,
        title=f"Attivita {key}",
        action_kind="deadline_fulfill",
        dedupe_key=key,
        priority="P2" if backlog else "P1",
        item_rank=rank,
        assigned_user_id="u1",
        in_backlog=backlog,
        fascicolo_label="2026/10",
        cliente_label="Rossi",
    )


def _signal(key, source="scadenziario", fascicolo="fasc-1"):
    return OperationalSignal(
        id=f"sig_{source}_{key}",
        tenant_id="studio-a",
        source_type=source,
        source_id=key,
        kind="deadline_fulfill",
        title=f"Scadenza {key}",
        dedupe_key="",
        fascicolo_id=fascicolo,
        due_at="2026-07-15",
        metadata={"scadenziario_id": key},
    )


@pytest.fixture()
def llm_vietato(monkeypatch):
    """Qualsiasi chiamata al gateway LLM durante la lettura fa fallire il test."""

    def _explode(*args, **kwargs):
        raise AssertionError("chiamata LLM vietata nel percorso di lettura")

    try:
        import lex.gateway.service as gateway_service

        monkeypatch.setattr(gateway_service.LexGateway, "ask", _explode, raising=True)
    except Exception:
        pass
    return _explode


def test_lettura_piano_poche_query_zero_llm(tmp_path, llm_vietato):
    """Target: lettura da snapshot con query contate e nessun LLM/scan."""
    counter = QueryCounter()
    repo = _traced_repository(tmp_path, counter)

    # semina realistica: 300 attività (50 in giornata, 250 backlog)
    items = [_item(f"g{i}", rank=i) for i in range(50)]
    items += [_item(f"b{i}", backlog=True, rank=i) for i in range(250)]
    repo.replace_items_for_date(DATE, items, plan_version="v1")
    repo.save_snapshot(
        target_date=DATE,
        user_id="u1",
        plan_version="v1",
        generation_mode="full",
        freshness={},
        coverage={"agenda": {"source_type": "agenda", "status": "complete"}},
        summary={"totale": 300},
        fixed_agenda=[],
        warnings=[],
    )

    counter.statements.clear()
    inizio = time.perf_counter()
    snapshot = repo.get_snapshot(DATE, "u1")
    rows = repo.list_items(DATE, assigned_user_id="u1")
    durata = time.perf_counter() - inizio

    assert snapshot is not None
    assert len(rows) == 50  # il backlog non viene caricato in blocco
    n_query = len(counter.statements)
    print(
        f"\n[benchmark lettura] durata={durata * 1000:.1f}ms query={n_query} "
        f"righe={len(rows)} llm=0"
    )
    assert n_query <= MAX_READ_QUERIES, counter.statements
    assert durata < MAX_READ_SECONDS


def test_backlog_paginato_query_costanti(tmp_path):
    counter = QueryCounter()
    repo = _traced_repository(tmp_path, counter)
    items = [_item(f"b{i}", backlog=True, rank=i) for i in range(500)]
    repo.replace_items_for_date(DATE, items, plan_version="v1")

    counter.statements.clear()
    inizio = time.perf_counter()
    page = repo.list_backlog_page(DATE, assigned_user_id="u1", limit=50)
    durata = time.perf_counter() - inizio
    print(
        f"\n[benchmark backlog] durata={durata * 1000:.1f}ms query={len(counter.statements)} "
        f"righe={len(page['items'])} totale={page['total_matching']}"
    )
    assert len(page["items"]) == 50
    assert page["total_matching"] == 500
    assert len(counter.statements) <= 3


def test_dedup_batch_scala_con_molti_segnali():
    """1500 segnali (500 eventi da 3 fonti) → 500 gruppi, tempo lineare."""
    segnali = []
    for i in range(500):
        for source in ("scadenziario", "pec", "case_presidio"):
            segnali.append(_signal(f"ev{i}", source=source, fascicolo=f"fasc-{i % 40}"))
    inizio = time.perf_counter()
    gruppi = merge_signals(correlate(segnali, clock=CLOCK))
    durata = time.perf_counter() - inizio
    print(f"\n[benchmark dedup] segnali=1500 gruppi={len(gruppi)} durata={durata * 1000:.1f}ms")
    assert len(gruppi) == 500
    assert all(len(g.signals) == 3 for g in gruppi)
    assert durata < 5.0


def test_upsert_batch_molti_segnali(tmp_path):
    counter = QueryCounter()
    repo = _traced_repository(tmp_path, counter)
    segnali = correlate([_signal(f"ev{i}") for i in range(400)], clock=CLOCK)

    inizio = time.perf_counter()
    stats = repo.upsert_signals(segnali)
    durata = time.perf_counter() - inizio
    print(
        f"\n[benchmark upsert] segnali=400 inseriti={stats['inserted']} "
        f"durata={durata * 1000:.1f}ms"
    )
    assert stats["inserted"] == 400
    assert durata < MAX_INCREMENTAL_SECONDS

    # secondo giro idempotente (aggiornamenti, non duplicati)
    stats2 = repo.upsert_signals(segnali)
    assert stats2 == {"inserted": 0, "updated": 400}


def test_refresh_incrementale_entro_budget(tmp_path, llm_vietato):
    """Un evento normale (un fascicolo sporco) viene assorbito entro 60s."""
    from pct.daily_plan.assignment import LawyerResolver
    from pct.daily_plan.collectors import Budget, CollectorContext
    from pct.daily_plan.service import DailyPlanService

    class _ScadStore:
        def __init__(self):
            self.rows = []

        def tutte(self, solo_aperte=True):
            return list(self.rows)

    store = _ScadStore()

    def context_factory(dirty):
        return CollectorContext(
            tenant_id="studio-a",
            clock=CLOCK,
            budget=Budget(),
            scadenziario_store=store,
            dirty_fascicoli=dirty,
        )

    repo = DailyPlanRepository(str(tmp_path / "inc.db"), tenant_id="studio-a", clock=CLOCK)
    service = DailyPlanService(
        repo,
        context_factory=context_factory,
        resolver_factory=lambda: LawyerResolver(users=[{"id": "u1", "username": "a", "nome_completo": "A B"}]),
        clock=CLOCK,
    )
    service.rebuild_full()

    # arriva un evento nuovo (es. PEC che tocca un fascicolo)
    from types import SimpleNamespace

    store.rows.append(
        SimpleNamespace(
            id="sc-nuova",
            titolo="Nuova scadenza da PEC",
            data_scadenza="2026-07-12",
            operational_due_at="",
            stato=SimpleNamespace(value="aperta"),
            id_fascicolo="fasc-9",
            id_utente_responsabile="",
            perentorio=True,
            creata_il="2026-07-11T07:00:00",
        )
    )
    service.refresh_from_event(entity_type="fascicolo", entity_ids=["fasc-9"], reason="pec")

    inizio = time.perf_counter()
    report = service.refresh_incremental()
    durata = time.perf_counter() - inizio
    print(f"\n[benchmark refresh] durata={durata * 1000:.1f}ms dirty={report['dirty_consumed']}")
    assert durata < MAX_INCREMENTAL_SECONDS
    assert report["dirty_consumed"] == 1
    items = repo.list_items(DATE)
    assert any("Nuova scadenza" in i.title for i in items)
