from __future__ import annotations

from core.jobs import JobQueue


def _add(a: int, b: int) -> int:
    return a + b


def _fail() -> None:
    raise RuntimeError("boom")


def test_job_queue_inline_fallback_success() -> None:
    queue = JobQueue("")
    handle = queue.enqueue(_add, 2, 3)
    assert handle.backend == "inline-fallback"
    assert handle.status == "finished"
    assert handle.result == 5
    assert queue.status(handle.id).result == 5


def test_job_queue_inline_fallback_failure() -> None:
    queue = JobQueue("")
    handle = queue.enqueue(_fail)
    assert handle.status == "failed"
    assert "boom" in handle.error
