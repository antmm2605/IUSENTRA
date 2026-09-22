"""Le pagine del modulo come immagini, per mostrarle al cliente sul telefono."""

from __future__ import annotations

import base64

from pct.rendering_pdf import pagine_png


# ---------------------------------------------------------------------------
# Anteprime per il portale clienti
# ---------------------------------------------------------------------------

def anteprima_pagine(percorso: str, *, dpi: int = 130) -> list[dict]:
    """PNG in base64 di ogni pagina, con le dimensioni in punti."""
    return [
        {
            "pagina": voce["pagina"],
            "larghezza": voce["larghezza"],
            "altezza": voce["altezza"],
            "png": "data:image/png;base64," + base64.b64encode(voce["png"]).decode(),
        }
        for voce in pagine_png(percorso, dpi=dpi)
    ]
