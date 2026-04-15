from __future__ import annotations

import statistics
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class RuntimeMetricObservation:
    bucket: str
    duration_ms: float


class RuntimeMetricsRegistry:
    """Metriche runtime leggere per endpoint HTTP e pipeline Lex."""

    def __init__(self, *, max_samples_per_bucket: int = 256) -> None:
        self._max_samples = max(32, int(max_samples_per_bucket or 256))
        self._lock = threading.Lock()
        self._http_samples: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self._max_samples)
        )
        self._lex_first_token_samples: deque[float] = deque(maxlen=self._max_samples)
        self._started_at = monotonic()

    def observe_http(self, *, method: str, endpoint: str, status_code: int, duration_ms: float) -> None:
        bucket = f"{method.upper()} {endpoint} [{int(status_code)}]"
        with self._lock:
            self._http_samples[bucket].append(float(duration_ms))

    def observe_lex_first_token(self, duration_ms: float) -> None:
        with self._lock:
            self._lex_first_token_samples.append(float(duration_ms))

    def uptime_seconds(self) -> int:
        return max(0, int(monotonic() - self._started_at))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            http_samples = {
                bucket: list(samples)
                for bucket, samples in self._http_samples.items()
                if samples
            }
            lex_first_token = list(self._lex_first_token_samples)

        return {
            "uptime_seconds": self.uptime_seconds(),
            "http": {
                "buckets": [
                    self._build_bucket_payload(bucket, samples)
                    for bucket, samples in sorted(
                        http_samples.items(),
                        key=lambda item: self._bucket_avg(item[1]),
                        reverse=True,
                    )
                ]
            },
            "lex": {
                "first_token": self._build_bucket_payload("first_token", lex_first_token),
            },
        }

    @staticmethod
    def _bucket_avg(samples: list[float]) -> float:
        return round(statistics.fmean(samples), 2) if samples else 0.0

    def _build_bucket_payload(self, bucket: str, samples: list[float]) -> dict[str, Any]:
        if not samples:
            return {
                "bucket": bucket,
                "count": 0,
                "avg_ms": 0.0,
                "p95_ms": 0.0,
                "max_ms": 0.0,
            }

        ordered = sorted(samples)
        p95_index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * 0.95)))
        return {
            "bucket": bucket,
            "count": len(ordered),
            "avg_ms": round(statistics.fmean(ordered), 2),
            "p95_ms": round(ordered[p95_index], 2),
            "max_ms": round(ordered[-1], 2),
        }
