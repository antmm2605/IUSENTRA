from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal_document_ingestion.evidence_hash import canonical_json, chain_hash, sha256_bytes
from legal_document_ingestion.repository import safe_join, safe_tenant, sanitize_filename


class LegalOcrEvidenceStore:
    def __init__(self, root: str | Path, tenant_id: str) -> None:
        self.root = Path(root).resolve()
        self.tenant_id = safe_tenant(tenant_id)
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return safe_join(self.root, Path("tenants") / self.tenant_id / "runs" / _safe_id(run_id))

    def pages_dir(self, run_id: str) -> Path:
        return safe_join(self.run_dir(run_id), "pages")

    def write_raw_blob(self, run_id: str, filename: str, data: bytes) -> str:
        target = safe_join(self.run_dir(run_id), Path("raw") / sanitize_filename(filename))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != bytes(data or b""):
            raise FileExistsError("Blob OCR già presente con contenuto diverso.")
        if not target.exists():
            target.write_bytes(bytes(data or b""))
        return self._rel(target)

    def write_text(self, run_id: str, name: str, text: str) -> str:
        target = safe_join(self.run_dir(run_id), Path("text") / sanitize_filename(name))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text(encoding="utf-8") != str(text or ""):
            raise FileExistsError("Testo OCR immutabile già presente con contenuto diverso.")
        if not target.exists():
            target.write_text(str(text or ""), encoding="utf-8")
        return self._rel(target)

    def write_evidence(self, evidence: dict[str, Any]) -> str:
        run_id = str(evidence.get("run_id") or "")
        target = safe_join(self.root, Path("tenants") / self.tenant_id / "evidence" / datetime.now(timezone.utc).strftime("%Y/%m/%d") / f"{_safe_id(run_id)}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_json(evidence)
        if target.exists() and target.read_text(encoding="utf-8") != payload:
            raise FileExistsError("Evidenza OCR immutabile già presente con contenuto diverso.")
        if not target.exists():
            target.write_text(payload, encoding="utf-8")
            self._append_index(run_id, target)
            self.append_audit(run_id, "EvidenceReady", {"evidence_path": self._rel(target), "metrics": evidence.get("metrics") or {}})
        return self._rel(target)

    def append_audit(self, run_id: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = safe_join(self.root, Path("tenants") / self.tenant_id / "audit" / f"{day}.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = ""
        if path.exists():
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                previous = str(json.loads(lines[-1]).get("chain_hash") or "")
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "tenant_id": self.tenant_id, "run_id": run_id, "action": action, "payload": payload, "previous_hash": previous}
        entry["chain_hash"] = chain_hash(previous, entry)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(entry) + "\n")
        self.write_merkle_snapshot(day)
        return entry

    def write_merkle_snapshot(self, day: str) -> dict[str, Any]:
        path = safe_join(self.root, Path("tenants") / self.tenant_id / "audit" / f"{day}.jsonl")
        hashes = [str(json.loads(line).get("chain_hash") or "") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
        snapshot = {"date": day, "tenant_id": self.tenant_id, "entries": len(hashes), "merkle_root": _merkle_root([h for h in hashes if h]), "created_at": datetime.now(timezone.utc).isoformat()}
        safe_join(self.root, Path("tenants") / self.tenant_id / "audit" / f"{day}.merkle.json").write_text(canonical_json(snapshot), encoding="utf-8")
        return snapshot

    def append_hil_correction(self, run_id: str, correction: dict[str, Any]) -> dict[str, Any]:
        safe_run_id = _safe_id(run_id)
        path = safe_join(self.root, Path("tenants") / self.tenant_id / "corrections" / f"{safe_run_id}.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = dict(correction or {})
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        entry.setdefault("user", "user")
        entry.setdefault("run_id", safe_run_id)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(entry) + "\n")
        self.append_audit(safe_run_id, "ocr.hil_correction", entry)
        return entry

    def load_evidence(self, run_id: str) -> dict[str, Any] | None:
        index = self._index_path()
        if not index.exists():
            return None
        for line in reversed(index.read_text(encoding="utf-8").splitlines()):
            row = json.loads(line)
            if str(row.get("run_id")) == str(run_id):
                return json.loads(safe_join(self.root, row["path"]).read_text(encoding="utf-8"))
        return None

    def load_evidence_with_corrections(self, run_id: str) -> dict[str, Any] | None:
        evidence = self.load_evidence(run_id)
        if not evidence:
            return None
        path = safe_join(self.root, Path("tenants") / self.tenant_id / "corrections" / f"{_safe_id(run_id)}.jsonl")
        extra = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
        evidence["hil_correction_history"] = extra
        evidence["correction_history_effective"] = list(evidence.get("correction_history") or []) + extra
        return evidence

    def find_latest_for_document(self, document_id: str) -> dict[str, Any] | None:
        index = self._index_path()
        if not index.exists():
            return None
        for line in reversed(index.read_text(encoding="utf-8").splitlines()):
            row = json.loads(line)
            if str(row.get("document_id") or "") == str(document_id):
                return json.loads(safe_join(self.root, row["path"]).read_text(encoding="utf-8"))
        return None

    def _append_index(self, run_id: str, target: Path) -> None:
        evidence = json.loads(target.read_text(encoding="utf-8"))
        index = self._index_path()
        index.parent.mkdir(parents=True, exist_ok=True)
        with index.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json({"run_id": run_id, "document_id": evidence.get("document_id") or "", "parent_run_id": evidence.get("parent_run_id") or "", "created_at": evidence.get("audit", {}).get("finish_ts") or datetime.now(timezone.utc).isoformat(), "path": self._rel(target)}) + "\n")

    def _index_path(self) -> Path:
        return safe_join(self.root, Path("tenants") / self.tenant_id / "runs_index.jsonl")

    def _rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()


def _merkle_root(hashes: list[str]) -> str:
    layer = list(hashes)
    if not layer:
        return ""
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [sha256_bytes((layer[i] + layer[i + 1]).encode("utf-8")) for i in range(0, len(layer), 2)]
    return layer[0]


def _safe_id(value: str) -> str:
    raw = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", raw):
        raise ValueError("Identificativo OCR non sicuro.")
    return raw
