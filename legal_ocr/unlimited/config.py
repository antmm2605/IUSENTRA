from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

TRUTHY_VALUES = {"1", "true", "yes", "si", "on", "enabled"}
DEFAULT_MODEL_NAME = "Unlimited-OCR"
DEFAULT_PROMPT = (
    "Estrai il testo del documento legale in italiano. Mantieni ordine, intestazioni, "
    "R.G., date, importi, parti, uffici, riferimenti normativi e tabelle in Markdown. "
    "Non inventare contenuti mancanti."
)


class UnlimitedOcrSettings:
    def __init__(
        self,
        *,
        enabled: bool,
        endpoint: str,
        model: str,
        provider: str,
        api_key: str,
        timeout_seconds: int,
        max_retries: int,
        retry_backoff_seconds: float,
        concurrency: int,
        max_pages: int,
        max_image_bytes: int,
        image_mode: str,
        prompt: str,
        synthetic_confidence: float,
        external_allowed: bool,
        stream: bool,
    ) -> None:
        self.enabled = enabled
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.provider = provider
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.concurrency = concurrency
        self.max_pages = max_pages
        self.max_image_bytes = max_image_bytes
        self.image_mode = image_mode
        self.prompt = prompt
        self.synthetic_confidence = synthetic_confidence
        self.external_allowed = external_allowed
        self.stream = stream

    @classmethod
    def from_env(cls) -> "UnlimitedOcrSettings":
        return cls(
            enabled=_truthy(_env_first("IUSENTRA_UNLIMITED_OCR_ENABLED", "UNLIMITED_OCR_ENABLED")),
            endpoint=_env_first("IUSENTRA_UNLIMITED_OCR_ENDPOINT", "UNLIMITED_OCR_ENDPOINT"),
            model=_env_first("IUSENTRA_UNLIMITED_OCR_MODEL", default=DEFAULT_MODEL_NAME),
            provider=_env_first("IUSENTRA_UNLIMITED_OCR_PROVIDER", default="self_hosted").lower(),
            api_key=_env_first("IUSENTRA_UNLIMITED_OCR_API_KEY", "UNLIMITED_OCR_API_KEY"),
            timeout_seconds=_int_env("IUSENTRA_UNLIMITED_OCR_TIMEOUT_SECONDS", 300, minimum=5, maximum=1800),
            max_retries=_int_env("IUSENTRA_UNLIMITED_OCR_MAX_RETRIES", 3, minimum=1, maximum=8),
            retry_backoff_seconds=_float_env("IUSENTRA_UNLIMITED_OCR_RETRY_BACKOFF_SECONDS", 2.0, minimum=0.1, maximum=30.0),
            concurrency=_int_env("IUSENTRA_UNLIMITED_OCR_CONCURRENCY", 2, minimum=1, maximum=16),
            max_pages=_int_env("IUSENTRA_UNLIMITED_OCR_MAX_PAGES", 48, minimum=1, maximum=256),
            max_image_bytes=_int_env("IUSENTRA_UNLIMITED_OCR_MAX_IMAGE_BYTES", 8 * 1024 * 1024, minimum=128 * 1024, maximum=64 * 1024 * 1024),
            image_mode=_env_first("IUSENTRA_UNLIMITED_OCR_IMAGE_MODE", default="base").lower(),
            prompt=_env_first("IUSENTRA_UNLIMITED_OCR_PROMPT", default=DEFAULT_PROMPT),
            synthetic_confidence=_float_env("IUSENTRA_UNLIMITED_OCR_SYNTHETIC_CONFIDENCE", 0.84, minimum=0.50, maximum=0.95),
            external_allowed=(
                _truthy(_env_first("IUSENTRA_UNLIMITED_OCR_EXTERNAL_ALLOWED"))
                or _truthy(_env_first("LEX_EXTERNAL_ALLOWED"))
                or _truthy(_env_first("IUSENTRA_EXTERNAL_OCR_ALLOWED"))
            ),
            stream=_truthy(_env_first("IUSENTRA_UNLIMITED_OCR_STREAM"), default=True),
        )

    @property
    def chat_completions_url(self) -> str:
        if self.endpoint.endswith("/v1/chat/completions"):
            return self.endpoint
        return f"{self.endpoint}/v1/chat/completions"

    @property
    def health_url(self) -> str:
        return f"{self.endpoint}/health"

    def readiness(self) -> dict[str, object]:
        warnings: list[str] = []
        if not self.enabled:
            return {"ok": False, "reason": "Feature flag IUSENTRA_UNLIMITED_OCR_ENABLED non attivo.", "warnings": warnings}
        if not self.endpoint:
            return {"ok": False, "reason": "Endpoint IUSENTRA_UNLIMITED_OCR_ENDPOINT mancante.", "warnings": warnings}
        parsed = urlparse(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return {"ok": False, "reason": "Endpoint Unlimited-OCR non valido.", "warnings": warnings}
        provider_is_cloud = self.provider in {"cloud", "maas", "external"}
        if provider_is_cloud and not self.external_allowed:
            return {"ok": False, "reason": "Provider Unlimited-OCR esterno bloccato dalla policy privacy.", "warnings": warnings}
        if not provider_is_cloud and not endpoint_is_local_or_private(self.endpoint) and not self.external_allowed:
            return {"ok": False, "reason": "Endpoint Unlimited-OCR non locale/privato senza autorizzazione provider esterni.", "warnings": warnings}
        if parsed.scheme == "http" and not endpoint_is_local(self.endpoint):
            warnings.append("Endpoint HTTP non locale: usare HTTPS o rete privata verificata prima di dati reali.")
        return {"ok": True, "warnings": warnings}


def endpoint_is_local(url: str) -> bool:
    host = (urlparse(url).hostname or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def endpoint_is_local_or_private(url: str) -> bool:
    host = (urlparse(url).hostname or "").strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(host)
        return address.is_private or address.is_loopback or address.is_link_local
    except ValueError:
        return False


def _truthy(value: str | None, *, default: bool = False) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw in TRUTHY_VALUES


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return default


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.getenv(name, "") or "").strip() or default)
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _float_env(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(str(os.getenv(name, "") or "").strip() or default)
    except ValueError:
        return default
    return min(max(value, minimum), maximum)
