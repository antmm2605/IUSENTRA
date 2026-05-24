from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / ".github" / "required-checks.json"
SUCCESSFUL_STATUS_STATES = {"success"}


@dataclass(frozen=True)
class RequiredCheck:
    name: str
    events: tuple[str, ...]
    accepted_conclusions: tuple[str, ...] = ("success",)


@dataclass(frozen=True)
class GateRow:
    name: str
    status: str
    conclusion: str
    state: str
    url: str = ""


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_matches(required_events: tuple[str, ...], event: str) -> bool:
    if event == "workflow_dispatch":
        event = "push"
    return event in required_events


def _as_tuple(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def expand_required_checks(config: dict[str, Any], event: str | None = None) -> list[RequiredCheck]:
    checks: list[RequiredCheck] = []

    def maybe_append(raw: dict[str, Any], name: str) -> None:
        events = _as_tuple(raw.get("events"), ("push", "pull_request"))
        if event and not _event_matches(events, event):
            return
        checks.append(
            RequiredCheck(
                name=name,
                events=events,
                accepted_conclusions=_as_tuple(raw.get("accepted_conclusions"), ("success",)),
            )
        )

    for raw in config.get("required_checks", []):
        maybe_append(raw, str(raw["name"]))

    for raw in config.get("required_ranges", []):
        values = raw.get("values")
        if values is None:
            values = range(int(raw["start"]), int(raw["end"]) + 1)
        for value in values:
            maybe_append(raw, str(raw["template"]).format(i=value))

    for raw in config.get("required_matrices", []):
        axes = raw.get("axes", {})
        names = list(axes)
        for values in itertools.product(*(axes[name] for name in names)):
            mapping = dict(zip(names, values, strict=True))
            maybe_append(raw, str(raw["template"]).format(**mapping))

    return checks


def branch_protection_contexts(config: dict[str, Any]) -> list[str]:
    names = {check.name for check in expand_required_checks(config)}
    final_gate = config.get("final_gate_check")
    if final_gate:
        names.add(str(final_gate))
    ignored = set(config.get("ignored_check_runs", []))
    return sorted(name for name in names if name not in ignored)


def _run(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def gh_api(path: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    command = ["gh", "api", path]
    input_text = None
    if method != "GET":
        command.extend(["--method", method])
    if body is not None:
        command.extend(["--input", "-"])
        input_text = json.dumps(body)
    result = _run(command, input_text=input_text)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"gh api failed for {path}: {message}")
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def resolve_repo(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo
    env_repo = os.environ.get("GITHUB_REPOSITORY")
    if env_repo:
        return env_repo
    result = _run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def resolve_sha(explicit_sha: str | None) -> str:
    if explicit_sha:
        return explicit_sha
    env_sha = os.environ.get("GITHUB_SHA")
    if env_sha:
        return env_sha
    result = _run(["git", "rev-parse", "HEAD"])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def fetch_check_runs(repo: str, sha: str) -> list[dict[str, Any]]:
    check_runs: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = gh_api(f"repos/{repo}/commits/{sha}/check-runs?per_page=100&page={page}")
        batch = payload.get("check_runs", [])
        check_runs.extend(batch)
        if len(batch) < 100:
            return check_runs
        page += 1


def fetch_statuses(repo: str, sha: str) -> list[dict[str, Any]]:
    payload = gh_api(f"repos/{repo}/commits/{sha}/status")
    return list(payload.get("statuses", []))


def _run_sort_key(run: dict[str, Any]) -> str:
    return str(run.get("completed_at") or run.get("started_at") or run.get("created_at") or "")


def latest_check_runs_by_name(check_runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in check_runs:
        name = str(run.get("name", ""))
        if not name:
            continue
        if name not in latest or _run_sort_key(run) > _run_sort_key(latest[name]):
            latest[name] = run
    return latest


def evaluate_required_checks(config: dict[str, Any], check_runs: list[dict[str, Any]], event: str) -> list[GateRow]:
    latest = latest_check_runs_by_name(check_runs)
    rows: list[GateRow] = []
    for required in expand_required_checks(config, event=event):
        run = latest.get(required.name)
        if run is None:
            rows.append(GateRow(required.name, "missing", "", "missing"))
            continue
        status = str(run.get("status") or "")
        conclusion = str(run.get("conclusion") or "")
        url = str(run.get("details_url") or "")
        if status != "completed":
            state = "pending"
        elif conclusion in required.accepted_conclusions:
            state = "ok"
        else:
            state = "failed"
        rows.append(GateRow(required.name, status, conclusion, state, url))
    return rows


def evaluate_statuses(config: dict[str, Any], statuses: list[dict[str, Any]]) -> list[GateRow]:
    ignored = set(config.get("ignored_status_contexts", []))
    rows: list[GateRow] = []
    latest: dict[str, dict[str, Any]] = {}
    for status in statuses:
        context = str(status.get("context", ""))
        if context not in latest:
            latest[context] = status
    for context, status in latest.items():
        state = str(status.get("state") or "")
        url = str(status.get("target_url") or "")
        if context in ignored:
            row_state = "ignored"
        elif state in SUCCESSFUL_STATUS_STATES:
            row_state = "ok"
        else:
            row_state = "failed"
        rows.append(GateRow(context, state, state, row_state, url))
    return sorted(rows, key=lambda row: row.name)


def has_open_failures(rows: list[GateRow]) -> bool:
    return any(row.state in {"failed", "missing", "pending"} for row in rows)


def render_markdown(
    *,
    repo: str,
    sha: str,
    event: str,
    check_rows: list[GateRow],
    status_rows: list[GateRow],
    branch_rows: list[GateRow] | None = None,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    verdict = "OK" if not has_open_failures(check_rows) and not has_open_failures([r for r in status_rows if r.state != "ignored"]) else "FAIL"
    lines = [
        "# Report CI richiesti",
        "",
        f"- Repository: `{repo}`",
        f"- SHA: `{sha}`",
        f"- Evento: `{event}`",
        f"- Generato: {now}",
        f"- Esito: **{verdict}**",
        "",
        "## Check richiesti",
        "",
        "| Check | Stato | Conclusione | Esito |",
        "| --- | --- | --- | --- |",
    ]
    for row in check_rows:
        label = f"[{row.name}]({row.url})" if row.url else row.name
        lines.append(f"| {label} | {row.status or '-'} | {row.conclusion or '-'} | {row.state} |")

    lines.extend(["", "## Status esterni", "", "| Context | Stato | Esito |", "| --- | --- | --- |"])
    if status_rows:
        for row in status_rows:
            label = f"[{row.name}]({row.url})" if row.url else row.name
            lines.append(f"| {label} | {row.status or '-'} | {row.state} |")
    else:
        lines.append("| Nessuno | - | ok |")

    if branch_rows is not None:
        lines.extend(["", "## Branch protection", "", "| Ramo | Stato | Esito |", "| --- | --- | --- |"])
        for row in branch_rows:
            lines.append(f"| {row.name} | {row.status} | {row.state} |")

    lines.append("")
    return "\n".join(lines)


def write_reports(
    *,
    md_path: Path | None,
    json_path: Path | None,
    markdown: str,
    repo: str,
    sha: str,
    event: str,
    check_rows: list[GateRow],
    status_rows: list[GateRow],
    branch_rows: list[GateRow] | None,
) -> None:
    if md_path:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding="utf-8")
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "repo": repo,
            "sha": sha,
            "event": event,
            "generated_at": datetime.now(UTC).isoformat(),
            "checks": [row.__dict__ for row in check_rows],
            "statuses": [row.__dict__ for row in status_rows],
            "branches": [row.__dict__ for row in branch_rows or []],
        }
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def branch_protection_payload(config: dict[str, Any]) -> dict[str, Any]:
    protection = config.get("branch_protection", {})
    return {
        "required_status_checks": {
            "strict": bool(protection.get("strict", True)),
            "contexts": branch_protection_contexts(config),
        },
        "enforce_admins": bool(protection.get("enforce_admins", True)),
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": bool(protection.get("required_linear_history", True)),
        "allow_force_pushes": bool(protection.get("allow_force_pushes", False)),
        "allow_deletions": bool(protection.get("allow_deletions", False)),
        "required_conversation_resolution": bool(protection.get("required_conversation_resolution", True)),
    }


def apply_branch_protection(repo: str, config: dict[str, Any]) -> list[GateRow]:
    payload = branch_protection_payload(config)
    rows: list[GateRow] = []
    for branch in config.get("branches", []):
        encoded = quote(str(branch), safe="")
        gh_api(f"repos/{repo}/branches/{encoded}/protection", method="PUT", body=payload)
        rows.append(GateRow(str(branch), "applied", "success", "ok"))
    return rows


def check_branch_protection(repo: str, config: dict[str, Any]) -> list[GateRow]:
    expected = set(branch_protection_contexts(config))
    forbidden = set(config.get("ignored_status_contexts", [])) | set(config.get("ignored_check_runs", []))
    rows: list[GateRow] = []
    for branch in config.get("branches", []):
        encoded = quote(str(branch), safe="")
        try:
            payload = gh_api(f"repos/{repo}/branches/{encoded}/protection")
        except RuntimeError as exc:
            rows.append(GateRow(str(branch), "missing", str(exc), "failed"))
            continue
        checks = payload.get("required_status_checks") or {}
        contexts = set(checks.get("contexts") or [])
        missing = sorted(expected - contexts)
        forbidden_present = sorted(forbidden & contexts)
        if missing or forbidden_present or not checks.get("strict"):
            details = []
            if missing:
                details.append(f"missing={len(missing)}")
            if forbidden_present:
                details.append("forbidden=" + ",".join(forbidden_present))
            if not checks.get("strict"):
                details.append("strict=false")
            rows.append(GateRow(str(branch), "configured", "; ".join(details), "failed"))
        else:
            rows.append(GateRow(str(branch), "configured", f"contexts={len(contexts)}", "ok"))
    return rows


def run_gate(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    repo = resolve_repo(args.repo)
    sha = resolve_sha(args.sha)
    event = args.event or os.environ.get("GITHUB_EVENT_NAME") or "push"
    deadline = time.monotonic() + args.timeout_seconds
    check_rows: list[GateRow] = []
    status_rows: list[GateRow] = []

    while True:
        check_rows = evaluate_required_checks(config, fetch_check_runs(repo, sha), event)
        status_rows = evaluate_statuses(config, fetch_statuses(repo, sha))
        hard_failure = any(row.state == "failed" for row in check_rows)
        external_failure = any(row.state == "failed" for row in status_rows)
        pending_or_missing = any(row.state in {"pending", "missing"} for row in check_rows)

        if hard_failure or external_failure or not pending_or_missing or not args.wait:
            break
        if time.monotonic() >= deadline:
            break
        print(
            f"Attendo check GitHub: "
            f"{sum(row.state == 'ok' for row in check_rows)}/{len(check_rows)} ok, "
            f"{sum(row.state == 'pending' for row in check_rows)} in corso, "
            f"{sum(row.state == 'missing' for row in check_rows)} mancanti...",
            flush=True,
        )
        time.sleep(args.poll_seconds)

    branch_rows = None
    if args.check_branch_protection:
        branch_rows = check_branch_protection(repo, config)

    markdown = render_markdown(
        repo=repo,
        sha=sha,
        event=event,
        check_rows=check_rows,
        status_rows=status_rows,
        branch_rows=branch_rows,
    )
    write_reports(
        md_path=Path(args.report_md) if args.report_md else None,
        json_path=Path(args.report_json) if args.report_json else None,
        markdown=markdown,
        repo=repo,
        sha=sha,
        event=event,
        check_rows=check_rows,
        status_rows=status_rows,
        branch_rows=branch_rows,
    )
    print(markdown)
    failed_rows = [row for row in check_rows if row.state != "ok"]
    failed_statuses = [row for row in status_rows if row.state == "failed"]
    failed_branches = [row for row in branch_rows or [] if row.state != "ok"]
    return 1 if failed_rows or failed_statuses or failed_branches else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica CI GitHub richiesti sullo SHA corrente.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--repo")
    parser.add_argument("--sha")
    parser.add_argument("--event", choices=["push", "pull_request", "workflow_dispatch"])
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=5400)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--report-md")
    parser.add_argument("--report-json")
    parser.add_argument("--check-branch-protection", action="store_true")
    parser.add_argument("--apply-branch-protection", action="store_true")
    args = parser.parse_args(argv)

    config = _load_json(Path(args.config))
    repo = resolve_repo(args.repo)
    if args.apply_branch_protection:
        rows = apply_branch_protection(repo, config)
        for row in rows:
            print(f"{row.name}: {row.status}")
        return 0
    return run_gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
