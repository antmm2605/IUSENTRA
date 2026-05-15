"""Runtime settings for the native Legal Source Engine."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping


GLOBAL_ENABLED_ENV = "IUSENTRA_LEX_AI_LEGAL_SOURCES_ENABLED"
GLOBAL_NETWORK_ENV = "IUSENTRA_LEGAL_SOURCES_ALLOW_NETWORK"
REQUIRE_CITATIONS_ENV = "IUSENTRA_LEGAL_SOURCES_REQUIRE_CITATIONS"
DATA_DIR_ENV = "IUSENTRA_LEGAL_SOURCES_DATA_DIR"
INDEX_DIR_ENV = "IUSENTRA_LEGAL_SOURCES_INDEX_DIR"
ARTIFACT_DIR_ENV = "IUSENTRA_LEGAL_SOURCES_ARTIFACT_DIR"
RATE_LIMIT_ENV = "IUSENTRA_LEGAL_SOURCES_RATE_LIMIT_PER_MINUTE"
AUTO_POPULATE_ENV = "IUSENTRA_LEGAL_SOURCES_AUTO_POPULATE"
POPULATE_ON_STARTUP_ENV = "IUSENTRA_LEGAL_SOURCES_POPULATE_ON_STARTUP"
ENABLE_ALL_SOURCES_ENV = "IUSENTRA_LEGAL_SOURCES_ENABLE_ALL_SOURCES"
RUNTIME_CONFIG_ENV = "IUSENTRA_LEGAL_SOURCES_RUNTIME_CONFIG"

SOURCE_ENV_NAMES = {
    "normattiva": "IUSENTRA_SOURCE_NORMATTIVA_ENABLED",
    "gazzetta_ufficiale": "IUSENTRA_SOURCE_GAZZETTA_UFFICIALE_ENABLED",
    "corte_costituzionale": "IUSENTRA_SOURCE_CORTE_COSTITUZIONALE_ENABLED",
    "cassazione": "IUSENTRA_SOURCE_CASSAZIONE_ENABLED",
    "giustizia_amministrativa": "IUSENTRA_SOURCE_GIUSTIZIA_AMMINISTRATIVA_ENABLED",
    "banca_dati_merito": "IUSENTRA_SOURCE_BANCA_DATI_MERITO_ENABLED",
    "eurlex": "IUSENTRA_SOURCE_EURLEX_ENABLED",
    "hudoc": "IUSENTRA_SOURCE_HUDOC_ENABLED",
    "agenzia_entrate": "IUSENTRA_SOURCE_AGENZIA_ENTRATE_ENABLED",
    "garante_privacy": "IUSENTRA_SOURCE_GARANTE_PRIVACY_ENABLED",
    "anac": "IUSENTRA_SOURCE_ANAC_ENABLED",
    "agcm": "IUSENTRA_SOURCE_AGCM_ENABLED",
    "camera": "IUSENTRA_SOURCE_CAMERA_ENABLED",
    "senato": "IUSENTRA_SOURCE_SENATO_ENABLED",
    "leggi_regionali": "IUSENTRA_SOURCE_LEGGI_REGIONALI_ENABLED",
}


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "si", "on", "enabled"}


def _int_value(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _read_runtime_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload or {}) if isinstance(payload, dict) else {}


@dataclass(frozen=True, slots=True)
class LegalSourceEngineSettings:
    enabled: bool = False
    allow_network: bool = False
    require_citations: bool = True
    data_dir: Path = Path("data/legal_sources")
    index_dir: Path = Path("indexes/legal_sources")
    artifact_dir: Path = Path("artifacts/legal_sources")
    rate_limit_per_minute: int = 30
    auto_populate: bool = False
    populate_on_startup: bool = False
    enable_all_sources: bool = False
    enabled_source_ids: tuple[str, ...] = field(default_factory=tuple)
    runtime_config_path: Path = Path("data/legal_sources/runtime_config.json")

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        include_runtime_config: bool | None = None,
    ) -> "LegalSourceEngineSettings":
        source = os.environ if env is None else env
        read_config = env is None if include_runtime_config is None else include_runtime_config

        default_data_dir = _default_runtime_path(source, "legal_sources", "data/legal_sources")
        default_index_dir = _default_runtime_path(source, "indexes/legal_sources", "indexes/legal_sources")
        default_artifact_dir = _default_runtime_path(source, "artifacts/legal_sources", "artifacts/legal_sources")
        data_dir = Path(str(source.get(DATA_DIR_ENV, default_data_dir) or default_data_dir))
        runtime_config_path = Path(
            str(source.get(RUNTIME_CONFIG_ENV, data_dir / "runtime_config.json") or data_dir / "runtime_config.json")
        )
        config = _read_runtime_config(runtime_config_path) if read_config else {}

        def _bool(env_name: str, config_key: str, default: bool) -> bool:
            if env_name in source:
                return truthy(source.get(env_name))
            if config_key in config:
                return truthy(config.get(config_key))
            return default

        def _path(env_name: str, config_key: str, default: str) -> Path:
            if env_name in source:
                return Path(str(source.get(env_name) or default))
            if config_key in config:
                return Path(str(config.get(config_key) or default))
            return Path(default)

        rate_limit = _int_value(source.get(RATE_LIMIT_ENV), 30)
        if RATE_LIMIT_ENV not in source:
            rate_limit = _int_value(config.get("rate_limit_per_minute"), 30)

        configured_sources = _source_ids_from_config(config)
        enabled_source_ids: set[str] = set(configured_sources)
        for source_id, env_name in SOURCE_ENV_NAMES.items():
            if truthy(source.get(env_name, "")):
                enabled_source_ids.add(source_id)

        enable_all = _bool(ENABLE_ALL_SOURCES_ENV, "enable_all_sources", False)

        return cls(
            enabled=_bool(GLOBAL_ENABLED_ENV, "enabled", False),
            allow_network=_bool(GLOBAL_NETWORK_ENV, "allow_network", False),
            require_citations=_bool(REQUIRE_CITATIONS_ENV, "require_citations", True),
            data_dir=data_dir,
            index_dir=_path(INDEX_DIR_ENV, "index_dir", str(default_index_dir)),
            artifact_dir=_path(ARTIFACT_DIR_ENV, "artifact_dir", str(default_artifact_dir)),
            rate_limit_per_minute=rate_limit,
            auto_populate=_bool(AUTO_POPULATE_ENV, "auto_populate", False),
            populate_on_startup=_bool(POPULATE_ON_STARTUP_ENV, "populate_on_startup", False),
            enable_all_sources=enable_all,
            enabled_source_ids=tuple(sorted(enabled_source_ids)),
            runtime_config_path=runtime_config_path,
        )

    def with_activation(self, source_ids: list[str] | tuple[str, ...]) -> "LegalSourceEngineSettings":
        return replace(
            self,
            enabled=True,
            allow_network=False,
            auto_populate=True,
            populate_on_startup=True,
            enabled_source_ids=tuple(sorted({str(source_id).strip() for source_id in source_ids if str(source_id).strip()})),
        )

    def to_runtime_config(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("data_dir", "index_dir", "artifact_dir", "runtime_config_path"):
            data[key] = str(data[key])
        return data


def _source_ids_from_config(config: Mapping[str, Any]) -> list[str]:
    raw = config.get("enabled_source_ids") or config.get("enabled_sources") or []
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",")]
    if not isinstance(raw, list | tuple | set):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _default_runtime_path(env: Mapping[str, str], suffix: str, fallback: str) -> Path:
    root = str(env.get("PCT_DATA_ROOT") or env.get("IUSENTRA_DATA_DIR") or "").strip()
    if root:
        return Path(root) / suffix
    return Path(fallback)


def save_runtime_config(settings: LegalSourceEngineSettings, path: str | Path | None = None) -> Path:
    target = Path(path or settings.runtime_config_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = settings.to_runtime_config()
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


__all__ = [
    "ARTIFACT_DIR_ENV",
    "AUTO_POPULATE_ENV",
    "DATA_DIR_ENV",
    "ENABLE_ALL_SOURCES_ENV",
    "GLOBAL_ENABLED_ENV",
    "GLOBAL_NETWORK_ENV",
    "INDEX_DIR_ENV",
    "POPULATE_ON_STARTUP_ENV",
    "RATE_LIMIT_ENV",
    "REQUIRE_CITATIONS_ENV",
    "RUNTIME_CONFIG_ENV",
    "SOURCE_ENV_NAMES",
    "LegalSourceEngineSettings",
    "save_runtime_config",
    "truthy",
]
