"""Coda job RQ con fallback controllato quando Redis non e' disponibile."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class JobHandle:
    id: str
    status: str
    backend: str
    result: Any = None
    error: str = ""


class JobQueue:
    def __init__(self, redis_url: str = "", *, queue_name: str = "default") -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name
        self._queue = self._connect_queue(redis_url, queue_name)
        self._fallback_jobs: dict[str, JobHandle] = {}

    @staticmethod
    def _connect_queue(redis_url: str, queue_name: str):
        if not redis_url:
            return None
        try:
            import redis
            from rq import Queue

            conn = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
            conn.ping()
            return Queue(queue_name, connection=conn)
        except Exception:
            return None

    @property
    def backend(self) -> str:
        return "rq" if self._queue is not None else "inline-fallback"

    def enqueue(self, func: Callable[..., Any], *args: Any, timeout: int = 300, **kwargs: Any) -> JobHandle:
        if self._queue is not None:
            job = self._queue.enqueue(func, *args, job_timeout=timeout, **kwargs)
            return JobHandle(id=job.id, status="queued", backend="rq")
        job_id = f"inline-{secrets.token_urlsafe(12)}"
        try:
            result = func(*args, **kwargs)
            handle = JobHandle(id=job_id, status="finished", backend="inline-fallback", result=result)
        except Exception as exc:
            handle = JobHandle(id=job_id, status="failed", backend="inline-fallback", error=str(exc))
        self._fallback_jobs[job_id] = handle
        return handle

    def status(self, job_id: str) -> JobHandle:
        if self._queue is None:
            return self._fallback_jobs.get(job_id) or JobHandle(id=job_id, status="unknown", backend="inline-fallback")
        try:
            from rq.job import Job

            job = Job.fetch(job_id, connection=self._queue.connection)
            return JobHandle(id=job.id, status=job.get_status(), backend="rq", result=job.result)
        except Exception as exc:
            return JobHandle(id=job_id, status="unknown", backend="rq", error=str(exc))
