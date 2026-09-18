"""Il ponte fra il portale clienti e i campi firma del modulo.

Il portale lavora con i byte del PDF, non con i percorsi, e riceve il tratto
della firma come JPEG. Qui si traduce: se il documento ha campi firma veri, la
firma ci va dentro; se non ne ha — una lettera, un parere, una relazione — non
c'e' nulla da fare e il portale ricade sul suo timbro di sempre.

Il tratto JPEG non ha trasparenza: incollato cosi' com'e' porterebbe con se' un
rettangolo bianco che copre il rigo del modulo e le parole prestampate. Il
bianco va reso trasparente prima di appoggiarlo.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from typing import Any

#: quanto un pixel deve essere chiaro per essere considerato sfondo del tratto
SOGLIA_BIANCO = 244

#: la riga in calce che dichiara la firma: piccola e grigia, perche' non e'
#: parte del modulo ministeriale e non deve sembrarlo
CORPO_NOTA = 6.5
MARGINE_NOTA = 22.0
GRIGIO_NOTA = (0.45, 0.45, 0.45)


def _pillow() -> Any:
    try:
        from PIL import Image

        return Image
    except ImportError:  # pragma: no cover - dipendenza del runtime Docker
        return None


def tratto_trasparente(dati: bytes) -> bytes:
    """Il tratto della firma con lo sfondo bianco reso trasparente, come PNG.

    Il portale riceve il tratto in JPEG, che non ha trasparenza: incollarlo
    sul modulo significherebbe coprire con un rettangolo bianco il rigo e le
    parole prestampate attorno al campo firma.
    """
    Image = _pillow()
    if Image is None or not dati:
        return dati
    try:
        with Image.open(io.BytesIO(dati)) as sorgente:
            immagine = sorgente.convert("RGBA")
    except Exception:
        return dati
    pixel = immagine.load()
    larghezza, altezza = immagine.size
    for y in range(altezza):
        for x in range(larghezza):
            rosso, verde, blu, _ = pixel[x, y]
            if rosso >= SOGLIA_BIANCO and verde >= SOGLIA_BIANCO and blu >= SOGLIA_BIANCO:
                pixel[x, y] = (rosso, verde, blu, 0)
    fuori = io.BytesIO()
    immagine.save(fuori, "PNG")
    return fuori.getvalue()


def campi_firma_del_documento(pdf: bytes) -> list[dict[str, Any]]:
    """I campi firma del documento, se ne ha. Lista vuota se non e' un modulo."""
    from .campi import campi_firmabili

    if not pdf:
        return []
    cartella = tempfile.mkdtemp(prefix="iusentra-firma-")
    percorso = os.path.join(cartella, "modulo.pdf")
    try:
        with open(percorso, "wb") as destinazione:
            destinazione.write(pdf)
        return [campo.as_dict() for campo in campi_firmabili(percorso)]
    except Exception:
        return []
    finally:
        shutil.rmtree(cartella, ignore_errors=True)


def _nota_in_calce(pdf: bytes, nota: str) -> bytes:
    """La riga discreta in calce che dice chi ha firmato e quando.

    Il registro delle prove del portale conserva gia' tutto, ma il documento
    che gira fuori dallo studio deve dirlo da solo: chi lo legge non ha accesso
    al registro. Sta nel margine basso dell'ultima pagina, in grigio e piccola,
    perche' non e' parte del modulo ministeriale e non deve sembrarlo.
    """
    from .applica import fitz

    if fitz is None or not nota.strip():
        return pdf
    try:
        documento = fitz.open(stream=pdf, filetype="pdf")
    except Exception:
        return pdf
    try:
        pagina = documento[-1]
        documento.xref_set_key(pagina.xref, "Annots", "[]")
        pagina.insert_text(
            fitz.Point(MARGINE_NOTA, pagina.rect.height - MARGINE_NOTA),
            nota[:200], fontsize=CORPO_NOTA, fontname="helv", color=GRIGIO_NOTA,
        )
        return documento.tobytes()
    except Exception:
        return pdf
    finally:
        documento.close()


def firma_nei_campi(pdf: bytes, tratto: bytes, *, testi: dict[str, str] | None = None,
                    nota: str = "") -> bytes | None:
    """La firma appoggiata nei campi firma del modulo, e il modulo appiattito.

    Restituisce `None` quando il documento non ha campi firma: non e' un
    errore, e' un documento che non e' un modulo, e il portale ha gia' il suo
    modo di firmarlo.

    Appiattire e' necessario: un modulo che resta compilabile puo' essere
    cambiato dopo la firma, e un documento del genere non prova nulla
    (art. 20 D.Lgs. 82/2005).
    """
    from .applica import applica_firme
    from .campi import campi_firmabili

    if not pdf or not tratto:
        return None
    cartella = tempfile.mkdtemp(prefix="iusentra-firma-")
    percorso = os.path.join(cartella, "modulo.pdf")
    try:
        with open(percorso, "wb") as destinazione:
            destinazione.write(pdf)
        campi = campi_firmabili(percorso)
        if not campi:
            return None
        png = tratto_trasparente(tratto)
        firme = {campo.nome: png for campo in campi}
        firmato = applica_firme(percorso, firme, testi=testi or {}, appiattisci=True)
        return _nota_in_calce(firmato, nota) if nota else firmato
    except Exception:
        return None
    finally:
        shutil.rmtree(cartella, ignore_errors=True)


__all__ = ["SOGLIA_BIANCO", "campi_firma_del_documento", "firma_nei_campi", "tratto_trasparente"]
