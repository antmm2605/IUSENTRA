"""Interfaccia provider immagini per contenuti del Sito Studio."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedImage:
    ok: bool
    provider: str
    prompt: str
    filename: str = ""
    bytes_data: bytes = b""
    mime_type: str = ""
    warning: str = ""


class ImageProvider:
    provider_name = "base"

    def generate(self, *, prompt: str, title: str = "") -> GeneratedImage:
        raise NotImplementedError
