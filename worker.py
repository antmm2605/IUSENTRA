"""Worker RQ IUSENTRA.

Avvio:
    python worker.py
"""

from __future__ import annotations

import os

from core.shutdown import register_shutdown_handlers


def main() -> int:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queues = [item.strip() for item in os.getenv("RQ_QUEUES", "default,documents,email,ocr,imports").split(",") if item.strip()]
    try:
        import redis
        from rq import Worker
    except Exception as exc:
        raise SystemExit(f"Dipendenze worker RQ non disponibili: {exc}") from exc

    conn = redis.Redis.from_url(redis_url)
    register_shutdown_handlers()
    Worker(queues, connection=conn).work(with_scheduler=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
