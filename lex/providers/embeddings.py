"""Hook futuri per embeddings di Lex."""

from __future__ import annotations


def embedding_provider_name() -> str:
    return "local_embeddings"
