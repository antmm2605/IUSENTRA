"""Runtime settings for the Lex operational knowledge layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping


TRUE_VALUES = {"1", "true", "yes", "y", "on", "si", "s", "vero", "abilitato", "enabled"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "none", "null", "", "falso", "disabilitato", "disabled"}


def env_bool(name: str, *, default: bool = False, env: Mapping[str, str] | None = None) -> bool:
    raw = (env or os.environ).get(name)
    if raw is None:
        return default
    value = str(raw or "").strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeSettings:
    enabled: bool = True
    audit_enabled: bool = False
    strict_mode_enabled: bool = False
    max_results: int = 12
    max_answer_items: int = 6

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, config: Mapping[str, Any] | None = None) -> "OperationalKnowledgeSettings":
        source = env or os.environ
        config = config or {}

        def _flag(name: str, default: bool = False) -> bool:
            if name in config:
                return env_bool(name, default=default, env={name: str(config[name])})
            return env_bool(name, default=default, env=source)

        def _int(name: str, default: int) -> int:
            value = config.get(name, source.get(name))
            try:
                return max(1, int(value))
            except Exception:
                return default

        return cls(
            enabled=_flag("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", True),
            audit_enabled=_flag("LEX_OPERATIONAL_AUDIT_ENABLED", False),
            strict_mode_enabled=_flag("LEX_OPERATIONAL_STRICT_MODE_ENABLED", False),
            max_results=_int("LEX_OPERATIONAL_MAX_RESULTS", 12),
            max_answer_items=_int("LEX_OPERATIONAL_MAX_ANSWER_ITEMS", 6),
        )
