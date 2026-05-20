from __future__ import annotations

import os
from typing import Any

from .deterministic_provider import DeterministicProvider
from .mock_provider import MockProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from lex.contracts import answer_contract_for


LEX_MODEL_ROUTING_SCHEMA = "iusentra.lex_model_routing.v1"

# ------------------------------------------------------------------ #
# Set workflow esistenti (retrocompatibili)                             #
# ------------------------------------------------------------------ #
_DETERMINISTIC_WORKFLOWS = {
    "economico",
    "next_action",
    "cabina",
    "atto_da_template",
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
_LEGAL_REASONER_WORKFLOWS: frozenset[str] = frozenset(
    {"normativa", "giurisprudenza", "giurisprudenza_specifica", "prassi"}
)

# Bozze atti: generazione testo lungo, struttura contrattuale/processuale
_DRAFTER_WORKFLOWS: frozenset[str] = frozenset({"atto", "documento"})

# Deterministici: nessuna generazione, logica regola-based
_DETERMINISTIC_PROFILE_WORKFLOWS: frozenset[str] = frozenset(
    {
        "economico",
        "next_action",
        "cabina",
        "atto_da_template",
        "telematico_status",
        "deposito_telematico",
        "compliance",
        "studio_data_lookup",
    }
)


_PROFILE_POLICIES: dict[str, dict[str, Any]] = {
    "classifier": {
        "llm_used": True,
        "deterministic": False,
        "cost_tier": "low",
        "latency_target_ms": 2000,
        "context_policy": "solo segnali minimi per classificare la domanda",
        "quality_gate": "non produce risposta legale finale",
    },
    "retrieval_summarizer": {
        "llm_used": True,
        "deterministic": False,
        "cost_tier": "medium",
        "latency_target_ms": 12000,
        "context_policy": "usa evidenze gia' selezionate, compattate e attribuite",
        "quality_gate": "fonti, duplicati, conflitti e OCR sporco controllati prima della risposta",
    },
    "legal_reasoner": {
        "llm_used": True,
        "deterministic": False,
        "cost_tier": "high",
        "latency_target_ms": 20000,
        "context_policy": "ragiona solo su fonti o dati resi espliciti nel contesto",
        "quality_gate": "distingue dato certo, inferenza, lacuna e punto da verificare",
    },
    "drafter": {
        "llm_used": True,
        "deterministic": False,
        "cost_tier": "high",
        "latency_target_ms": 30000,
        "context_policy": "usa fascicolo, template reali e documenti selezionati",
        "quality_gate": "bozza nell'editor professionale con modifiche tracciabili",
    },
    "deterministic": {
        "llm_used": False,
        "deterministic": True,
        "cost_tier": "none",
        "latency_target_ms": 100,
        "context_policy": "risposta da dati strutturati senza chiamata modello",
        "quality_gate": "non consuma crediti e non usa web",
    },
}


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


def _provider_name(provider: Any) -> str:
    return str(
        getattr(provider, "provider_name", None)
        or getattr(provider, "name", None)
        or type(provider).__name__
    )


def routing_policy_for_profile(profile: str) -> dict[str, Any]:
    policy = dict(_PROFILE_POLICIES.get(profile) or _PROFILE_POLICIES["legal_reasoner"])
    policy["profile"] = profile
    policy["schema"] = LEX_MODEL_ROUTING_SCHEMA
    return policy


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

        # Costruisci reason leggibile
        metadata = dict(getattr(request, "metadata", {}) or {})
        forced = str(metadata.get("force_provider") or "").strip().lower()

        if forced == "openai" and not _external_provider_allowed():
            reason = "provider esterno richiesto ma non autorizzato: uso routing interno"
        elif forced in self.providers and _provider_name(provider) == forced:
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

    def routing_policy(
        self,
        request: Any,
        context: Any,
        workflow: str,
        evidence: Any,
    ) -> dict[str, Any]:
        provider, profile, reason = self.pick_with_profile(request, context, workflow, evidence)
        policy = routing_policy_for_profile(profile)
        policy.update(
            {
                "provider": _provider_name(provider),
                "reason": reason,
                "workflow": str(workflow or ""),
                "external_allowed": _external_provider_allowed(),
            }
        )
        return policy

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
        policy = routing_policy_for_profile(profile)
        return {
            "schema": LEX_MODEL_ROUTING_SCHEMA,
            "provider": _provider_name(provider),
            "profile": profile,
            "reason": reason,
            "workflow": str(workflow or ""),
            "external_allowed": _external_provider_allowed(),
            "ollama_url": _get_ollama_url_safe(),
            "profile_policy": policy,
            "llm_used": bool(policy.get("llm_used")),
            "deterministic": bool(policy.get("deterministic")),
        }
