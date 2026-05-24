from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LegalOcrConfig:
    tenant_id: str
    primary_engine: str = "tesseract"
    fallback_engine: str = "native-text-fallback"
    language: str = "ita"
    local_first_only: bool = True
    avg_confidence_fallback_threshold: float = 0.85
    pct_tokens_low_fallback_threshold: float = 10.0
    avg_confidence_hil_threshold: float = 0.70
    pct_tokens_very_low_hil_threshold: float = 5.0
    layout_missing_bbox_hil_threshold: float = 20.0
    lex_min_confidence: float = 0.75
    worker_id: str = ""
