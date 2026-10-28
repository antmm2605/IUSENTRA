"""
Client Normattiva Open Data - download multi-collezione.

Endpoint allineati alla documentazione ufficiale Normattiva Open Data:
- https://dati.normattiva.it/assets/come_fare_per/Normattiva%20OpenData.html
- GET /collections/collection-predefinite
- GET /collections/download/collection-preconfezionata?nome=...&formato=XML&formatoRichiesta=...

Nota sulle etichette di richiesta:
- O/V/M indicano i parametri trasmessi, non una certificazione del testo ricevuto.
- Le raccolte XML di atti abrogati possono restituire il solo avviso di abrogazione
  anche con O: originalità, versione e corpo vanno riscontrati sul documento.
- Per la successione ufficiale dei testi usare l'export AKN multiversione e il
  lettore dedicato, conservando payload, SHA e date FRBR/fotogrammi distinti.
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


CERTIFICATI_INTERMEDI = Path(__file__).resolve().parent / "certificati"


def bundle_ca_normattiva() -> str | bool:
    """CA di sistema + certificati intermedi che api.normattiva.it non invia.

    Il server Normattiva presenta solo il proprio certificato, senza l'intermedio
    "GlobalSign GCC R46 OV TLS CA 2025": Python (certifi) non completa la catena e la
    connessione fallisce con CERTIFICATE_VERIFY_FAILED. L'intermedio pubblico e' incluso nel
    repository; la verifica TLS resta attiva. ``LEX_NORMATTIVA_CA_BUNDLE`` permette di indicare
    un bundle diverso.
    """

    import os
    import tempfile

    esplicito = str(os.getenv("LEX_NORMATTIVA_CA_BUNDLE", "") or "").strip()
    if esplicito:
        return esplicito
    intermedi = sorted(CERTIFICATI_INTERMEDI.glob("*.pem"))
    if not intermedi:
        return True
    base = str(os.getenv("REQUESTS_CA_BUNDLE", "") or "").strip()
    if not base:
        try:
            import certifi

            base = certifi.where()
        except Exception:
            return True
    try:
        contenuto = Path(base).read_bytes() + b"\n" + b"\n".join(p.read_bytes() for p in intermedi)
        impronta = hashlib.sha256(contenuto).hexdigest()[:16]
        destinazione = Path(tempfile.gettempdir()) / f"iusentra_normattiva_ca_{impronta}.pem"
        if not destinazione.exists():
            provvisorio = destinazione.with_suffix(f".{os.getpid()}.tmp")
            provvisorio.write_bytes(contenuto)
            os.replace(provvisorio, destinazione)
        return str(destinazione)
    except OSError:
        return True


def _sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


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
        if session is None:
            self.session.verify = bundle_ca_normattiva()

    def list_collections_raw(self) -> Any:
        response = self.session.get(COLLECTIONS_URL, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def list_collection_names(self) -> list[str]:
        raw = self.list_collections_raw()
        names = sorted(set(_extract_collection_names(raw)), key=lambda x: x.lower())
        return names

    def _get_public_download(self, url: str, **kwargs):
        """Un solo retry di connessione per GET pubbliche idempotenti.

        Le risposte HTTP, compresi 403/429, restano al chiamante e non vengono
        ritentate. Non avvia nuove esportazioni asincrone.
        """
        for attempt in range(2):
            try:
                return self.session.get(url, **kwargs)
            except requests.exceptions.SSLError:
                raise
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt:
                    raise
                import logging
                logging.getLogger(__name__).warning("Normattiva download pubblico: %s, unico retry di connessione",type(exc).__name__)
                time.sleep(2)
        raise RuntimeError("Limite tentativi download pubblico")

    def download_collection(
        self,
        name: str,
        *,
        output_dir: str | Path,
        formato: str = "XML",
        vigenza: str = "ORIGINALE",
        formato_richiesta: str | None = None,
        overwrite: bool = False,
        replace_existing: bool = False,
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
            return DownloadResult(
                collection_name=name,
                formato=formato.upper(),
                vigenza=vigenza_norm,
                formato_richiesta=formato_richiesta,
                url=DOWNLOAD_COLLECTION_URL,
                output_path=str(out_path),
                sha256=_sha256_file(out_path),
                size_bytes=out_path.stat().st_size,
                content_type="existing-file",
                final_url="existing-file",
            )

        response = self._get_public_download(
            DOWNLOAD_COLLECTION_URL,
            params=params,
            headers={"Accept-Encoding": "identity"},
            timeout=self.timeout,
            allow_redirects=True,
            stream=True,
        )

        # Se Normattiva risponde con 302, requests segue il token temporaneo /file-download/...
        # Se ricevi 403/429, non forzare: riduci frequenza e verifica condizioni d'uso.
        response.raise_for_status()

        content_type = response.headers.get("content-type")
        tmp_path = out_path.with_suffix(".zip.part")
        if tmp_path.exists():
            # Un nuovo tentativo non distrugge i byte del precedente.
            previous=tmp_path.with_name(tmp_path.name+".interrotto-"+str(time.time_ns()))
            if previous.exists():
                raise FileExistsError("Destinazione di conservazione parziale già presente")
            tmp_path.rename(previous)
        sha = hashlib.sha256()
        size = 0

        try:
            with tmp_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    f.write(chunk)
                    sha.update(chunk)
                    size += len(chunk)
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError):
            from .trasferimento import riprendi_download_zip
            response.close()
            riprendi_download_zip(self.session,response,tmp_path,timeout=self.timeout)
            size=tmp_path.stat().st_size
            with tmp_path.open("rb") as source:
                sha=hashlib.file_digest(source,"sha256")

        with tmp_path.open("rb") as source:
            preview_bytes=source.read(500)
        first_bytes=preview_bytes[:4]
        if not first_bytes.startswith(b"PK"):
            # Alcuni errori applicativi possono arrivare come JSON/HTML con status 200.
            preview = preview_bytes.decode("utf-8", errors="replace")
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Il file scaricato non sembra uno ZIP. "
                f"content-type={content_type!r}; preview={preview!r}"
            )

        existing_files = sorted(out_dir.glob(f"{safe_name}_{formato.upper()}_{vigenza_norm}_*.zip"))
        for existing in existing_files:
            if existing == out_path or not existing.is_file():
                continue
            try:
                if _sha256_file(existing) == sha.hexdigest():
                    tmp_path.unlink(missing_ok=True)
                    return DownloadResult(
                        collection_name=name,
                        formato=formato.upper(),
                        vigenza=vigenza_norm,
                        formato_richiesta=formato_richiesta,
                        url=response.request.url,
                        output_path=str(existing),
                        sha256=sha.hexdigest(),
                        size_bytes=size,
                        content_type="existing-sha",
                        final_url=response.url,
                    )
            except OSError:
                continue

        if replace_existing:
            for existing in existing_files:
                if existing == out_path or not existing.is_file():
                    continue
                existing.unlink(missing_ok=True)

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

    def request_export(self, filters: dict[str, Any], *, formato: str = "XML", vigenza: str = "V") -> str:
        """Esportazione ufficiale responsive, senza email e senza dati privati.

        Il limite ufficiale di 7000 atti resta applicato dal servizio. Il
        chiamante salva token e intervallo prima di effettuare altre richieste.
        """
        import uuid

        if vigenza not in {"O", "V", "M"} or formato not in {"XML", "AKN"}:
            raise ValueError("Formato di esportazione non ammesso")
        allowed = {"denominazioneAtto", "numeroProvvedimento", "annoProvvedimento", "meseProvvedimento",
                   "giornoProvvedimento", "dataInizioEmanazione", "dataFineEmanazione",
                   "dataInizioPubblicazione", "dataFinePubblicazione", "dataVigenza"}
        if not isinstance(filters, dict) or not filters or set(filters) - allowed:
            raise ValueError("Sono ammessi soltanto filtri normativi strutturati, mai fatti o testi privati")
        for name, value in filters.items():
            if name == "denominazioneAtto":
                if not isinstance(value, str) or not value or len(value) > 150:
                    raise ValueError("Tipo di atto non valido")
            elif name.startswith("data"):
                from datetime import datetime
                if not isinstance(value, str):
                    raise ValueError("Data del filtro non valida")
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            elif type(value) is not int or value < 0:
                raise ValueError("Identificatore normativo non valido")
        response = self.session.post(
            API_BASE + "/bff-opendata/v1/api/v1/ricerca-asincrona/nuova-ricerca",
            json={"formato": formato, "richiestaExport": vigenza, "modalita": "R",
                  "tipoRicerca": "A", "parametriRicerca": filters}, timeout=self.timeout,
        )
        response.raise_for_status()
        token = response.text.strip().strip('"')
        if str(uuid.UUID(token)) != token.lower():
            raise ValueError("Token di esportazione non valido")
        return token

    def export_status(self, token: str) -> dict[str, Any]:
        import uuid

        token = str(uuid.UUID(token))
        response = self.session.get(
            API_BASE + "/bff-opendata/v1/api/v1/ricerca-asincrona/check-status/" + token,
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or type(result.get("stato")) is not int:
            raise ValueError("Stato di esportazione non valido")
        return result

    def download_export(self, token: str, *, output: Path) -> dict[str, Any]:
        """Scarica il solo token ufficiale e conserva SHA e archivio originale."""
        import uuid
        import zipfile

        token = str(uuid.UUID(token))
        output = Path(output)
        if output.exists():
            raise FileExistsError("Archivio già presente: verificare l'impronta prima di riutilizzarlo")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".part")
        if temporary.exists():
            raise FileExistsError("Download parziale presente: non sovrascriverlo")
        response = self._get_public_download(
            API_BASE + "/bff-opendata/v1/api/v1/collections/download/collection-asincrona/" + token,
            headers={"Accept-Encoding": "identity"}, timeout=self.timeout, stream=True,
        )
        response.raise_for_status()
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary.open("xb") as target:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        target.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError):
            from .trasferimento import riprendi_download_zip
            response.close()
            riprendi_download_zip(self.session,response,temporary,timeout=self.timeout)
            size=temporary.stat().st_size
            with temporary.open("rb") as source:
                digest=hashlib.file_digest(source,"sha256")
        with zipfile.ZipFile(temporary) as archive:
            if not any(info.filename.lower().endswith(".xml") and not info.is_dir() for info in archive.infolist()):
                raise ValueError("Esportazione senza documenti XML: il parziale è conservato, nessuna fonte è stata acquisita")
            if archive.testzip() is not None:
                raise ValueError("Archivio ufficiale non integro")
        temporary.replace(output)
        from datetime import datetime, timezone
        return {"output_path": str(output), "sha256": digest.hexdigest(), "size_bytes": size,
                "ricevuto_utc":datetime.now(timezone.utc).isoformat(),
                "fonte": "Normattiva OpenData — esportazione responsive"}

    def download_many(
        self,
        names: Iterable[str],
        *,
        output_dir: str | Path,
        formato: str = "XML",
        vigenza: str = "ORIGINALE",
        formato_richiesta: str | None = None,
        overwrite: bool = False,
        replace_existing: bool = False,
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
                    replace_existing=replace_existing,
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


def write_manifest(
    results: list[DownloadResult],
    path: str | Path,
    *,
    previous_items: list[dict[str, Any]] | None = None,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    result_items = [r.__dict__ for r in results]
    replaced = {
        (
            str(item.get("collection_name") or ""),
            str(item.get("formato") or ""),
            str(item.get("vigenza") or ""),
            str(item.get("formato_richiesta") or ""),
        )
        for item in result_items
    }
    items = [
        item
        for item in list(previous_items or [])
        if (
            str(item.get("collection_name") or ""),
            str(item.get("formato") or ""),
            str(item.get("vigenza") or ""),
            str(item.get("formato_richiesta") or ""),
        )
        not in replaced
    ]
    items.extend(result_items)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(items),
        "items": items,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
