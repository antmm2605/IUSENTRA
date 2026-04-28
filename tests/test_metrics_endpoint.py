from __future__ import annotations

from core.metrics import prometheus_payload


def test_prometheus_payload_contains_core_metrics() -> None:
    payload = prometheus_payload(
        {
            "summary": {"degraded": False},
            "runtime": {"http": {"buckets": [{"bucket": "GET /", "count": 2, "avg_ms": 5.0, "p95_ms": 7.0}]}},
            "ocr": {"pending": 1, "failed": 0},
            "alerts": [{"level": "warning"}],
        }
    )
    assert "iusentra_health_status 1" in payload
    assert "iusentra_http_requests_total" in payload
    assert "iusentra_ocr_queue_pending 1" in payload
    assert "iusentra_alerts_total 1" in payload
