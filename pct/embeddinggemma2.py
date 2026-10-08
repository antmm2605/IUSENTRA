"""Contratto del modello locale e trasporto HTTP separato dal modello conversazionale."""

from __future__ import annotations

import os
import math
import urllib.parse

def runtime_profile(runtime: str) -> tuple[str, str]:
    if runtime == "litert":
        return "9be6e8b90982095dc05c2bd162e4b954ee4dbac7", "text-q4-qat-litert0180-segments768-mean-768-v1"
    if runtime == "sentence_transformers":
        return "914f7f89142e33e77833254d9c9b90c3cef7303b", "text-f32-768-v1"
    raise ValueError("Runtime embedding locale non riconosciuto")


RUNTIME = os.getenv("IUSENTRA_EMBEDDING_RUNTIME", "sentence_transformers").strip()
REVISION, PROFILE_SUFFIX = runtime_profile(RUNTIME)
MODEL = f"embeddinggemma2:{REVISION}-{PROFILE_SUFFIX}"
PROVIDER = "embeddinggemma2_local"
QUERY_PREFIX = "task: search query | text: " if RUNTIME == "litert" else "task: search result | query: "
DOCUMENT_PREFIX = "task: search result | text: " if RUNTIME == "litert" else "title: none | text: "


def configured() -> bool:
    return os.environ.get("IUSENTRA_EMBEDDING_PROVIDER", "").strip().lower() in {
        "embeddinggemma2", PROVIDER,
    }


def base_url() -> str:
    raw = os.environ.get("IUSENTRA_EMBEDDING_LOCAL_URL", "http://embeddinggemma2:11140").strip()
    parsed = urllib.parse.urlsplit(raw)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "embeddinggemma2"}
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("EmbeddingGemma 2 deve usare il servizio sullo stesso host")
    return raw.rstrip("/")


def query_text(text: str) -> str:
    return QUERY_PREFIX + text


class LocalEmbeddingClient:
    """Lotti limitati e verifica dello spazio vettoriale prima della scrittura SQL."""

    def health(self) -> bool:
        import requests
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(base_url()+"/health", timeout=(1, 1), allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Il servizio locale non può reindirizzare la richiesta")
        payload = response.json()
        return payload.get("ready") is True and payload.get("model") == MODEL

    def embed_texts(self, model_name: str, inputs: list[str]) -> dict:
        import requests

        if model_name != MODEL:
            raise ValueError("Modello embedding locale non corrispondente")
        vectors = []
        for start in range(0, len(inputs), 16):
            batch = inputs[start:start + 16]
            query = all(text.startswith(QUERY_PREFIX) for text in batch)
            # Un proxy di ambiente non deve ricevere testi dello studio.
            with requests.Session() as session:
                session.trust_env = False
                response = session.post(
                    base_url() + "/api/embed",
                    json={"model": MODEL, "input": batch, "truncate": False},
                    timeout=(2, 4 if query else 120),
                    allow_redirects=False,
                )
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Il servizio locale non può reindirizzare la richiesta")
            payload = response.json()
            result = payload.get("embeddings") or []
            if payload.get("model") != MODEL or len(result) != len(batch):
                raise ValueError("Risposta embedding non corrispondente alla richiesta")
            if any(
                len(v) != 768 or not all(math.isfinite(x) for x in v)
                or not 0.999 <= sum(x * x for x in v) <= 1.001
                for v in result
            ):
                raise ValueError("Vettore embedding non valido")
            vectors.extend(result)
        return {"embeddings": vectors, "model": MODEL, "revision": REVISION}
