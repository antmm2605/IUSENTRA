"""Un recupero del runtime conserva la prova di generazione terminata."""

import pytest

from lex.contracts import EvidenceItem, LexRequest
from lex.providers.ollama_provider import OllamaProvider, _OllamaText


@pytest.mark.parametrize("reason", ["stop", "length"])
def test_recovered_runtime_keeps_completion_reason(monkeypatch, reason):
    monkeypatch.setattr("lex.providers.ollama_provider._resolve_runtime",
        lambda: {"api_base_url": "http://first.invalid/api", "chat_model": "accepted", "keep_alive": "10m"})
    monkeypatch.setattr("lex.providers.ollama_runtime.refresh_live_ollama_runtime",
        lambda: {"api_base_url": "http://recovered.invalid/api", "chat_model": "accepted", "keep_alive": "10m"})
    calls = []

    def call(payload, api_base_url, **kwargs):
        calls.append(api_base_url)
        if len(calls) == 1:
            raise TimeoutError("Prova controllata")
        return _OllamaText("La fonte indica un termine di sei mesi [1].",
                           {"done": True, "done_reason": reason, "prompt_eval_count": 50})

    monkeypatch.setattr("lex.providers.ollama_provider._call_ollama", call)
    item = EvidenceItem(source_type="web_libero", source_id="public", title="Fonte pubblica",
                        content="Il termine è di sei mesi.", score=1)
    request = LexRequest(tenant_id="controlled", user_id="tester", session_id="retry", query="Leggi la fonte")
    draft = OllamaProvider().generate(request, {}, {"items": [item], "citations": []}, "research")
    assert len(calls) == 2
    assert draft.metadata["runtime_refreshed_after_error"] is True
    assert draft.metadata["generation_result"] == {"done": True, "done_reason": reason}
