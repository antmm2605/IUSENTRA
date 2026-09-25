from __future__ import annotations

import json

from scripts.analyze_caddy_latency import analyze


def test_analisi_latenza_rimuove_query_e_identificativi() -> None:
    lines = [
        json.dumps(
            {
                "ts": 100,
                "duration": 0.1,
                "status": 200,
                "request": {"uri": "/api/fascicoli/ABC123456789?token=segreto"},
            }
        ),
        json.dumps(
            {
                "ts": 101,
                "duration": 0.9,
                "status": 503,
                "request": {"uri": "/api/fascicoli/ABC123456789?token=altro"},
            }
        ),
    ]

    report = analyze(lines, since_epoch=0)

    assert report["requests"] == 2
    assert report["routes"] == [
        {
            "route": "/api/fascicoli/:id",
            "count": 2,
            "avg_ms": 500.0,
            "p95_ms": 900.0,
            "max_ms": 900.0,
            "http_5xx": 1,
        }
    ]
    assert "segreto" not in json.dumps(report)
    assert "ABC123456789" not in json.dumps(report)


def test_analisi_latenza_ignora_righe_non_valide_e_fuori_finestra() -> None:
    report = analyze(
        [
            "non-json",
            json.dumps({"ts": 4, "duration": 99, "request": {"uri": "/vecchia"}}),
            json.dumps({"ts": 6, "duration": 0.25, "status": 200, "request": {"uri": "/corrente"}}),
        ],
        since_epoch=5,
    )

    assert report["discarded_lines"] == 1
    assert report["requests"] == 1
    assert report["routes"][0]["route"] == "/corrente"
