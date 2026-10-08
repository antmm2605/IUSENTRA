"""Adapter CPU dei pesi QAT ufficiali: stesso trasporto e coda del RAG locale."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from pct.embeddinggemma2 import DOCUMENT_PREFIX, QUERY_PREFIX, REVISION, RUNTIME


class LiteRTEncoder:
    def __init__(self, directory: Path, *, gate, threads: int = 4):
        if RUNTIME != "litert":
            raise ValueError("Il worker richiede il profilo LiteRT distinto")
        pinned = json.loads(Path(__file__).with_name("litert-model-manifest.json").read_text())
        actual = json.loads((directory / "manifest.json").read_text())
        if actual != pinned or actual["revision"] != REVISION:
            raise ValueError("Manifest LiteRT diverso dai pesi ufficiali verificati")
        filename = actual["file"]
        if {p.name for p in directory.iterdir()} != {filename, "manifest.json"}:
            raise ValueError("File LiteRT estranei alla revisione verificata")
        source = directory / filename
        with source.open("rb") as stream:
            if source.stat().st_size != actual["bytes"] or hashlib.file_digest(stream, "sha256").hexdigest() != actual["sha256"]:
                raise ValueError("Impronta dei pesi LiteRT non corrispondente")
        from litert_lm import Backend, EmbeddingEngine, EmbeddingOptions, InputOverflowStrategy

        cache = Path("/tmp/embeddinggemma2-litert-cache")
        cache.mkdir(exist_ok=True)
        self.model = EmbeddingEngine(
            str(source), backend=Backend.CPU(thread_count=max(1, min(threads, 8))),
            cache_dir=str(cache), min_input_length=128, max_input_length=2048,
        )
        # Il metodo nativo conserva tutto l'input oltre il contesto per i documenti.
        # Le domande non possono essere troncate né cambiare significato in silenzio.
        self.document_options = EmbeddingOptions(normalize=True, output_size=768,
            input_overflow_strategy=InputOverflowStrategy.CHUNK_AND_AVERAGE)
        self.query_options = EmbeddingOptions(normalize=True, output_size=768,
            input_overflow_strategy=InputOverflowStrategy.ERROR)
        self.gate = gate

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or len(texts) > 32 or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("Testi assenti o lotto non valido")
        result = []
        for text in texts:
            query = text.startswith(QUERY_PREFIX)
            if query:
                with self.gate.slot(True):
                    result.append(self.model.compute_embedding(text, self.query_options).embedding)
                continue
            body = text[len(DOCUMENT_PREFIX):] if text.startswith(DOCUMENT_PREFIX) else text
            # Nessun carattere scartato. Cedere il turno tra segmenti permette
            # alle ricerche di precedere una lunga lettura già in corso.
            total = [0.0] * 768
            for start in range(0, len(body), 768):
                part = body[start:start + 768]
                with self.gate.slot(False):
                    vector = self.model.compute_embedding(DOCUMENT_PREFIX + part, self.document_options).embedding
                for index, value in enumerate(vector):
                    total[index] += value * len(part)
            norm = math.sqrt(sum(value * value for value in total))
            if not math.isfinite(norm) or norm <= 0:
                raise ValueError("Vettore documentale non valido")
            result.append([value / norm for value in total])
        return result
