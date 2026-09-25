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


def test_prometheus_payload_usa_le_chiavi_reali_dello_snapshot_ocr() -> None:
    payload = prometheus_payload(
        {
            "summary": {"degraded": True},
            "runtime": {"http": {"buckets": []}},
            "ocr": {"in_coda": 4, "errori": 3},
            "alerts": [{"level": "warning"}],
        }
    )

    assert "iusentra_health_status 0" in payload
    assert "iusentra_ocr_queue_pending 4" in payload
    assert "iusentra_ocr_jobs_failed 3" in payload


def test_prometheus_payload_non_sostituisce_lo_zero_reale_con_alias_storici() -> None:
    payload = prometheus_payload(
        {
            "summary": {"degraded": False},
            "runtime": {"http": {"buckets": []}},
            "ocr": {"in_coda": 0, "pending": 8, "errori": 0, "failed": 6},
            "alerts": [],
        }
    )

    assert "iusentra_ocr_queue_pending 0" in payload
    assert "iusentra_ocr_jobs_failed 0" in payload
