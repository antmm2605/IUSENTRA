from __future__ import annotations

import hashlib
import html as html_lib
import io
import json
import logging
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
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pdfplumber
import requests

from pct.local_ai_runtime import OllamaRuntimeProvisioner

logger = logging.getLogger("pct.local_ai")

_ENC_MAGIC = b"PCTENC\x01"

_HEADING_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("intestazione", re.compile(r"^(TRIBUNALE|CORTE D'APPELLO|CORTE DI CASSAZIONE|GIUDICE DI PACE|TAR|CONSIGLIO DI STATO)\b", re.I)),
    ("parti", re.compile(r"^(RICORRENTE|RICORRENTI|ATTORE|ATTRICE|CONVENUTO|CONVENUTA|APPELLANTE|APPELLATO|OPPONENTE|OPPOSTO)\b", re.I)),
    ("fatto", re.compile(r"^(FATTO|IN FATTO|SVOLGIMENTO DEL PROCESSO|ESPOSIZIONE DEI FATTI)\b", re.I)),
    ("diritto", re.compile(r"^(DIRITTO|IN DIRITTO|MOTIVI IN DIRITTO|CONSIDERATO IN DIRITTO)\b", re.I)),
    ("motivazione", re.compile(r"^(MOTIVAZIONE|MOTIVI DELLA DECISIONE|RITENUTO IN FATTO E IN DIRITTO|OSSERVA|RILEVATO CHE|CONSIDERATO CHE)\b", re.I)),
    ("conclusioni", re.compile(r"^(CONCLUSIONI|PER QUESTI MOTIVI|P\.Q\.M\.|PQM|CHIEDE|SI CHIEDE)\b", re.I)),
    ("dispositivo", re.compile(r"^(DISPOSITIVO|P\.Q\.M\.|PQM)\b", re.I)),
    ("allegati", re.compile(r"^(ALLEGATI|DOCUMENTI ALLEGATI|ELENCO ALLEGATI)\b", re.I)),
]


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


def _normalize_text(text: str) -> str:
    return (
        str(text or "")
        .replace("\u00a0", " ")
        .replace("\r", "")
        .replace("\t", " ")
        .replace("\x00", " ")
    )


def _strip_html(raw: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", str(raw or ""), flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return _clean_spaces(text.replace(" .", "."))


def _detect_language(text: str) -> str | None:
    sample = str(text or "").lower()[:3000]
    hits = [
        "tribunale",
        "ricorrente",
        "convenuto",
        "sentenza",
        "decreto",
        "diritto",
        "fatto",
        "conclusioni",
        "udienza",
        "procura",
    ]
    return "it" if sum(1 for token in hits if token in sample) >= 3 else None


def _is_supported_mime(mime_type: str) -> bool:
    return mime_type in {
        "text/plain",
        "text/markdown",
        "text/html",
        "application/xhtml+xml",
        "application/json",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }


def _docx_text_from_bytes(data: bytes) -> str:
    namespaces = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    }
    chunks: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = sorted(
            [
                name
                for name in archive.namelist()
                if name == "word/document.xml"
                or name.startswith("word/header")
                or name.startswith("word/footer")
                or name.startswith("word/footnotes")
                or name.startswith("word/endnotes")
            ]
        )
        for name in names:
            try:
                root = ET.fromstring(archive.read(name))
            except Exception:
                continue
            paragraphs: list[str] = []
            for paragraph in root.findall(".//w:p", namespaces):
                texts = [node.text or "" for node in paragraph.findall(".//w:t", namespaces)]
                line = _clean_spaces("".join(texts))
                if line:
                    paragraphs.append(line)
            if paragraphs:
                chunks.append("\n\n".join(paragraphs))
    return "\n\n".join(chunks).strip()


def _paragraphs(text: str) -> list[str]:
    return [
        chunk.strip()
        for chunk in re.split(r"\n{2,}", _normalize_text(text))
        if chunk and chunk.strip()
    ]


def _looks_like_heading(text: str) -> tuple[str, str | None]:
    raw = _clean_spaces(text)
    if not raw:
        return "corpo", None
    for section_type, regex in _HEADING_PATTERNS:
        if regex.search(raw):
            return section_type, raw
    if len(raw) <= 90 and raw.upper() == raw and re.search(r"[A-ZÀ-ÖØ-Þ]", raw):
        return "sezione", raw
    return "corpo", None


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
        return self._request("POST", "/pull", payload={"model": model_name, "stream": False}, timeout=900)

    def warmup_model(self, model_name: str, keep_alive: str = "10m") -> dict[str, Any]:
        return self._request(
            "POST",
            "/generate",
            payload={"model": model_name, "prompt": "ok", "stream": False, "keep_alive": keep_alive},
            timeout=240,
        )

    def embed_texts(self, model_name: str, inputs: list[str]) -> dict[str, Any]:
        data = self._request(
            "POST",
            "/embed",
            payload={"model": model_name, "input": inputs, "truncate": True},
            timeout=240,
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
            timeout=300,
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
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError as exc:
            logger.warning(
                "SQLite WAL non disponibile per %s, fallback a DELETE: %s",
                self.db_path,
                exc,
            )
            conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _ensure_schema(self) -> None:
        sql = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            conn.executescript(
                """
                DROP TRIGGER IF EXISTS rag_chunks_au;
                CREATE TRIGGER rag_chunks_au
                AFTER UPDATE OF id, document_id, practice_id, text ON rag_chunks BEGIN
                    INSERT INTO rag_chunks_fts(rag_chunks_fts, rowid, id, document_id, practice_id, text)
                    VALUES ('delete', old.rowid, old.id, old.document_id, old.practice_id, old.text);
                    INSERT INTO rag_chunks_fts(rowid, id, document_id, practice_id, text)
                    VALUES (new.rowid, new.id, new.document_id, new.practice_id, new.text);
                END;
                """
            )
            doc_columns = {row["name"] for row in conn.execute("PRAGMA table_info(rag_documents)").fetchall()}
            if "practice_id" not in doc_columns:
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

        settings = LocalAiSettings()
        try:
            cfg = GestioneConfigStudio(config_path=str(self.config_path)).config
            ai = getattr(cfg, "ai", None)
            if ai:
                settings = LocalAiSettings(
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
        env_map = {
            "enabled": "PCT_LOCAL_AI_ENABLED",
            "base_url": "PCT_LOCAL_AI_BASE_URL",
            "auto_bootstrap": "PCT_LOCAL_AI_AUTO_BOOTSTRAP",
            "chat_model": "PCT_LOCAL_AI_CHAT_MODEL",
            "embed_model": "PCT_LOCAL_AI_EMBED_MODEL",
            "keep_alive": "PCT_LOCAL_AI_KEEP_ALIVE",
            "auto_index_documents": "PCT_LOCAL_AI_AUTO_INDEX_DOCUMENTS",
        }
        if env_map["enabled"] in os.environ:
            settings.enabled = os.getenv(env_map["enabled"], "1").lower() not in {"0", "false", "no"}
        if env_map["base_url"] in os.environ:
            settings.base_url = _normalize_api_base_url(os.getenv(env_map["base_url"], "") or settings.base_url)
        if env_map["auto_bootstrap"] in os.environ:
            settings.auto_bootstrap = os.getenv(env_map["auto_bootstrap"], "1").lower() not in {"0", "false", "no"}
        if env_map["chat_model"] in os.environ:
            settings.chat_model = str(os.getenv(env_map["chat_model"], "") or "").strip()
        if env_map["embed_model"] in os.environ:
            settings.embed_model = str(os.getenv(env_map["embed_model"], "") or "").strip()
        if env_map["keep_alive"] in os.environ:
            settings.keep_alive = str(os.getenv(env_map["keep_alive"], "10m") or "10m").strip()
        if env_map["auto_index_documents"] in os.environ:
            settings.auto_index_documents = os.getenv(env_map["auto_index_documents"], "1").lower() not in {
                "0",
                "false",
                "no",
            }
        return settings

    def _ollama_client(self, settings: LocalAiSettings | None = None) -> OllamaHttpClient:
        cfg = settings or self._load_settings()
        return OllamaHttpClient(cfg.base_url)

    def _candidate_base_urls(self, settings: LocalAiSettings) -> list[str]:
        urls: list[str] = []

        def _append(value: str | None) -> None:
            raw = str(value or "").strip()
            if not raw:
                return
            normalized = _normalize_api_base_url(raw)
            if normalized not in urls:
                urls.append(normalized)

        _append(settings.base_url)
        _append(os.getenv("PCT_OLLAMA_URL", ""))
        provisioner = self._runtime_provisioner()
        if getattr(provisioner, "containerized", False):
            host_platform = str(getattr(provisioner, "host_platform_name", "") or "")
            if host_platform in {"windows", "darwin"}:
                _append("http://host.docker.internal:11434/api")
                _append("http://ollama:11434/api")
            else:
                _append("http://ollama:11434/api")
                _append("http://host.docker.internal:11434/api")
        return urls

    def _resolve_live_runtime(
        self,
        settings: LocalAiSettings,
    ) -> tuple[OllamaHttpClient, str | None, str]:
        last_client = self._ollama_client(settings)
        last_base_url = settings.base_url
        for base_url in self._candidate_base_urls(settings):
            client = OllamaHttpClient(base_url)
            version = client.get_version()
            last_client = client
            last_base_url = base_url
            if version:
                return client, version, base_url
        return last_client, None, last_base_url

    def _missing_runtime_message(self, settings: LocalAiSettings) -> str:
        provisioner = self._runtime_provisioner()
        tried = ", ".join(self._candidate_base_urls(settings))
        strategy_code = ""
        strategy_resolver = getattr(provisioner, "strategy_code", None)
        if callable(strategy_resolver):
            strategy_code = str(strategy_resolver() or "")
        if strategy_code in {"host_bridge_windows", "host_bridge_darwin"}:
            return (
                "Runtime Ollama non raggiungibile sull'host reale della macchina che esegue HACS. "
                "Se HACS gira in Docker su Windows o macOS, la strategia corretta e' usare Ollama "
                "sull'host e collegarlo dal container tramite host.docker.internal. "
                f"URL verificati: {tried}"
            )
        if strategy_code == "docker_service":
            return (
                "Servizio Ollama non raggiungibile sulla stessa macchina di HACS. "
                "Se HACS gira in Docker, la strategia corretta e' il servizio Docker 'ollama' "
                f"oppure un runtime esposto all'URL host raggiungibile dal container. URL verificati: {tried}"
            )
        return f"Ollama non raggiungibile. URL verificati: {tried}"

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

    def _is_embedding_model(self, model_name: str) -> bool:
        normalized = str(model_name or "").strip().lower()
        return normalized.startswith("embedding") or "embed" in normalized

    def _fallback_profile_order(self, profile_code: str) -> list[str]:
        if profile_code == "strong":
            return ["strong", "medium", "weak"]
        if profile_code == "medium":
            return ["medium", "weak", "strong"]
        return ["weak", "medium", "strong"]

    def _policy_model_candidates(
        self,
        *,
        role: str,
        profile_code: str,
        policy: dict[str, Any],
    ) -> list[str]:
        field = "chatModel" if role == "chat" else "embedModel"
        seen: set[str] = set()
        candidates: list[str] = []
        for code in self._fallback_profile_order(profile_code):
            model_name = str((policy.get("profiles") or {}).get(code, {}).get(field) or "").strip()
            if not model_name or model_name in seen:
                continue
            seen.add(model_name)
            candidates.append(model_name)
        if role == "embed" and "embeddinggemma:300m" not in seen:
            candidates.append("embeddinggemma:300m")
        return candidates

    def _available_model_names(
        self,
        *,
        role: str,
        installed_models: Iterable[dict[str, Any]] | None = None,
        running_models: Iterable[dict[str, Any]] | None = None,
        db_models: Iterable[dict[str, Any]] | None = None,
    ) -> list[str]:
        names: list[str] = []
        for row in list(running_models or []) + list(installed_models or []) + list(db_models or []):
            model_name = str(row.get("name") or row.get("model_name") or row.get("model") or "").strip()
            if not model_name or model_name in names:
                continue
            if role == "embed" and not self._is_embedding_model(model_name):
                continue
            if role == "chat" and self._is_embedding_model(model_name):
                continue
            names.append(model_name)
        return names

    def _resolve_effective_models(
        self,
        *,
        settings: LocalAiSettings,
        hardware: dict[str, Any],
        policy: dict[str, Any],
        installed_models: Iterable[dict[str, Any]] | None = None,
        running_models: Iterable[dict[str, Any]] | None = None,
        db_models: Iterable[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        preferred = self._resolve_model_policy(hardware, settings, policy)

        def _pick(role: str, preferred_model: str) -> tuple[str, str]:
            available = self._available_model_names(
                role=role,
                installed_models=installed_models,
                running_models=running_models,
                db_models=db_models,
            )
            if preferred_model in available or not available:
                return preferred_model, "preferred"
            for candidate in self._policy_model_candidates(
                role=role,
                profile_code=str(preferred["profile"] or "weak"),
                policy=policy,
            ):
                if candidate in available:
                    return candidate, "fallback"
            return available[0], "fallback"

        chat_model, chat_source = _pick("chat", str(preferred["chat_model"] or ""))
        embed_model, embed_source = _pick("embed", str(preferred["embed_model"] or ""))
        return {
            "profile": preferred["profile"],
            "preferred_chat_model": preferred["chat_model"],
            "preferred_embed_model": preferred["embed_model"],
            "chat_model": chat_model,
            "embed_model": embed_model,
            "chat_source": chat_source,
            "embed_source": embed_source,
            "disable_rag_by_default": preferred["disable_rag_by_default"],
        }

    def _assert_embedding_runtime(self, runtime_version: str, model_name: str, policy: dict[str, Any]) -> None:
        if not str(model_name or "").startswith("embeddinggemma"):
            return
        minimum = str(policy.get("ollama", {}).get("minVersionForEmbeddingGemma", "0.11.10"))
        if _compare_versions(runtime_version, minimum) < 0:
            raise RuntimeError(f"embeddinggemma richiede Ollama >= {minimum}, trovato {runtime_version}")

    def _runtime_provisioner(self) -> OllamaRuntimeProvisioner:
        return OllamaRuntimeProvisioner(self.app_root, self.models_path)

    def _start_managed_ollama(self, settings: LocalAiSettings, policy: dict[str, Any]) -> str:
        timeout_s = float(policy.get("ollama", {}).get("startupTimeoutMs", 45000)) / 1000.0
        interval = max(float(policy.get("ollama", {}).get("healthPollIntervalMs", 1500)) / 1000.0, 0.4)
        provisioner = self._runtime_provisioner()
        candidate = provisioner.discover_executable()
        if candidate is None:
            candidate = provisioner.ensure_runtime()
        env = dict(os.environ)
        env["OLLAMA_HOST"] = "127.0.0.1:11434"
        env["OLLAMA_MODELS"] = str(self.models_path)
        popen_kwargs: dict[str, Any] = {
            "args": [str(candidate), "serve"],
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
            "cwd": str(candidate.parent),
            "env": env,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(**popen_kwargs)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            _, version, _ = self._resolve_live_runtime(settings)
            if version:
                return str(candidate)
            time.sleep(interval)
        raise TimeoutError("Timeout avvio Ollama locale")

    def _ensure_model_installed(
        self,
        conn: sqlite3.Connection,
        client: OllamaHttpClient,
        role: str,
        model_name: str,
        installed: dict[str, dict[str, Any]],
        force_pull: bool = False,
    ) -> None:
        details = installed.get(model_name) or {}
        if not details or force_pull:
            self._upsert_model(
                conn,
                {
                    "id": f"{role}:{model_name}",
                    "role": role,
                    "model_name": model_name,
                    "install_state": "pulling",
                    "notes": "Download modello in corso",
                },
            )
            conn.commit()
            client.pull_model(model_name)
            installed = {row.get("name"): row for row in client.list_models()}
            details = installed.get(model_name) or {}
        self._upsert_model(
            conn,
            {
                "id": f"{role}:{model_name}",
                "role": role,
                "model_name": model_name,
                "install_state": "ready",
                "size_bytes": details.get("size"),
                "context_window": None,
                "notes": json.dumps(details.get("details") or {}, ensure_ascii=False) if details.get("details") else None,
            },
        )

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

            client, version, resolved_base_url = self._resolve_live_runtime(settings)
            install_path = ""
            strategy = self._runtime_provisioner().strategy_code()
            if not version and strategy in {"host_managed_windows", "host_managed_linux"} and settings.auto_bootstrap:
                try:
                    install_path = self._start_managed_ollama(settings, policy)
                    client, version, resolved_base_url = self._resolve_live_runtime(settings)
                except Exception as exc:
                    self._upsert_runtime(
                        conn,
                        {
                            "status": "error",
                            "api_base_url": resolved_base_url,
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
                        "api_base_url": resolved_base_url,
                        "last_error": self._missing_runtime_message(settings),
                        "last_health_check_at": _now_iso(),
                    },
                )
                return {
                    "status": "missing",
                    "error": self._missing_runtime_message(settings),
                    "hardware_profile": hardware["profile"],
                    "chat_model": model_policy["chat_model"],
                    "embed_model": model_policy["embed_model"],
                }

            try:
                self._assert_embedding_runtime(version, model_policy["embed_model"], policy)
                installed = {row.get("name"): row for row in client.list_models()}
                self._ensure_model_installed(conn, client, "chat", model_policy["chat_model"], installed, force_pull=force)
                installed = {row.get("name"): row for row in client.list_models()}
                self._ensure_model_installed(conn, client, "embed", model_policy["embed_model"], installed, force_pull=force)
                client.warmup_model(
                    model_policy["chat_model"],
                    keep_alive=settings.keep_alive or policy.get("ollama", {}).get("defaultWarmupKeepAlive", "10m"),
                )
                client.embed_texts(model_policy["embed_model"], ["test"])
            except Exception as exc:
                self._upsert_runtime(
                    conn,
                    {
                        "status": "error",
                        "ollama_version": version,
                        "install_path": install_path or None,
                        "last_error": str(exc),
                        "last_health_check_at": _now_iso(),
                    },
                )
                conn.commit()
                return {
                    "status": "error",
                    "error": str(exc),
                    "hardware_profile": hardware["profile"],
                    "chat_model": model_policy["chat_model"],
                    "embed_model": model_policy["embed_model"],
                }

            self._upsert_runtime(
                conn,
                {
                    "status": "ready",
                    "api_base_url": resolved_base_url,
                    "ollama_version": version,
                    "install_path": install_path or self._runtime_row(conn).get("install_path"),
                    "last_error": None,
                    "last_health_check_at": _now_iso(),
                },
            )
            conn.commit()
            return {
                "status": "ready",
                "version": version,
                "hardware_profile": hardware["profile"],
                "chat_model": model_policy["chat_model"],
                "embed_model": model_policy["embed_model"],
            }

    def health_snapshot(self) -> dict[str, Any]:
        settings = self._load_settings()
        policy = self._load_policy()
        hardware = self._detect_hardware()
        with self._connect() as conn:
            runtime = self._runtime_row(conn)
            models = [dict(row) for row in conn.execute("SELECT * FROM local_ai_models ORDER BY role, model_name").fetchall()]
            counts = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM rag_documents) AS documents_total,
                    (SELECT COUNT(*) FROM rag_chunks) AS chunks_total,
                    (SELECT COUNT(*) FROM rag_chunks WHERE embedding_state = 'embedded') AS chunks_embedded,
                    (SELECT COUNT(*) FROM rag_chunks WHERE embedding_state = 'pending') AS chunks_pending
                """
            ).fetchone()
        client, version, resolved_base_url = self._resolve_live_runtime(settings)
        installed_models: list[dict[str, Any]] = []
        running_models: list[dict[str, Any]] = []
        try:
            installed_models = client.list_models() if version else []
        except Exception:
            installed_models = []
        try:
            running_models = client.list_running_models() if version else []
        except Exception:
            running_models = []
        model_policy = self._resolve_effective_models(
            settings=settings,
            hardware=hardware,
            policy=policy,
            installed_models=installed_models,
            running_models=running_models,
            db_models=models,
        )
        installer = self._runtime_provisioner().installer_snapshot(live_version=version)
        return {
            "settings": {
                "enabled": settings.enabled,
                "base_url": settings.base_url,
                "auto_bootstrap": settings.auto_bootstrap,
                "chat_model": settings.chat_model,
                "embed_model": settings.embed_model,
                "keep_alive": settings.keep_alive,
                "auto_index_documents": settings.auto_index_documents,
            },
            "runtime": runtime,
            "runtime_online": bool(version),
            "runtime_version_live": version,
            "runtime_base_url_live": resolved_base_url if version else "",
            "models": models,
            "running_models": running_models,
            "policy": policy,
            "preferred_models": {
                "chat": model_policy["preferred_chat_model"],
                "embed": model_policy["preferred_embed_model"],
            },
            "resolved_models": {
                "chat": model_policy["chat_model"],
                "embed": model_policy["embed_model"],
            },
            "installer": installer,
            "counts": dict(counts or {}),
            "models_path": str(self.models_path),
        }

    def _active_model(self, role: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT model_name FROM local_ai_models WHERE role = ? AND is_active = 1 ORDER BY last_verified_at DESC LIMIT 1",
                (role,),
            ).fetchone()
            if row:
                return str(row["model_name"] or "").strip() or None
        settings = self._load_settings()
        hardware = self._detect_hardware()
        policy = self._load_policy()
        client, version, _ = self._resolve_live_runtime(settings)
        installed_models: list[dict[str, Any]] = []
        running_models: list[dict[str, Any]] = []
        if version:
            try:
                installed_models = client.list_models()
            except Exception:
                installed_models = []
            try:
                running_models = client.list_running_models()
            except Exception:
                running_models = []
        resolved = self._resolve_effective_models(
            settings=settings,
            hardware=hardware,
            policy=policy,
            installed_models=installed_models,
            running_models=running_models,
        )
        return resolved["chat_model"] if role == "chat" else resolved["embed_model"]

    def _read_document_file(self, file_path: Path) -> bytes:
        data = file_path.read_bytes()
        try:
            return _decrypt_document_bytes(data)
        except Exception:
            return data

    def _extract_pdf_pages(self, data: bytes) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = _normalize_text(page.extract_text() or "")
                text = re.sub(r"[ \t]+", " ", text)
                text = re.sub(r"\n{3,}", "\n\n", text).strip()
                if text:
                    pages.append({"page_number": index, "text": text})
        if not pages:
            raise ValueError("PDF senza testo estraibile. OCR non attivo di default.")
        return pages

    def _extract_docx_pages(self, data: bytes) -> list[dict[str, Any]]:
        text = _docx_text_from_bytes(data)
        if not text.strip():
            raise ValueError("DOCX senza testo estraibile")
        return [{"page_number": 1, "text": _normalize_text(text).strip()}]

    def _extract_text_pages(self, data: bytes, mime_type: str) -> list[dict[str, Any]]:
        if mime_type in {"text/plain", "text/markdown"}:
            return [{"page_number": 1, "text": _normalize_text(data.decode("utf-8", errors="replace")).strip()}]
        if mime_type == "application/json":
            try:
                parsed = json.loads(data.decode("utf-8", errors="replace"))
                text = json.dumps(parsed, ensure_ascii=False, indent=2)
            except Exception:
                text = data.decode("utf-8", errors="replace")
            return [{"page_number": 1, "text": _normalize_text(text).strip()}]
        if mime_type in {"text/html", "application/xhtml+xml"}:
            text = _strip_html(data.decode("utf-8", errors="replace"))
            return [{"page_number": 1, "text": _normalize_text(text).strip()}]
        if mime_type == "application/pdf":
            return self._extract_pdf_pages(data)
        if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self._extract_docx_pages(data)
        raise ValueError(f"Formato non supportato per parsing locale: {mime_type}")

    def _detect_mime(self, file_path: Path, explicit: str | None = None) -> str:
        if explicit:
            return explicit
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type == "text/markdown":
            return mime_type
        if file_path.suffix.lower() == ".md":
            return "text/markdown"
        if file_path.suffix.lower() == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return mime_type or "application/octet-stream"

    def _build_sections(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for page in pages:
            for paragraph in _paragraphs(page.get("text", "")):
                section_type, heading = _looks_like_heading(paragraph)
                if heading and section_type != "corpo":
                    if current and current.get("text"):
                        sections.append(current)
                    current = {
                        "section_type": section_type,
                        "heading": heading,
                        "text": "",
                        "page_from": page.get("page_number"),
                        "page_to": page.get("page_number"),
                    }
                    continue
                if current is None:
                    current = {
                        "section_type": "corpo",
                        "heading": None,
                        "text": "",
                        "page_from": page.get("page_number"),
                        "page_to": page.get("page_number"),
                    }
                current["text"] = f"{current.get('text', '').rstrip()}\n\n{paragraph}".strip()
                current["page_to"] = page.get("page_number")
        if current and current.get("text"):
            sections.append(current)
        if not sections:
            joined = "\n\n".join(page.get("text", "") for page in pages if page.get("text"))
            if joined.strip():
                sections.append(
                    {
                        "section_type": "corpo",
                        "heading": None,
                        "text": joined.strip(),
                        "page_from": pages[0].get("page_number") if pages else None,
                        "page_to": pages[-1].get("page_number") if pages else None,
                    }
                )
        return sections

    def _split_section(self, text: str, max_tokens: int = 800, overlap_tokens: int = 100) -> list[str]:
        paragraphs = _paragraphs(text)
        if not paragraphs:
            return []
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0
        for paragraph in paragraphs:
            paragraph_tokens = _estimate_tokens(paragraph)
            if current and current_tokens + paragraph_tokens > max_tokens:
                chunks.append("\n\n".join(current).strip())
                overlap: list[str] = []
                overlap_count = 0
                for existing in reversed(current):
                    existing_tokens = _estimate_tokens(existing)
                    if overlap and overlap_count + existing_tokens > overlap_tokens:
                        break
                    overlap.insert(0, existing)
                    overlap_count += existing_tokens
                current = overlap + [paragraph]
                current_tokens = _estimate_tokens("\n\n".join(current))
            else:
                current.append(paragraph)
                current_tokens += paragraph_tokens
        if current:
            chunks.append("\n\n".join(current).strip())
        return [chunk for chunk in chunks if chunk]

    def _parse_document_bytes(
        self,
        *,
        data: bytes,
        file_path: Path,
        mime_type: str,
        title: str,
    ) -> dict[str, Any]:
        pages = self._extract_text_pages(data, mime_type)
        pages = [{"page_number": page["page_number"], "text": _normalize_text(page["text"]).strip()} for page in pages if page.get("text", "").strip()]
        raw_text = "\n\n".join(page["text"] for page in pages)
        sections = self._build_sections(pages)
        return {
            "title": title,
            "mime_type": mime_type,
            "file_path": str(file_path),
            "raw_text": raw_text,
            "pages": pages,
            "sections": sections,
            "language": _detect_language(raw_text),
        }

    def _build_chunk_rows(
        self,
        *,
        document_id: str,
        practice_id: str | None,
        parsed: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        ordinal = 1
        for section in parsed.get("sections") or []:
            for chunk_text in self._split_section(section.get("text", "")):
                rows.append(
                    {
                        "id": uuid.uuid4().hex,
                        "document_id": document_id,
                        "practice_id": practice_id,
                        "section_type": section.get("section_type"),
                        "ordinal": ordinal,
                        "page_from": section.get("page_from"),
                        "page_to": section.get("page_to"),
                        "token_estimate": _estimate_tokens(chunk_text),
                        "text": chunk_text,
                        "metadata_json": json.dumps(
                            {
                                "heading": section.get("heading"),
                                "section_type": section.get("section_type"),
                                "page_from": section.get("page_from"),
                                "page_to": section.get("page_to"),
                            },
                            ensure_ascii=False,
                        ),
                        "embedding_state": "pending",
                        "embedding_json": None,
                        "embedding_dimensions": None,
                        "created_at": _now_iso(),
                        "updated_at": _now_iso(),
                    }
                )
                ordinal += 1
        return rows

    def _document_by_source(self, conn: sqlite3.Connection, source_type: str, source_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM rag_documents WHERE source_type = ? AND source_id = ? LIMIT 1",
            (source_type, source_id),
        ).fetchone()
        return dict(row) if row else None

    def _upsert_document(
        self,
        conn: sqlite3.Connection,
        *,
        document_id: str | None,
        source_type: str,
        source_id: str,
        practice_id: str | None,
        title: str,
        file_path: str,
        mime_type: str,
        sha256: str,
    ) -> str:
        now = _now_iso()
        existing = self._document_by_source(conn, source_type, source_id)
        if existing:
            conn.execute(
                """
                UPDATE rag_documents
                SET
                    practice_id = ?,
                    title = ?,
                    file_path = ?,
                    mime_type = ?,
                    sha256 = ?,
                    parse_state = 'pending',
                    chunk_count = 0,
                    last_indexed_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    practice_id,
                    title,
                    file_path,
                    mime_type,
                    sha256,
                    now,
                    existing["id"],
                ),
            )
            return str(existing["id"])
        doc_id = document_id or uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO rag_documents (
                id, source_type, source_id, practice_id, title, file_path, mime_type, sha256,
                language, parse_state, chunk_count, last_indexed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                source_type,
                source_id,
                practice_id,
                title,
                file_path,
                mime_type,
                sha256,
                None,
                "pending",
                0,
                None,
                now,
                now,
            ),
        )
        return doc_id

    def _replace_document_chunks(self, conn: sqlite3.Connection, document_id: str, chunk_rows: list[dict[str, Any]]) -> None:
        conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (document_id,))
        for row in chunk_rows:
            conn.execute(
                """
                INSERT INTO rag_chunks (
                    id, document_id, practice_id, section_type, ordinal, page_from, page_to,
                    token_estimate, text, metadata_json, embedding_state, embedding_json,
                    embedding_dimensions, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["document_id"],
                    row["practice_id"],
                    row["section_type"],
                    row["ordinal"],
                    row["page_from"],
                    row["page_to"],
                    row["token_estimate"],
                    row["text"],
                    row["metadata_json"],
                    row["embedding_state"],
                    row["embedding_json"],
                    row["embedding_dimensions"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    def index_file(
        self,
        *,
        source_type: str,
        source_id: str,
        practice_id: str | None,
        file_path: str,
        title: str | None = None,
        mime_type: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        resolved = Path(file_path)
        if not resolved.exists():
            raise FileNotFoundError(f"Documento non trovato: {resolved}")
        detected_mime = self._detect_mime(resolved, mime_type)
        if not _is_supported_mime(detected_mime):
            return {"status": "unsupported", "file_path": str(resolved), "mime_type": detected_mime}
        data = self._read_document_file(resolved)
        sha256 = _sha256_bytes(data)
        with self._connect() as conn:
            existing = self._document_by_source(conn, source_type, source_id)
            if existing and not force and existing.get("sha256") == sha256 and str(existing.get("parse_state") or "") == "parsed":
                return {
                    "status": "skipped",
                    "document_id": existing["id"],
                    "chunk_count": int(existing.get("chunk_count") or 0),
                    "mime_type": detected_mime,
                }
            document_id = self._upsert_document(
                conn,
                document_id=existing["id"] if existing else None,
                source_type=source_type,
                source_id=source_id,
                practice_id=practice_id,
                title=title or resolved.name,
                file_path=str(resolved),
                mime_type=detected_mime,
                sha256=sha256,
            )
            try:
                parsed = self._parse_document_bytes(
                    data=data,
                    file_path=resolved,
                    mime_type=detected_mime,
                    title=title or resolved.name,
                )
                chunk_rows = self._build_chunk_rows(document_id=document_id, practice_id=practice_id, parsed=parsed)
                self._replace_document_chunks(conn, document_id, chunk_rows)
                conn.execute(
                    """
                    UPDATE rag_documents
                    SET language = ?, parse_state = 'parsed', chunk_count = ?, last_indexed_at = ?, updated_at = ?, practice_id = ?
                    WHERE id = ?
                    """,
                    (
                        parsed.get("language"),
                        len(chunk_rows),
                        _now_iso(),
                        _now_iso(),
                        practice_id,
                        document_id,
                    ),
                )
                conn.commit()
                return {
                    "status": "indexed",
                    "document_id": document_id,
                    "chunk_count": len(chunk_rows),
                    "mime_type": detected_mime,
                    "language": parsed.get("language"),
                }
            except Exception:
                conn.execute(
                    "UPDATE rag_documents SET parse_state = 'error', updated_at = ? WHERE id = ?",
                    (_now_iso(), document_id),
                )
                conn.commit()
                raise

    def index_fascicolo_documents(self, fascicolo: Any, documents_dir: str, *, force: bool = False, limit: int | None = None) -> dict[str, Any]:
        results = {"indexed": 0, "skipped": 0, "unsupported": 0, "errors": []}
        docs = list(getattr(fascicolo, "documenti", []) or [])
        if limit:
            docs = docs[:limit]
        for doc in docs:
            try:
                raw_path = getattr(doc, "percorso", "")
                path = Path(raw_path)
                full_path = path if path.is_absolute() else Path(documents_dir) / raw_path
                outcome = self.index_file(
                    source_type="fascicolo_documento",
                    source_id=str(getattr(doc, "id", "")),
                    practice_id=str(getattr(fascicolo, "id", "")) or None,
                    file_path=str(full_path),
                    title=str(getattr(doc, "nome", "") or full_path.name),
                    force=force,
                )
                results[outcome["status"]] = results.get(outcome["status"], 0) + 1
            except Exception as exc:
                results["errors"].append(
                    {
                        "document_id": str(getattr(doc, "id", "")),
                        "nome": str(getattr(doc, "nome", "")),
                        "errore": str(exc),
                    }
                )
        return results

    def embed_pending_chunks(self, *, limit: int = 100) -> dict[str, Any]:
        bootstrap = self.bootstrap_runtime()
        if bootstrap.get("status") != "ready":
            return {"status": bootstrap.get("status"), "embedded": 0, "error": bootstrap.get("error")}
        embed_model = bootstrap.get("embed_model") or self._active_model("embed")
        if not embed_model:
            return {"status": "error", "embedded": 0, "error": "Modello embedding non disponibile"}
        settings = self._load_settings()
        client = self._ollama_client(settings)
        with self._connect() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, text
                    FROM rag_chunks
                    WHERE embedding_state = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]
            if not rows:
                return {"status": "ready", "embedded": 0, "vector_dimensions": None}
            embed_result = client.embed_texts(str(embed_model), [str(row["text"] or "") for row in rows])
            vectors = embed_result.get("embeddings") or []
            if len(vectors) != len(rows):
                raise ValueError("Numero embeddings diverso dai chunk in pending")
            touched_documents: set[str] = set()
            id_to_document: dict[str, str] = {}
            for row in conn.execute(
                "SELECT id, document_id FROM rag_chunks WHERE id IN ({})".format(",".join("?" for _ in rows)),
                tuple(item["id"] for item in rows),
            ).fetchall():
                id_to_document[str(row["id"])] = str(row["document_id"])
            for idx, row in enumerate(rows):
                vector = vectors[idx]
                conn.execute(
                    """
                    UPDATE rag_chunks
                    SET embedding_state = 'embedded', embedding_json = ?, embedding_dimensions = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (json.dumps(vector), len(vector), _now_iso(), row["id"]),
                )
                if id_to_document.get(str(row["id"])):
                    touched_documents.add(id_to_document[str(row["id"])])
            for document_id in touched_documents:
                count_row = conn.execute(
                    "SELECT COUNT(*) AS total FROM rag_chunks WHERE document_id = ?",
                    (document_id,),
                ).fetchone()
                conn.execute(
                    "UPDATE rag_documents SET chunk_count = ?, last_indexed_at = ?, updated_at = ? WHERE id = ?",
                    (int(count_row["total"] or 0), _now_iso(), _now_iso(), document_id),
                )
            conn.commit()
            return {
                "status": "ready",
                "embedded": len(rows),
                "vector_dimensions": len(vectors[0]) if vectors else None,
                "load_duration_ms": embed_result.get("load_duration"),
                "prompt_eval_count": embed_result.get("prompt_eval_count"),
                "eval_count": embed_result.get("eval_count"),
            }

    def reindex_fascicolo(self, fascicolo: Any, documents_dir: str, *, force: bool = False) -> dict[str, Any]:
        doc_result = self.index_fascicolo_documents(fascicolo, documents_dir, force=force)
        embed_result = self.embed_pending_chunks(limit=200)
        return {
            "documents": doc_result,
            "embeddings": embed_result,
        }

    def _fts_rows(self, conn: sqlite3.Connection, query_text: str, practice_id: str | None, document_id: str | None, top_k: int) -> list[dict[str, Any]]:
        tokens = _extract_text_tokens(query_text)[:10]
        if not tokens:
            return []
        fts_query = " OR ".join(f'"{token}"' for token in tokens)
        conditions = ["rag_chunks_fts MATCH ?"]
        params: list[Any] = [fts_query]
        if practice_id:
            conditions.append("c.practice_id = ?")
            params.append(practice_id)
        if document_id:
            conditions.append("c.document_id = ?")
            params.append(document_id)
        sql = f"""
            SELECT
                c.id, c.document_id, c.practice_id, c.section_type, c.ordinal,
                c.page_from, c.page_to, c.text, c.metadata_json,
                bm25(rag_chunks_fts) AS bm25_score
            FROM rag_chunks_fts
            JOIN rag_chunks AS c ON c.rowid = rag_chunks_fts.rowid
            WHERE {' AND '.join(conditions)}
            ORDER BY bm25_score ASC
            LIMIT ?
        """
        params.append(top_k * 3)
        return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def _vector_rows(self, conn: sqlite3.Connection, query_vector: list[float], practice_id: str | None, document_id: str | None, top_k: int) -> list[dict[str, Any]]:
        conditions = ["embedding_state = 'embedded'", "embedding_json IS NOT NULL"]
        params: list[Any] = []
        if practice_id:
            conditions.append("practice_id = ?")
            params.append(practice_id)
        if document_id:
            conditions.append("document_id = ?")
            params.append(document_id)
        sql = f"""
            SELECT
                id, document_id, practice_id, section_type, ordinal,
                page_from, page_to, text, metadata_json, embedding_json
            FROM rag_chunks
            WHERE {' AND '.join(conditions)}
            ORDER BY updated_at DESC
            LIMIT ?
        """
        params.append(max(200, top_k * 40))
        rows: list[dict[str, Any]] = []
        for row in conn.execute(sql, params).fetchall():
            payload = dict(row)
            try:
                vector = json.loads(payload.pop("embedding_json") or "[]")
            except Exception:
                vector = []
            payload["vector_score"] = _cosine_similarity(query_vector, vector)
            rows.append(payload)
        rows.sort(key=lambda item: float(item.get("vector_score") or 0), reverse=True)
        return rows[: top_k * 3]

    def _document_titles(self, conn: sqlite3.Connection, document_ids: Iterable[str]) -> dict[str, str]:
        ids = [doc_id for doc_id in document_ids if doc_id]
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        sql = f"SELECT id, title FROM rag_documents WHERE id IN ({placeholders})"
        return {str(row["id"]): str(row["title"] or "Documento") for row in conn.execute(sql, ids).fetchall()}

    def _citation_for_row(self, row: dict[str, Any], title: str) -> str:
        page_from = row.get("page_from")
        page_to = row.get("page_to")
        if page_from and page_to and page_from != page_to:
            page_label = f"pp. {page_from}-{page_to}"
        elif page_from or page_to:
            page_label = f"p. {page_from or page_to}"
        else:
            page_label = "pagina n.d."
        section_type = str(row.get("section_type") or "sezione").strip()
        return f"{title}, {page_label} · {section_type} · chunk {str(row.get('id', ''))[:8]}"

    def hybrid_search(
        self,
        query_text: str,
        *,
        practice_id: str | None = None,
        document_id: str | None = None,
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        if not str(query_text or "").strip():
            return []
        settings = self._load_settings()
        client = self._ollama_client(settings)
        embed_model = self._active_model("embed")
        query_vector: list[float] = []
        load_duration = None
        prompt_eval_count = None
        if embed_model:
            try:
                embed_result = client.embed_texts(embed_model, [query_text])
                query_vector = list(embed_result.get("embeddings") or [[]])[0]
                load_duration = embed_result.get("load_duration")
                prompt_eval_count = embed_result.get("prompt_eval_count")
            except Exception:
                query_vector = []
        with self._connect() as conn:
            text_rows = self._fts_rows(conn, query_text, practice_id, document_id, top_k)
            vector_rows = self._vector_rows(conn, query_vector, practice_id, document_id, top_k) if query_vector else []
            by_id: dict[str, dict[str, Any]] = {}
            for index, row in enumerate(vector_rows):
                item = by_id.setdefault(str(row["id"]), dict(row))
                item["hybrid_score"] = float(item.get("hybrid_score") or 0.0) + (1.0 / (61 + index))
                item["vector_score"] = row.get("vector_score")
            for index, row in enumerate(text_rows):
                item = by_id.setdefault(str(row["id"]), dict(row))
                item["hybrid_score"] = float(item.get("hybrid_score") or 0.0) + (1.0 / (61 + index))
                item["text_score"] = row.get("bm25_score")
            document_titles = self._document_titles(conn, [row.get("document_id") for row in by_id.values()])
            ordered = sorted(by_id.values(), key=lambda item: float(item.get("hybrid_score") or 0.0), reverse=True)[:top_k]
            for row in ordered:
                title = document_titles.get(str(row.get("document_id")), "Documento")
                row["citation"] = self._citation_for_row(row, title)
                row["title"] = title
            conn.execute(
                """
                INSERT INTO rag_query_logs (
                    id, query_text, query_type, top_k, duration_ms, load_duration_ms,
                    prompt_eval_count, eval_count, retrieved_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    query_text,
                    "hybrid",
                    top_k,
                    None,
                    load_duration,
                    prompt_eval_count,
                    None,
                    json.dumps([row["id"] for row in ordered], ensure_ascii=False),
                    _now_iso(),
                ),
            )
            conn.commit()
            return ordered

    def _summarize_scadenze(self, scadenze: Iterable[Any]) -> list[str]:
        rows: list[str] = []
        for item in list(scadenze or [])[:8]:
            titolo = _clean_spaces(getattr(item, "titolo", "") or getattr(item, "descrizione", ""))
            data = getattr(item, "data_scadenza", "") or getattr(item, "data", "")
            stato = getattr(item, "stato", "")
            rows.append(f"- {titolo or 'Scadenza'} · {data} · {getattr(stato, 'value', stato) or 'n.d.'}")
        return rows

    def _summarize_apps(self, apps: Iterable[Any]) -> list[str]:
        rows: list[str] = []
        for item in list(apps or [])[:8]:
            titolo = _clean_spaces(getattr(item, "titolo", "") or getattr(item, "descrizione", ""))
            data = getattr(item, "data_ora", "") or getattr(item, "data", "")
            luogo = _clean_spaces(getattr(item, "luogo", ""))
            label = f"- {titolo or 'Appuntamento'} · {data}"
            if luogo:
                label += f" · {luogo}"
            rows.append(label)
        return rows

    def _prompt_for_fascicolo(
        self,
        *,
        fascicolo: Any,
        question: str,
        workspace: dict[str, Any] | None,
        intelligenza: dict[str, Any] | None,
        apps: Iterable[Any],
        scadenze: Iterable[Any],
        rag_rows: list[dict[str, Any]],
    ) -> str:
        fascicolo_lines = [
            f"ID fascicolo: {getattr(fascicolo, 'id', '')}",
            f"Titolo: {getattr(fascicolo, 'titolo', '')}",
            f"Oggetto: {getattr(fascicolo, 'oggetto', '')}",
            f"Tribunale/ufficio: {getattr(fascicolo, 'tribunale', '')}",
            f"Numero RG: {getattr(fascicolo, 'numero_rg', '')}",
            f"Anno RG: {getattr(fascicolo, 'anno_rg', '')}",
            f"Controparte: {getattr(fascicolo, 'controparte', '')}",
            f"Stato: {getattr(getattr(fascicolo, 'stato', ''), 'value', getattr(fascicolo, 'stato', ''))}",
            f"Tipo: {getattr(getattr(fascicolo, 'tipo', ''), 'value', getattr(fascicolo, 'tipo', ''))}",
        ]
        if workspace:
            prossime = workspace.get("prossime_azioni") or workspace.get("azioni") or []
            if prossime:
                fascicolo_lines.append("Azioni operative:")
                fascicolo_lines.extend(f"- {str(item)}" for item in prossime[:6])
        if intelligenza:
            evidenze = intelligenza.get("evidenze") or intelligenza.get("alert") or []
            if evidenze:
                fascicolo_lines.append("Alert intelligenti:")
                fascicolo_lines.extend(f"- {str(item)}" for item in evidenze[:6])
            giuri = intelligenza.get("giurisprudenza_suggerita") or []
            if giuri:
                fascicolo_lines.append("Giurisprudenza suggerita:")
                for row in giuri[:5]:
                    fascicolo_lines.append(
                        f"- {row.get('autorita') or row.get('authority') or 'Giurisprudenza'} · "
                        f"{row.get('numero') or row.get('decision_number') or ''} · "
                        f"{row.get('titolo') or row.get('title') or row.get('massima') or ''}"
                    )
        app_lines = self._summarize_apps(apps)
        if app_lines:
            fascicolo_lines.append("Agenda collegata:")
            fascicolo_lines.extend(app_lines)
        scadenza_lines = self._summarize_scadenze(scadenze)
        if scadenza_lines:
            fascicolo_lines.append("Scadenziario collegato:")
            fascicolo_lines.extend(scadenza_lines)
        context = "\n".join(line for line in fascicolo_lines if _clean_spaces(line))
        rag_context = "\n\n---\n\n".join(
            f"[Fonte {idx + 1}] {row.get('citation')}\n{row.get('text')}"
            for idx, row in enumerate(rag_rows)
        ) or "Nessun documento indicizzato rilevante."
        return "\n".join(
            [
                "Sei l'assistente locale operativo di HACS per studi legali italiani.",
                "Rispondi in italiano, con taglio pratico e professionale.",
                "Usa solo il contesto fornito. Se il contesto non basta, dichiaralo chiaramente.",
                "Non inventare norme, date, esiti o documenti mancanti.",
                "Se citi documenti, usa le citazioni fornite nel contesto.",
                "",
                "Domanda utente:",
                question.strip(),
                "",
                "Contesto fascicolo:",
                context,
                "",
                "Contesto documentale RAG:",
                rag_context,
                "",
                "Struttura la risposta in modo operativo.",
                "Chiudi sempre con una sezione 'Fonti' che elenchi solo le fonti effettivamente usate.",
            ]
        )

    def prepare_fascicolo_query(
        self,
        *,
        fascicolo: Any,
        documents_dir: str,
        question: str,
        apps: Iterable[Any] | None = None,
        scadenze: Iterable[Any] | None = None,
        workspace: dict[str, Any] | None = None,
        intelligenza: dict[str, Any] | None = None,
        auto_index: bool | None = None,
    ) -> dict[str, Any]:
        settings = self._load_settings()
        should_index = settings.auto_index_documents if auto_index is None else bool(auto_index)
        indexing = None
        if should_index:
            indexing = self.index_fascicolo_documents(fascicolo, documents_dir)
        rag_rows = self.hybrid_search(question, practice_id=str(getattr(fascicolo, "id", "")), top_k=8)
        prompt = self._prompt_for_fascicolo(
            fascicolo=fascicolo,
            question=question,
            workspace=workspace,
            intelligenza=intelligenza,
            apps=apps or [],
            scadenze=scadenze or [],
            rag_rows=rag_rows,
        )
        return {
            "ok": True,
            "query_type": "fascicolo_ai",
            "question": question,
            "prompt": prompt,
            "sources": rag_rows,
            "citations": [row.get("citation") for row in rag_rows if row.get("citation")],
            "indexing": indexing,
        }

    def _prompt_for_workspace(self, *, question: str, overview: dict[str, Any], rag_rows: list[dict[str, Any]]) -> str:
        focus_lines = [
            f"Scadenze urgenti: {len(overview.get('scadenze_urgenti') or [])}",
            f"Appuntamenti imminenti: {len(overview.get('appuntamenti_imminenti') or [])}",
            f"Fascicoli hot: {len(overview.get('fascicoli_urgenti') or [])}",
        ]
        patron = overview.get("patrono_studio") or {}
        if patron:
            focus_lines.append(
                f"Patrono studio: {patron.get('label') or patron.get('patron_name') or ''} · "
                f"{patron.get('status_label') or patron.get('status') or ''}"
            )
        sync_profiles = overview.get("calendar_sync") or overview.get("sincronizzazioni") or []
        if sync_profiles:
            focus_lines.append(f"Profili agenda sincronizzati: {len(sync_profiles)}")
        rag_context = "\n\n---\n\n".join(
            f"[Fonte {idx + 1}] {row.get('citation')}\n{row.get('text')}"
            for idx, row in enumerate(rag_rows)
        ) or "Nessun documento indicizzato rilevante."
        return "\n".join(
            [
                "Sei l'assistente operativo locale di HACS.",
                "Aiuti lo studio a coordinare agenda, scadenziario, fascicoli e documenti.",
                "Usa solo il contesto disponibile. Se serve altro, dillo.",
                "",
                f"Domanda: {question.strip()}",
                "",
                "Quadro operativo:",
                "\n".join(focus_lines),
                "",
                "Contesto documentale RAG:",
                rag_context,
                "",
                "Rispondi con priorità pratiche, rischi e prossimi passi.",
                "Chiudi con una sezione 'Fonti'.",
            ]
        )

    def prepare_workspace_query(
        self,
        *,
        question: str,
        overview: dict[str, Any],
    ) -> dict[str, Any]:
        rag_rows = self.hybrid_search(question, top_k=8)
        prompt = self._prompt_for_workspace(question=question, overview=overview, rag_rows=rag_rows)
        return {
            "ok": True,
            "query_type": "workspace_ai",
            "question": question,
            "prompt": prompt,
            "sources": rag_rows,
            "citations": [row.get("citation") for row in rag_rows if row.get("citation")],
        }

    def _complete_prepared_query(
        self,
        *,
        prepared: dict[str, Any],
        runtime: dict[str, Any],
        keep_alive: str,
    ) -> dict[str, Any]:
        client = self._ollama_client(self._load_settings())
        chat_model = str(runtime.get("chat_model") or self._active_model("chat") or "")
        started = time.time()
        response = client.generate(chat_model, str(prepared.get("prompt") or ""), keep_alive=keep_alive)
        duration_ms = int((time.time() - started) * 1000)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rag_query_logs (
                    id, query_text, query_type, top_k, duration_ms, load_duration_ms,
                    prompt_eval_count, eval_count, retrieved_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    str(prepared.get("question") or ""),
                    str(prepared.get("query_type") or "rag_query"),
                    len(prepared.get("sources") or []),
                    duration_ms,
                    response.get("load_duration"),
                    response.get("prompt_eval_count"),
                    response.get("eval_count"),
                    json.dumps([row.get("id") for row in prepared.get("sources") or []], ensure_ascii=False),
                    _now_iso(),
                ),
            )
            conn.commit()
        return {
            "ok": True,
            "status": "ready",
            "answer": str(response.get("response") or "").strip(),
            "sources": prepared.get("sources") or [],
            "citations": prepared.get("citations") or [],
            "runtime": runtime,
            "indexing": prepared.get("indexing"),
        }

    def ask_fascicolo(
        self,
        *,
        fascicolo: Any,
        documents_dir: str,
        question: str,
        apps: Iterable[Any] | None = None,
        scadenze: Iterable[Any] | None = None,
        workspace: dict[str, Any] | None = None,
        intelligenza: dict[str, Any] | None = None,
        auto_index: bool | None = None,
    ) -> dict[str, Any]:
        bootstrap = self.bootstrap_runtime()
        if bootstrap.get("status") != "ready":
            return {
                "ok": False,
                "status": bootstrap.get("status"),
                "errore": bootstrap.get("error") or "AI locale non pronta",
                "sources": [],
                "citations": [],
                "answer": "",
            }
        settings = self._load_settings()
        prepared = self.prepare_fascicolo_query(
            fascicolo=fascicolo,
            documents_dir=documents_dir,
            question=question,
            apps=apps or [],
            scadenze=scadenze or [],
            workspace=workspace,
            intelligenza=intelligenza,
            auto_index=auto_index,
        )
        self.embed_pending_chunks(limit=200)
        return self._complete_prepared_query(prepared=prepared, runtime=bootstrap, keep_alive=settings.keep_alive)

    def ask_workspace(
        self,
        *,
        question: str,
        overview: dict[str, Any],
    ) -> dict[str, Any]:
        bootstrap = self.bootstrap_runtime()
        if bootstrap.get("status") != "ready":
            return {
                "ok": False,
                "status": bootstrap.get("status"),
                "errore": bootstrap.get("error") or "AI locale non pronta",
                "sources": [],
                "citations": [],
                "answer": "",
            }
        settings = self._load_settings()
        prepared = self.prepare_workspace_query(question=question, overview=overview)
        return self._complete_prepared_query(prepared=prepared, runtime=bootstrap, keep_alive=settings.keep_alive)

    def scheduled_maintenance(self, fascicoli_gestore: Any | None = None, documents_dir: str | None = None) -> dict[str, Any]:
        bootstrap = self.bootstrap_runtime()
        if bootstrap.get("status") != "ready":
            return {"status": bootstrap.get("status"), "error": bootstrap.get("error")}
        indexed_total = 0
        error_total = 0
        if fascicoli_gestore and documents_dir and self._load_settings().auto_index_documents:
            try:
                fascicoli = list(fascicoli_gestore.tutti())[:10]
                for fascicolo in fascicoli:
                    outcome = self.index_fascicolo_documents(fascicolo, documents_dir, limit=12)
                    indexed_total += int(outcome.get("indexed") or 0)
                    error_total += len(outcome.get("errors") or [])
            except Exception as exc:
                return {"status": "error", "error": str(exc)}
        embeddings = self.embed_pending_chunks(limit=250)
        return {
            "status": "ready",
            "indexed": indexed_total,
            "index_errors": error_total,
            "embeddings": embeddings,
        }


__all__ = [
    "LocalAIService",
    "LocalAiSettings",
    "OllamaHttpClient",
    "strip_api_suffix",
]
