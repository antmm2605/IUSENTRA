"""Risorse del server misurate dalla catena: memoria libera, coda OCR, scaricamento dell'AI locale."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.request
from contextlib import closing
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def memoria_libera_mb(meminfo: str = "/proc/meminfo") -> int:
    """MemAvailable in MB (0 se non leggibile: la catena allora non aspetta)."""
    try:
        for riga in Path(meminfo).read_text(encoding="ascii").splitlines():
            if riga.startswith("MemAvailable:"):
                return int(riga.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def ocr_in_coda(config: dict[str, Any]) -> int:
    """Documenti in attesa nella coda del worker OCR (sola lettura)."""
    percorso = str(os.getenv("PCT_OCR_QUEUE_DB", "")).strip()
    if not percorso:
        indice = config.get("SEARCH_INDEX") or os.getenv("PCT_SEARCH_INDEX", "")
        if not indice:
            return 0
        percorso = str(Path(str(indice)).parent / "ocr_jobs.db")
    if not Path(percorso).exists():
        return 0
    try:
        with closing(sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=10)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM ocr_jobs WHERE status IN ('pending','running')").fetchone()
        return int(row[0] if row else 0)
    except sqlite3.Error:
        return 0


def _base_ollama() -> str:
    url = os.getenv("PCT_OLLAMA_URL") or os.getenv("OLLAMA_URL") or os.getenv("PCT_LOCAL_AI_BASE_URL") or ""
    url = url.strip() or "http://ollama:11434"
    return url.split("/api/")[0].rstrip("/")


def scarica_ai_locale(timeout: float = 10.0) -> list[str]:
    """Chiede a Ollama di scaricare dalla memoria i modelli caricati (keep_alive=0). Mai bloccante."""
    base = _base_ollama()
    scaricati: list[str] = []
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=timeout) as risposta:  # noqa: S310 - host interno
            modelli = json.loads(risposta.read().decode("utf-8") or "{}").get("models") or []
    except Exception as exc:  # AI locale assente o spenta: nulla da scaricare
        logger.info("[notte] AI locale non raggiungibile per lo scaricamento: %s", type(exc).__name__)
        return scaricati
    for modello in modelli:
        nome = str(modello.get("name") or modello.get("model") or "")
        if not nome:
            continue
        percorso = "/api/embed" if "embed" in nome else "/api/generate"
        corpo = {"model": nome, "keep_alive": 0}
        if percorso == "/api/embed":
            corpo["input"] = ""
        richiesta = urllib.request.Request(f"{base}{percorso}", data=json.dumps(corpo).encode("utf-8"),
                                           headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(richiesta, timeout=timeout):  # noqa: S310 - host interno
                scaricati.append(nome)
        except Exception as exc:
            logger.info("[notte] Modello %s non scaricato: %s", nome, type(exc).__name__)
    return scaricati
