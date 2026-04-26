"""Stub configurabile per provider immagini OpenAI.

L'implementazione reale resta disattivata se non configurata esplicitamente.
"""

from __future__ import annotations

from .local_stub import LocalStubImageProvider


class OpenAIImagesProvider(LocalStubImageProvider):
    provider_name = "openai_images"
