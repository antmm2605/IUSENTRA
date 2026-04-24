import requests


class LocalModelRegistry:
    def __init__(self, ollama_base_url: str = "http://127.0.0.1:11434"):
        self.ollama_base_url = ollama_base_url.rstrip("/")

    def list_ollama_models(self) -> list[str]:
        try:
            response = requests.get(
                self.ollama_base_url + "/api/tags",
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []

    def has_model(self, model_name: str) -> bool:
        return model_name in self.list_ollama_models()
