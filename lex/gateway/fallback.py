from typing import Callable

from lex.gateway.messages import ProviderResponse


class FallbackRunner:
    def run(
        self,
        provider_order: list[str],
        call_provider: Callable[[str], ProviderResponse],
    ) -> ProviderResponse:
        errors: list[str] = []

        for provider_name in provider_order:
            try:
                return call_provider(provider_name)
            except Exception as exc:
                errors.append(f"{provider_name}: {type(exc).__name__}: {exc}")

        joined = " | ".join(errors)
        raise RuntimeError(f"Tutti i provider Lex sono falliti: {joined}")
