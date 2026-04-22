from types import SimpleNamespace

from lex.providers.ollama_provider import OllamaProvider


def test_ollama_provider_non_si_rompe_con_payload_senza_evidenze(monkeypatch):
    provider = OllamaProvider()

    monkeypatch.setattr(
        "lex.providers.ollama_provider._resolve_runtime",
        lambda: {
            "api_base_url": "http://127.0.0.1:11434/api",
            "chat_model": "mistral",
            "keep_alive": "10m",
        },
    )
    monkeypatch.setattr(
        "lex.providers.ollama_provider._call_ollama",
        lambda payload, api_base_url, timeout=120: "Risposta con fallback web gestito correttamente.",
    )

    draft = provider.generate(
        request=SimpleNamespace(query="sentenza n. 8785 del 08/04/2026"),
        context={"focus": "ricerca_legale"},
        evidence={"items": [], "citations": [], "official_sources": []},
        workflow="giurisprudenza",
    )

    assert "fallback web" in draft.text.lower()
    assert draft.metadata["status"] == "ok"
    assert draft.metadata["evidence_count"] == 0


def test_ollama_provider_filtra_risposte_meta_su_fascicolo(monkeypatch):
    provider = OllamaProvider()

    monkeypatch.setattr(
        "lex.providers.ollama_provider._resolve_runtime",
        lambda: {
            "api_base_url": "http://127.0.0.1:11434/api",
            "chat_model": "mistral",
            "keep_alive": "10m",
        },
    )
    monkeypatch.setattr(
        "lex.providers.ollama_provider._call_ollama",
        lambda payload, api_base_url, timeout=120: (
            "Ok, capisco. **Passi Proposti:**\n1. Identificazione prioritaria dei fascicoli.\n"
            "Per aiutarti ulteriormente avrei bisogno di altre informazioni."
        ),
    )

    draft = provider.generate(
        request=SimpleNamespace(query="Che cosa devo fare su questo fascicolo?"),
        context={
            "structured_context": {
                "fascicolo": {
                    "numero": "RG 1025/2024",
                    "titolo": "Appello civile",
                    "cliente": "Mario Rossi",
                    "stato": "IN_CORSO",
                    "documenti_count": 3,
                },
                "documenti": [{"id": "DOC-1", "nome": "Sentenza", "tipo": "PROVVEDIMENTO"}],
                "agenda": [],
                "scadenziario": [],
            }
        },
        evidence={"items": [], "citations": [], "official_sources": []},
        workflow="fascicolo",
    )

    assert "Sto lavorando sul fascicolo RG 1025/2024" in draft.text
    assert draft.metadata["status"] == "fallback_meta"
    assert draft.metadata["fallback_provider"] == "deterministic"


def test_ollama_provider_filtra_risposte_meta_su_giurisprudenza(monkeypatch):
    provider = OllamaProvider()

    monkeypatch.setattr(
        "lex.providers.ollama_provider._resolve_runtime",
        lambda: {
            "api_base_url": "http://127.0.0.1:11434/api",
            "chat_model": "mistral",
            "keep_alive": "10m",
        },
    )
    monkeypatch.setattr(
        "lex.providers.ollama_provider._call_ollama",
        lambda payload, api_base_url, timeout=120: (
            "Ecco un esempio di risposta all'input fornito.\nMotivazione:\nSpero che questa risposta sia utile."
        ),
    )

    draft = provider.generate(
        request=SimpleNamespace(query="Sentenza n. 8785 del 08/04/2026"),
        context={"focus": "ricerca_legale"},
        evidence={"items": [], "citations": [], "official_sources": []},
        workflow="giurisprudenza",
    )

    assert "base verificata sufficiente" in draft.text
    assert draft.metadata["status"] == "fallback_meta"
    assert draft.metadata["meta_response_filtered"] is True
