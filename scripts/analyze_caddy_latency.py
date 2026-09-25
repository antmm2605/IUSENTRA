#!/usr/bin/env python3
"""Aggrega la latenza Caddy senza esporre query, utenti o identificativi."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
import re
import time
from pathlib import Path
from typing import Any, Iterable, TextIO


_DYNAMIC_SEGMENT = re.compile(r"^(?=.*\d)[A-Za-z0-9_-]{8,}$")


def _route(uri: object) -> str:
    path = str(uri or "/").split("?", 1)[0].split("#", 1)[0]
    segments = []
    for segment in path.split("/"):
        if not segment:
            continue
        segments.append(":id" if _DYNAMIC_SEGMENT.fullmatch(segment) else segment)
    return "/" + "/".join(segments)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    # Metodo nearest-rank: con campioni piccoli il p95 deve riflettere anche
    # il valore peggiore, non cadere artificialmente sul primo elemento.
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * percentile) - 1))
    return ordered[index]


def analyze(lines: Iterable[str], *, since_epoch: float) -> dict[str, Any]:
    durations: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    discarded = 0
    for line in lines:
        try:
            row = json.loads(line)
        except (TypeError, ValueError, json.JSONDecodeError):
            discarded += 1
            continue
        if float(row.get("ts") or 0) < since_epoch:
            continue
        request = row.get("request") if isinstance(row.get("request"), dict) else {}
        route = _route(request.get("uri"))
        durations[route].append(max(0.0, float(row.get("duration") or 0.0) * 1000.0))
        if int(row.get("status") or 0) >= 500:
            errors[route] += 1

    routes = []
    for route, samples in durations.items():
        routes.append(
            {
                "route": route,
                "count": len(samples),
                "avg_ms": round(sum(samples) / len(samples), 2),
                "p95_ms": round(_percentile(samples, 0.95), 2),
                "max_ms": round(max(samples), 2),
                "http_5xx": int(errors.get(route, 0)),
            }
        )
    routes.sort(key=lambda item: (item["p95_ms"], item["count"]), reverse=True)
    return {
        "privacy": "query, utente e identificativi dinamici esclusi",
        "requests": sum(len(samples) for samples in durations.values()),
        "routes": routes,
        "discarded_lines": discarded,
    }


def _open_log(path: str) -> tuple[Iterable[str], TextIO | None]:
    if path == "-":
        import sys

        return sys.stdin, None
    handle = Path(path).open("r", encoding="utf-8", errors="replace")
    return handle, handle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", help="File JSON Caddy oppure - per stdin")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--minimum-count", type=int, default=2)
    args = parser.parse_args()
    lines, handle = _open_log(args.log)
    try:
        result = analyze(lines, since_epoch=time.time() - max(0.0, args.hours) * 3600.0)
    finally:
        if handle is not None:
            handle.close()
    result["hours"] = args.hours
    result["routes"] = [
        item for item in result["routes"] if int(item["count"]) >= max(1, args.minimum_count)
    ][: max(1, args.top)]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
