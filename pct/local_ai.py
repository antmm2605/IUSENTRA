from __future__ import annotations

import hashlib
import io
import json
import math
import mimetypes
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber
import requests


_ENC_MAGIC = b"PCTENC\x01"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _clean_spaces(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_api_base_url(value: str) -> str:
    raw = str(value or "http://127.0.0.1:11434/api").strip().rstrip("/")
    if raw.endswith("/api"):
        return raw
    return f"{raw}/api"


def strip_api_suffix(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    return raw[:-4] if raw.endswith("/api") else raw


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compare_versions(left: str, right: str) -> int:
    def _parts(value: str) -> list[int]:
        cleaned = str(value or "").strip().lstrip("vV")
        return [int(chunk) for chunk in re.findall(r"\d+", cleaned)]

    left_parts = _parts(left)
    right_parts = _parts(right)
    max_len = max(len(left_parts), len(right_parts))
    for idx in range(max_len):
        left_value = left_parts[idx] if idx < len(left_parts) else 0
        right_value = right_parts[idx] if idx < len(right_parts) else 0
        if left_value > right_value:
            return 1
        if left_value < right_value:
            return -1
    return 0


def _estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(str(text or "")) / 4))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _extract_text_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]{2,}", str(text or "").lower()):
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _read_json_file(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _doc_key() -> bytes | None:
    raw = os.getenv("PCT_DOC_KEY", "")
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _decrypt_document_bytes(data: bytes) -> bytes:
    if not data.startswith(_ENC_MAGIC):
        return data
    key = _doc_key()
    if not key:
        raise ValueError("Documento cifrato ma PCT_DOC_KEY non configurata.")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    payload = data[len(_ENC_MAGIC):]
    nonce = payload[:12]
    ciphertext = payload[12:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)


@dataclass
class LocalAiSettings:
    enabled: bool = True
    base_url: str = "http://127.0.0.1:11434/api"
    auto_bootstrap: bool = True
    chat_model: str = ""
    embed_model: str = ""
    keep_alive: str = "10m"
    auto_index_documents: bool = True


class OllamaHttpClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = _normalize_api_base_url(base_url)
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        response = requests.request(
            method=method,
            url=f"{self.base_url}{path}",
            json=payload,
            timeout=timeout or self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_version(self) -> str | None:
        try:
            return str(self._request("GET", "/version", timeout=5).get("version") or "").strip() or None
        except Exception:
            return None

    def list_models(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/tags", timeout=10).get("models") or [])

    def list_running_models(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/ps", timeout=10).get("models") or [])

    def pull_model(self, model_name: str) -> dict[str, Any]:
        return self._request("POST", "/pull", payload={"model": model_name, "stream": False}, timeout=600)

    def warmup_model(self, model_name: str, keep_alive: str = "10m") -> dict[str, Any]:
        return self._request(
            "POST",
            "/generate",
            payload={"model": model_name, "prompt": "ok", "stream": False, "keep_alive": keep_alive},
            timeout=180,
        )

    def embed_texts(self, model_name: str, inputs: list[str]) -> dict[str, Any]:
        data = self._request(
            "POST",
            "/embed",
            payload={"model": model_name, "input": inputs, "truncate": True},
            timeout=180,
        )
        embeddings = data.get("embeddings") or []
        if not embeddings:
            raise ValueError(f"Embedding vuoto per modello {model_name}")
        return {
            "embeddings": embeddings,
            "total_duration": data.get("total_duration"),
            "load_duration": data.get("load_duration"),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count"),
        }

    def generate(self, model_name: str, prompt: str, keep_alive: str = "10m") -> dict[str, Any]:
        return self._request(
            "POST",
            "/generate",
            payload={"model": model_name, "prompt": prompt, "stream": False, "keep_alive": keep_alive},
            timeout=240,
        )


class LocalAIService:
    def __init__(
        self,
        *,
        db_path: str,
        policy_path: str,
        config_path: str,
        app_root: str,
        models_path: str,
    ) -> None:
        self.db_path = Path(db_path)
        self.policy_path = Path(policy_path)
        self.config_path = Path(config_path)
        self.app_root = Path(app_root)
        self.models_path = Path(models_path)
        self.schema_path = self.app_root / "pct" / "sql" / "20260413_local_ai.sql"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _ensure_schema(self) -> None:
        sql = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(rag_documents)").fetchall()}
            if "practice_id" not in columns:
                conn.execute("ALTER TABLE rag_documents ADD COLUMN practice_id TEXT")
            chunk_columns = {row["name"] for row in conn.execute("PRAGMA table_info(rag_chunks)").fetchall()}
            if "embedding_json" not in chunk_columns:
                conn.execute("ALTER TABLE rag_chunks ADD COLUMN embedding_json TEXT")
            if "embedding_dimensions" not in chunk_columns:
                conn.execute("ALTER TABLE rag_chunks ADD COLUMN embedding_dimensions INTEGER")
            conn.commit()

    def _load_policy(self) -> dict[str, Any]:
        return _read_json_file(
            self.policy_path,
            {
                "ollama": {
                    "baseUrl": "http://127.0.0.1:11434/api",
                    "minVersionForEmbeddingGemma": "0.11.10",
                    "startupTimeoutMs": 45000,
                    "healthPollIntervalMs": 1500,
                    "defaultWarmupKeepAlive": "10m",
                },
                "profiles": {
                    "weak": {
                        "minRamGb": 0,
                        "maxRamGb": 7.99,
                        "minDiskFreeGb": 12,
                        "chatModel": "qwen2.5:0.5b",
                        "embedModel": "embeddinggemma:300m",
                        "disableRagByDefault": False,
                    },
                    "medium": {
                        "minRamGb": 8,
                        "maxRamGb": 15.99,
                        "minDiskFreeGb": 20,
                        "chatModel": "gemma3:1b",
                        "embedModel": "embeddinggemma:300m",
                        "disableRagByDefault": False,
                    },
                    "strong": {
                        "minRamGb": 16,
                        "maxRamGb": 999,
                        "minDiskFreeGb": 40,
                        "chatModel": "gemma3:4b",
                        "embedModel": "embeddinggemma:300m",
                        "disableRagByDefault": False,
                    },
                },
            },
        )

    def _load_settings(self) -> LocalAiSettings:
        from pct.config_studio import GestioneConfigStudio

        try:
            cfg = GestioneConfigStudio(config_path=str(self.config_path)).config
            ai = getattr(cfg, "ai", None)
            if ai:
                return LocalAiSettings(
                    enabled=bool(getattr(ai, "enabled", True)),
                    base_url=_normalize_api_base_url(getattr(ai, "base_url", "") or "http://127.0.0.1:11434/api"),
                    auto_bootstrap=bool(getattr(ai, "auto_bootstrap", True)),
                    chat_model=str(getattr(ai, "chat_model", "") or "").strip(),
                    embed_model=str(getattr(ai, "embed_model", "") or "").strip(),
                    keep_alive=str(getattr(ai, "keep_alive", "10m") or "10m").strip(),
                    auto_index_documents=bool(getattr(ai, "auto_index_documents", True)),
                )
        except Exception:
            pass
        return LocalAiSettings()

    def _ollama_client(self, settings: LocalAiSettings | None = None) -> OllamaHttpClient:
        cfg = settings or self._load_settings()
        return OllamaHttpClient(cfg.base_url)

    def _select_profile(self, ram_gb: float, disk_free_gb: float, policy: dict[str, Any]) -> str:
        profiles = policy.get("profiles") or {}
        for code in ("weak", "medium", "strong"):
            row = profiles.get(code) or {}
            min_ram = float(row.get("minRamGb", 0))
            max_ram = float(row.get("maxRamGb", 999))
            min_disk = float(row.get("minDiskFreeGb", 0))
            if ram_gb >= min_ram and ram_gb <= max_ram and disk_free_gb >= min_disk:
                return code
        if ram_gb >= 16 and disk_free_gb >= 40:
            return "strong"
        if ram_gb >= 8 and disk_free_gb >= 20:
            return "medium"
        return "weak"

    def _detect_ram_gb(self) -> float:
        if hasattr(os, "sysconf"):
            try:
                pagesize = int(os.sysconf("SC_PAGE_SIZE"))
                pages = int(os.sysconf("SC_PHYS_PAGES"))
                return (pagesize * pages) / (1024 ** 3)
            except Exception:
                pass
        if os.name == "nt":
            try:
                script = "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)"
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                    capture_output=True,
                    text=True,
                    timeout=6,
                    check=False,
                )
                return float(result.stdout.strip() or "0")
            except Exception:
                return 0.0
        return 0.0

    def _detect_windows_gpu(self) -> tuple[str, str]:
        try:
            script = (
                "$gpu = Get-CimInstance Win32_VideoController | Select-Object -First 1 Name, AdapterCompatibility;"
                "if ($null -eq $gpu) { Write-Output '{}' ; exit 0 };"
                "$gpu | ConvertTo-Json -Compress | Write-Output"
            )
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
            )
            payload = json.loads(result.stdout.strip() or "{}")
            return str(payload.get("AdapterCompatibility") or ""), str(payload.get("Name") or "")
        except Exception:
            return "", ""

    def _detect_hardware(self) -> dict[str, Any]:
        ram_gb = round(self._detect_ram_gb(), 2)
        root = str(self.models_path.drive or self.models_path.anchor or self.models_path)
        disk_usage = shutil.disk_usage(root)
        disk_free_gb = round(disk_usage.free / (1024 ** 3), 2)
        cpu_name = platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "") or "Unknown CPU"
        gpu_vendor = ""
        gpu_name = ""
        if os.name == "nt":
            gpu_vendor, gpu_name = self._detect_windows_gpu()
        policy = self._load_policy()
        profile = self._select_profile(ram_gb, disk_free_gb, policy)
        return {
            "profile": profile,
            "ram_gb": ram_gb,
            "disk_free_gb": disk_free_gb,
            "cpu_name": cpu_name,
            "gpu_vendor": gpu_vendor,
            "gpu_name": gpu_name,
            "os_version": f"{platform.system()} {platform.release()}",
            "is_windows": os.name == "nt",
        }

    def _runtime_row(self, conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM local_ai_runtime WHERE id = 1").fetchone()
        return dict(row) if row else {}

    def _upsert_runtime(self, conn: sqlite3.Connection, patch: dict[str, Any]) -> dict[str, Any]:
        current = self._runtime_row(conn)
        if not current:
            now = _now_iso()
            current = {
                "id": 1,
                "status": "missing",
                "api_base_url": "http://127.0.0.1:11434/api",
                "ollama_version": None,
                "install_path": None,
                "models_path": None,
                "hardware_profile": "weak",
                "os_version": None,
                "ram_gb": None,
                "disk_free_gb": None,
                "cpu_name": None,
                "gpu_vendor": None,
                "gpu_name": None,
                "last_health_check_at": None,
                "last_error": None,
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(
                """
                INSERT OR REPLACE INTO local_ai_runtime (
                    id, status, api_base_url, ollama_version, install_path, models_path,
                    hardware_profile, os_version, ram_gb, disk_free_gb, cpu_name,
                    gpu_vendor, gpu_name, last_health_check_at, last_error, created_at, updated_at
                ) VALUES (
                    :id, :status, :api_base_url, :ollama_version, :install_path, :models_path,
                    :hardware_profile, :os_version, :ram_gb, :disk_free_gb, :cpu_name,
                    :gpu_vendor, :gpu_name, :last_health_check_at, :last_error, :created_at, :updated_at
                )
                """,
                current,
            )
        next_row = dict(current)
        next_row.update(patch)
        next_row["updated_at"] = patch.get("updated_at") or _now_iso()
        conn.execute(
            """
            UPDATE local_ai_runtime
            SET
                status = :status,
                api_base_url = :api_base_url,
                ollama_version = :ollama_version,
                install_path = :install_path,
                models_path = :models_path,
                hardware_profile = :hardware_profile,
                os_version = :os_version,
                ram_gb = :ram_gb,
                disk_free_gb = :disk_free_gb,
                cpu_name = :cpu_name,
                gpu_vendor = :gpu_vendor,
                gpu_name = :gpu_name,
                last_health_check_at = :last_health_check_at,
                last_error = :last_error,
                updated_at = :updated_at
            WHERE id = 1
            """,
            next_row,
        )
        conn.commit()
        return self._runtime_row(conn)

    def _upsert_model(self, conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
        conn.execute("UPDATE local_ai_models SET is_active = 0 WHERE role = ?", (payload["role"],))
        conn.execute(
            """
            INSERT INTO local_ai_models (
                id, role, model_name, install_state, size_bytes, context_window,
                is_active, last_verified_at, notes
            ) VALUES (
                :id, :role, :model_name, :install_state, :size_bytes, :context_window,
                :is_active, :last_verified_at, :notes
            )
            ON CONFLICT(id) DO UPDATE SET
                role = excluded.role,
                model_name = excluded.model_name,
                install_state = excluded.install_state,
                size_bytes = excluded.size_bytes,
                context_window = excluded.context_window,
                is_active = excluded.is_active,
                last_verified_at = excluded.last_verified_at,
                notes = excluded.notes
            """,
            {
                "id": payload["id"],
                "role": payload["role"],
                "model_name": payload["model_name"],
                "install_state": payload["install_state"],
                "size_bytes": payload.get("size_bytes"),
                "context_window": payload.get("context_window"),
                "is_active": payload.get("is_active", 1),
                "last_verified_at": payload.get("last_verified_at") or _now_iso(),
                "notes": payload.get("notes"),
            },
        )

    def _resolve_model_policy(
        self,
        hardware: dict[str, Any],
        settings: LocalAiSettings,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        profile_code = hardware["profile"]
        row = (policy.get("profiles") or {}).get(profile_code) or {}
        return {
            "profile": profile_code,
            "chat_model": settings.chat_model or row.get("chatModel") or "qwen2.5:0.5b",
            "embed_model": settings.embed_model or row.get("embedModel") or "embeddinggemma:300m",
            "disable_rag_by_default": bool(row.get("disableRagByDefault", False)),
        }

    def _ollama_executable_candidates(self) -> list[Path]:
        return [
            self.app_root / "bin" / "ollama" / "ollama.exe",
            self.app_root / "tools" / "ollama" / "ollama.exe",
        ]

    def _start_windows_ollama(self, settings: LocalAiSettings, policy: dict[str, Any]) -> str:
        for candidate in self._ollama_executable_candidates():
            if not candidate.exists():
                continue
            env = dict(os.environ)
            env["OLLAMA_HOST"] = "127.0.0.1:11434"
            env["OLLAMA_MODELS"] = str(self.models_path)
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                [str(candidate), "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                cwd=str(candidate.parent),
                env=env,
                creationflags=creationflags,
            )
            deadline = time.time() + (float(policy.get("ollama", {}).get("startupTimeoutMs", 45000)) / 1000.0)
            client = self._ollama_client(settings)
            interval = float(policy.get("ollama", {}).get("healthPollIntervalMs", 1500)) / 1000.0
            while time.time() < deadline:
                version = client.get_version()
                if version:
                    return str(candidate)
                time.sleep(max(interval, 0.4))
            raise TimeoutError("Timeout avvio Ollama locale")
        raise FileNotFoundError("Runtime Ollama non trovato nei percorsi previsti")

    def bootstrap_runtime(self, *, force: bool = False) -> dict[str, Any]:
        settings = self._load_settings()
        policy = self._load_policy()
        hardware = self._detect_hardware()
        model_policy = self._resolve_model_policy(hardware, settings, policy)
        with self._connect() as conn:
            self._upsert_runtime(
                conn,
                {
                    "status": "disabled" if not settings.enabled else "starting",
                    "api_base_url": settings.base_url,
                    "models_path": str(self.models_path),
                    "hardware_profile": hardware["profile"],
                    "os_version": hardware["os_version"],
                    "ram_gb": hardware["ram_gb"],
                    "disk_free_gb": hardware["disk_free_gb"],
                    "cpu_name": hardware["cpu_name"],
                    "gpu_vendor": hardware["gpu_vendor"] or None,
                    "gpu_name": hardware["gpu_name"] or None,
                    "last_error": None,
                },
            )
            if not settings.enabled:
                return {
                    "status": "disabled",
                    "hardware_profile": hardware["profile"],
                    "chat_model": model_policy["chat_model"],
                    "embed_model": model_policy["embed_model"],
                }

            client = self._ollama_client(settings)
            version = client.get_version()
            install_path = ""
            if not version and os.name == "nt" and settings.auto_bootstrap:
                try:
                    install_path = self._start_windows_ollama(settings, policy)
                    version = client.get_version()
                except Exception as exc:
                    self._upsert_runtime(
                        conn,
                        {
                            "status": "error",
                            "install_path": install_path or None,
                            "last_error": str(exc),
                            "last_health_check_at": _now_iso(),
                        },
                    )
                    return {
                        "status": "error",
                        "error": str(exc),
                        "hardware_profile": hardware["profile"],
                        "chat_model": model_policy["chat_model"],
                        "embed_model": model_policy["embed_model"],
                    }

            if not version:
                self._upsert_runtime(
                    conn,
                    {
                        "status": "missing",
                        "last_error": "Ollama non raggiungibile",
                        "last_health_check_at": _now_iso(),
                    },
                )
                return {
                    "status": "missing",
                    "error": "Ollama non raggiungibile",
                    "hardware_profile": hardware["profile"],
                    "chat_model": model_policy["chat_model"],
                    "embed_model": model_policy["embed_model"],
                }
