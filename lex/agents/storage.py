"""Persistenza JSON tenant-aware per run e metriche agentiche."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context

from web.services.tenant_paths import tenant_data_path

from .models import AgentMetric, AgentRun, utc_now_iso


def current_tenant_scope() -> str:
    if has_request_context():
        for name in ("tenant_context_slug", "tenant_slug"):
            value = str(getattr(g, name, "") or "").strip()
            if value:
                return value
        tenant = getattr(g, "tenant", None)
        value = str(getattr(tenant, "slug", "") or "").strip()
        if value:
            return value
    if has_app_context() and not current_app.config.get("MULTI_TENANT"):
        return "single-tenant"
    return ""


def _configured_path(config_key: str, env_key: str, default: str) -> Path:
    if has_app_context():
        configured = current_app.config.get(config_key)
        try:
            return Path(tenant_data_path(config_key, str(configured or default), require_tenant=True))
        except Exception:
            if configured:
                return Path(str(configured))
    return Path(os.getenv(env_key, default))


def workflow_runs_path() -> Path:
    return _configured_path(
        "WORKFLOW_AGENTS_RUNS_DB",
        "PCT_WORKFLOW_AGENTS_RUNS_DB",
        "./data/intelligence/workflow_agents/runs.json",
    )


def workflow_metrics_path() -> Path:
    return _configured_path(
        "WORKFLOW_AGENTS_METRICS_DB",
        "PCT_WORKFLOW_AGENTS_METRICS_DB",
        "./data/intelligence/workflow_agents/metrics.json",
    )


def workflow_actions_path() -> Path:
    return _configured_path(
        "WORKFLOW_AGENTS_ACTIONS_DB",
        "PCT_WORKFLOW_AGENTS_ACTIONS_DB",
        "./data/intelligence/workflow_agents/actions.json",
    )


class WorkflowAgentStorage:
    def __init__(
        self,
        runs_path: str | Path | None = None,
        metrics_path: str | Path | None = None,
        *,
        tenant_scope: str | None = None,
    ):
        self.runs_path = Path(runs_path) if runs_path else workflow_runs_path()
        self.metrics_path = Path(metrics_path) if metrics_path else workflow_metrics_path()
        self.tenant_scope = str(tenant_scope if tenant_scope is not None else current_tenant_scope()).strip()

    def _read(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        temp.replace(path)

    def save_run(self, run: AgentRun) -> AgentRun:
        if self.tenant_scope and not run.tenant_scope:
            run.tenant_scope = self.tenant_scope
        data = self._read(self.runs_path)
        data[run.id] = run.to_dict()
        data[run.id]["updated_at"] = utc_now_iso()
        self._write(self.runs_path, data)
        return run

    def get_run(self, run_id: str) -> AgentRun:
        data = self._read(self.runs_path).get(str(run_id or "").strip())
        if not isinstance(data, dict):
            raise KeyError("Percorso agentico non trovato.")
        run = AgentRun.from_dict(data)
        if self.tenant_scope and run.tenant_scope != self.tenant_scope:
            raise PermissionError("Percorso non disponibile per questo studio.")
        return run

    def list_runs(self, *, limit: int = 20, workflow_code: str = "") -> list[AgentRun]:
        runs: list[AgentRun] = []
        for item in self._read(self.runs_path).values():
            if not isinstance(item, dict):
                continue
            run = AgentRun.from_dict(item)
            if self.tenant_scope and run.tenant_scope != self.tenant_scope:
                continue
            if workflow_code and run.workflow_code != workflow_code:
                continue
            runs.append(run)
        return sorted(runs, key=lambda run: run.created_at, reverse=True)[: max(1, int(limit or 20))]

    def save_metric(self, metric: AgentMetric) -> AgentMetric:
        data = self._read(self.metrics_path)
        data[metric.id] = metric.to_dict()
        data[metric.id]["tenant_scope"] = self.tenant_scope
        self._write(self.metrics_path, data)
        return metric

    def list_metrics(self, *, limit: int = 200) -> list[AgentMetric]:
        metrics: list[AgentMetric] = []
        for item in self._read(self.metrics_path).values():
            if not isinstance(item, dict):
                continue
            if self.tenant_scope and str(item.get("tenant_scope") or "") != self.tenant_scope:
                continue
            metrics.append(AgentMetric.from_dict(item))
        return sorted(metrics, key=lambda metric: metric.created_at, reverse=True)[: max(1, int(limit or 200))]


class WorkflowAgentActionStore:
    def __init__(self, path: str | Path | None = None, *, tenant_scope: str | None = None):
        self.path = Path(path) if path else workflow_actions_path()
        self.tenant_scope = str(tenant_scope if tenant_scope is not None else current_tenant_scope()).strip() or "single-tenant"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"items": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {"items": []}
        except Exception:
            return {"items": []}

    def append(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .models import new_id
        from .serialization import redact_value

        data = self._read()
        item = {
            "id": new_id("action"),
            "tenant_scope": self.tenant_scope,
            "action_type": action_type,
            "created_at": utc_now_iso(),
            "payload": redact_value(payload),
        }
        items = list(data.get("items") or [])
        items.append(item)
        data["items"] = items
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
        return item
