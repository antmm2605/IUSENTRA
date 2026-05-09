from __future__ import annotations

import os
from typing import Any

from .deterministic_provider import DeterministicProvider
from .mock_provider import MockProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from lex.contracts import answer_contract_for


# ------------------------------------------------------------------ #
# Set workflow esistenti (retrocompatibili)                             #
# ------------------------------------------------------------------ #
_DETERMINISTIC_WORKFLOWS = {
    "economico",
    "next_action",
    "cabina",
    "telematico_status",
    "deposito_telematico",
    "compliance",
    "studio_data_lookup",
}
_STRICT_LEGAL_WORKFLOWS = {"normativa", "giurisprudenza", "giurisprudenza_specifica", "prassi", "research", "fonti"}


# ------------------------------------------------------------------ #
# Profili di routing professionale                                      #
# ------------------------------------------------------------------ #

# Classificazione rapida: routing leggero, latenza minima
_CLASSIFIER_WORKFLOWS: frozenset[str] = frozenset({"question_answering"})

# Sintesi fonti: retrieval pesante, output strutturato per citazioni
_RETRIEVAL_SUMMARIZER_WORKFLOWS: frozenset[str] = frozenset({"research", "fonti"})

# Ragionamento normativo: provider con capacita' legale, fonti ufficiali
_LEGAL_REASONER_WORKFLOWS: frozenset[str] = frozenset({"normativa", "giurisprudenza", "prassi"})

# Bozze atti: generazione testo lungo, struttura contrattuale/processuale
_DRAFTER_WORKFLOWS: frozenset[str] = frozenset({"atto", "documento"})

# Deterministici: nessuna generazione, logica regola-based
_DETERMINISTIC_PROFILE_WORKFLOWS: frozenset[str] = frozenset(
    {
        "economico",
        "next_action",
        "cabina",
        "telematico_status",
        "deposito_telematico",
        "compliance",
        "studio_data_lookup",
    }
)


def _resolve_profile(workflow: str) -> str:
    """Ritorna il nome del profilo di routing per il workflow dato."""
    if workflow in _CLASSIFIER_WORKFLOWS:
        return "classifier"
    if workflow in _RETRIEVAL_SUMMARIZER_WORKFLOWS:
        return "retrieval_summarizer"
    if workflow in _LEGAL_REASONER_WORKFLOWS:
        return "legal_reasoner"
    if workflow in _DRAFTER_WORKFLOWS:
        return "drafter"
    if workflow in _DETERMINISTIC_PROFILE_WORKFLOWS:
        return "deterministic"
    return "legal_reasoner"  # default sicuro per workflow sconosciuti


def _has_fascicolo_context(context: Any) -> bool:
    if not isinstance(context, dict):
        return False
    structured = context.get("structured_context") or {}
    if isinstance(structured, dict) and structured.get("fascicolo"):
        return True
    return bool(context.get("fascicolo"))


def _external_provider_allowed() -> bool:
    return os.getenv("LEX_EXTERNAL_ALLOWED", "").strip().lower() in {"1", "true", "yes", "si", "on"}


def _get_ollama_url_safe() -> str:
    """Ritorna solo l'host:port di Ollama senza credenziali."""
    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        port = parsed.port or 11434
        return f"{parsed.scheme}://{parsed.hostname}:{port}"
    except Exception:
        return "http://localhost:11434"


class ProviderRegistry:
    def __init__(self) -> None:
        self.providers: dict[str, Any] = {
            "mock": MockProvider(),
            "ollama": OllamaProvider(),
            "openai": OpenAIProvider(),
            "deterministic": DeterministicProvider(),
        }

    def pick(self, request: Any, context: Any, workflow: str, evidence: Any) -> Any:
        """Seleziona il provider per il workflow dato (logica originale invariata)."""
        metadata = dict(getattr(request, "metadata", {}) or {})
        forced = str(metadata.get("force_provider") or "").strip().lower()
        if forced == "mock" and (
            os.getenv("LEX_PROVIDER_FORCE_MOCK", "").strip() == "1"
            or os.getenv("PYTEST_CURRENT_TEST")
        ):
            return self.providers[forced]
        if forced in {"ollama", "deterministic"} and forced in self.providers:
            return self.providers[forced]
        if forced == "openai" and _external_provider_allowed():
            return self.providers["openai"]

        if os.getenv("LEX_PROVIDER_FORCE_MOCK", "").strip() == "1":
            return self.providers["mock"]

        if workflow in _DETERMINISTIC_WORKFLOWS:
            return self.providers["deterministic"]

        contract = answer_contract_for(workflow)
        if contract.provider_hint and contract.provider_hint in self.providers:
            return self.providers[contract.provider_hint]

        if workflow == "fascicolo" and _has_fascicolo_context(context):
            return self.providers["deterministic"]

        if workflow in _STRICT_LEGAL_WORKFLOWS:
            return self.providers["ollama"]

        if workflow in {"telematico", "udienza", "atto", "documento", "question_answering", "intelligence"}:
            return self.providers["ollama"]

        if workflow == "fascicolo":
            return self.providers["deterministic"]

        return self.providers["ollama"]

    def pick_with_profile(
        self,
        request: Any,
        context: Any,
        workflow: str,
        evidence: Any,
    ) -> tuple[Any, str, str]:
        """Seleziona il provider e ritorna (provider, profile_name, reason).

        profile_name e' uno di: classifier, retrieval_summarizer,
        legal_reasoner, drafter, deterministic.

        reason spiega brevemente il criterio di selezione applicato.
        """
        profile = _resolve_profile(workflow)
        provider = self.pick(request, context, workflow, evidence)
        provider_name = str(getattr(provider, "name", type(provider).__name__))

        # Costruisci reason leggibile
        metadata = dict(getattr(request, "metadata", {}) or {})
        forced = str(metadata.get("force_provider") or "").strip().lower()

        if forced in self.providers:
            reason = f"provider forzato via metadata: {forced}"
        elif os.getenv("LEX_PROVIDER_FORCE_MOCK", "").strip() == "1":
            reason = "mock forzato da variabile d'ambiente LEX_PROVIDER_FORCE_MOCK"
        elif workflow in _DETERMINISTIC_WORKFLOWS:
            reason = f"workflow '{workflow}' richiede risposta deterministica"
        elif workflow in _LEGAL_REASONER_WORKFLOWS:
            reason = f"workflow '{workflow}' richiede ragionamento normativo (profilo: {profile})"
        elif workflow in _RETRIEVAL_SUMMARIZER_WORKFLOWS:
            reason = f"workflow '{workflow}' richiede sintesi da retrieval (profilo: {profile})"
        elif workflow in _CLASSIFIER_WORKFLOWS:
            reason = f"workflow '{workflow}' usa classificazione rapida (profilo: {profile})"
        elif workflow in _DRAFTER_WORKFLOWS:
            reason = f"workflow '{workflow}' richiede generazione bozza atto (profilo: {profile})"
        elif workflow == "fascicolo" and _has_fascicolo_context(context):
            reason = "fascicolo presente in contesto: risposta deterministica"
        else:
            contract = answer_contract_for(workflow)
            if contract.provider_hint:
                reason = f"contract hint '{contract.provider_hint}' per workflow '{workflow}'"
            else:
                reason = f"default provider per workflow '{workflow}'"

        return provider, profile, reason

    def get_routing_metadata(
        self,
        request: Any,
        context: Any,
        workflow: str,
        evidence: Any,
    ) -> dict[str, Any]:
        """Ritorna metadata di routing per debug UI.

        Non espone credenziali ne' informazioni sensibili.
        """
        provider, profile, reason = self.pick_with_profile(request, context, workflow, evidence)
        return {
            "provider": str(getattr(provider, "name", type(provider).__name__)),
            "profile": profile,
            "reason": reason,
            "workflow": str(workflow or ""),
            "external_allowed": _external_provider_allowed(),
            "ollama_url": _get_ollama_url_safe(),
        }
