from lex.gateway.config import GatewayConfig
from lex.gateway.fallback import FallbackRunner
from lex.gateway.messages import ChatMessage, ProviderResponse
from lex.gateway.privacy_guard import PrivacyGuard
from lex.gateway.providers import build_provider
from lex.gateway.rate_limit import InMemoryRateLimiter
from lex.gateway.router import LexRouter

DEFAULT_SYSTEM_PROMPT = """
Sei Lex AI, assistente operativo per uno studio legale italiano.
Rispondi in modo professionale, chiaro e prudente.
Non inventare riferimenti normativi, sentenze o dati.
Se mancano elementi, dichiara cosa manca.
Se la richiesta riguarda atti, fascicoli, scadenze, depositi o dati cliente,
mantieni un approccio conservativo e orientato alla verifica.
""".strip()


class LexGateway:
    def __init__(self, config: GatewayConfig | None = None):
        self.config = config or GatewayConfig.from_env()
        self.privacy_guard = PrivacyGuard()
        self.router = LexRouter(self.config)
        self.fallback = FallbackRunner()
        self.rate_limiter = InMemoryRateLimiter()

        self.providers = {
            name: build_provider(cfg)
            for name, cfg in self.config.providers.items()
            if cfg.enabled
        }

    def ask(
        self,
        user_id: str,
        prompt: str,
        task: str = "general",
        allow_external: bool = False,
        requested_provider: str | None = None,
        requested_model: str | None = None,
        system_prompt: str | None = None,
    ) -> ProviderResponse:
        self.rate_limiter.check(user_id)

        privacy = self.privacy_guard.classify_text(prompt)

        route = self.router.route(
            task=task,
            privacy=privacy,
            allow_external=allow_external,
            requested_provider=requested_provider,
            requested_model=requested_model,
        )

        final_prompt = prompt

        if route.external_allowed and privacy.sensitivity != "public":
            final_prompt = privacy.redacted_text

        messages = [
            ChatMessage(
                role="system",
                content=system_prompt or DEFAULT_SYSTEM_PROMPT,
            ),
            ChatMessage(
                role="user",
                content=final_prompt,
            ),
        ]

        def call_provider(provider_name: str) -> ProviderResponse:
            provider = self.providers.get(provider_name)
            if not provider:
                raise RuntimeError(f"Provider non disponibile: {provider_name}")

            cfg = self.config.providers[provider_name]
            model = requested_model or route.model or cfg.default_model

            if not cfg.is_local and privacy.sensitivity in {"sensitive", "highly_sensitive"}:
                raise PermissionError(
                    "Blocco privacy: contenuto sensibile non inviabile a provider esterno."
                )

            return provider.chat(
                messages=messages,
                model=model,
                temperature=0.2,
                max_tokens=2048,
            )

        response = self.fallback.run(route.provider_order, call_provider)

        provider_raw = response.raw if isinstance(response.raw, dict) else {}
        response.raw = {
            "provider_raw": provider_raw,
            "lex_route": {
                "provider_order": route.provider_order,
                "reason": route.reason,
                "privacy_sensitivity": privacy.sensitivity,
                "privacy_reasons": privacy.reasons,
                "external_allowed": route.external_allowed,
            },
        }

        return response
