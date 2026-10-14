"""Confronto riproducibile dei dodici artefatti di copertura critica."""
from __future__ import annotations

import argparse
import hashlib
import io
import importlib.metadata
import json
import os
import platform
import re
import runpy
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from contextlib import chdir
from fractions import Fraction
from pathlib import Path
from typing import Any


SHARDS = frozenset(range(1, 13))
SCOPE = ("lex", "pct.auth", "pct.storage", "pct.storage_postgres",
         "pct.telematico_repository", "pct.telematico_workflow")
ENVIRONMENT_KEYS = ("python", "coverage", "config_sha256", "requirements_sha256", "distributions_sha256", "scope")
REPO_ROOT = Path(__file__).resolve().parents[1]


def collect_shards(directory: Path) -> list[Path]:
    found: dict[int, Path] = {}
    for path in directory.rglob(".coverage.critical.*"):
        match = re.fullmatch(r"\.coverage\.critical\.(\d+)", path.name)
        if not match:
            continue
        number = int(match.group(1))
        if number not in SHARDS or number in found:
            raise ValueError("Artefatti di copertura duplicati o shard non previsto")
        found[number] = path
    if set(found) != SHARDS:
        missing = sorted(SHARDS - set(found))
        raise ValueError(f"Artefatti mancanti: shard {missing}")
    return [found[number] for number in sorted(SHARDS)]


def package_versions() -> dict[str, str]:
    packages = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name", "")
        version = distribution.version
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", version):
            raise ValueError("Nome o versione del pacchetto installato non registrabile nel congelamento")
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in packages and packages[key] != version:
            raise ValueError("Versioni discordanti dello stesso pacchetto installato")
        packages[key] = version
    return dict(sorted(packages.items()))


def environment(root: Path, lock: Path | None = None) -> dict[str, Any]:
    import coverage

    digest = hashlib.sha256()
    if lock:
        digest.update(lock.read_bytes().replace(b"\r\n", b"\n"))
    else:
        for name in ("requirements.txt", "requirements-dev.txt", "requirements/constraints.txt"):
            digest.update(name.encode())
            digest.update((root / name).read_bytes().replace(b"\r\n", b"\n"))
    return {
        "python": platform.python_version(), "coverage": coverage.__version__,
        "config_sha256": hashlib.sha256((root / "config/coverage-critical.ini").read_bytes()
                                        .replace(b"\r\n", b"\n")).hexdigest(),
        "requirements_sha256": digest.hexdigest(), "scope": list(SCOPE),
        "distributions_sha256": hashlib.sha256(json.dumps(package_versions(), sort_keys=True).encode()).hexdigest(),
    }


def test_suite_digest(root: Path) -> str:
    registry = runpy.run_path(str(root / "scripts/run_pytest_phases.py"))
    selected = set()
    for target in registry["CI_TEST_SUITES"]["coverage-critical"]:
        selected.update(target.rglob("test_*.py") if target.is_dir() else [target])
    digest = hashlib.sha256()
    for path in sorted(selected):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def compare_measurements(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    for measurement in (baseline, candidate):
        if not isinstance(measurement, dict) or not isinstance(measurement.get("environment"), dict):
            raise ValueError("Metadati di misura non validi")
        if set(measurement.get("shards", [])) != SHARDS or len(measurement["shards"]) != 12:
            raise ValueError("Servono tutti e dodici gli shard, senza duplicati")
        for key in ENVIRONMENT_KEYS:
            if key not in measurement.get("environment", {}):
                raise ValueError(f"Metadato di ambiente mancante: {key}")
        if not measurement.get("files"):
            raise ValueError("Perimetro misurato assente")
        for item in measurement["files"].values():
            if not isinstance(item.get("source_sha256"), str) or len(item["source_sha256"]) != 64:
                raise ValueError("Impronta del sorgente misurato assente")
            if not isinstance(item.get("statements"), int) or not isinstance(item.get("covered"), int):
                raise ValueError("Conteggi di copertura non validi")
            if not 0 <= item["covered"] <= item["statements"]:
                raise ValueError("Conteggi di copertura incoerenti")
    old, new = baseline["files"], candidate["files"]
    environment_changes = [key for key in ENVIRONMENT_KEYS
                           if baseline["environment"][key] != candidate["environment"][key]]
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    changed = sorted(path for path in old.keys() & new.keys()
                     if (old[path]["source_sha256"], old[path]["statements"])
                     != (new[path]["source_sha256"], new[path]["statements"]))
    totals = {}
    for name, files in (("baseline", old), ("candidate", new)):
        covered = sum(item["covered"] for item in files.values())
        statements = sum(item["statements"] for item in files.values())
        if not statements:
            raise ValueError("Perimetro misurato privo di istruzioni")
        totals[name] = {"covered": covered, "statements": statements,
                        "percent": float(Fraction(100 * covered, statements))}
    report = {"baseline": totals["baseline"], "candidate": totals["candidate"],
              "environment_changes": environment_changes, "added_files": added,
              "removed_files": removed, "changed_sources": changed,
              "test_suite_changed": baseline.get("test_suite_sha256") != candidate.get("test_suite_sha256")}
    lost_lines = {path: sorted(set(old[path].get("executed_lines", [])) - set(new[path].get("executed_lines", [])))
                  for path in old.keys() & new.keys() if path not in changed}
    report["previously_covered_lines_lost"] = {path: lines for path, lines in lost_lines.items() if lines}
    if environment_changes or added or removed:
        report.update(status="non_homogeneous", blocking=True,
                      reason="Confronto non omogeneo: verificare ambiente e perimetro prima di accettare una nuova baseline")
    elif report["previously_covered_lines_lost"] or Fraction(totals["candidate"]["covered"], totals["candidate"]["statements"]) < Fraction(
            totals["baseline"]["covered"], totals["baseline"]["statements"]):
        report.update(status="regression", blocking=True, reason="Calo reale della copertura critica")
    else:
        report.update(status="accepted", blocking=False, reason="Copertura critica preservata o migliorata")
    return report


def measure(directory: Path, source_root: Path, output: Path, metadata: dict[str, Any],
            original_root: str = "/home/runner/work/IUSENTRA/IUSENTRA") -> dict[str, Any]:
    import coverage

    directory, source_root, output = directory.resolve(), source_root.resolve(), output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    shards = collect_shards(directory)
    combined = coverage.CoverageData(basename=str(output.with_suffix(".combined")))
    prefix = original_root.rstrip("/") + "/"

    def remap(path: str) -> str:
        if not path.startswith(prefix):
            raise ValueError(f"Percorso di misura inatteso: {path}")
        relative = path[len(prefix):]
        allowed = {name.replace(".", "/") + ".py" for name in SCOPE if name != "lex"}
        if (not relative.startswith("lex/") and relative not in allowed) or not relative.endswith(".py"):
            raise ValueError("Artefatto riferito a un sorgente esterno al perimetro critico")
        target = (source_root / relative).resolve()
        if not target.is_relative_to(source_root.resolve()):
            raise ValueError("Percorso di misura esterno al repository")
        return str(target)

    for shard in shards:
        sidecar = shard.with_name(shard.name + ".metadata.json")
        if sidecar.exists():
            prefix = json.loads(sidecar.read_text(encoding="utf-8"))["source_root"].rstrip("/") + "/"
        with sqlite3.connect(f"file:{shard.as_posix()}?mode=ro", uri=True) as connection:
            original_version = connection.execute("select value from meta where key='version'").fetchone()
        if not original_version or original_version[0] != metadata["coverage"]:
            raise ValueError("Versione originale di coverage non omogenea negli artefatti")
        if coverage.__version__ != metadata["coverage"]:
            raise ValueError("Versione dell'analizzatore differente dalla misura originale")
        data = coverage.CoverageData(basename=str(shard))
        data.read()
        combined.update(data, map_path=remap)
    combined.write()
    with chdir(source_root):
        analyzer = coverage.Coverage(data_file=str(output.with_suffix(".combined")),
                                     config_file=str(source_root / "config/coverage-critical.ini"))
        analyzer.load()
        analyzer.json_report(outfile=str(output))
    raw = json.loads(output.read_text(encoding="utf-8"))
    files = {}
    for name, item in raw["files"].items():
        path = Path(name)
        if not path.is_absolute():
            path = source_root / path
        relative = path.resolve().relative_to(source_root.resolve()).as_posix()
        files[relative] = {"covered": item["summary"]["covered_lines"],
                           "statements": item["summary"]["num_statements"],
                           "executed_lines": item["executed_lines"],
                           "source_sha256": hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()}
    return {"shards": sorted(SHARDS), "environment": metadata, "files": files}


def github_json(repo: str, endpoint: str) -> dict[str, Any]:
    response = subprocess.run(["gh", "api", f"repos/{repo}/{endpoint}"], check=True, capture_output=True, text=True)
    return json.loads(response.stdout)


def select_artifact_names(artifacts: list[dict[str, Any]], family: str, attempt: int) -> list[str]:
    selected: dict[int, tuple[int, str]] = {}
    pattern = re.compile(re.escape(family) + r"-(\d+)(?:-attempt-(\d+))?$")
    for artifact in artifacts:
        match = pattern.fullmatch(artifact["name"])
        if not match or artifact.get("expired"):
            continue
        shard, revision = int(match.group(1)), int(match.group(2) or 0)
        if shard not in SHARDS:
            raise ValueError("Shard non previsto nel registro degli artefatti")
        if revision > attempt:
            continue
        previous = selected.get(shard)
        if previous and previous[0] == revision:
            raise ValueError("Artefatti ambigui per il medesimo shard e tentativo")
        if not previous or previous[0] < revision:
            selected[shard] = (revision, artifact["name"])
    if set(selected) != SHARDS:
        raise ValueError(f"Artefatti mancanti o scaduti: shard {sorted(SHARDS - set(selected))}")
    return [selected[shard][1] for shard in sorted(SHARDS)]


def download_shards(repo: str, run_id: int, family: str, destination: Path, attempt: int) -> None:
    artifacts = []
    for page in range(1, 11):
        result = github_json(repo, f"actions/runs/{run_id}/artifacts?per_page=100&page={page}")
        artifacts.extend(result["artifacts"])
        if len(artifacts) >= result["total_count"]:
            break
    else:
        raise ValueError("Registro degli artefatti oltre il limite di acquisizione governata")
    names = select_artifact_names(artifacts, family, attempt)
    command = ["gh", "run", "download", str(run_id), "--repo", repo, "--dir", str(destination)]
    for name in names:
        command.extend(["--name", name])
    subprocess.run(command, check=True)


def select_baseline(repo: str, candidate_sha: str) -> tuple[dict[str, Any], dict[str, Any]]:
    deployments = github_json(repo, "actions/workflows/deploy-hetzner.yml/runs?branch=main&status=success&per_page=100")
    eligible = [run for run in deployments["workflow_runs"] if run["head_sha"] != candidate_sha]
    if not eligible:
        raise ValueError("Nessuna versione precedente accettata dal deploy main")
    deploy = max(eligible, key=lambda run: run["updated_at"])
    checks = github_json(repo, f"actions/workflows/ci.yml/runs?head_sha={deploy['head_sha']}&status=success&per_page=100")
    matched = [run for run in checks["workflow_runs"] if run["head_sha"] == deploy["head_sha"]]
    if not matched:
        raise ValueError("Baseline distribuita priva della CI positiva sul medesimo commit")
    return deploy, max(matched, key=lambda run: run["updated_at"])


def load_metadata(directory: Path, expected_sha: str) -> tuple[dict[str, Any], str, str]:
    records = []
    for path in collect_shards(directory):
        sidecar = path.with_name(path.name + ".metadata.json")
        record = json.loads(sidecar.read_text(encoding="utf-8"))
        if record["sha"] != expected_sha or record["shard"] != int(path.name.rsplit(".", 1)[1]):
            raise ValueError("Metadati non riferiti allo shard e al commit richiesti")
        if not isinstance(record.get("source_root"), str) or not Path(record["source_root"]).is_absolute():
            raise ValueError("Percorso originale del sorgente assente o non valido")
        records.append(record)
    if any((record["environment"], record["test_suite_sha256"])
           != (records[0]["environment"], records[0]["test_suite_sha256"])
           for record in records):
        raise ValueError("Ambienti o tentativi discordanti fra i dodici shard")
    return records[0]["environment"], records[0]["test_suite_sha256"], records[0]["source_root"]


def archive_sources(sha: str, destination: Path) -> None:
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], check=False)
    if ancestor.returncode:
        raise ValueError("La baseline accettata non appartiene alla storia della candidata")
    archive = subprocess.run(["git", "archive", sha, "lex", "pct", "tests", "scripts/run_pytest_phases.py",
                              "config/coverage-critical.ini", "requirements.txt", "requirements-dev.txt",
                              "requirements"], check=True, capture_output=True)
    destination.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as bundle:
        bundle.extractall(destination, filter="data")


def prepare_environment(repo: str, output: Path) -> None:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    deploy, ci = select_baseline(repo, sha)
    if not re.fullmatch(r"[0-9a-f]{40}", deploy["head_sha"]):
        raise ValueError("Commit della baseline non valido")
    output.mkdir(parents=True, exist_ok=True)
    info = {"sha": deploy["head_sha"], "candidate_sha": sha, "ci_run_id": ci["id"], "deploy_run_id": deploy["id"]}
    (output / "baseline.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    frozen = "".join(f"{name}=={version}\n" for name, version in package_versions().items())
    (output / "critical-env-freeze.txt").write_text(frozen, encoding="utf-8")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as destination:
            destination.write(f"baseline_sha={info['sha']}\n")
            destination.write(f"environment_artifact=critical-measurement-environment-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}\n")


def run_gate(repo: str, candidate_directory: Path, baseline_directory: Path,
             baseline_info: Path, output: Path, lock: Path) -> dict[str, Any]:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    info = json.loads(baseline_info.read_text(encoding="utf-8"))
    deploy, ci = select_baseline(repo, sha)
    if (info["sha"], info["candidate_sha"]) != (deploy["head_sha"], sha):
        raise ValueError("La baseline accettata è cambiata durante il collaudo")
    run_id, attempt = int(os.environ["GITHUB_RUN_ID"]), int(os.environ["GITHUB_RUN_ATTEMPT"])
    download_shards(repo, run_id, "coverage-critical", candidate_directory, attempt)
    download_shards(repo, run_id, "coverage-baseline", baseline_directory, attempt)
    with tempfile.TemporaryDirectory(prefix="iusentra-critical-baseline-") as temporary:
        work = Path(temporary)
        source = work / "source"
        archive_sources(ci["head_sha"], source)
        baseline_environment, baseline_tests, baseline_root = load_metadata(baseline_directory, ci["head_sha"])
        candidate_environment, candidate_tests, candidate_root = load_metadata(candidate_directory, sha)
        if environment(REPO_ROOT, lock) != candidate_environment or environment(source, lock) != baseline_environment:
            raise ValueError("L'ambiente del confronto non coincide con gli shard candidati")
        baseline = measure(baseline_directory, source, output / "baseline-measurement.json", baseline_environment, baseline_root)
        candidate = measure(candidate_directory, REPO_ROOT, output / "candidate-measurement.json", candidate_environment, candidate_root)
        baseline["test_suite_sha256"], candidate["test_suite_sha256"] = baseline_tests, candidate_tests
        report = compare_measurements(baseline, candidate)
        report.update(baseline_sha=ci["head_sha"], candidate_sha=sha,
                      baseline_ci_run=ci["id"], baseline_deploy_run=deploy["id"],
                      baseline_remeasured=True, measurement_ci_run=os.environ.get("GITHUB_RUN_ID"))
        original_directory = work / "original-artifacts"
        download_shards(repo, ci["id"], "coverage-critical", original_directory, ci["run_attempt"])
        collect_shards(original_directory)
        original = measure(original_directory, source, output / "original-baseline-measurement.json",
                           baseline_environment)
        report["original_baseline"] = {
            "covered": sum(item["covered"] for item in original["files"].values()),
            "statements": sum(item["statements"] for item in original["files"].values()),
        }
        return report


def render_report(report: dict[str, Any]) -> str:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from pct.formatting import format_datetime_it

    lines = ["# Confronto della copertura critica", "",
             f"Generato: {format_datetime_it(datetime.now(UTC))}", "", report["reason"], ""]
    for name, label in (("baseline", "Baseline accettata"), ("candidate", "Candidata")):
        if name in report:
            value = report[name]
            percent = f"{value['percent']:.7f}".replace(".", ",")
            lines.append(f"- {label}: {value['covered']}/{value['statements']} — {percent}%")
    for key, label in (("baseline_sha", "Commit baseline"), ("candidate_sha", "Commit candidata"),
                       ("environment_changes", "Differenze di ambiente"), ("added_files", "Moduli aggiunti"),
                       ("removed_files", "Moduli rimossi"), ("changed_sources", "Sorgenti modificati")):
        if report.get(key):
            lines.append(f"- {label}: {report[key]}")
    lines.append("\nUna variazione del perimetro non è presentata come un calo reale né accettata silenziosamente.")
    if report.get("baseline_remeasured"):
        lines.append("La precedente versione accettata è rimisurata nei dodici shard con lo stesso ambiente congelato della candidata.")
    if report.get("original_baseline"):
        original = report["original_baseline"]
        lines.append(f"Misura originale conservata: {original['covered']}/{original['statements']} istruzioni coperte.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--github-repo")
    parser.add_argument("--candidate-directory", type=Path)
    parser.add_argument("--baseline-directory", type=Path)
    parser.add_argument("--baseline-info", type=Path)
    parser.add_argument("--prepare-directory", type=Path)
    parser.add_argument("--environment-lock", type=Path)
    parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--record-metadata", type=Path)
    parser.add_argument("--shard", type=int)
    args = parser.parse_args()
    if args.prepare_directory:
        if not args.github_repo:
            parser.error("Specificare il repository GitHub della baseline")
        prepare_environment(args.github_repo, args.prepare_directory)
        return 0
    if args.record_metadata:
        if args.shard not in SHARDS:
            parser.error("Specificare uno shard da 1 a 12")
        record = {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.source_root, text=True).strip(),
                  "shard": args.shard, "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
                  "source_root": args.source_root.resolve().as_posix(),
                  "environment": environment(args.source_root, args.environment_lock),
                  "test_suite_sha256": test_suite_digest(args.source_root)}
        args.record_metadata.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return 0
    if not args.report:
        parser.error("Specificare il percorso del report")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.github_repo and args.candidate_directory and args.baseline_directory and args.baseline_info and args.environment_lock:
            report = run_gate(args.github_repo, args.candidate_directory, args.baseline_directory,
                              args.baseline_info, args.report.parent, args.environment_lock)
        elif args.baseline and args.candidate:
            report = compare_measurements(json.loads(args.baseline.read_text(encoding="utf-8")),
                                          json.loads(args.candidate.read_text(encoding="utf-8")))
        else:
            raise ValueError("Specificare gli artefatti GitHub o due misure complete")
    except (OSError, sqlite3.Error, tarfile.TarError, subprocess.CalledProcessError, ImportError) as error:
        report = {"status": "invalid", "blocking": True,
                  "reason": "Acquisizione o lettura della misura non riuscita: artefatti, sorgenti e ambiente devono essere disponibili.",
                  "technical_details": str(error)}
    except (ValueError, KeyError, TypeError) as error:
        report = {"status": "invalid", "blocking": True, "reason": str(error)}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.with_suffix(".md").write_text(render_report(report), encoding="utf-8")
    print(report["reason"])
    return int(report["blocking"])


if __name__ == "__main__":
    raise SystemExit(main())
