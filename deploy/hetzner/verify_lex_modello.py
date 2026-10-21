"""Verifica risoluzione per studio, digest e generazione del modello distribuito."""
import json
import os

import requests

from web.app import create_app
from lex.providers.ollama_runtime import resolved_ollama_runtime
from lex.gateway.config import _modello_predefinito
from scripts.backfill_archivio_batches import _targets, _tenant_context


def main():
    app = create_app()
    manager, studios = _targets(app, os.getenv("LEX_VERIFY_TENANT", ""))
    checked = set()
    for slug, owner in studios.items():
        with _tenant_context(app, manager, owner, slug):
            runtime = resolved_ollama_runtime(force_refresh=True)
            gateway_model = _modello_predefinito()
            assert runtime["chat_model"] == gateway_model == os.environ["LEX_MODELLO"], (runtime["chat_model"], gateway_model)
            base = runtime["base_url"].rstrip("/")
            key = (base, gateway_model)
            if key in checked:
                continue
            response = requests.get(base + "/api/tags", timeout=20)
            response.raise_for_status()
            model = next(x for x in response.json()["models"] if x["name"] == gateway_model)
            assert model["digest"] == os.environ["LEX_DIGEST"]
            response = requests.post(base + "/api/chat", json={
                "model": gateway_model,
                "messages": [{"role": "user", "content": "Scrivi una frase in italiano sull'organizzazione dello studio."}],
                "stream": False, "think": False,
                "options": {"num_ctx": 8192, "num_predict": 80, "temperature": 0.2},
            }, timeout=300)
            response.raise_for_status()
            answer = response.json()
            assert answer.get("done") and answer.get("message", {}).get("content", "").strip(), answer
            assert answer["model"] == gateway_model
            checked.add(key)
            print(json.dumps({"chat_model": gateway_model, "gateway_model": gateway_model,
                "digest": model["digest"], "answer": answer["message"]["content"],
                "eval_count": answer.get("eval_count"), "done": answer["done"]}, ensure_ascii=False), flush=True)
    print(json.dumps({"studios_checked": len(studios), "runtimes_checked": len(checked)}), flush=True)


if __name__ == "__main__":
    main()
