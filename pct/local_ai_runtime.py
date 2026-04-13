from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Any

import requests


class OllamaRuntimeProvisioner:
    """Gestisce il runtime Ollama sulla stessa macchina che esegue HACS."""

    _LATEST_RELEASE_URL = "https://api.github.com/repos/ollama/ollama/releases/latest"
    _DOCKER_IMAGE_NAME = "ollama/ollama:latest"
    _DOCKER_IMAGE_URL = "https://hub.docker.com/r/ollama/ollama"

    def __init__(
        self,
        app_root: str | Path,
        models_path: str | Path,
        *,
        platform_name: str | None = None,
        machine_name: str | None = None,
    ) -> None:
        self.app_root = Path(app_root).resolve()
        self.models_path = Path(models_path).resolve()
        self.execution_platform_name = self._normalize_platform_name(self._detect_execution_platform_name())
        self.execution_machine_name = self._normalize_machine_name(platform.machine() or "unknown")
        self.host_platform_name = self._normalize_platform_name(
            platform_name or os.getenv("PCT_HOST_PLATFORM") or self.execution_platform_name
        )
        self.host_machine_name = self._normalize_machine_name(
            machine_name or os.getenv("PCT_HOST_MACHINE") or self.execution_machine_name
        )
        self.containerized = self._detect_containerized()
        self.runtime_root = self.models_path.parent / "runtime" / "ollama"
        self.legacy_runtime_root = self.app_root / "tools" / "ollama"
        self.cache_root = self.models_path.parent / "downloads" / "ollama"
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.release_cache_path = self.cache_root / "latest-release.json"

    def candidate_executables(self) -> list[Path]:
        suffix = "ollama.exe" if self.host_platform_name == "windows" else "ollama"
        candidates: list[Path] = []
        for root in (self.runtime_root, self.legacy_runtime_root):
            direct = root / suffix
            if direct not in candidates:
                candidates.append(direct)
            if root.exists():
                for match in sorted(root.rglob(suffix)):
                    if match not in candidates:
                        candidates.append(match)
        which_path = shutil.which("ollama")
        if which_path:
            resolved = Path(which_path).resolve()
            if resolved not in candidates:
                candidates.append(resolved)
        return candidates

    def discover_executable(self) -> Path | None:
        for candidate in self.candidate_executables():
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def fetch_latest_release(
        self,
        *,
        force_refresh: bool = False,
        max_age_seconds: int = 6 * 60 * 60,
    ) -> dict[str, Any]:
        cached = self._load_cached_release()
        if cached and not force_refresh:
            fetched_at = float(cached.get("fetched_at_epoch") or 0)
            if time.time() - fetched_at <= max_age_seconds:
                return cached

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "HACS-Local-AI/1.0",
        }
        try:
            response = requests.get(self._LATEST_RELEASE_URL, headers=headers, timeout=20)
            response.raise_for_status()
            payload = response.json()
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
        self.release_cache_path.write_text(
            json.dumps(curated, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return curated

    def select_download_asset(
        self,
        release: dict[str, Any],
        *,
        platform_name: str | None = None,
        machine_name: str | None = None,
    ) -> dict[str, Any] | None:
        assets = release.get("assets") or []
        target_platform = self._normalize_platform_name(platform_name or self.host_platform_name)
        target_machine = self._normalize_machine_name(machine_name or self.host_machine_name)
        preferred_names: list[str] = []

        if target_platform == "windows":
            preferred_names = ["ollama-windows-arm64.zip"] if target_machine == "arm64" else ["ollama-windows-amd64.zip"]
        elif target_platform == "linux":
            if target_machine == "arm64":
                preferred_names = ["ollama-linux-arm64.tar.zst", "ollama-linux-arm64.tgz"]
            else:
                preferred_names = ["ollama-linux-amd64.tar.zst", "ollama-linux-amd64.tgz"]

        for asset_name in preferred_names:
            for asset in assets:
                if asset.get("name") == asset_name:
                    return asset
        return None

    def strategy_code(self) -> str:
        if self.containerized:
            if self.host_platform_name == "windows":
                return "host_bridge_windows"
            if self.host_platform_name == "darwin":
                return "host_bridge_darwin"
            return "docker_service"
        if self.host_platform_name == "windows":
            return "host_managed_windows"
        if self.host_platform_name == "linux":
            return "host_managed_linux"
        return "host_guided_install"

    def automatic_install_supported(self) -> bool:
        return self.strategy_code() in {
            "host_managed_windows",
            "host_managed_linux",
        }

    def installer_snapshot(self, *, live_version: str | None = None) -> dict[str, Any]:
        strategy = self.strategy_code()
        executable = self.discover_executable()
        snapshot: dict[str, Any] = {
            "platform": self.host_platform_name,
            "machine": self.host_machine_name,
            "execution_platform": self.execution_platform_name,
            "execution_machine": self.execution_machine_name,
            "host_platform": self.host_platform_name,
            "host_machine": self.host_machine_name,
            "containerized": self.containerized,
            "automatic_install_supported": self.automatic_install_supported(),
            "managed_runtime_dir": str(self.runtime_root),
            "download_cache_dir": str(self.cache_root),
            "detected_executable": str(executable) if executable else "",
            "candidate_paths": [str(path) for path in self.candidate_executables()],
            "distribution_scope": "Il runtime AI viene gestito sulla stessa macchina che esegue HACS e non viene distribuito al browser del cliente.",
            "strategy_code": strategy,
        }

        if strategy == "docker_service":
            snapshot.update(
                {
                    "strategy_label": "Servizio Ollama Docker sulla stessa macchina di HACS",
                    "asset_name": self._DOCKER_IMAGE_NAME,
                    "asset_download_url": self._DOCKER_IMAGE_URL,
                    "asset_size_bytes": None,
                    "asset_updated_at": "",
                    "download_supported": True,
                }
            )
        elif strategy == "host_bridge_windows":
            snapshot["strategy_label"] = "Runtime Ollama Windows sull'host collegato al container HACS"
        elif strategy == "host_bridge_darwin":
            snapshot["strategy_label"] = "Runtime Ollama macOS sull'host collegato al container HACS"
        elif strategy == "host_managed_windows":
            snapshot["strategy_label"] = "Runtime locale gestito sullo stesso host Windows di HACS"
        elif strategy == "host_managed_linux":
            snapshot["strategy_label"] = "Runtime locale gestito sullo stesso host Linux di HACS"
        else:
            snapshot["strategy_label"] = "Runtime locale guidato sullo stesso host di HACS"

        try:
            release = self.fetch_latest_release()
            snapshot.update(
                {
                    "latest_version": release.get("version") or "",
                    "latest_release_url": release.get("html_url") or "",
                    "latest_published_at": release.get("published_at") or "",
                }
            )
            if strategy in {"host_managed_windows", "host_bridge_windows"}:
                asset = self.select_download_asset(release, platform_name="windows", machine_name=self.host_machine_name)
                snapshot.update(
                    {
                        "download_supported": bool(asset and asset.get("browser_download_url")),
                        "asset_name": asset.get("name") if asset else "",
                        "asset_download_url": asset.get("browser_download_url") if asset else "",
                        "asset_size_bytes": asset.get("size") if asset else None,
                        "asset_updated_at": asset.get("updated_at") if asset else "",
                    }
                )
            elif strategy == "host_managed_linux":
                asset = self.select_download_asset(release, platform_name="linux", machine_name=self.host_machine_name)
                snapshot.update(
                    {
                        "download_supported": bool(asset and asset.get("browser_download_url")),
                        "asset_name": asset.get("name") if asset else "",
                        "asset_download_url": asset.get("browser_download_url") if asset else "",
                        "asset_size_bytes": asset.get("size") if asset else None,
                        "asset_updated_at": asset.get("updated_at") if asset else "",
                    }
                )
        except Exception as exc:
            snapshot.update(
                {
                    "download_supported": snapshot.get("download_supported", False),
                    "release_error": str(exc),
                    "latest_version": "",
                    "latest_release_url": "",
                    "latest_published_at": "",
                }
            )

        if live_version:
            snapshot["summary_title"] = "Runtime locale operativo"
            snapshot["summary_body"] = (
                "Ollama e' gia' raggiungibile sulla stessa macchina che esegue HACS. "
                "Il browser del cliente finale non esegue alcun runtime AI."
            )
        elif executable:
            snapshot["summary_title"] = "Runtime locale rilevato"
            snapshot["summary_body"] = (
                "HACS ha trovato un eseguibile Ollama sulla macchina corrente e puo' usarlo "
                "nel bootstrap del pannello AI."
            )
        elif strategy == "docker_service":
            snapshot["summary_title"] = "Provisioning automatico via Docker"
            snapshot["summary_body"] = (
                "HACS sta girando in un container Linux su host Linux. La strategia corretta non e' installare "
                "un binario nel browser, ma usare il servizio Docker "
                "ufficiale Ollama sulla stessa macchina che ospita HACS."
            )
        elif strategy == "host_bridge_windows":
            snapshot["summary_title"] = "Host Windows rilevato"
            snapshot["summary_body"] = (
                "HACS gira in un container, ma l'host reale e' Windows. La strategia corretta e' usare "
                "Ollama Windows sull'host e collegare il container a quell'istanza tramite host.docker.internal."
            )
        elif strategy == "host_bridge_darwin":
            snapshot["summary_title"] = "Host macOS rilevato"
            snapshot["summary_body"] = (
                "HACS gira in un container, ma l'host reale e' macOS. La strategia corretta e' usare "
                "Ollama sull'host e collegare il container a quell'istanza tramite host.docker.internal."
            )
        elif strategy == "host_managed_windows":
            snapshot["summary_title"] = "Provisioning automatico su Windows"
            snapshot["summary_body"] = (
                "La strategia corretta e' installare Ollama sulla stessa macchina Windows che esegue HACS. "
                "Se il runtime non e' presente, il bootstrap puo' scaricare il pacchetto ufficiale e "
                "prepararlo in automatico."
            )
        elif strategy == "host_managed_linux":
            snapshot["summary_title"] = "Provisioning automatico su Linux"
            snapshot["summary_body"] = (
                "La strategia corretta e' installare Ollama sulla stessa macchina Linux che esegue HACS. "
                "Se il runtime non e' presente, il bootstrap puo' scaricare il pacchetto ufficiale e "
                "prepararlo in automatico."
            )
        else:
            snapshot["summary_title"] = "Installazione guidata sullo stesso host"
            snapshot["summary_body"] = (
                "Su questo host HACS continua a funzionare anche senza AI locale. "
                "Quando possibile va comunque usato un runtime Ollama sulla stessa macchina di HACS."
            )
        return snapshot

    def ensure_runtime(self, *, force_download: bool = False) -> Path:
        strategy = self.strategy_code()
        if strategy == "host_managed_windows":
            return self.ensure_windows_runtime(force_download=force_download)
        if strategy == "host_managed_linux":
            return self.ensure_linux_runtime(force_download=force_download)
        raise RuntimeError(
            "In ambiente containerizzato la strategia corretta e' usare il servizio Docker 'ollama' "
            "sulla stessa macchina di HACS."
        )

    def ensure_windows_runtime(self, *, force_download: bool = False) -> Path:
        if self.host_platform_name != "windows":
            raise RuntimeError("Il provisioning automatico Windows richiede un host Windows reale.")

        detected = self.discover_executable()
        if detected and not force_download:
            return detected

        release = self.fetch_latest_release(force_refresh=force_download)
        asset = self.select_download_asset(release, platform_name="windows", machine_name=self.host_machine_name)
        if not asset or not asset.get("browser_download_url"):
            raise RuntimeError("Pacchetto standalone ufficiale per Windows non disponibile nella release corrente di Ollama.")

        archive_path = self._download_asset(asset, force_download=force_download)
        return self._extract_windows_archive(archive_path)

    def ensure_linux_runtime(self, *, force_download: bool = False) -> Path:
        if self.host_platform_name != "linux":
            raise RuntimeError("Il provisioning automatico Linux richiede un host Linux reale.")

        detected = self.discover_executable()
        if detected and not force_download:
            return detected

        release = self.fetch_latest_release(force_refresh=force_download)
        asset = self.select_download_asset(release, platform_name="linux", machine_name=self.host_machine_name)
        if not asset or not asset.get("browser_download_url"):
            raise RuntimeError("Pacchetto ufficiale per Linux non disponibile nella release corrente di Ollama.")

        archive_path = self._download_asset(asset, force_download=force_download)
        return self._extract_linux_archive(archive_path)

    def _download_asset(self, asset: dict[str, Any], *, force_download: bool = False) -> Path:
        asset_name = str(asset.get("name") or "").strip()
        download_url = str(asset.get("browser_download_url") or "").strip()
        if not asset_name or not download_url:
            raise RuntimeError("Asset Ollama non valido per il download automatico.")

        target = self.cache_root / asset_name
        expected_size = int(asset.get("size") or 0)
        if target.exists() and not force_download:
            if expected_size <= 0 or target.stat().st_size == expected_size:
                return target

        headers = {"User-Agent": "HACS-Local-AI/1.0"}
        with requests.get(download_url, headers=headers, timeout=60, stream=True) as response:
            response.raise_for_status()
            with target.open("wb") as stream:
                for chunk in response.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        stream.write(chunk)
        return target

    def _extract_windows_archive(self, archive_path: Path) -> Path:
        extract_root = self._prepare_extract_root()
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(extract_root)
        executable = next((path for path in extract_root.rglob("ollama.exe") if path.is_file()), None)
        if executable is None:
            raise RuntimeError("Il pacchetto Ollama scaricato non contiene ollama.exe.")
        self._sync_extracted_tree(extract_root)
        return self._require_detected_executable()

    def _extract_linux_archive(self, archive_path: Path) -> Path:
        extract_root = self._prepare_extract_root()
        if not self._extract_with_python(archive_path, extract_root):
            self._extract_with_tar_command(archive_path, extract_root)
        executable = next((path for path in extract_root.rglob("ollama") if path.is_file()), None)
        if executable is None:
            raise RuntimeError("Il pacchetto Ollama scaricato non contiene il binario 'ollama'.")
        self._sync_extracted_tree(extract_root)
        detected = self._require_detected_executable()
        try:
            detected.chmod(detected.stat().st_mode | 0o111)
        except Exception:
            pass
        return detected

    def _prepare_extract_root(self) -> Path:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        extract_root = self.cache_root / "_extract"
        if extract_root.exists():
            shutil.rmtree(extract_root, ignore_errors=True)
        extract_root.mkdir(parents=True, exist_ok=True)
        return extract_root

    def _extract_with_python(self, archive_path: Path, extract_root: Path) -> bool:
        try:
            with tarfile.open(archive_path, "r:*") as archive:
                archive.extractall(extract_root)
            return True
        except Exception:
            return False

    def _extract_with_tar_command(self, archive_path: Path, extract_root: Path) -> None:
        cmd = ["tar"]
        if archive_path.name.endswith(".tar.zst"):
            cmd.extend(["--zstd", "-xf", str(archive_path), "-C", str(extract_root)])
        else:
            cmd.extend(["-xf", str(archive_path), "-C", str(extract_root)])
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except Exception as exc:
            raise RuntimeError(
                "Non sono riuscito a estrarre automaticamente il pacchetto Ollama su questo host."
            ) from exc

    def _sync_extracted_tree(self, extract_root: Path) -> None:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        for entry in extract_root.iterdir():
            target = self.runtime_root / entry.name
            if entry.is_dir():
                shutil.copytree(entry, target, dirs_exist_ok=True)
            else:
                shutil.copy2(entry, target)
        shutil.rmtree(extract_root, ignore_errors=True)

    def _require_detected_executable(self) -> Path:
        detected = self.discover_executable()
        if detected is None:
            raise RuntimeError("Runtime Ollama estratto ma non rilevabile nei percorsi gestiti.")
        return detected

    def _load_cached_release(self) -> dict[str, Any] | None:
        if not self.release_cache_path.exists():
            return None
        try:
            return json.loads(self.release_cache_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _detect_execution_platform_name(self) -> str:
        if os.name == "nt":
            return "windows"
        return platform.system().lower() or "unknown"

    def _detect_containerized(self) -> bool:
        if os.path.exists("/.dockerenv"):
            return True
        cgroup_path = Path("/proc/1/cgroup")
        try:
            content = cgroup_path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            return False
        return any(token in content for token in ("docker", "containerd", "kubepods", "podman"))

    def _normalize_platform_name(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        if raw in {"windows", "windows_nt", "win32"}:
            return "windows"
        if raw in {"darwin", "mac", "macos", "osx"}:
            return "darwin"
        if "linux" in raw:
            return "linux"
        return raw or "unknown"

    def _normalize_machine_name(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        if raw in {"amd64", "x86_64", "x64"}:
            return "amd64"
        if raw in {"arm64", "aarch64"}:
            return "arm64"
        return raw or "unknown"
