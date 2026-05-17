"""Nightly operational micro-agents for Lex AI.

The agents do not perform user-facing actions. They inspect tenant-aware
archives, refresh a compact operational inventory for Lex and report whether a
domain is ready, incomplete or needs follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "iusentra.lex_operational_agents.v1"
DEFAULT_DB_NAME = "lex_operational_agents.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists() or not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _records_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("items", "records", "clienti", "fascicoli", "preventivi", "conferimenti", "parcelle"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
            if isinstance(value, dict):
                return len(value)
        return len(payload)
    return 0


def _db_path(config: dict[str, Any]) -> Path:
    explicit = (
        config.get("LEX_OPERATIONAL_AGENTS_DB")
        or config.get("IUSENTRA_LEX_OPERATIONAL_AGENTS_DB")
        or os.getenv("IUSENTRA_LEX_OPERATIONAL_AGENTS_DB")
        or os.getenv("LEX_OPERATIONAL_AGENTS_DB")
    )
    if explicit:
        return Path(str(explicit))
    legal_db = config.get("LEGAL_INTELLIGENCE_DB") or os.getenv("PCT_LEGAL_INTELLIGENCE_DB")
    if legal_db:
        return Path(str(legal_db)).expanduser().resolve().parent / DEFAULT_DB_NAME
    if Path("/data").exists():
        return Path("/data/intelligence") / DEFAULT_DB_NAME
    return Path("intelligence") / DEFAULT_DB_NAME


@dataclass(frozen=True, slots=True)
class AgentTarget:
    tenant_slug: str
    tenant_name: str
    paths: dict[str, str]


class OperationalAgentRunRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def load(self) -> dict[str, Any]:
        payload = _json_load(self.db_path, {})
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("schema_version", SCHEMA_VERSION)
        payload.setdefault("generated_at", "")
        payload.setdefault("latest", {})
        payload.setdefault("runs", [])
        return payload

    def record(self, run: dict[str, Any]) -> dict[str, Any]:
        payload = self.load()
        payload["generated_at"] = _now_iso()
        agent_id = _clean(run.get("agent_id"))
        tenant_slug = _clean(run.get("tenant_slug") or "platform")
        latest = payload.setdefault("latest", {})
        latest.setdefault(agent_id, {})[tenant_slug] = run
        runs = list(payload.get("runs") or [])
        runs.append(run)
        payload["runs"] = runs[-500:]
        _json_dump(self.db_path, payload)
        return payload

    def latest(self, agent_id: str = "") -> dict[str, Any]:
        payload = self.load()
        latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
        if agent_id:
            return dict(latest.get(agent_id) or {})
        return dict(latest)


def _tenant_targets(config: dict[str, Any]) -> list[AgentTarget]:
    if bool(config.get("MULTI_TENANT")) and (config.get("TENANTS_REGISTRY") or os.getenv("TENANTS_REGISTRY")):
        try:
            from pct.tenant import GestioneTenant, StatoTenant

            manager = GestioneTenant(str(config.get("TENANTS_REGISTRY") or os.getenv("TENANTS_REGISTRY")))
            targets: list[AgentTarget] = []
            suspended_enum = getattr(StatoTenant, "SOSPESO", "SOSPESO")
            suspended_value = str(getattr(suspended_enum, "value", suspended_enum))
            for studio in manager.lista():
                studio_state = _clean(getattr(studio, "stato", "")).upper()
                if studio_state == suspended_value.upper() or studio_state == "SOSPESO":
                    continue
                slug = _clean(getattr(studio, "slug", ""))
                if not slug:
                    continue
                targets.append(
                    AgentTarget(
                        tenant_slug=slug,
                        tenant_name=_clean(getattr(studio, "nome", "")) or slug,
                        paths=manager.percorsi_dati(slug, reconcile_aliases=False),
                    )
                )
            if targets:
                return targets
        except Exception:
            pass
    return [AgentTarget("default", "Studio corrente", {key: str(value) for key, value in config.items() if isinstance(value, (str, os.PathLike))})]


def _path_probe(key: str, raw_path: Any) -> dict[str, Any]:
    path_text = _clean(raw_path)
    if not path_text:
        return {"key": key, "configured": False, "exists": False, "status": "non_configurato", "records": 0, "bytes": 0}
    path = Path(path_text)
    row: dict[str, Any] = {
        "key": key,
        "configured": True,
        "exists": path.exists(),
        "status": "presente" if path.exists() else "da_verificare",
        "records": 0,
        "bytes": 0,
    }
    try:
        if path.is_file():
            row["bytes"] = path.stat().st_size
            if path.suffix.lower() == ".json":
                row["records"] = _records_count(_json_load(path, {}))
        elif path.is_dir():
            total = 0
            count = 0
            for child in path.rglob("*"):
                if child.is_file():
                    count += 1
                    try:
                        total += child.stat().st_size
                    except OSError:
                        pass
                if count >= 10000:
                    row["partial"] = True
                    break
            row["records"] = count
            row["bytes"] = total
    except OSError as exc:
        row["status"] = "errore"
        row["message"] = str(exc)
    return row


def _prepare_known_archive(key: str, raw_path: Any) -> None:
    path_text = _clean(raw_path)
    if not path_text:
        return
    path = Path(path_text)
    if path.exists():
        return
    if key == "PDP_PENALE_DB":
        try:
            from pct.pdp_penale_workflow import PDPPenaleWorkflowRepository

            repo = PDPPenaleWorkflowRepository(str(path))
            repo.close()
        except Exception:
            return


def _email_attachment_probe(db_path: str) -> dict[str, int]:
    payload = _json_load(Path(db_path), {})
    rows = list(payload.values()) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
    total = archived = loose = missing_metadata = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        for attachment in list(row.get("allegati") or []):
            if not isinstance(attachment, dict):
                continue
            total += 1
            if _clean(attachment.get("archivio_membro")):
                archived += 1
            elif _clean(attachment.get("path") or attachment.get("percorso") or attachment.get("file")):
                loose += 1
            else:
                missing_metadata += 1
    return {
        "attachments_total": total,
        "attachments_archived": archived,
        "attachments_loose": loose,
        "attachments_missing_metadata": missing_metadata,
    }


def run_operational_micro_agent(
    *,
    agent_id: str,
    app: Any = None,
    config: dict[str, Any] | None = None,
    required_path_keys: list[str] | tuple[str, ...] = (),
    criteria: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    cfg = dict(config or getattr(app, "config", {}) or {})
    repository = OperationalAgentRunRepository(_db_path(cfg))
    targets = _tenant_targets(cfg)
    runs: list[dict[str, Any]] = []
    overall_missing = 0
    overall_errors = 0

    for target in targets:
        details = []
        for key in required_path_keys:
            raw_path = target.paths.get(key) or cfg.get(key)
            _prepare_known_archive(key, raw_path)
            details.append(_path_probe(key, raw_path))
        for row in details:
            if row["status"] in {"non_configurato", "da_verificare"}:
                overall_missing += 1
            if row["status"] == "errore":
                overall_errors += 1
        if agent_id in {"email_pec", "email_ordinaria"}:
            email_key = "EMAIL_CASELLA_DB" if agent_id == "email_pec" else "EMAIL_ORDINARIA_DB"
            email_path = target.paths.get(email_key) or cfg.get(email_key)
            if email_path:
                details.append({"key": f"{email_key}_ALLEGATI", **_email_attachment_probe(str(email_path))})
        status = "ok"
        if any(row.get("status") == "errore" for row in details):
            status = "errore"
        elif any(row.get("status") in {"non_configurato", "da_verificare"} for row in details):
            status = "da_verificare"
        run = {
            "agent_id": agent_id,
            "tenant_slug": target.tenant_slug,
            "tenant_name": target.tenant_name,
            "status": status,
            "generated_at": _now_iso(),
            "criteria": list(criteria),
            "details": details,
            "self_check": (
                "Superato: inventario operativo aggiornato."
                if status == "ok"
                else "Da verificare: uno o piu' archivi non sono pronti o non risultano configurati."
            ),
            "supervisor_check": (
                "L'agente ha aggiornato il database operativo Lex senza azioni dispositive."
                if status == "ok"
                else "L'agente ha registrato il blocco e richiede configurazione, sincronizzazione o riparazione mirata."
            ),
        }
        repository.record(run)
        runs.append(run)

    ok = overall_missing == 0 and overall_errors == 0
    missing_keys = sorted(
        {
            str(row.get("key") or "")
            for run in runs
            for row in (run.get("details") or [])
            if row.get("status") in {"non_configurato", "da_verificare"}
        }
    )
    return {
        "ok": ok,
        "agent_id": agent_id,
        "status": "ok" if ok else ("errore" if overall_errors else "da_verificare"),
        "summary": (
            f"Agente {agent_id}: {len(runs)} studi aggiornati."
            if ok
            else f"Agente {agent_id}: inventario aggiornato, {overall_missing + overall_errors} punti da verificare."
        ),
        "self_check": (
            "Superato: tutti gli archivi richiesti sono disponibili."
            if ok
            else "Da verificare: completare archivi mancanti o correggere configurazione tenant."
        ),
        "supervisor_check": "Esito salvato nel database operativo Lex per consultazione e audit.",
        "criteria": list(criteria),
        "missing_keys": missing_keys,
        "runs": runs,
        "db_path": str(repository.db_path),
    }


def run_operational_micro_agents(
    *,
    app: Any = None,
    config: dict[str, Any] | None = None,
    agents: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    results = [
        run_operational_micro_agent(
            agent_id=str(agent.get("agent_id") or ""),
            app=app,
            config=config,
            required_path_keys=list(agent.get("paths") or []),
            criteria=list(agent.get("criteria") or []),
        )
        for agent in agents
        if _clean(agent.get("agent_id"))
    ]
    return {
        "ok": all(result.get("ok") for result in results),
        "generated_at": _now_iso(),
        "results": results,
    }


def load_operational_agents_payload(
    *,
    app: Any = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Legge l'ultimo inventario degli agenti senza avviare controlli."""

    cfg = dict(config or getattr(app, "config", {}) or {})
    repository = OperationalAgentRunRepository(_db_path(cfg))
    payload = repository.load()
    payload["db_path"] = str(repository.db_path)
    return payload


__all__ = [
    "load_operational_agents_payload",
    "OperationalAgentRunRepository",
    "run_operational_micro_agent",
    "run_operational_micro_agents",
]
