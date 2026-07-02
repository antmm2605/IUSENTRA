"""Fetch cortese di pagine pubbliche: robots.txt + rate-limit per dominio.

Colma il gap dei fetcher esistenti (`http_client`, `legal_intelligence`,
`legal_update_source_parsers`): nessuno di essi consulta robots.txt né applica
un intervallo minimo per dominio. Questo wrapper avvolge un `http_get`
iniettabile (default: `OfficialSourceHttpClient.get`, import pigro) e applica:

- guardia URL pubblica locale (solo http/https, niente IP privati/loopback —
  replica minimale del controllo di `lex/retrieval/official_web.py`, che non si
  importa qui perché la sua catena di import è pesante e stubbata nei test);
- robots.txt per dominio con cache: 4xx = consentito (standard de facto),
  errore di rete o 5xx = **negato fail-closed** (coerente con la cultura del
  progetto: in dubbio non si scarica);
- intervallo minimo tra fetch verso lo stesso dominio (`sleep_fn`/`now_fn`
  iniettabili: nei test non si dorme davvero);
- tetto dimensione risposta (`max_bytes`) su Content-Length e sul corpo.

Mai credenziali, mai bypass di paywall, mai retry aggressivi.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from datetime import datetime, timezone
from urllib import robotparser
from urllib.parse import urlsplit

from lex.sources.models import SourceFetchResult

_DEFAULT_USER_AGENT = "IUSENTRA-LexAI/0.1 (ricerca legale governata; contatti: studio legale)"
_BLOCKED_HOSTS = frozenset({"localhost", "localhost.localdomain"})


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _monotonic() -> float:
    import time

    return time.monotonic()


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def is_public_http_url(url: str) -> bool:
    """True solo per URL http/https verso host pubblici (no IP privati/loopback)."""

    try:
        parts = urlsplit(str(url or "").strip())
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return False
    host = parts.hostname.casefold()
    if host in _BLOCKED_HOSTS or host.endswith((".local", ".internal", ".lan")):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "." in host  # nome DNS con almeno un punto
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


class PoliteFetcher:
    def __init__(
        self,
        *,
        http_get: Callable[..., object] | None = None,
        user_agent: str = _DEFAULT_USER_AGENT,
        min_interval_seconds: float = 2.0,
        timeout_seconds: int = 20,
        max_bytes: int = 2_000_000,
        respect_robots: bool = True,
        robots_loader: Callable[[str], str | None] | None = None,
        sleep_fn: Callable[[float], None] = _sleep,
        now_fn: Callable[[], float] = _monotonic,
        iso_now: Callable[[], str] = _iso_now_utc,
    ) -> None:
        self._http_get = http_get
        self.user_agent = user_agent
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.max_bytes = max(1024, int(max_bytes))
        self.respect_robots = bool(respect_robots)
        self._robots_loader = robots_loader
        self._sleep = sleep_fn
        self._now = now_fn
        self._iso_now = iso_now
        self._robots_cache: dict[str, robotparser.RobotFileParser | None] = {}
        self._last_fetch_at: dict[str, float] = {}

    def fetch(self, url: str) -> SourceFetchResult:
        url = str(url or "").strip()
        started = self._now()
        if not is_public_http_url(url):
            return SourceFetchResult(
                url=url,
                status="invalid_url",
                fetched_at=self._iso_now(),
                warnings=["URL non pubblica o schema non ammesso: fetch rifiutato."],
            )
        domain = urlsplit(url).hostname or ""

        if self.respect_robots:
            allowed, robots_warning = self._robots_allows(domain, url)
            if not allowed:
                return SourceFetchResult(
                    url=url,
                    status="robots_blocked",
                    fetched_at=self._iso_now(),
                    warnings=[robots_warning or "robots.txt nega l'accesso alla risorsa."],
                )

        self._respect_rate_limit(domain)
        try:
            response = self._get(url)
        except Exception as exc:  # rete/timeout/HTTP: mai propagare dal fetch cortese
            self._last_fetch_at[domain] = self._now()
            status_code = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
            return SourceFetchResult(
                url=url,
                status="http_error" if status_code else "network_error",
                http_status=status_code,
                fetched_at=self._iso_now(),
                elapsed_ms=int((self._now() - started) * 1000),
                warnings=[f"Fetch non riuscito: {exc}"],
            )
        self._last_fetch_at[domain] = self._now()

        content = bytes(getattr(response, "content", b"") or b"")
        headers = getattr(response, "headers", {}) or {}
        declared = str(headers.get("Content-Length") or "").strip()
        if (declared.isdigit() and int(declared) > self.max_bytes) or len(content) > self.max_bytes:
            return SourceFetchResult(
                url=url,
                status="too_large",
                final_url=str(getattr(response, "url", url)),
                http_status=int(getattr(response, "status_code", 0) or 0),
                content_type=str(headers.get("Content-Type") or ""),
                fetched_at=self._iso_now(),
                elapsed_ms=int((self._now() - started) * 1000),
                warnings=[f"Risposta oltre il limite di {self.max_bytes} byte: scartata."],
            )
        return SourceFetchResult(
            url=url,
            status="ok",
            final_url=str(getattr(response, "url", url)),
            http_status=int(getattr(response, "status_code", 200) or 200),
            content_type=str(headers.get("Content-Type") or ""),
            content=content,
            fetched_at=self._iso_now(),
            elapsed_ms=int((self._now() - started) * 1000),
        )

    # -- interni -----------------------------------------------------------

    def _get(self, url: str):
        if self._http_get is None:
            # Import pigro: il client riusa sessione, user-agent chiaro e delay
            # di cortesia già presenti in lex/sources/http_client.py.
            from lex.sources.http_client import OfficialSourceHttpClient

            client = OfficialSourceHttpClient(timeout=self.timeout_seconds)
            client.session.headers["User-Agent"] = self.user_agent
            self._http_get = client.get
        return self._http_get(url, headers={"User-Agent": self.user_agent})

    def _respect_rate_limit(self, domain: str) -> None:
        if self.min_interval_seconds <= 0:
            return
        last = self._last_fetch_at.get(domain)
        if last is None:
            return
        remaining = self.min_interval_seconds - (self._now() - last)
        if remaining > 0:
            self._sleep(remaining)

    def _robots_allows(self, domain: str, url: str) -> tuple[bool, str]:
        parser = self._robots_for(domain, url)
        if parser is None:
            # Fail-closed: robots non leggibile per errore rete/5xx → negato.
            return False, (
                f"robots.txt di {domain} non leggibile (errore di rete o server): "
                "accesso negato in via prudenziale (fail-closed)."
            )
        if parser.can_fetch(self.user_agent, url):
            return True, ""
        return False, f"robots.txt di {domain} vieta l'accesso a questa risorsa."

    def _robots_for(self, domain: str, url: str) -> robotparser.RobotFileParser | None:
        if domain in self._robots_cache:
            return self._robots_cache[domain]
        parts = urlsplit(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        text: str | None
        if self._robots_loader is not None:
            text = self._robots_loader(robots_url)
        else:
            text = self._download_robots(robots_url)
        parser: robotparser.RobotFileParser | None
        if text is None:
            parser = None  # errore rete/5xx → fail-closed
        else:
            parser = robotparser.RobotFileParser()
            parser.parse(text.splitlines())
        self._robots_cache[domain] = parser
        return parser

    def _download_robots(self, robots_url: str) -> str | None:
        """Scarica robots.txt: 2xx→testo, 4xx→'' (tutto consentito), rete/5xx→None."""

        try:
            response = self._get(robots_url)
        except Exception as exc:
            status_code = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
            if 400 <= status_code < 500:
                return ""
            return None
        status = int(getattr(response, "status_code", 200) or 200)
        if 400 <= status < 500:
            return ""
        if status >= 500:
            return None
        content = getattr(response, "content", b"") or b""
        return content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)


__all__ = ["PoliteFetcher", "is_public_http_url"]
