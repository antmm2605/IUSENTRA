from dataclasses import dataclass

from lex.gateway.config import GatewayConfig
from lex.gateway.privacy_guard import PrivacyResult


@dataclass
class RouteDecision:
    provider_order: list[str]
    model: str | None
    reason: str
    external_allowed: bool


class LexRouter:
    def __init__(self, config: GatewayConfig):
        self.config = config

    def route(
        self,
        task: str,
        privacy: PrivacyResult,
        allow_external: bool = False,
        requested_provider: str | None = None,
        requested_model: str | None = None,
    ) -> RouteDecision:
        if requested_provider:
            provider = self.config.providers.get(requested_provider)
            if not provider:
                raise ValueError(f"Provider richiesto non configurato: {requested_provider}")

            if not provider.is_local and privacy.sensitivity in {"sensitive", "highly_sensitive"}:
                raise PermissionError("Contenuto sensibile: non posso inviarlo a provider esterni.")

            if not provider.is_local and not self.config.external_allowed:
                raise PermissionError("Provider esterni disabilitati nella configurazione Lex.")

            return RouteDecision(
                provider_order=[requested_provider],
                model=requested_model or provider.default_model,
                reason="provider_richiesto",
                external_allowed=provider.is_local or allow_external,
            )

        if privacy.sensitivity in {"sensitive", "highly_sensitive"}:
            return RouteDecision(
                provider_order=self._local_providers(),
                model=requested_model,
                reason=f"contenuto_{privacy.sensitivity}_solo_locale",
                external_allowed=False,
            )

        if self.config.mode == "local_only":
            return RouteDecision(
                provider_order=self._local_providers(),
                model=requested_model,
                reason="modalita_local_only",
                external_allowed=False,
            )

        if task in {"code", "debug", "refactor", "tests"}:
            return RouteDecision(
                provider_order=self._local_first_then_external(allow_external),
                model=requested_model,
                reason="task_tecnico_local_first",
                external_allowed=allow_external and self.config.external_allowed,
            )

        return RouteDecision(
            provider_order=self._local_first_then_external(allow_external),
            model=requested_model,
            reason="default_local_first",
            external_allowed=allow_external and self.config.external_allowed,
        )

    def _local_providers(self) -> list[str]:
        providers = [
            name
            for name, cfg in self.config.providers.items()
            if cfg.enabled and cfg.is_local
        ]

        if not providers:
            raise RuntimeError("Nessun provider locale abilitato.")

        return providers

    def _external_providers(self) -> list[str]:
        if not self.config.external_allowed:
            return []

        return [
            name
            for name, cfg in self.config.providers.items()
            if cfg.enabled and not cfg.is_local
        ]

    def _local_first_then_external(self, allow_external: bool) -> list[str]:
        order = self._local_providers()

        if allow_external and self.config.external_allowed:
            order.extend(self._external_providers())

        return order
