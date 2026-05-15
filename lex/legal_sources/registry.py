"""Registry for native Legal Source Engine adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .adapters import ADAPTER_CLASSES
from .models import PolicyResult, SourceMetadata, SourceResearchManuscript, SourceScorecard
from .policies import SourcePolicy
from .scorecard import evaluate_scorecard
from .settings import (
    GLOBAL_ENABLED_ENV,
    GLOBAL_NETWORK_ENV,
    SOURCE_ENV_NAMES,
    LegalSourceEngineSettings,
)
from .source_contract import LegalSourceContract


class LegalSourceRegistry:
    def __init__(
        self,
        sources: list[LegalSourceContract] | None = None,
        *,
        env: Mapping[str, str] | None = None,
        settings: LegalSourceEngineSettings | None = None,
    ) -> None:
        self.settings = settings or LegalSourceEngineSettings.from_env(
            env=env,
            include_runtime_config=env is None,
        )
        self._sources: dict[str, LegalSourceContract] = {}
        for source in list(sources or []):
            self.register(source)

    @classmethod
    def default(
        cls,
        *,
        env: Mapping[str, str] | None = None,
        settings: LegalSourceEngineSettings | None = None,
    ) -> "LegalSourceRegistry":
        return cls([adapter_class() for adapter_class in ADAPTER_CLASSES], env=env, settings=settings)

    def register(self, source: LegalSourceContract) -> None:
        self._sources[source.metadata.source_id] = source

    def all_sources(self) -> list[LegalSourceContract]:
        return list(self._sources.values())

    def source_ids(self) -> list[str]:
        return list(self._sources.keys())

    def get(self, source_id: str) -> LegalSourceContract | None:
        return self._sources.get(str(source_id or "").strip())

    def get_by_category(self, category: str) -> list[LegalSourceContract]:
        normalized = str(category or "").strip()
        return [source for source in self.all_sources() if source.metadata.category == normalized]

    def metadata(self, source_id: str) -> SourceMetadata | None:
        source = self.get(source_id)
        return source.metadata if source else None

    def manuscripts(self) -> list[SourceResearchManuscript]:
        return [source.manuscript for source in self.all_sources()]

    def manuscript(self, source_id: str) -> SourceResearchManuscript | None:
        source = self.get(source_id)
        return source.manuscript if source else None

    def scorecards(self) -> list[SourceScorecard]:
        return [evaluate_scorecard(source) for source in self.all_sources()]

    def scorecard(self, source_id: str) -> SourceScorecard | None:
        source = self.get(source_id)
        return evaluate_scorecard(source) if source else None

    def legal_sources_enabled(self) -> bool:
        return bool(self.settings.enabled)

    def network_allowed(self) -> bool:
        return bool(self.settings.allow_network)

    def is_source_enabled(self, source_id: str) -> bool:
        source = self.get(source_id)
        if not source or not self.legal_sources_enabled():
            return False
        if self.settings.enable_all_sources:
            return True
        return source.metadata.source_id in set(self.settings.enabled_source_ids)

    def enabled_sources(self) -> list[LegalSourceContract]:
        return [source for source in self.all_sources() if self.is_source_enabled(source.metadata.source_id)]

    def validate(self) -> PolicyResult:
        result = SourcePolicy().validate_sources(self.all_sources())
        if not self.network_allowed():
            for source in self.all_sources():
                if source.metadata.network_allowed_by_default:
                    result.add_error(
                        "network_default_violation",
                        "Una fonte dichiara rete abilitata di default.",
                        source_id=source.metadata.source_id,
                    )
        return result

    def registry_report(self) -> dict[str, Any]:
        return {
            "legal_sources_enabled": self.legal_sources_enabled(),
            "network_allowed": self.network_allowed(),
            "auto_populate": bool(self.settings.auto_populate),
            "populate_on_startup": bool(self.settings.populate_on_startup),
            "data_dir": str(self.settings.data_dir),
            "index_dir": str(self.settings.index_dir),
            "artifact_dir": str(self.settings.artifact_dir),
            "total_sources": len(self._sources),
            "enabled_sources": [source.metadata.source_id for source in self.enabled_sources()],
            "sources": [source.metadata.to_dict() for source in self.all_sources()],
        }


def create_default_registry(
    *,
    env: Mapping[str, str] | None = None,
    settings: LegalSourceEngineSettings | None = None,
) -> LegalSourceRegistry:
    return LegalSourceRegistry.default(env=env, settings=settings)


__all__ = [
    "GLOBAL_ENABLED_ENV",
    "GLOBAL_NETWORK_ENV",
    "SOURCE_ENV_NAMES",
    "LegalSourceRegistry",
    "create_default_registry",
]
