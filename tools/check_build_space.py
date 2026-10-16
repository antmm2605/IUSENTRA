"""Preflight read-only: budget fisico per volume, distinto dallo spazio Docker."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

GIB = 1024 ** 3


def positive_gib(value: str) -> int:
    amount = float(value)
    if not math.isfinite(amount) or amount <= 0 or not math.isfinite(amount * GIB):
        raise ValueError("Il budget deve essere positivo e finito")
    return math.ceil(amount * GIB)


def assess(measurements: list[dict]) -> dict:
    """Ruoli sullo stesso volume consumano un budget cumulativo."""
    volumes: dict[str, dict] = {}
    if not measurements:
        raise ValueError("Nessun volume verificato")
    for item in measurements:
        if item["required_bytes"] <= 0 or item["free_bytes"] < 0:
            raise ValueError("Misura o budget non validi")
        device = str(item["device"])
        volume = volumes.setdefault(device, {"device": device, "paths": [],
            "required_bytes": 0, "free_bytes": item["free_bytes"]})
        volume["paths"].append(item["path"])
        volume["required_bytes"] += item["required_bytes"]
        volume["free_bytes"] = min(volume["free_bytes"], item["free_bytes"])
    for volume in volumes.values():
        volume["ok"] = volume["free_bytes"] >= volume["required_bytes"]
    return {"ok": all(v["ok"] for v in volumes.values()),
            "volumes": list(volumes.values())}


def measure(path: str, required_bytes: int) -> dict:
    target = Path(path).resolve(strict=True)
    if not target.is_dir():
        raise ValueError("Il percorso del budget deve essere una cartella")
    return {"path": str(target), "device": target.stat().st_dev,
            "free_bytes": shutil.disk_usage(target).free,
            "required_bytes": required_bytes}


def engine_measure(container: str, required_bytes: int) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", container):
        raise ValueError("Nome container non valido")
    code = "import json,shutil;print(json.dumps({'free_bytes':shutil.disk_usage('/').free}))"
    result = subprocess.run(["docker", "exec", container, "python", "-c", code],
        check=True, capture_output=True, text=True, timeout=20)
    free = json.loads(result.stdout)["free_bytes"]
    if type(free) is not int or free < 0:
        raise ValueError("Misura Docker non valida")
    return {"free_bytes": free, "required_bytes": required_bytes,
            "ok": free >= required_bytes, "container": container}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path-budget", action="append", default=[],
        help="Cartella=GiB; budget distinti sullo stesso volume vengono sommati")
    parser.add_argument("--docker-root-budget-gib",
        help="Budget del filesystem Docker locale al server (non Docker Desktop)")
    parser.add_argument("--engine-container",
        help="Container esistente per misurare separatamente il disco virtuale")
    parser.add_argument("--engine-budget-gib", default="20")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report: dict = {"ok": False}
    try:
        measurements = []
        for specification in args.path_budget:
            path, amount = specification.rsplit("=", 1)
            measurements.append(measure(path, positive_gib(amount)))
        if args.docker_root_budget_gib:
            root = subprocess.run(["docker", "info", "--format", "{{.DockerRootDir}}"],
                check=True, capture_output=True, text=True, timeout=20).stdout.strip()
            measurements.append(measure(root, positive_gib(args.docker_root_budget_gib)))
        report = assess(measurements)
        if args.engine_container:
            report["engine"] = engine_measure(args.engine_container,
                positive_gib(args.engine_budget_gib))
            report["ok"] = report["ok"] and report["engine"]["ok"]
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        report = {"ok": False, "error": str(exc)}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
