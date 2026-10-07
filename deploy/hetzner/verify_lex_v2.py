"""Prova reale del modello risolto da Lex, dal gateway e da Ollama."""
import json
import requests
from web.app import create_app
from lex.providers.ollama_runtime import resolved_ollama_runtime
from lex.gateway.config import _modello_predefinito

app = create_app()
with app.app_context():
    runtime = resolved_ollama_runtime(force_refresh=True)
    gateway_model = _modello_predefinito()
    assert runtime["chat_model"] == gateway_model == "iusentra-lex-v2:9b", (runtime["chat_model"], gateway_model)
    base = runtime["base_url"].rstrip("/")
    tags = requests.get(base + "/api/tags", timeout=20).json()["models"]
    model = next(x for x in tags if x["name"] == runtime["chat_model"])
    assert model["digest"] == "a079f24b41a203f59bbd1482248c138b126de02dfeffe1cc57d3fe4387e1a3cb"
    response = requests.post(base + "/api/chat", json={"model": runtime["chat_model"], "messages": [{"role": "user", "content": "Scrivi una frase in italiano sull'organizzazione dello studio."}], "stream": False, "think": False, "options": {"num_ctx": 8192, "num_predict": 80, "temperature": 0.2}}, timeout=300)
    response.raise_for_status()
    answer = response.json()
    assert answer.get("done") and answer.get("message", {}).get("content", "").strip(), answer
    assert answer["model"] == runtime["chat_model"]
    print(json.dumps({"chat_model": runtime["chat_model"], "gateway_model": gateway_model, "digest": model["digest"], "answer": answer["message"]["content"], "eval_count": answer.get("eval_count"), "done": answer["done"]}, ensure_ascii=False))
