"""Factory provider immagini per funzioni AI di IUSENTRA."""

from __future__ import annotations

import os

from .base import GeneratedImage, ImageProvider
from .comfyui import ComfyUIImageProvider
from .local_stub import LocalStubImageProvider
from .openai_images import OpenAIImagesProvider
from .stable_diffusion import StableDiffusionImageProvider


def get_image_provider(provider_name: str | None = None) -> ImageProvider:
    code = str(provider_name or os.environ.get("IUSENTRA_AI_IMAGE_PROVIDER") or "local_stub").strip().lower()
    if code == "comfyui":
        return ComfyUIImageProvider()
    if code in {"stable_diffusion", "stable-diffusion"}:
        return StableDiffusionImageProvider()
    if code in {"openai", "openai_images", "openai-images"}:
        return OpenAIImagesProvider()
    return LocalStubImageProvider()


__all__ = ["GeneratedImage", "ImageProvider", "get_image_provider"]
