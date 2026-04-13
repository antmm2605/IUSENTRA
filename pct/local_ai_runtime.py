from __future__ import annotations

import json
import os
import platform
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import requests


class OllamaRuntimeProvisioner:
    """Gestisce rilevamento e provisioning del runtime Ollama sullo stesso host di HACS."""

    _LATEST_RELEASE_URL = "https://api.github.com/repos/ollama/ollama/releases/latest"

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
        self.platform_name = (platform_name or self._detect_platform_name()).lower()
        self.machine_name = (machine_name or platform.machine() or "unknown").lower()
        self.runtime_root = self.models_path.parent / "runtime" / "ollama"
        self.legacy_runtime_root = self.app_root / "tools" / "ollama"
        self.cache_root = self.models_path.parent / "downloads" / "ollama"
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.release_cache_path = self.cache_root / "latest-release.json"

    def candidate_executables(self) -> list[Path]:
        suffix = "ollama.exe" if self.platform_name == "windows" else "ollama"
        candidates: list[Path] = []
        roots = [self.runtime_root, self.legacy_runtime_root]
        for root in roots:
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
        self.release_cache_path.write_text(json.dumps(curated, ensure_ascii=False, indent=2), encoding="utf-8")
        return curated

    def select_download_asset(self, release: dict[str, Any]) -> dict[str, Any] | None:
        assets = release.get("assets") or []
        preferred_names: list[str] = []
        if self.platform_name == "windows":
            if "arm" in self.machine_name:
                preferred_names = ["ollama-windows-arm64.zip"]
            else:
                preferred_names = ["ollama-windows-amd64.zip"]
        elif self.platform_name == "linux":
            if "arm" in self.machine_name:
                preferred_names = ["ollama-linux-arm64.tar.zst"]
            else:
                preferred_names = ["ollama-linux-amd64.tar.zst"]
        for asset_name in preferred_names:
            for asset in assets:
                if asset.get("name") == asset_name:
                    return asset
        return None

    def installer_snapshot(self, *, live_version: str | None = None) -> dict[str, Any]:
        executable = self.discover_executable()
        snapshot: dict[str, Any] = {
            "platform": self.platform_name,
            "machine": self.machine_name,
            "automatic_install_supported": self.platform_name == "windows",
            "managed_runtime_dir": str(self.runtime_root),
            "download_cache_dir": str(self.cache_root),
            "detected_executable": str(executable) if executable else "",
            "candidate_paths": [str(path) for path in self.candidate_executables()],
            "distribution_scope": "Il runtime AI viene gestito sulla stessa macchina che esegue HACS e non viene distribuito al browser del cliente.",
            "strategy_code": "host_managed_windows" if self.platform_name == "windows" else "host_guided_install",
            "strategy_label": "Runtime locale gestito sullo stesso host di HACS" if self.platform_name == "windows" else "Runtime locale guidato sullo stesso host di HACS",
        }

        try:
            release = self.fetch_latest_release()
            asset = self.select_download_asset(release)
            snapshot.update(
                {
                    "latest_version": release.get("version") or "",
                    "latest_release_url": release.get("html_url") or "",
                    "latest_published_at": release.get("published_at") or "",
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
                    "download_supported": False,
                    "release_error": str(exc),
                    "latest_version": "",
                    "latest_release_url": "",
                    "latest_published_at": "",
                    "asset_name": "",
                    "asset_download_url": "",
                    "asset_size_bytes": None,
                    "asset_updated_at": "",
                }
            )

        if live_version:
            snapshot["summary_title"] = "Runtime locale operativo"
            snapshot["summary_body"] = (
                "Ollama è già raggiungibile sullo stesso host di HACS. "
                "I browser degli utenti non eseguono alcun runtime AI locale."
            )
        elif executable:
            snapshot["summary_title"] = "Runtime locale rilevato"
            snapshot["summary_body"] = (
                "HACS ha trovato un eseguibile Ollama sulla macchina corrente. "
                "È possibile avviarlo automaticamente dal bootstrap del pannello AI."
            )
        elif self.platform_name == "windows":
            snapshot["summary_title"] = "Provisioning automatico disponibile"
            snapshot["summary_body"] = (
                "La strategia consigliata è installare Ollama sulla stessa macchina Windows che ospita HACS. "
                "Se il runtime non è presente, il bootstrap può scaricare il pacchetto standalone ufficiale e prepararlo in automatico."
            )
        else:
            snapshot["summary_title"] = "Installazione guidata sullo stesso host"
            snapshot["summary_body"] = (
                "Su questo host HACS non distribuisce il runtime AI al browser del cliente. "
                "La soluzione corretta è installare Ollama sulla stessa macchina o sullo stesso server che esegue HACS, poi lasciare al pannello AI il bootstrap di modelli e indice."
            )
        return snapshot

    def ensure_windows_runtime(self, *, force_download: bool = False) -> Path:
        if self.platform_name != "windows":
            raise RuntimeError(
                "Il provisioning automatico del runtime Ollama è supportato solo su Windows sullo stesso host di HACS."
            )

        detected = self.discover_executable()
        if detected and not force_download:
            return detected

        release = self.fetch_latest_release(force_refresh=force_download)
        asset = self.select_download_asset(release)
        if not asset or not asset.get("browser_download_url"):
            raise RuntimeError(
                "Pacchetto standalone ufficiale per Windows non disponibile nella release corrente di Ollama."
            )

        archive_path = self._download_asset(asset, force_download=force_download)
        return self._extract_windows_archive(archive_path)

    def _download_asset(self, asset: dict[str, Any], *, force_download: bool = False) -> Path:
        asset_name = str(asset.get("name") or "").strip()
        download_url = str(asset.get("browser_download_url") or "").strip()
        if not asset_name or not download_url:
            raise RuntimeError("Asset Ollama non valido per il download automatico.")

        target = self.cache_root / asset_name
        expected_size = int(asset.get("size") or 0)
        if (
            target.exists()
            and not force_download
            and (expected_size <= 0 or target.stat().st_size == expected_size)
        ):
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
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        extract_root = self.cache_root / "_extract"
        if extract_root.exists():
            shutil.rmtree(extract_root, ignore_errors=True)
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(extract_root)

        executable = next((path for path in extract_root.rglob("ollama.exe") if path.is_file()), None)
        if executable is None:
            raise RuntimeError("Il pacchetto Ollama scaricato non contiene ollama.exe.")

        source_root = executable.parent
        shutil.copytree(source_root, self.runtime_root, dirs_exist_ok=True)
        shutil.rmtree(extract_root, ignore_errors=True)
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

    def _detect_platform_name(self) -> str:
        if os.name == "nt":
            return "windows"
        system = platform.system().lower()
        return system or "unknown"
