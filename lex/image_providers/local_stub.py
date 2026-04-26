"""Provider locale sicuro: non chiama servizi esterni e restituisce un placeholder."""

from __future__ import annotations

from .base import GeneratedImage, ImageProvider


class LocalStubImageProvider(ImageProvider):
    provider_name = "local_stub"

    def generate(self, *, prompt: str, title: str = "") -> GeneratedImage:
        return GeneratedImage(
            ok=False,
            provider=self.provider_name,
            prompt=prompt,
            warning="Nessun provider immagini reale configurato: e' stato salvato un placeholder professionale.",
        )
