"""Immagine della pagina da mostrare accanto al testo riconosciuto.

Il riconoscimento non va accettato alla cieca. L'avvocato deve poter guardare la
pagina e il testo affiancati e, quando qualcosa non torna, vedere esattamente
da quale punto del foglio viene quel capoverso. Per farlo la pagina va portata
in schermata, ma non a piena risoluzione: una pagina a 300 dpi pesa alcuni
megabyte e l'attesa costerebbe piu' del vantaggio.

Qui la pagina diventa un'anteprima leggera, e viene dichiarata la scala fra i
pixel dell'anteprima e le coordinate dei riquadri riconosciuti, cosi' la
sovrapposizione dei blocchi sull'immagine e' esatta invece che approssimata.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

# Lato lungo dell'anteprima: un A4 resta leggibile a schermo e pesa poche
# centinaia di kilobyte invece di alcuni megabyte.
LATO_ANTEPRIMA = 1400
QUALITA_ANTEPRIMA = 78


@dataclass(frozen=True)
class Anteprima:
    """Immagine della pagina e scala rispetto alle coordinate riconosciute."""

    dati: bytes
    larghezza: int
    altezza: int
    scala: float
    tipo: str = "image/jpeg"

    @property
    def vuota(self) -> bool:
        return not self.dati


ANTEPRIMA_ASSENTE = Anteprima(dati=b"", larghezza=0, altezza=0, scala=1.0)


def anteprima_da_immagine(immagine) -> Anteprima:
    """Anteprima JPEG di un'immagine gia' in memoria, senza toccare l'originale."""
    if immagine is None:
        return ANTEPRIMA_ASSENTE
    try:
        larghezza, altezza = immagine.size
        if larghezza <= 0 or altezza <= 0:
            return ANTEPRIMA_ASSENTE
        scala = min(1.0, LATO_ANTEPRIMA / max(larghezza, altezza))
        ridotta = immagine
        if scala < 1.0:
            from PIL import Image

            ridotta = immagine.resize(
                (max(1, round(larghezza * scala)), max(1, round(altezza * scala))),
                Image.LANCZOS,
            )
        if ridotta.mode not in {"RGB", "L"}:
            ridotta = ridotta.convert("RGB")
        uscita = io.BytesIO()
        ridotta.save(uscita, "JPEG", quality=QUALITA_ANTEPRIMA, optimize=True)
        if ridotta is not immagine:
            ridotta.close()
        return Anteprima(
            dati=uscita.getvalue(),
            larghezza=max(1, round(larghezza * scala)),
            altezza=max(1, round(altezza * scala)),
            scala=scala,
        )
    except Exception:
        # L'anteprima e' un aiuto alla lettura: se non si genera, il
        # riconoscimento deve comunque arrivare all'avvocato.
        return ANTEPRIMA_ASSENTE


def anteprima_da_pdf(pagina, scala_coordinate: float) -> Anteprima:
    """Anteprima di una pagina PDF, con la scala riferita alle sue coordinate.

    `scala_coordinate` e' il fattore con cui i riquadri riconosciuti sono stati
    espressi (punti del PDF moltiplicati per quel valore): l'anteprima deve
    dichiarare la propria scala nella stessa unita', altrimenti i riquadri
    finirebbero sull'immagine spostati.
    """
    try:
        import fitz  # type: ignore

        riquadro = pagina.rect
        lato = max(riquadro.width, riquadro.height) or 1.0
        zoom = min(scala_coordinate, LATO_ANTEPRIMA / lato)
        pixmap = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        dati = bytes(pixmap.tobytes("jpeg", jpg_quality=QUALITA_ANTEPRIMA))
        return Anteprima(
            dati=dati,
            larghezza=int(pixmap.width),
            altezza=int(pixmap.height),
            scala=(zoom / scala_coordinate) if scala_coordinate else 1.0,
        )
    except Exception:
        # Come sopra: senza anteprima si legge il testo, senza testo no.
        return ANTEPRIMA_ASSENTE


def come_payload(anteprima: Anteprima) -> dict[str, object]:
    """Anteprima nella forma attesa dalla pagina React."""
    import base64

    if anteprima.vuota:
        return {}
    return {
        "immagine_base64": base64.b64encode(anteprima.dati).decode("ascii"),
        "tipo": anteprima.tipo,
        "larghezza": anteprima.larghezza,
        "altezza": anteprima.altezza,
        "scala": round(float(anteprima.scala), 5),
    }


__all__ = ["ANTEPRIMA_ASSENTE", "Anteprima", "anteprima_da_immagine", "anteprima_da_pdf", "come_payload"]
