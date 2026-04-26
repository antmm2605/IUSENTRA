"""Stub configurabile per ComfyUI.

Il provider non viene chiamato automaticamente: serve una configurazione esplicita
e una successiva integrazione operativa del workflow immagini.
"""

from __future__ import annotations

from .local_stub import LocalStubImageProvider


class ComfyUIImageProvider(LocalStubImageProvider):
    provider_name = "comfyui"
