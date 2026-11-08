"""Lettura limitata dei canali ufficiali: solo HTTPS, solo host dell'ente, tempo e dimensione massimi.

Un canale lento o irraggiungibile solleva `ErroreFonte` con un messaggio in italiano:
il giro lo registra come stato della fonte e passa alle altre.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests

RequestGet = Callable[..., Any]

TIMEOUT = (6, 20)  # connessione, lettura
DIMENSIONE_MASSIMA = 3 * 1024 * 1024
_REINDIRIZZAMENTI = 3
_INTESTAZIONI = {
    "User-Agent": "Mozilla/5.0 (compatible; IUSENTRA/1.0; +https://app.iusentra.it)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "Accept-Language": "it-IT,it;q=0.9",
}


class ErroreFonte(RuntimeError):
    """La fonte non ha restituito un contenuto leggibile."""


def _ammesso(url: str, host_ammessi: tuple[str, ...]) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in host_ammessi


def scarica(url: str, host_ammessi: tuple[str, ...], *, request_get: RequestGet = requests.get) -> bytes:
    """Contenuto del canale, seguendo al massimo tre reindirizzamenti verso host ammessi."""
    corrente = url
    for _ in range(_REINDIRIZZAMENTI + 1):
        if not _ammesso(corrente, host_ammessi):
            raise ErroreFonte("Indirizzo non ammesso per questa fonte istituzionale.")
        try:
            risposta = request_get(corrente, headers=_INTESTAZIONI, timeout=TIMEOUT, allow_redirects=False, stream=True)
        except requests.Timeout as exc:
            raise ErroreFonte("La fonte non ha risposto entro il tempo massimo.") from exc
        except requests.RequestException as exc:
            raise ErroreFonte("La fonte non è raggiungibile in questo momento.") from exc
        stato = int(getattr(risposta, "status_code", 0) or 0)
        if stato in {301, 302, 303, 307, 308}:
            destinazione = str(getattr(risposta, "headers", {}).get("Location") or "").strip()
            if not destinazione:
                raise ErroreFonte("La fonte ha restituito un reindirizzamento non valido.")
            corrente = urljoin(corrente, destinazione)
            continue
        if stato != 200:
            raise ErroreFonte(f"La fonte ha risposto con lo stato {stato}.")
        return _corpo_limitato(risposta)
    raise ErroreFonte("La fonte ha superato il numero massimo di reindirizzamenti.")


def _corpo_limitato(risposta: Any) -> bytes:
    iter_content = getattr(risposta, "iter_content", None)
    if not callable(iter_content):
        corpo = bytes(getattr(risposta, "content", b"") or b"")
    else:
        parti: list[bytes] = []
        letti = 0
        for parte in iter_content(chunk_size=65536):
            letti += len(parte)
            if letti > DIMENSIONE_MASSIMA:
                raise ErroreFonte("Il contenuto della fonte supera la dimensione ammessa.")
            parti.append(parte)
        corpo = b"".join(parti)
    if len(corpo) > DIMENSIONE_MASSIMA:
        raise ErroreFonte("Il contenuto della fonte supera la dimensione ammessa.")
    if not corpo.strip():
        raise ErroreFonte("La fonte ha restituito un contenuto vuoto.")
    return corpo


__all__ = ["ErroreFonte", "RequestGet", "scarica"]
