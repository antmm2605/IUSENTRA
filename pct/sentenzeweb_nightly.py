"""Nightly public acquisition, sharing the historical collector and its lock."""

import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import requests

INTERMEDIATE_SHA256 = "74059aea6296cda7202c510ab109d92fc5bd2be0e17b2043dff97fdb88d04137"


def tls_bundle(directory):
    intermediate = Path(__file__).with_name("certificates") / "ti_trust_ov_ca.pem"
    extra = intermediate.read_bytes()
    if hashlib.sha256(extra).hexdigest() != INTERMEDIATE_SHA256:
        raise ValueError("Unexpected public intermediate certificate")
    data = Path(requests.certs.where()).read_bytes() + b"\n" + extra
    path = directory / ("ca-" + hashlib.sha256(data).hexdigest() + ".pem")
    try:
        with path.open("xb") as handle:
            os.chmod(path, 0o644)  # Public CA material; integrity-checked across app/worker UIDs.
            handle.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError("Existing TLS bundle differs") from None
    return path


def run_nightly(config):
    value = str(
        config.get("IUSENTRA_SENTENZEWEB_DIRECTORY") or os.getenv("IUSENTRA_SENTENZEWEB_DIRECTORY") or ""
    ).strip()
    if not value:
        return {"ok": False, "status": "not_configured", "downloaded": False}
    directory = Path(value).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    bundle = tls_bundle(directory)
    command = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "tools/sentenzeweb_importa.py"),
        "--directory",
        str(directory),
        "--ca-bundle",
        str(bundle),
        "--incremental",
        "--max-pages",
        "1000",
    ]
    environment = os.environ.copy()
    for key in ("IUSENTRA_SENTENZEWEB_BRIDGE_URL", "IUSENTRA_SENTENZEWEB_BRIDGE_TOKEN"):
        if config.get(key):
            environment[key] = str(config[key])
    process = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False, env=environment)
    if process.returncode == 75:
        return {"ok": True, "status": "already_running", "downloaded": False}
    if process.returncode:
        raise RuntimeError("SentenzeWeb acquisition failed; checkpoint and original responses preserved")
    with sqlite3.connect((directory / "giurisprudenza_corpus.db").as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        progress = dict(
            connection.execute("SELECT seen,expected,status FROM sentenzeweb_progress WHERE id=1").fetchone()
        )
    recovery_command = [sys.executable,
        str(Path(__file__).resolve().parents[1] / "tools/sentenzeweb_recupera.py"),
        "--directory", str(directory), "--max-records", "25"]
    recovery = subprocess.run(recovery_command, capture_output=True, text=True,
                              timeout=1200, check=False, env=environment)
    if recovery.returncode not in (0, 75):
        raise RuntimeError("Public recovery failed; native queue and preserved originals retained")
    return {
        "ok": True,
        "recovery_status": "already_running" if recovery.returncode == 75 else "bounded_batch_completed",
        "status": progress["status"],
        "source_records": progress["seen"],
        "expected": progress["expected"],
        "downloaded": progress["seen"] > 0,
    }
