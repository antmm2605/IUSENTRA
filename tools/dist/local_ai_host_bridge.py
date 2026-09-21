from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterator


DEFAULT_POLICY: dict[str, Any] = {
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
}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _normalize_platform_name(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw.startswith("win"):
        return "windows"
    if raw.startswith("darwin") or raw.startswith("mac"):
        return "darwin"
    if raw.startswith("linux"):
        return "linux"
    return raw or "unknown"


def _normalize_machine_name(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"amd64", "x86_64", "x64"}:
        return "amd64"
    if raw in {"arm64", "aarch64"}:
        return "arm64"
    return raw or "unknown"


def _normalize_api_base_url(value: str | None) -> str:
    raw = str(value or DEFAULT_POLICY["ollama"]["baseUrl"]).strip().rstrip("/")
    if not raw:
        raw = DEFAULT_POLICY["ollama"]["baseUrl"]
    if raw.endswith("/api"):
        return raw
    return f"{raw}/api"


def _compare_versions(left: str, right: str) -> int:
    def _parts(value: str) -> list[int]:
        cleaned = str(value or "").strip().lstrip("vV")
        return [int(chunk) for chunk in __import__("re").findall(r"\d+", cleaned)]

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


class OllamaLocalClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = _normalize_api_base_url(base_url)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {exc.code} su {path}: {details}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(str(exc.reason or exc)) from exc
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def get_version(self) -> str | None:
        try:
            version = str(self._request("GET", "/version", timeout=5).get("version") or "").strip()
            return version or None
        except Exception:
            return None

    def list_models(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/tags", timeout=15).get("models") or [])

    def list_running_models(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/ps", timeout=10).get("models") or [])

    def pull_model(self, model_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/pull",
            payload={"model": model_name, "stream": False},
            timeout=900,
        )

    def warmup_model(self, model_name: str, keep_alive: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/generate",
            payload={"model": model_name, "prompt": "ok", "stream": False, "keep_alive": keep_alive},
            timeout=240,
        )

    def embed_texts(self, model_name: str, inputs: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/embed",
            payload={"model": model_name, "input": inputs, "truncate": True},
            timeout=240,
        )

    def generate(self, model_name: str, prompt: str, keep_alive: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/generate",
            payload={"model": model_name, "prompt": prompt, "stream": False, "keep_alive": keep_alive},
            timeout=300,
        )

    def generate_stream(self, model_name: str, prompt: str, keep_alive: str, timeout: float = 300.0) -> Iterator[dict[str, Any]]:
        payload = {"model": model_name, "prompt": prompt, "stream": True, "keep_alive": keep_alive}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/generate",
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {exc.code} su /generate: {details}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(str(exc.reason or exc)) from exc

        try:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        finally:
            response.close()


class LocalAiHostBridge:
    _LATEST_RELEASE_URL = "https://api.github.com/repos/ollama/ollama/releases/latest"

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root_dir = Path(root_dir or Path(__file__).resolve().parent).resolve()
        self.ai_root = self.root_dir / "ai"
        self.models_path = self.ai_root / "models"
        self.runtime_root = self.ai_root / "runtime" / "ollama"
        self.download_root = self.ai_root / "downloads" / "ollama"
        self.release_cache_path = self.download_root / "latest-release.json"
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.download_root.mkdir(parents=True, exist_ok=True)

    def _settings(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        data = dict(overrides or {})
        enabled_raw = str(data.get("enabled", True)).strip().lower()
        auto_bootstrap_raw = str(data.get("auto_bootstrap", True)).strip().lower()
        auto_index_raw = str(data.get("auto_index_documents", True)).strip().lower()
        return {
            "enabled": enabled_raw not in {"0", "false", "no", "off"},
            "base_url": _normalize_api_base_url(data.get("base_url")),
            "auto_bootstrap": auto_bootstrap_raw not in {"0", "false", "no", "off"},
            "chat_model": str(data.get("chat_model") or "").strip(),
            "embed_model": str(data.get("embed_model") or "").strip(),
            "keep_alive": str(data.get("keep_alive") or DEFAULT_POLICY["ollama"]["defaultWarmupKeepAlive"]).strip()
            or DEFAULT_POLICY["ollama"]["defaultWarmupKeepAlive"],
            "auto_index_documents": auto_index_raw not in {"0", "false", "no", "off"},
        }

    def _detect_ram_gb(self) -> float:
        if os.name == "nt":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
                return round(status.ullTotalPhys / (1024 ** 3), 2)
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            pages = os.sysconf("SC_PHYS_PAGES")
            return round((page_size * pages) / (1024 ** 3), 2)
        except Exception:
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

    def _detect_windows_cpu_name(self) -> str:
        raw = os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
        if raw:
            return raw
        try:
            script = "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)"
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
            )
            value = str(result.stdout or "").strip()
            if value:
                return value
        except Exception:
            pass
        return platform.processor() or "CPU non rilevata"

    def detect_hardware(self) -> dict[str, Any]:
        root = self.models_path.drive or self.models_path.anchor or str(self.models_path)
        disk_free_gb = round(shutil.disk_usage(root).free / (1024 ** 3), 2)
        ram_gb = self._detect_ram_gb()
        host_platform = _normalize_platform_name(sys.platform)
        host_machine = _normalize_machine_name(platform.machine() or "unknown")
        gpu_vendor = ""
        gpu_name = ""
        if host_platform == "windows":
            gpu_vendor, gpu_name = self._detect_windows_gpu()
            cpu_name = self._detect_windows_cpu_name()
        else:
            cpu_name = platform.processor() or platform.machine() or "CPU non rilevata"
        return {
            "profile": self._select_profile(ram_gb, disk_free_gb),
            "ram_gb": ram_gb,
            "disk_free_gb": disk_free_gb,
            "cpu_name": cpu_name,
            "gpu_vendor": gpu_vendor,
            "gpu_name": gpu_name,
            "os_version": f"{platform.system()} {platform.release()}".strip(),
            "host_platform": host_platform,
            "host_machine": host_machine,
        }

    def _select_profile(self, ram_gb: float, disk_free_gb: float) -> str:
        profiles = DEFAULT_POLICY["profiles"]
        for code, row in profiles.items():
            if ram_gb >= row["minRamGb"] and ram_gb <= row["maxRamGb"] and disk_free_gb >= row["minDiskFreeGb"]:
                return code
        if ram_gb >= 16 and disk_free_gb >= 40:
            return "strong"
        if ram_gb >= 8 and disk_free_gb >= 20:
            return "medium"
        return "weak"

    def resolve_models(self, settings: dict[str, Any], hardware: dict[str, Any]) -> dict[str, Any]:
        profile = hardware["profile"]
        rule = DEFAULT_POLICY["profiles"][profile]
        return {
            "profile": profile,
            "chat": settings["chat_model"] or rule["chatModel"],
            "embed": settings["embed_model"] or rule["embedModel"],
        }

    def _is_embedding_model(self, model_name: str) -> bool:
        normalized = str(model_name or "").strip().lower()
        return normalized.startswith("embedding") or "embed" in normalized

    def _fallback_profile_order(self, profile: str) -> list[str]:
        if profile == "strong":
            return ["strong", "medium", "weak"]
        if profile == "medium":
            return ["medium", "weak", "strong"]
        return ["weak", "medium", "strong"]

    def _policy_model_candidates(self, *, role: str, profile: str) -> list[str]:
        field = "chatModel" if role == "chat" else "embedModel"
        seen: set[str] = set()
        candidates: list[str] = []
        for code in self._fallback_profile_order(profile):
            model_name = str(DEFAULT_POLICY["profiles"].get(code, {}).get(field) or "").strip()
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
        installed_models: list[dict[str, Any]] | None = None,
        running_models: list[dict[str, Any]] | None = None,
        role: str,
    ) -> list[str]:
        rows = list(running_models or []) + list(installed_models or [])
        names: list[str] = []
        for row in rows:
            model_name = str(row.get("name") or row.get("model") or "").strip()
            if not model_name or model_name in names:
                continue
            if role == "embed" and not self._is_embedding_model(model_name):
                continue
            if role == "chat" and self._is_embedding_model(model_name):
                continue
            names.append(model_name)
        return names

    def _effective_model_name(
        self,
        *,
        role: str,
        preferred_model: str,
        profile: str,
        installed_models: list[dict[str, Any]] | None = None,
        running_models: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str, str]:
        available_names = self._available_model_names(
            installed_models=installed_models,
            running_models=running_models,
            role=role,
        )
        if preferred_model in available_names or not available_names:
            return preferred_model, "preferred", ""

        for candidate in self._policy_model_candidates(role=role, profile=profile):
            if candidate in available_names:
                return candidate, "fallback", f"preferred_missing:{preferred_model}"

        return available_names[0], "fallback", f"preferred_missing:{preferred_model}"

    def resolve_effective_models(
        self,
        settings: dict[str, Any],
        hardware: dict[str, Any],
        *,
        installed_models: list[dict[str, Any]] | None = None,
        running_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        preferred = self.resolve_models(settings, hardware)
        chat, chat_source, chat_reason = self._effective_model_name(
            role="chat",
            preferred_model=str(preferred["chat"] or ""),
            profile=str(preferred["profile"] or "weak"),
            installed_models=installed_models,
            running_models=running_models,
        )
        embed, embed_source, embed_reason = self._effective_model_name(
            role="embed",
            preferred_model=str(preferred["embed"] or ""),
            profile=str(preferred["profile"] or "weak"),
            installed_models=installed_models,
            running_models=running_models,
        )
        return {
            "profile": preferred["profile"],
            "preferred_chat": preferred["chat"],
            "preferred_embed": preferred["embed"],
            "chat": chat,
            "embed": embed,
            "chat_source": chat_source,
            "embed_source": embed_source,
            "chat_reason": chat_reason,
            "embed_reason": embed_reason,
        }

    def _load_cached_release(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.release_cache_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def fetch_latest_release(self, *, force_refresh: bool = False, max_age_seconds: int = 21600) -> dict[str, Any]:
        cached = self._load_cached_release()
        if cached and not force_refresh:
            fetched_at = float(cached.get("fetched_at_epoch") or 0)
            if time.time() - fetched_at <= max_age_seconds:
                return cached

        request = urllib.request.Request(
            self._LATEST_RELEASE_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "IUSENTRA-Local-AI-Bridge/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            if cached:
                return cached
            raise

        curated = {
            "version": payload.get("tag_name") or "",
            "html_url": payload.get("html_url") or "",
            "published_at": payload.get("published_at") or "",
            "fetched_at_epoch": time.time(),
            "assets": [
                {
                    "name": asset.get("name") or "",
                    "browser_download_url": asset.get("browser_download_url") or "",
                    "size": asset.get("size") or 0,
                    "updated_at": asset.get("updated_at") or asset.get("created_at") or "",
                }
                for asset in payload.get("assets") or []
            ],
        }
        self.release_cache_path.write_text(json.dumps(curated, ensure_ascii=False, indent=2), encoding="utf-8")
        return curated

    def _runtime_inventory(
        self,
        client: OllamaLocalClient,
        *,
        enabled: bool,
    ) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
        version = client.get_version() if enabled else None
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
        return version, installed_models, running_models

    def _resolved_chat_model(
        self,
        *,
        settings: dict[str, Any],
        hardware: dict[str, Any],
        installed_models: list[dict[str, Any]],
        running_models: list[dict[str, Any]],
        requested_model: str = "",
    ) -> str:
        effective_settings = dict(settings)
        if requested_model:
            effective_settings["chat_model"] = requested_model
        resolved_models = self.resolve_effective_models(
            effective_settings,
            hardware,
            installed_models=installed_models,
            running_models=running_models,
        )
        return str(resolved_models["chat"]).strip()

    def _select_download_asset(
        self,
        release: dict[str, Any],
        hardware: dict[str, Any],
        *,
        purpose: str = "installer",
    ) -> dict[str, Any] | None:
        host_platform = hardware["host_platform"]
        host_machine = hardware["host_machine"]
        preferred: list[str] = []
        if host_platform == "windows":
            if purpose == "runtime":
                preferred = ["ollama-windows-arm64.zip"] if host_machine == "arm64" else ["ollama-windows-amd64.zip"]
            else:
                preferred = ["OllamaSetup.exe"]
        elif host_platform == "linux":
            preferred = ["ollama-linux-arm64.tgz"] if host_machine == "arm64" else ["ollama-linux-amd64.tgz"]
        elif host_platform == "darwin":
            preferred = ["Ollama.dmg", "Ollama-darwin.zip"]
        for name in preferred:
            for asset in release.get("assets") or []:
                if asset.get("name") == name:
                    return asset
        return None

    def candidate_executables(self, hardware: dict[str, Any]) -> list[Path]:
        suffix = "ollama.exe" if hardware["host_platform"] == "windows" else "ollama"
        candidates: list[Path] = []
        direct = self.runtime_root / suffix
        candidates.append(direct)
        if self.runtime_root.exists():
            for match in sorted(self.runtime_root.rglob(suffix)):
                if match not in candidates:
                    candidates.append(match)
        which_path = shutil.which("ollama")
        if which_path:
            resolved = Path(which_path).resolve()
            if resolved not in candidates:
                candidates.append(resolved)
        return candidates

    def discover_executable(self, hardware: dict[str, Any]) -> Path | None:
        for candidate in self.candidate_executables(hardware):
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def installer_snapshot(
        self,
        *,
        settings: dict[str, Any],
        hardware: dict[str, Any],
        live_version: str | None,
    ) -> dict[str, Any]:
        executable = self.discover_executable(hardware)
        snapshot: dict[str, Any] = {
            "strategy_code": f"local_companion_{hardware['host_platform']}",
            "strategy_label": "Companion locale sul dispositivo del cliente",
            "platform": hardware["host_platform"],
            "machine": hardware["host_machine"],
            "execution_platform": hardware["host_platform"],
            "execution_machine": hardware["host_machine"],
            "host_platform": hardware["host_platform"],
            "host_machine": hardware["host_machine"],
            "containerized": False,
            "automatic_install_supported": hardware["host_platform"] in {"windows", "linux"},
            "managed_runtime_dir": str(self.runtime_root),
            "download_cache_dir": str(self.download_root),
            "detected_executable": str(executable) if executable else "",
            "candidate_paths": [str(path) for path in self.candidate_executables(hardware)],
            "distribution_scope": (
                "Quando IUSENTRA e' online, il browser parla con il Local Signer sul dispositivo cliente. "
                "Il companion locale avvia Ollama sulla stessa macchina e non distribuisce alcun runtime al browser."
            ),
            "asset_name": "",
            "asset_download_url": "",
            "asset_size_bytes": None,
            "asset_updated_at": "",
            "latest_version": "",
            "latest_release_url": "",
            "latest_published_at": "",
            "post_install_note": "",
        }

        try:
            release = self.fetch_latest_release()
            asset = self._select_download_asset(release, hardware, purpose="installer")
            snapshot.update(
                {
                    "latest_version": release.get("version") or "",
                    "latest_release_url": release.get("html_url") or "",
                    "latest_published_at": release.get("published_at") or "",
                    "asset_name": asset.get("name") if asset else "",
                    "asset_download_url": asset.get("browser_download_url") if asset else "",
                    "asset_size_bytes": asset.get("size") if asset else None,
                    "asset_updated_at": asset.get("updated_at") if asset else "",
                    "asset_label": "Installer consigliato" if hardware["host_platform"] == "windows" else "Pacchetto consigliato",
                    "asset_cta_label": "Scarica installer ufficiale" if hardware["host_platform"] == "windows" else "Apri il download ufficiale",
                    "post_install_note": (
                        "Dopo l'installazione il companion locale prepara automaticamente il modello operativo "
                        "piu' adatto al profilo hardware del dispositivo e il modello embeddings consigliato."
                    ),
                }
            )
        except Exception as exc:
            snapshot["release_error"] = str(exc)

        if live_version:
            snapshot["summary_title"] = "Runtime locale operativo"
            snapshot["summary_body"] = (
                "Il companion locale ha raggiunto Ollama sul dispositivo cliente. "
                "IUSENTRA online continua a usare il browser come ponte verso il servizio locale."
            )
        elif hardware["host_platform"] == "windows":
            snapshot["summary_title"] = "Provisioning automatico sul dispositivo Windows"
            snapshot["summary_body"] = (
                "Sul PC Windows del cliente il percorso consigliato e' installare Ollama con l'installer ufficiale. "
                "Dopo l'installazione IUSENTRA rileva automaticamente il runtime locale, scarica il modello operativo giusto "
                "per il profilo hardware e collega la web app ai modelli tramite localhost."
            )
        else:
            snapshot["summary_title"] = "Installazione guidata sul dispositivo locale"
            snapshot["summary_body"] = (
                "Su questo sistema il companion locale verifica Ollama sul dispositivo cliente. "
                "Se il runtime non e' gia' presente, IUSENTRA mostra la procedura corretta senza bloccare il gestionale."
            )
        return snapshot

    def _download_asset(self, asset: dict[str, Any], *, force_download: bool = False) -> Path:
        asset_name = str(asset.get("name") or "").strip()
        download_url = str(asset.get("browser_download_url") or "").strip()
        if not asset_name or not download_url:
            raise RuntimeError("Asset Ollama non valido per il download automatico.")
        target = self.download_root / asset_name
        expected_size = int(asset.get("size") or 0)
        if target.exists() and not force_download:
            if expected_size <= 0 or target.stat().st_size == expected_size:
                return target

        request = urllib.request.Request(
            download_url,
            headers={"User-Agent": "IUSENTRA-Local-AI-Bridge/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as stream:
            while True:
                chunk = response.read(1024 * 512)
                if not chunk:
                    break
                stream.write(chunk)
        return target

    def _extract_windows_archive(self, archive_path: Path, hardware: dict[str, Any]) -> Path:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(self.runtime_root)
        executable = self.discover_executable(hardware)
        if not executable:
            raise RuntimeError("Archivio Ollama estratto ma eseguibile non trovato.")
        return executable

    def _extract_linux_archive(self, archive_path: Path, hardware: dict[str, Any]) -> Path:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(self.runtime_root)
        executable = self.discover_executable(hardware)
        if not executable:
            raise RuntimeError("Archivio Ollama estratto ma eseguibile non trovato.")
        return executable

    def _ensure_runtime_binary(self, *, hardware: dict[str, Any], force_download: bool = False) -> Path:
        detected = self.discover_executable(hardware)
        if detected and not force_download:
            return detected

        if hardware["host_platform"] not in {"windows", "linux"}:
            raise RuntimeError("Installazione automatica disponibile al momento solo su Windows o Linux.")

        release = self.fetch_latest_release(force_refresh=force_download)
        asset = self._select_download_asset(release, hardware, purpose="runtime")
        if not asset:
            raise RuntimeError("Pacchetto ufficiale Ollama non disponibile per questo sistema.")
        archive_path = self._download_asset(asset, force_download=force_download)
        if hardware["host_platform"] == "windows":
            return self._extract_windows_archive(archive_path, hardware)
        return self._extract_linux_archive(archive_path, hardware)

    def _start_runtime(self, executable: Path) -> None:
        env = dict(os.environ)
        env["OLLAMA_MODELS"] = str(self.models_path)
        env["OLLAMA_HOST"] = "127.0.0.1:11434"
        kwargs: dict[str, Any] = {
            "args": [str(executable), "serve"],
            "env": env,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
            "cwd": str(executable.parent),
            "start_new_session": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = 0x00000008 | 0x08000000
        subprocess.Popen(**kwargs)

    def _wait_for_runtime(self, client: OllamaLocalClient) -> str:
        timeout_ms = int(DEFAULT_POLICY["ollama"]["startupTimeoutMs"])
        poll_ms = int(DEFAULT_POLICY["ollama"]["healthPollIntervalMs"])
        started = time.time()
        while (time.time() - started) * 1000 < timeout_ms:
            version = client.get_version()
            if version:
                return version
            time.sleep(poll_ms / 1000.0)
        raise RuntimeError("Timeout durante l'avvio del runtime Ollama locale.")

    def _ensure_models(self, client: OllamaLocalClient, resolved_models: dict[str, Any], keep_alive: str) -> None:
        version = client.get_version()
        if not version:
            raise RuntimeError("Ollama non disponibile durante la preparazione dei modelli.")
        embed_model = str(resolved_models["embed"] or "")
        if embed_model.startswith("embeddinggemma"):
            minimum = DEFAULT_POLICY["ollama"]["minVersionForEmbeddingGemma"]
            if _compare_versions(version, minimum) < 0:
                raise RuntimeError(f"embeddinggemma richiede Ollama >= {minimum}, trovato {version}.")

        installed = client.list_models()
        installed_names = {str(row.get("name") or "").strip() for row in installed}
        for model_name in (resolved_models["chat"], resolved_models["embed"]):
            if model_name not in installed_names:
                client.pull_model(model_name)
                installed_names.add(model_name)
        client.warmup_model(resolved_models["chat"], keep_alive)
        embed_result = client.embed_texts(resolved_models["embed"], ["test"])
        embeddings = embed_result.get("embeddings") or []
        if not embeddings or not isinstance(embeddings[0], list):
            raise RuntimeError("Embedding di test non disponibile dopo il bootstrap.")

    def _model_rows(
        self,
        *,
        installed_models: list[dict[str, Any]],
        resolved_models: dict[str, Any],
        verified_at: str,
    ) -> list[dict[str, Any]]:
        installed_map = {
            str(row.get("name") or "").strip(): row
            for row in installed_models
            if str(row.get("name") or "").strip()
        }
        rows: list[dict[str, Any]] = []
        for role, model_name in (("chat", resolved_models["chat"]), ("embed", resolved_models["embed"])):
            current = installed_map.get(model_name) or {}
            preferred_key = "preferred_chat" if role == "chat" else "preferred_embed"
            note_parts = [f"hardware_profile={resolved_models['profile']}"]
            preferred_model = str(resolved_models.get(preferred_key) or "").strip()
            if preferred_model and preferred_model != model_name:
                note_parts.append(f"preferred_model={preferred_model}")
            rows.append(
                {
                    "id": f"{role}:{model_name}",
                    "role": role,
                    "model_name": model_name,
                    "install_state": "ready" if model_name in installed_map else "missing",
                    "size_bytes": current.get("size"),
                    "context_window": None,
                    "is_active": 1,
                    "last_verified_at": verified_at,
                    "notes": " ".join(note_parts),
                }
            )
        return rows

    def health_snapshot(self, overrides: dict[str, Any] | None = None, *, last_error: str | None = None) -> dict[str, Any]:
        settings = self._settings(overrides)
        hardware = self.detect_hardware()
        client = OllamaLocalClient(settings["base_url"])
        verified_at = _now_iso()
        version = client.get_version() if settings["enabled"] else None
        runtime_error = ""
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
        elif settings["enabled"]:
            runtime_error = last_error or "Ollama non raggiungibile"

        resolved_models = self.resolve_effective_models(
            settings,
            hardware,
            installed_models=installed_models,
            running_models=running_models,
        )

        runtime_status = "disabled" if not settings["enabled"] else ("ready" if version else ("error" if last_error else "missing"))
        installer = self.installer_snapshot(settings=settings, hardware=hardware, live_version=version)

        return {
            "ok": True,
            "settings": settings,
            "runtime": {
                "id": 1,
                "status": runtime_status,
                "api_base_url": settings["base_url"],
                "ollama_version": version or "",
                "install_path": str(self.discover_executable(hardware) or ""),
                "models_path": str(self.models_path),
                "hardware_profile": hardware["profile"],
                "os_version": hardware["os_version"],
                "ram_gb": hardware["ram_gb"],
                "disk_free_gb": hardware["disk_free_gb"],
                "cpu_name": hardware["cpu_name"],
                "gpu_vendor": hardware["gpu_vendor"],
                "gpu_name": hardware["gpu_name"],
                "last_health_check_at": verified_at,
                "last_error": runtime_error or last_error or "",
                "created_at": verified_at,
                "updated_at": verified_at,
            },
            "runtime_online": bool(version),
            "runtime_version_live": version or "",
            "runtime_base_url_live": settings["base_url"] if version else "",
            "models": self._model_rows(
                installed_models=installed_models,
                resolved_models=resolved_models,
                verified_at=verified_at,
            ),
            "running_models": running_models,
            "preferred_models": {
                "chat": resolved_models.get("preferred_chat") or "",
                "embed": resolved_models.get("preferred_embed") or "",
            },
            "resolved_models": {
                "chat": resolved_models["chat"],
                "embed": resolved_models["embed"],
            },
            "installer": installer,
            "counts": {
                "documents_total": 0,
                "chunks_total": 0,
                "chunks_embedded": 0,
                "chunks_pending": 0,
            },
            "models_path": str(self.models_path),
        }

    def bootstrap_runtime(self, overrides: dict[str, Any] | None = None, *, force: bool = False) -> dict[str, Any]:
        settings = self._settings(overrides)
        if not settings["enabled"]:
            payload = self.health_snapshot(settings)
            return {
                "ok": True,
                "result": {
                    "status": "disabled",
                    "error": "",
                    "version": "",
                },
                "status_payload": payload,
            }

        hardware = self.detect_hardware()
        preferred_models = self.resolve_models(settings, hardware)
        client = OllamaLocalClient(settings["base_url"])
        version = client.get_version()

        try:
            if not version:
                executable = self._ensure_runtime_binary(hardware=hardware, force_download=force)
                self._start_runtime(executable)
                version = self._wait_for_runtime(client)
            self._ensure_models(client, preferred_models, settings["keep_alive"])
        except Exception as exc:
            payload = self.health_snapshot(settings, last_error=str(exc))
            payload["runtime"]["status"] = "error"
            payload["runtime"]["last_error"] = str(exc)
            return {
                "ok": True,
                "result": {
                    "status": "error",
                    "error": str(exc),
                    "version": version or "",
                },
                "status_payload": payload,
            }

        payload = self.health_snapshot(settings)
        return {
            "ok": True,
            "result": {
                "status": "ready",
                "error": "",
                "version": version or "",
                "chat_model": payload.get("resolved_models", {}).get("chat") or preferred_models["chat"],
                "embed_model": payload.get("resolved_models", {}).get("embed") or preferred_models["embed"],
            },
            "status_payload": payload,
        }

    def chat(self, prompt: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = self._settings(overrides)
        hardware = self.detect_hardware()
        client = OllamaLocalClient(settings["base_url"])
        _version, installed_models, running_models = self._runtime_inventory(client, enabled=settings["enabled"])
        model_name = self._resolved_chat_model(
            settings=settings,
            hardware=hardware,
            installed_models=installed_models,
            running_models=running_models,
            requested_model=str((overrides or {}).get("model") or "").strip(),
        )
        payload = client.generate(model_name, prompt, settings["keep_alive"])
        return {
            "ok": True,
            "model": model_name,
            "response": str(payload.get("response") or "").strip(),
            "created_at": _now_iso(),
        }

    def chat_stream(self, prompt: str, overrides: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        settings = self._settings(overrides)
        hardware = self.detect_hardware()
        client = OllamaLocalClient(settings["base_url"])
        _version, installed_models, running_models = self._runtime_inventory(client, enabled=settings["enabled"])
        model_name = self._resolved_chat_model(
            settings=settings,
            hardware=hardware,
            installed_models=installed_models,
            running_models=running_models,
            requested_model=str((overrides or {}).get("model") or "").strip(),
        )
        full_parts: list[str] = []
        for event in client.generate_stream(model_name, prompt, settings["keep_alive"]):
            token = str(event.get("response") or "")
            if token:
                full_parts.append(token)
                yield {"token": token, "model": model_name}
            if event.get("done"):
                yield {
                    "done": True,
                    "model": model_name,
                    "answer": "".join(full_parts).strip(),
                    "created_at": _now_iso(),
                    "load_duration": event.get("load_duration"),
                    "prompt_eval_count": event.get("prompt_eval_count"),
                    "eval_count": event.get("eval_count"),
                }
                return

    def _rag_prompt(self, *, question: str, prompt: str, sources: list[dict[str, Any]]) -> str:
        provided = str(prompt or "").strip()
        if provided:
            return provided
        context = "\n\n---\n\n".join(
            f"[Fonte {index + 1}] {str(source.get('citation') or source.get('title') or 'Documento').strip()}\n"
            f"{str(source.get('text') or '').strip()}"
            for index, source in enumerate(sources)
            if str(source.get("text") or "").strip()
        ) or "Nessuna fonte documentale disponibile."
        return "\n".join(
            [
                "Sei l'assistente operativo locale di IUSENTRA.",
                "Rispondi usando solo il contesto fornito.",
                "Se il contesto e' insufficiente, dichiaralo in modo esplicito.",
                "",
                f"Domanda: {question.strip()}",
                "",
                "Contesto documentale:",
                context,
                "",
                "Chiudi con una sezione 'Fonti' che elenchi solo i riferimenti effettivamente usati.",
            ]
        )

    def rag_query(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        overrides = dict(payload or {})
        settings = self._settings(overrides)
        hardware = self.detect_hardware()
        question = str(overrides.get("question") or "").strip()
        sources = list(overrides.get("sources") or [])
        prompt = self._rag_prompt(question=question, prompt=str(overrides.get("prompt") or ""), sources=sources)
        client = OllamaLocalClient(settings["base_url"])
        _version, installed_models, running_models = self._runtime_inventory(client, enabled=settings["enabled"])
        model_name = self._resolved_chat_model(
            settings=settings,
            hardware=hardware,
            installed_models=installed_models,
            running_models=running_models,
            requested_model=str(overrides.get("model") or "").strip(),
        )
        response = client.generate(model_name, prompt, settings["keep_alive"])
        citations = [str(item.get("citation") or "").strip() for item in sources if str(item.get("citation") or "").strip()]
        return {
            "ok": True,
            "model": model_name,
            "question": question,
            "answer": str(response.get("response") or "").strip(),
            "sources": sources,
            "citations": citations,
            "created_at": _now_iso(),
            "load_duration": response.get("load_duration"),
            "prompt_eval_count": response.get("prompt_eval_count"),
            "eval_count": response.get("eval_count"),
        }

    def rag_query_stream(self, payload: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        overrides = dict(payload or {})
        settings = self._settings(overrides)
        hardware = self.detect_hardware()
        question = str(overrides.get("question") or "").strip()
        sources = list(overrides.get("sources") or [])
        citations = [str(item.get("citation") or "").strip() for item in sources if str(item.get("citation") or "").strip()]
        prompt = self._rag_prompt(question=question, prompt=str(overrides.get("prompt") or ""), sources=sources)
        client = OllamaLocalClient(settings["base_url"])
        _version, installed_models, running_models = self._runtime_inventory(client, enabled=settings["enabled"])
        model_name = self._resolved_chat_model(
            settings=settings,
            hardware=hardware,
            installed_models=installed_models,
            running_models=running_models,
            requested_model=str(overrides.get("model") or "").strip(),
        )
        full_parts: list[str] = []
        for event in client.generate_stream(model_name, prompt, settings["keep_alive"]):
            token = str(event.get("response") or "")
            if token:
                full_parts.append(token)
                yield {"token": token, "model": model_name}
            if event.get("done"):
                yield {
                    "done": True,
                    "model": model_name,
                    "question": question,
                    "answer": "".join(full_parts).strip(),
                    "sources": sources,
                    "citations": citations,
                    "created_at": _now_iso(),
                    "load_duration": event.get("load_duration"),
                    "prompt_eval_count": event.get("prompt_eval_count"),
                    "eval_count": event.get("eval_count"),
                }
                return

    def embed(self, inputs: list[str], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = self._settings(overrides)
        hardware = self.detect_hardware()
        client = OllamaLocalClient(settings["base_url"])
        version = client.get_version() if settings["enabled"] else None
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
        effective_settings = dict(settings)
        if str((overrides or {}).get("model") or "").strip():
            effective_settings["embed_model"] = str((overrides or {}).get("model") or "").strip()
        resolved_models = self.resolve_effective_models(
            effective_settings,
            hardware,
            installed_models=installed_models,
            running_models=running_models,
        )
        model_name = str(resolved_models["embed"]).strip()
        payload = client.embed_texts(model_name, inputs)
        return {
            "ok": True,
            "model": model_name,
            "embeddings": payload.get("embeddings") or [],
            "total_duration": payload.get("total_duration"),
            "load_duration": payload.get("load_duration"),
            "prompt_eval_count": payload.get("prompt_eval_count"),
            "created_at": _now_iso(),
        }
