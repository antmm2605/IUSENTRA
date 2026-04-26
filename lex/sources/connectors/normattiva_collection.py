from __future__ import annotations

from datetime import datetime
from pathlib import Path
from .base import BaseConnector
from ..models import DocumentCandidate
from ..http_client import sanitize_filename


DEFAULT_COLLECTIONS_ENDPOINT = "https://api.normattiva.it/t/normattiva.api/bff-opendata/v1/api/v1/collections/collection-predefinite"
DEFAULT_DOWNLOAD_ENDPOINT = "https://api.normattiva.it/t/normattiva.api/bff-opendata/v1/api/v1/collections/download/collection-preconfezionata"


class NormattivaCollectionConnector(BaseConnector):
    """Scarica collezioni preconfezionate Normattiva.

    Endpoint derivato da cattura browser/F12: il download reale passa da
    /collections/download/collection-preconfezionata con parametri nome, formato,
    formatoRichiesta e poi 302 verso /file-download/v1/download/<token>.
    """

    def fetch(self, output_dir: Path):
        settings = self.source.settings
        if settings.get("download_enabled") is False:
            return

        collections = settings.get("collections") or []
        formato = settings.get("formato", "XML")
        formato_richiesta = settings.get("formato_richiesta") or ("V" if str(settings.get("vigenza", "")).upper() == "VIGENTE" else "O")
        endpoint_download = settings.get("endpoint_download") or DEFAULT_DOWNLOAD_ENDPOINT

        for collection_name in collections:
            params = {
                "nome": collection_name,
                "formato": formato,
                "formatoRichiesta": formato_richiesta,
            }
            headers = {
                "Origin": "https://dati.normattiva.it",
                "Referer": "https://dati.normattiva.it/home",
                "Accept": "application/json, text/plain, */*",
            }
            response = self.client.get(endpoint_download, params=params, headers=headers, allow_redirects=True)
            stamp = datetime.now().strftime("%Y-%m-%d")
            filename = sanitize_filename(f"{collection_name}_{formato}_{formato_richiesta}_{stamp}.zip")
            path = self._write_content(output_dir, filename, response.content)
            yield DocumentCandidate(
                source_id=self.source.id,
                title=f"Normattiva - {collection_name}",
                url=response.url,
                content_type=response.headers.get("content-type", "application/octet-stream"),
                filename=filename,
                topics=self.source.topics,
                metadata={
                    "connector": "normattiva_collection",
                    "collection": collection_name,
                    "formato": formato,
                    "formato_richiesta": formato_richiesta,
                    "endpoint": endpoint_download,
                    "note": "URL finale con token temporaneo: non salvarlo come endpoint stabile.",
                },
            ), path

    def list_collections(self) -> list:
        endpoint = self.source.settings.get("endpoint_collections") or DEFAULT_COLLECTIONS_ENDPOINT
        if not endpoint:
            return []
        response = self.client.get(endpoint, headers={"Origin": "https://dati.normattiva.it", "Referer": "https://dati.normattiva.it/home"})
        try:
            return response.json()
        except Exception:
            return []
