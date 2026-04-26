from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from ..models import DocumentCandidate, SourceConfig
from .base import BaseConnector


@dataclass(frozen=True)
class GazzettaIssue:
    listing_url: str
    source_url: str
    download_url: str
    data_pubblicazione: str
    numero_gazzetta: str
    tipo_serie: str
    tipo_supplemento: str
    numero_supplemento: str
    progressivo: str
    edizione: str

    @property
    def key(self) -> tuple[str, str, str, str, str, str, str]:
        return (
            self.data_pubblicazione,
            self.numero_gazzetta,
            self.tipo_serie,
            self.tipo_supplemento,
            self.numero_supplemento,
            self.progressivo,
            self.edizione,
        )


class GazzettaUfficialeConnector(BaseConnector):
    """Connettore per Gazzetta Ufficiale basato sugli endpoint catturati.

    Endpoint individuati da capture browser/F12:
    - elenco ultimi 30 giorni: https://www.gazzettaufficiale.it/30giorni/serie_generale
    - PDF paginato: /do/gazzetta/serie_generale/0/pdfPaginato?...&numPagina=1...
    - download PDF pagina/fascicolo: /do/gazzetta/downloadPdf?...&estensione=pdf...

    Il connettore scarica il fascicolo PDF intero quando possibile, rimuovendo
    numPagina/home/elenco30giorni dai link paginati.
    """

    DEFAULT_SERIES_PAGES = [
        {
            "id": "serie_generale",
            "name": "Serie Generale - ultimi 30 giorni",
            "url": "https://www.gazzettaufficiale.it/30giorni/serie_generale",
            "tipo_serie": "SG",
        }
    ]

    DOWNLOAD_PATH = "/do/gazzetta/downloadPdf"
    PAGINATED_PATH_RE = re.compile(r"/do/gazzetta/.*/pdfPaginato", re.I)

    def fetch(self, output_dir: Path) -> Iterable[tuple[DocumentCandidate, Path]]:
        settings = self.source.settings or {}
        series_pages = settings.get("series_pages") or self.DEFAULT_SERIES_PAGES
        max_issues = int(settings.get("max_issues", 20))
        min_date = str(settings.get("min_date", "")).strip()  # formato YYYYMMDD, opzionale
        only_series = {str(x).upper() for x in settings.get("only_tipo_serie", []) if str(x).strip()}

        seen: set[tuple[str, str, str, str, str, str, str]] = set()
        yielded = 0

        for page in series_pages:
            if yielded >= max_issues:
                break

            listing_url = str(page.get("url") or "").strip()
            if not listing_url:
                continue

            html_response = self.client.get(
                listing_url,
                headers={"Referer": self.source.base_url or "https://www.gazzettaufficiale.it/"},
            )
            html = html_response.text

            for issue in self._extract_issues_from_html(html, listing_url):
                if yielded >= max_issues:
                    break
                if issue.key in seen:
                    continue
                if min_date and issue.data_pubblicazione < min_date:
                    continue
                if only_series and issue.tipo_serie.upper() not in only_series:
                    continue

                seen.add(issue.key)

                response = self.client.get(
                    issue.download_url,
                    headers={"Referer": issue.listing_url},
                    allow_redirects=True,
                )
                content_type = response.headers.get("content-type", "application/pdf")
                content = response.content

                # Evita di salvare pagine HTML di errore spacciate per download.
                if b"%PDF" not in content[:1024] and "pdf" not in content_type.lower():
                    continue

                filename = self._filename(issue)
                path = self._write_content(output_dir, filename, content)
                doc = DocumentCandidate(
                    source_id=self.source.id,
                    title=self._title(issue),
                    url=issue.download_url,
                    content_type="application/pdf",
                    filename=filename,
                    published_at=self._iso_date(issue.data_pubblicazione),
                    topics=list(self.source.topics or []),
                    metadata={
                        "fonte": "Gazzetta Ufficiale",
                        "listing_url": issue.listing_url,
                        "source_url": issue.source_url,
                        "dataPubblicazioneGazzetta": issue.data_pubblicazione,
                        "numeroGazzetta": issue.numero_gazzetta,
                        "tipoSerie": issue.tipo_serie,
                        "tipoSupplemento": issue.tipo_supplemento,
                        "numeroSupplemento": issue.numero_supplemento,
                        "progressivo": issue.progressivo,
                        "edizione": issue.edizione,
                        "endpoint_type": "downloadPdf",
                    },
                )
                yielded += 1
                yield doc, path

    def _extract_issues_from_html(self, html: str, listing_url: str) -> list[GazzettaIssue]:
        soup = BeautifulSoup(html, "html.parser")
        hrefs: list[str] = []
        for a in soup.find_all("a", href=True):
            href = str(a.get("href") or "").strip()
            if not href:
                continue
            if "downloadPdf" in href or "pdfPaginato" in href:
                hrefs.append(urljoin(listing_url, href))

        # Alcuni link possono essere dentro onclick/script.
        for match in re.finditer(r"(?:href=|window\.open\(|location\.href\s*=)?['\"]([^'\"]*(?:downloadPdf|pdfPaginato)[^'\"]*)['\"]", html):
            hrefs.append(urljoin(listing_url, match.group(1)))

        issues: list[GazzettaIssue] = []
        seen: set[tuple[str, str, str, str, str, str, str]] = set()
        for href in hrefs:
            issue = self._issue_from_url(href, listing_url)
            if not issue:
                continue
            if issue.key in seen:
                continue
            seen.add(issue.key)
            issues.append(issue)

        # Ordina dal piu' recente al meno recente, poi per numero decrescente.
        issues.sort(key=lambda x: (x.data_pubblicazione, int(x.numero_gazzetta or "0")), reverse=True)
        return issues

    def _issue_from_url(self, url: str, listing_url: str) -> GazzettaIssue | None:
        parsed = urlparse(url)
        qs = {k: v[-1] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}

        required = ["dataPubblicazioneGazzetta", "numeroGazzetta", "tipoSerie"]
        if any(not qs.get(k) for k in required):
            return None

        download_url = self._to_full_issue_download_url(url, qs)
        return GazzettaIssue(
            listing_url=listing_url,
            source_url=url,
            download_url=download_url,
            data_pubblicazione=str(qs.get("dataPubblicazioneGazzetta", "")),
            numero_gazzetta=str(qs.get("numeroGazzetta", "")),
            tipo_serie=str(qs.get("tipoSerie", "")),
            tipo_supplemento=str(qs.get("tipoSupplemento", "GU")),
            numero_supplemento=str(qs.get("numeroSupplemento", "0")),
            progressivo=str(qs.get("progressivo", "0")),
            edizione=str(qs.get("edizione", "0")),
        )

    def _to_full_issue_download_url(self, url: str, qs: dict[str, str]) -> str:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}{self.DOWNLOAD_PATH}"

        allowed_keys = [
            "dataPubblicazioneGazzetta",
            "numeroGazzetta",
            "tipoSerie",
            "tipoSupplemento",
            "numeroSupplemento",
            "progressivo",
            "estensione",
            "edizione",
        ]
        clean = {k: qs[k] for k in allowed_keys if k in qs and qs[k] not in {None, ""}}
        clean.setdefault("tipoSupplemento", "GU")
        clean.setdefault("numeroSupplemento", "0")
        clean.setdefault("progressivo", "0")
        clean.setdefault("estensione", "pdf")
        clean.setdefault("edizione", "0")

        return urlunparse((parsed.scheme, parsed.netloc, self.DOWNLOAD_PATH, "", urlencode(clean), ""))

    def _filename(self, issue: GazzettaIssue) -> str:
        num = str(issue.numero_gazzetta).zfill(3)
        parts = ["GU", issue.tipo_serie or "SERIE", issue.data_pubblicazione, num]
        if issue.tipo_supplemento and issue.tipo_supplemento != "GU":
            parts.extend([issue.tipo_supplemento, issue.numero_supplemento or "0"])
        if issue.progressivo and issue.progressivo != "0":
            parts.append(f"prog{issue.progressivo}")
        return "_".join(parts) + ".pdf"

    def _title(self, issue: GazzettaIssue) -> str:
        date_it = self._date_it(issue.data_pubblicazione)
        serie = self._series_label(issue.tipo_serie)
        return f"Gazzetta Ufficiale - {serie} n. {issue.numero_gazzetta} del {date_it}"

    @staticmethod
    def _series_label(tipo_serie: str) -> str:
        mapping = {
            "SG": "Serie Generale",
            "1SS": "1a Serie Speciale",
            "2SS": "2a Serie Speciale",
            "3SS": "3a Serie Speciale",
            "4SS": "4a Serie Speciale",
            "5SS": "5a Serie Speciale",
        }
        return mapping.get((tipo_serie or "").upper(), tipo_serie or "Serie")

    @staticmethod
    def _iso_date(yyyymmdd: str) -> str | None:
        if not re.fullmatch(r"\d{8}", yyyymmdd or ""):
            return None
        return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"

    @staticmethod
    def _date_it(yyyymmdd: str) -> str:
        if not re.fullmatch(r"\d{8}", yyyymmdd or ""):
            return yyyymmdd
        return f"{yyyymmdd[6:8]}/{yyyymmdd[4:6]}/{yyyymmdd[0:4]}"
