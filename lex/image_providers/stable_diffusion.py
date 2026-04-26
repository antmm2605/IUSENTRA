"""Stub configurabile per Stable Diffusion locale."""

from __future__ import annotations

from .local_stub import LocalStubImageProvider


class StableDiffusionImageProvider(LocalStubImageProvider):
    provider_name = "stable_diffusion"
