"""Guardrail per impedire canali diretti non verificati sui portali non-PST."""

from __future__ import annotations

from typing import Any

from web.services.portal_integration_policy import (
    MODE_DIRECT_VERIFIED,
    get_portal_integration_policy,
)


class UnverifiedDirectPortalError(RuntimeError):
    """Sollevata quando un client produttivo tenta un accesso diretto non verificato."""


def ensure_direct_portal_verified(portale: str, config: dict[str, Any] | None = None) -> None:
    if config is None:
        try:
            from flask import current_app

            config = current_app.config  # type: ignore[assignment]
        except Exception:
            config = None
    policy = get_portal_integration_policy(portale, config)
    if policy.portale == "pst":
        return
    if policy.portale in {"ptt", "pat", "pdp"} and policy.direct_allowed and policy.mode == MODE_DIRECT_VERIFIED:
        return
    raise UnverifiedDirectPortalError(
        "PTT/PAT/PDP non è abilitato come integrazione diretta verificata. "
        "Usare portale ufficiale assistito e import automatico di file/ricevute/esiti."
    )
