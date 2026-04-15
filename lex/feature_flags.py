"""Feature flag interne del modulo Lex."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LexFeatureFlags:
    enable_udienza_workflow: bool = True
    enable_atto_workflow: bool = True
    enable_next_action_workflow: bool = True
    enable_provider_fallback: bool = True
    enable_response_cache: bool = False
    enable_case_memory: bool = True
