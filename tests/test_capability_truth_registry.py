from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pct.capability_truth_registry import (
    P0_CAPABILITIES,
    P0_CAPABILITY_IDS,
    REGISTRY_VERSION,
    build_capability_truth_registry,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_capability_truth_registry_censisce_esattamente_i_diciassette_flussi_p0() -> None:
    payload = build_capability_truth_registry(application_version="test")
    entries = payload["capabilities"]

    assert len(P0_CAPABILITIES) == 17
    assert len(entries) == 17
    assert tuple(item["id"] for item in entries) == P0_CAPABILITY_IDS
    assert payload["registryVersion"] == REGISTRY_VERSION
    assert payload["summary"] == {"total": 17, "verified": 0, "partial": 0, "pending": 17, "blocked": 0}


def test_capability_truth_registry_non_promuove_prove_mancanti_e_referenza_file_reali() -> None:
    payload = build_capability_truth_registry(application_version="test")

    for capability in payload["capabilities"]:
        required = {
            "module", "owner", "route", "api", "backend", "operations", "permissions", "storage", "featureFlag",
            "tests", "lastSmoke", "environment", "evidence", "dependencies", "limitations", "rollback", "incidents", "version",
        }
        assert required.issubset(capability)
        assert capability["status"] != "verificata"
        assert capability["lastSmoke"]["status"] == "non_eseguito"
        assert {evidence["kind"] for evidence in capability["evidence"]} == {"ci", "browser", "provider"}
        assert all(evidence["status"] != "pass" for evidence in capability["evidence"])
        assert all((REPO_ROOT / test_ref).is_file() for test_ref in capability["tests"])


def test_capability_truth_registry_non_esegue_provider_o_scansioni_runtime() -> None:
    payload = build_capability_truth_registry(application_version="test")

    assert payload["contracts"] == {
        "writes": "none",
        "sourceOfTruth": "catalogo Python versionato",
        "tenantScope": "nessun dato tenant nel payload",
        "providerCalls": False,
        "runtimeScans": False,
        "secretsExposed": False,
    }


def test_generatore_capability_truth_registry_e_allineato() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/react-migration/generate_capability_truth_registry.py", "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
