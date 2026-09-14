"""Il motore si procura da solo cio' che gli manca, quando puo' farlo con certezza.

Nel container di produzione Tesseract e il dizionario italiano arrivano dal
Dockerfile. Su un host Windows dello studio possono mancare: qui il dizionario
ufficiale `ita.traineddata` (tessdata_fast 4.1.0, lo stesso del pacchetto
Debian usato in produzione) viene scaricato una volta, verificato con il suo
SHA-256 e messo nella cartella che il runtime gia' conosce. Un file che non
corrisponde all'impronta non viene usato: meglio un motore fermo che un
dizionario di provenienza incerta. L'eseguibile, su Windows, si installa con
`winget` dal pacchetto ufficiale UB-Mannheim (`scripts/installa_tesseract_windows.ps1`).
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import re
import shutil
import subprocess
import threading
import urllib.request
from pathlib import Path

from .runtime import comando_tesseract

logger = logging.getLogger(__name__)

DIZIONARI: dict[str, tuple[tuple[str, ...], str, int]] = {
    # lingua: (URL ufficiali immutabili, SHA-256 atteso, dimensione minima in byte)
    "ita": (
        (
            "https://github.com/tesseract-ocr/tessdata_fast/raw/4.1.0/ita.traineddata",
            "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/ita.traineddata",
        ),
        "b8f89e1e785118dac4d51ae042c029a64edb5c3ee42ef73027a6d412748d8827",
        1_000_000,
    ),
}
PACCHETTO_WINGET = "UB-Mannheim.TesseractOCR"
_BLOCCO = threading.Lock()
_TENTATO: set[str] = set()


def abilitato() -> bool:
    return str(os.environ.get("IUSENTRA_OCR_AUTOPROVISION", "1")).strip().lower() not in {"0", "false", "no", "off"}


def cartella_dizionari_scrivibile() -> Path:
    """Dove mettere i dizionari scaricati: dichiarata, o quella dell'utente."""
    configurata = str(os.environ.get("IUSENTRA_TESSDATA_PREFIX") or "").strip().strip('"')
    if configurata:
        return Path(configurata)
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", "").strip() or str(Path.home() / "AppData" / "Local")
        return Path(base) / "IUSENTRA" / "tessdata"
    dati = str(os.environ.get("PCT_DATA_DIR") or "").strip()
    if dati:
        return Path(dati) / "tessdata"
    return Path.home() / ".local" / "share" / "iusentra" / "tessdata"


def _scarica(url: str, timeout: int = 120) -> bytes:
    richiesta = urllib.request.Request(url, headers={"User-Agent": "IUSENTRA-OCR-provisioning"})
    with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:  # noqa: S310 - URL fissi e verificati
        return risposta.read(80_000_000)


def cartella_tessdata_di_sistema() -> Path | None:
    """La cartella dei dizionari dell'installazione di Tesseract, chiesta al motore stesso."""
    comando = comando_tesseract()
    if not comando:
        return None
    try:
        esito = subprocess.run([comando, "--list-langs"], capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    testo = (esito.stdout or "") + (esito.stderr or "")
    trovata = re.search(r'in "([^"]+)"', testo)
    if trovata:
        cartella = Path(trovata.group(1))
        if cartella.is_dir():
            return cartella
    accanto = Path(comando).resolve().parent / "tessdata"
    return accanto if accanto.is_dir() else None


def _completa_cartella(destinazione: Path, sistema: Path | None) -> None:
    """Porta nella cartella propria i file di corredo del motore (pdf.ttf, altri dizionari).

    Tesseract legge una sola cartella di dizionari: se e' la nostra deve
    contenere anche `pdf.ttf`, senza il quale il PDF ricercabile non viene
    scritto, e i dizionari gia' installati che il motore usa per orientamento
    e lingua secondaria.
    """
    if sistema is None or sistema == destinazione:
        return
    for file in sistema.iterdir():
        if file.suffix in {".ttf", ".traineddata"} and file.is_file():
            copia = destinazione / file.name
            if not copia.exists():
                try:
                    shutil.copyfile(file, copia)
                except OSError:
                    continue


def assicura_dizionario(lingua: str = "ita") -> str:
    """Scarica e verifica il dizionario se manca; restituisce la cartella che lo contiene o ''.

    Si prova prima la cartella dell'installazione (cosi' il motore non cambia
    cartella); se non e' scrivibile si usa quella propria, completata con i
    file di corredo. In entrambi i casi il file e' quello ufficiale, con
    l'impronta verificata.
    """
    voce = DIZIONARI.get(lingua)
    if voce is None or not abilitato():
        return ""
    with _BLOCCO:
        if lingua in _TENTATO:
            return ""
        _TENTATO.add(lingua)
    urls, impronta, minimo = voce
    sistema = cartella_tessdata_di_sistema()
    propria = cartella_dizionari_scrivibile()
    candidate = [cartella for cartella in (sistema, propria) if cartella is not None]
    for cartella in candidate:
        esistente = cartella / f"{lingua}.traineddata"
        if esistente.is_file() and hashlib.sha256(esistente.read_bytes()).hexdigest() == impronta:
            if cartella != sistema:
                _completa_cartella(cartella, sistema)
            return str(cartella)
    dati = b""
    for url in urls:
        try:
            scaricati = _scarica(url)
        except Exception as exc:
            logger.warning("Dizionario OCR %s non scaricato da %s: %s", lingua, url, exc)
            continue
        if len(scaricati) < minimo or hashlib.sha256(scaricati).hexdigest() != impronta:
            logger.warning("Dizionario OCR %s da %s non corrisponde all'impronta attesa: scartato.", lingua, url)
            continue
        dati = scaricati
        break
    if not dati:
        return ""
    for cartella in candidate:
        try:
            cartella.mkdir(parents=True, exist_ok=True)
            provvisorio = cartella / f"{lingua}.traineddata.parziale"
            provvisorio.write_bytes(dati)
            provvisorio.replace(cartella / f"{lingua}.traineddata")
        except OSError as exc:
            logger.info("Dizionario OCR %s non salvabile in %s: %s", lingua, cartella, exc)
            continue
        if cartella != sistema:
            _completa_cartella(cartella, sistema)
        logger.info("Dizionario OCR %s installato in %s (SHA-256 verificato).", lingua, cartella)
        return str(cartella)
    return ""


def installa_tesseract_windows(timeout: int = 900) -> bool:
    """Su Windows installa Tesseract con winget dal pacchetto ufficiale; altrove non fa nulla."""
    if platform.system() != "Windows" or not abilitato():
        return False
    with _BLOCCO:
        if "tesseract" in _TENTATO:
            return False
        _TENTATO.add("tesseract")
    comando = [
        "winget", "install", "-e", "--id", PACCHETTO_WINGET, "--silent",
        "--accept-package-agreements", "--accept-source-agreements",
    ]
    try:
        esito = subprocess.run(comando, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Installazione automatica di Tesseract non riuscita: %s", exc)
        return False
    if esito.returncode != 0:
        logger.warning("winget ha risposto %s: %s", esito.returncode, (esito.stderr or esito.stdout or "").strip()[:400])
        return False
    return True


__all__ = ["DIZIONARI", "PACCHETTO_WINGET", "abilitato", "assicura_dizionario", "cartella_dizionari_scrivibile", "cartella_tessdata_di_sistema", "installa_tesseract_windows"]
