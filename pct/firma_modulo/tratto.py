"""Il tratto della firma: dal PNG del cliente all'immagine da appoggiare.

Il tratto arriva con molto bianco attorno (la tela su cui il cliente ha
firmato): va rifilato, altrimenti la firma risulta minuscola dentro un
riquadro vuoto."""

from __future__ import annotations

import base64
import io

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Preparazione dell'immagine della firma
# ---------------------------------------------------------------------------

def _da_base64(dato: str | bytes) -> bytes:
    if isinstance(dato, bytes):
        return dato
    testo = dato.strip()
    if testo.startswith("data:"):
        testo = testo.split(",", 1)[1]
    return base64.b64decode(testo)


def rifila_firma(png: bytes, *, margine: int = 6) -> tuple[bytes, float]:
    """
    Toglie il trasparente attorno al tratto e restituisce (png, proporzione).
    Senza rifilatura la firma finirebbe centrata su una tela mezza vuota e
    risulterebbe minuscola dentro il campo.
    """
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    alfa = img.getchannel("A")
    riquadro = alfa.getbbox()
    if riquadro:
        x0, y0, x1, y1 = riquadro
        x0 = max(0, x0 - margine)
        y0 = max(0, y0 - margine)
        x1 = min(img.width, x1 + margine)
        y1 = min(img.height, y1 + margine)
        img = img.crop((x0, y0, x1, y1))

    flusso = io.BytesIO()
    img.save(flusso, format="PNG", optimize=True)
    return flusso.getvalue(), img.width / max(1, img.height)
