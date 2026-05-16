"""
Client Normattiva Open Data - download multi-collezione.

Endpoint ricavati da capture browser:
- GET /collections/collection-predefinite
- GET /collections/download/collection-preconfezionata?nome=...&formato=XML&formatoRichiesta=...

Nota:
- formatoRichiesta="O" è verificato per ORIGINALE.
- formatoRichiesta="V" è predisposto per VIGENTE ma va confermato con un capture VIGENTE se il server lo rifiuta.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import hashlib
import json
import re
import time
import unicodedata

import requests


API_BASE = "https://api.normattiva.it/t/normattiva.api"
COLLECTIONS_URL = f"{API_BASE}/bff-opendata/v1/api/v1/collections/collection-predefinite"
DOWNLOAD_COLLECTION_URL = f"{API_BASE}/bff-opendata/v1/api/v1/collections/download/collection-preconfezionata"

VIGENZA_TO_FORMATO_RICHIESTA = {
    "ORIGINALE": "O",
    "VIGENTE": "V",
}

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://dati.normattiva.it",
    "Referer": "https://dati.normattiva.it/home",
    "User-Agent": "IUSENTRA-Normattiva-Sync/1.0 (+studio-legale)",
}


@dataclass(frozen=True)
class DownloadResult:
    collection_name: str
    formato: str
    vigenza: str
    formato_richiesta: str
    url: str
    output_path: str
    sha256: str
    size_bytes: int
    content_type: str | None
    final_url: str


class NormattivaClient:
    def __init__(
        self,
        *,
        timeout: int = 180,
        sleep_seconds: float = 2.0,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def list_collections_raw(self) -> Any:
        response = self.session.get(COLLECTIONS_URL, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def list_collection_names(self) -> list[str]:
        raw = self.list_collections_raw()
        names = sorted(set(_extract_collection_names(raw)), key=lambda x: x.lower())
        return names

    def download_collection(
        self,
        name: str,
        *,
        output_dir: str | Path,
        formato: str = "XML",
        vigenza: str = "ORIGINALE",
        formato_richiesta: str | None = None,
        overwrite: bool = False,
    ) -> DownloadResult:
        vigenza_norm = vigenza.strip().upper()
        formato_richiesta = formato_richiesta or VIGENZA_TO_FORMATO_RICHIESTA.get(vigenza_norm)

        if not formato_richiesta:
            raise ValueError(
                f"Vigenza non supportata: {vigenza!r}. "
                "Usa formato_richiesta esplicito, es. --formato-richiesta O"
            )

        params = {
            "nome": name,
            "formato": formato.upper(),
            "formatoRichiesta": formato_richiesta,
        }

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        today = time.strftime("%Y-%m-%d")
        safe_name = _safe_filename(name)
        out_path = out_dir / f"{safe_name}_{formato.upper()}_{vigenza_norm}_{today}.zip"

        if out_path.exists() and not overwrite:
            data = out_path.read_bytes()
            return DownloadResult(
                collection_name=name,
                formato=formato.upper(),
                vigenza=vigenza_norm,
                formato_richiesta=formato_richiesta,
                url=DOWNLOAD_COLLECTION_URL,
                output_path=str(out_path),
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                content_type="existing-file",
                final_url="existing-file",
            )

        response = self.session.get(
            DOWNLOAD_COLLECTION_URL,
            params=params,
            timeout=self.timeout,
            allow_redirects=True,
            stream=True,
        )

        # Se Normattiva risponde con 302, requests segue il token temporaneo /file-download/...
        # Se ricevi 403/429, non forzare: riduci frequenza e verifica condizioni d'uso.
        response.raise_for_status()

        content_type = response.headers.get("content-type")
        tmp_path = out_path.with_suffix(".zip.part")
        sha = hashlib.sha256()
        size = 0

        with tmp_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                f.write(chunk)
                sha.update(chunk)
                size += len(chunk)

        first_bytes = tmp_path.read_bytes()[:4]
        if not first_bytes.startswith(b"PK"):
            # Alcuni errori applicativi possono arrivare come JSON/HTML con status 200.
            preview = tmp_path.read_bytes()[:500].decode("utf-8", errors="replace")
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Il file scaricato non sembra uno ZIP. "
                f"content-type={content_type!r}; preview={preview!r}"
            )

        tmp_path.replace(out_path)

        return DownloadResult(
            collection_name=name,
            formato=formato.upper(),
            vigenza=vigenza_norm,
            formato_richiesta=formato_richiesta,
            url=response.request.url,
            output_path=str(out_path),
            sha256=sha.hexdigest(),
            size_bytes=size,
            content_type=content_type,
            final_url=response.url,
        )

    def download_many(
        self,
        names: Iterable[str],
        *,
        output_dir: str | Path,
        formato: str = "XML",
        vigenza: str = "ORIGINALE",
        formato_richiesta: str | None = None,
        overwrite: bool = False,
    ) -> list[DownloadResult]:
        results: list[DownloadResult] = []
        for index, name in enumerate(names, start=1):
            print(f"[{index}] download: {name}")
            try:
                result = self.download_collection(
                    name,
                    output_dir=output_dir,
                    formato=formato,
                    vigenza=vigenza,
                    formato_richiesta=formato_richiesta,
                    overwrite=overwrite,
                )
            except Exception as exc:
                print(f"[ERRORE] {name}: {exc}")
                time.sleep(self.sleep_seconds)
                continue
            results.append(result)
            time.sleep(self.sleep_seconds)
        return results


def _extract_collection_names(obj: Any) -> list[str]:
    """
    Estrae nomi di collezioni anche se la struttura JSON cambia.
    Preferisce chiavi italiane/inglesi probabili.
    """
    names: list[str] = []

    if isinstance(obj, dict):
        for key in ("nomeCollezione", "nome", "name", "titolo", "title", "descrizione", "description", "label"):
            value = obj.get(key)
            if isinstance(value, str) and _looks_like_collection_name(value):
                names.append(value.strip())

        for value in obj.values():
            names.extend(_extract_collection_names(value))

    elif isinstance(obj, list):
        for item in obj:
            names.extend(_extract_collection_names(item))

    return names


def _looks_like_collection_name(value: str) -> bool:
    v = value.strip()
    if not v or len(v) < 3 or len(v) > 160:
        return False

    deny = {
        "xml", "json", "pdf", "originale", "vigente", "html",
        "true", "false", "null",
    }
    if v.lower() in deny:
        return False

    # Le collezioni Normattiva sono descrittive: Codici, DPR, Testi Unici, Decreti...
    keywords = (
        "atti", "codici", "decreti", "decreto", "leggi", "legge", "dpcm",
        "dpr", "regolamenti", "testi unici", "dl", "regi"
    )
    return any(k in v.lower() for k in keywords)


def _safe_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name)
    ascii_name = re.sub(r"_+", "_", ascii_name).strip("._-")
    return ascii_name[:120] or "normattiva_collection"


def write_manifest(results: list[DownloadResult], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(results),
        "items": [r.__dict__ for r in results],
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
