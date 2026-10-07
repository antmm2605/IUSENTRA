from pathlib import Path
import ast
import inspect
import textwrap

from pct.scheduler_registry import SchedulerRegistryRepository


def test_existing_registry_migration_keeps_runs_and_indexes_lookup(tmp_path: Path):
    path = tmp_path / "scheduler.sqlite"
    repo = SchedulerRegistryRepository(path)
    with repo.connect() as conn:
        conn.execute("DROP INDEX idx_scheduled_job_runs_run_id")
        conn.executemany(
            """INSERT INTO scheduled_job_runs (
                run_id, job_id, origin, status, created_at
            ) VALUES (?, 'agenda', 'scheduler', 'completed', '2026-10-06T20:00:00Z')""",
            [(f"run-{number}",) for number in range(1000)],
        )
        before = [tuple(row) for row in conn.execute("SELECT * FROM scheduled_job_runs ORDER BY id")]

    migrated = SchedulerRegistryRepository(path)
    migrated.init_db()
    with migrated.connect() as conn:
        after = [tuple(row) for row in conn.execute("SELECT * FROM scheduled_job_runs ORDER BY id")]
        assert after == before
        plan = conn.execute(
            "EXPLAIN QUERY PLAN UPDATE scheduled_job_runs SET status=? WHERE run_id=?",
            ("cancelled", "run-999"),
        ).fetchall()
        assert any("USING INDEX idx_scheduled_job_runs_run_id" in row[3] for row in plan)
        assert not any("SCAN scheduled_job_runs" in row[3] for row in plan)


def test_run_index_preserves_non_unique_historical_identifiers(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    with repo.connect() as conn:
        conn.executemany(
            """INSERT INTO scheduled_job_runs (
                run_id, job_id, origin, status, created_at
            ) VALUES ('same-run', 'agenda', 'scheduler', ?, '2026-10-06T20:00:00Z')""",
            [("running",), ("completed",)],
        )
        assert conn.execute("SELECT count(*) FROM scheduled_job_runs WHERE run_id='same-run'").fetchone()[0] == 2
        index = next(row for row in conn.execute("PRAGMA index_list(scheduled_job_runs)") if row[1] == "idx_scheduled_job_runs_run_id")
        assert index[2] == 0


def test_reconciliation_uses_terminal_date_index(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    tree = ast.parse(textwrap.dedent(inspect.getsource(repo.upsert_default_jobs)))
    sql = next(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and "DELETE FROM scheduled_job_runs AS stale" in node.value
    )
    with repo.connect() as conn:
        plan = conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
        assert any(
            "idx_scheduled_job_runs_reconciliation_terminal" in row[3]
            and "scheduled_at=?" in row[3]
            for row in plan
        )
