"""EmbeddingGemma 2 locale: un processo dedicato, pesi verificati e nessun download runtime."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pct.embeddinggemma2 import DOCUMENT_PREFIX, MODEL, REVISION, RUNTIME


class InferenceGate:
    """Un solo calcolo per volta; le domande precedono i lotti d'indicizzazione."""

    def __init__(self):
        self.condition = threading.Condition()
        self.pending = []
        self.sequence = 0
        self.busy = False

    @contextmanager
    def slot(self, query: bool):
        with self.condition:
            if len(self.pending) >= 16:
                raise BlockingIOError("Coda locale occupata")
            self.sequence += 1
            ticket = (0 if query else 1, self.sequence)
            self.pending.append(ticket)
            deadline = time.monotonic() + (3 if query else 120)
            while self.busy or min(self.pending) != ticket:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.pending.remove(ticket)
                    self.condition.notify_all()
                    raise BlockingIOError("Coda locale occupata")
                self.condition.wait(remaining)
            self.pending.remove(ticket)
            self.busy = True
        try:
            yield
        finally:
            with self.condition:
                self.busy = False
                self.condition.notify_all()


class LocalEncoder:
    def __init__(self, directory: Path, threads: int = 4):
        os.environ.update(
            HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
            HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false",
        )
        manifest = json.loads((directory / "iusentra-manifest.json").read_text())
        pinned = json.loads(Path(__file__).with_name("model-manifest.json").read_text())
        if manifest != pinned:
            raise ValueError("Manifest diverso dalla revisione ufficiale predisposta")
        if manifest.get("revision") != REVISION:
            raise ValueError("Revisione del modello diversa da quella verificata")
        required = {
            "model.safetensors", "config.json", "modules.json", "tokenizer.json",
            "tokenizer.model", "tokenizer_config.json", "sentence_bert_config.json",
            "config_sentence_transformers.json", "1_Pooling/config.json",
            "2_Normalize/config.json", "processor_config.json", "preprocessor_config.json",
            "chat_template.jinja",
        }
        if not required.issubset(manifest.get("sha256", {})):
            raise ValueError("Manifest dei pesi incompleto")
        if manifest["sha256"]["model.safetensors"] != "197a32965d4b1105faf060417baa899e193fb73cd401f42ec9295234d5553d79":
            raise ValueError("Pesi diversi dalla revisione ufficiale verificata")
        actual = {str(p.relative_to(directory)).replace("\\", "/") for p in directory.rglob("*") if p.is_file()}
        if actual - {"iusentra-manifest.json"} != set(manifest["sha256"]):
            raise ValueError("File del modello estranei o non verificati")
        for name, digest in manifest["sha256"].items():
            source = (directory / name).resolve()
            if not source.is_relative_to(directory.resolve()):
                raise ValueError("Percorso dei pesi non valido")
            with source.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError("Impronta del modello non corrispondente")
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(max(1, min(threads, 8)))
        torch.set_num_interop_threads(1)
        self.model = SentenceTransformer(
            str(directory), device="cpu", local_files_only=True,
            trust_remote_code=False,
            config_kwargs={"vision_config": None, "audio_config": None},
            model_kwargs={"dtype": torch.float32},
        )
        self.gate = InferenceGate()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or len(texts) > 32 or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("Testi assenti o lotto non valido")
        prepared = [t if t.startswith(("task: ", "title: ")) else DOCUMENT_PREFIX + t for t in texts]
        # Non troncare una fonte silenziosamente per rispettare il contesto.
        result = []
        for start in range(0, len(prepared)):
            batch = prepared[start:start + 1]
            with self.gate.slot(all(t.startswith("task: ") for t in batch)):
                if any(len(self.model.tokenizer.encode(t, truncation=False)) > 8192 for t in batch):
                    raise ValueError("Testo oltre il contesto: suddividere in chunk prima dell'invio")
                vectors = self.model.encode(
                    batch, batch_size=1, normalize_embeddings=True,
                    show_progress_bar=False, convert_to_numpy=True,
                )
                result.extend(vectors.tolist())
        return result


def serve(encoder: LocalEncoder, host: str = "127.0.0.1", port: int = 11140):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # I testi e i dati dello studio non entrano nei log HTTP.

        def reply(self, status: int, data: dict):
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path in ("/health", "/api/version"):
                self.reply(200, {"ready": True, "provider": "embeddinggemma2_local", "model": MODEL})
            elif self.path == "/api/tags":
                self.reply(200, {"models": [{"name": MODEL, "model": MODEL, "digest": REVISION}]})
            else:
                self.reply(404, {"error": "Risorsa non disponibile"})

        def do_POST(self):
            try:
                self.connection.settimeout(10)
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1024 * 1024:
                    raise ValueError("Dimensione richiesta non valida")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Richiesta non valida")
                if body.get("model") != MODEL:
                    raise ValueError("Modello diverso da quello caricato")
                if self.path == "/api/show":
                    self.reply(200, {"digest": REVISION, "model": MODEL})
                    return
                if self.path != "/api/embed":
                    self.reply(404, {"error": "Risorsa non disponibile"})
                    return
                inputs = body.get("input")
                if isinstance(inputs, str):
                    inputs = [inputs]
                if not isinstance(inputs, list):
                    raise ValueError("Elenco dei testi non valido")
                self.reply(200, {"model": MODEL, "embeddings": encoder.embed(inputs)})
            except BlockingIOError:
                self.reply(429, {"error": "Elaborazione locale già in corso"})
            except (ValueError, TypeError, UnicodeError):
                self.reply(400, {"error": "Richiesta embedding non valida"})
            except Exception:
                self.reply(503, {"error": "Lettura semantica locale non riuscita"})

    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    directory = Path(os.environ["IUSENTRA_EMBEDDING_MODEL_DIR"])
    if RUNTIME == "litert":
        from litert_encoder import LiteRTEncoder
        encoder = LiteRTEncoder(directory, gate=InferenceGate())
    else:
        encoder = LocalEncoder(directory)
    serve(
        encoder,
        host=os.environ.get("IUSENTRA_EMBEDDING_BIND", "127.0.0.1"),
        port=int(os.environ.get("IUSENTRA_EMBEDDING_PORT", "11140")),
    )
