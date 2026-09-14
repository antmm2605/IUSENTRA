"""Il runtime Tesseract dello studio: dove sta, quali lingue ha, come si avvia.

Un solo punto decide come si raggiunge il motore: il percorso dell'eseguibile
(variabile d'ambiente, PATH, installazione Windows), la cartella dei dizionari
e la lingua. Prima queste decisioni erano copiate in tre moduli e potevano
divergere: qui vivono una volta sola, e chi legge una pagina le usa cosi'.

Il motore lavora meglio con un solo thread per processo: piu' processi in
parallelo (una pagina per thread, una configurazione per thread) rendono di
piu' della parallelizzazione interna, che su un server condiviso satura le CPU
e rallenta tutti. Per questo il limite OpenMP viene fissato a uno.
"""

from __future__ import annotations

import os
from pathlib import Path
from shutil import which

LINGUA_PREDEFINITA = "ita"


def comando_tesseract() -> str:
    """Percorso dell'eseguibile Tesseract, o stringa vuota se non c'e'."""
    configurato = os.environ.get("IUSENTRA_TESSERACT_CMD", "").strip()
    if configurato and Path(configurato).is_file():
        return configurato
    trovato = which("tesseract")
    if trovato:
        return trovato
    for radice in (
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        os.environ.get("LOCALAPPDATA", ""),
    ):
        if not radice:
            continue
        candidato = Path(radice) / "Tesseract-OCR" / "tesseract.exe"
        if candidato.is_file():
            return str(candidato)
    return ""


def cartella_tessdata(comando: str) -> str:
    """Cartella dei dizionari, se dichiarata o accanto all'eseguibile."""
    candidati: list[Path] = []
    for nome in ("IUSENTRA_TESSDATA_PREFIX", "TESSDATA_PREFIX"):
        configurato = os.environ.get(nome, "").strip().strip('"')
        if configurato:
            candidati.append(Path(configurato))
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        candidati.append(Path(local_app_data) / "IUSENTRA" / "tessdata")
    if comando:
        candidati.append(Path(comando).resolve().parent / "tessdata")
    for candidato in candidati:
        if candidato.is_dir() and any(candidato.glob("*.traineddata")):
            return str(candidato)
    return ""


def configura(pytesseract: object, *, comando: str | None = None) -> str:
    """Punta pytesseract all'eseguibile e ai dizionari; restituisce la configurazione base.

    La configurazione base e' vuota: la cartella dei dizionari passa dalla
    variabile d'ambiente `TESSDATA_PREFIX`, che il motore legge senza virgolette.
    """
    percorso = comando_tesseract() if comando is None else comando
    modulo = getattr(pytesseract, "pytesseract", None)
    if percorso and modulo is not None and hasattr(modulo, "tesseract_cmd"):
        modulo.tesseract_cmd = percorso
    tessdata = cartella_tessdata(percorso)
    if tessdata:
        os.environ["TESSDATA_PREFIX"] = tessdata
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    return ""


def lingua_disponibile(pytesseract: object, preferita: str = LINGUA_PREDEFINITA, configurazione: str = "") -> str:
    """La lingua richiesta se installata, altrimenti la piu' vicina disponibile."""
    richiesta = str(preferita or LINGUA_PREDEFINITA).strip() or LINGUA_PREDEFINITA
    elenco = getattr(pytesseract, "get_languages", None)
    if not callable(elenco):
        return richiesta
    try:
        lingue = set(elenco(config=configurazione))
    except TypeError:
        lingue = set(elenco())
    except Exception:
        return richiesta
    if richiesta in lingue:
        return richiesta
    if richiesta.startswith("it") and "ita" in lingue:
        return "ita"
    if "eng" in lingue:
        return "eng"
    return next(iter(sorted(lingue)), richiesta)


def lingue_installate(pytesseract: object) -> set[str]:
    elenco = getattr(pytesseract, "get_languages", None)
    if not callable(elenco):
        return set()
    try:
        return set(elenco(config=""))
    except TypeError:
        return set(elenco())
    except Exception:
        return set()


def versione(pytesseract: object) -> str:
    try:
        return f"tesseract:{pytesseract.get_tesseract_version()}"
    except Exception:
        return ""


__all__ = [
    "LINGUA_PREDEFINITA",
    "cartella_tessdata",
    "comando_tesseract",
    "configura",
    "lingua_disponibile",
    "lingue_installate",
    "versione",
]
