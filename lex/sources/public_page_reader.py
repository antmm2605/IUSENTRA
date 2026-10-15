"""Lettura pubblica anonima con trasporto nativo e controlli comuni ai siti.

Non effettua ricerche, non promuove fonti nel corpus e non riceve il contesto
privato dello studio. Ogni URL viene letto o conserva un esito esplicito.
"""

from __future__ import annotations

import hashlib
import socket
import ssl
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

from lex.sources.extractors import extract_text_from_bytes
from lex.sources.html_structure import read_html_structure
from lex.sources.polite_fetcher import PoliteFetcher
from pct.mediazione_public_sources import fetch_public, public_url


class PublicPageReader:
    def __init__(self, *, transport=fetch_public):
        self._transport = transport
        self._policy_failures = {}
        self._active_failure = None
        self._fetcher = PoliteFetcher(http_get=self._get, robots_loader=self._load_robots)

    @staticmethod
    def _transport_failure(exc):
        from urllib3.exceptions import NewConnectionError, SSLError
        from urllib3.exceptions import TimeoutError as HttpTimeoutError

        if isinstance(exc, socket.gaierror):
            reason = "Nome del sito non risolvibile: verifica dell'accesso non eseguita."
        elif isinstance(exc, (ssl.SSLError, SSLError)):
            reason = "Connessione sicura al sito non verificabile."
        elif isinstance(exc, NewConnectionError):
            reason = "Connessione al sito non riuscita."
        elif isinstance(exc, (HttpTimeoutError, TimeoutError)):
            reason = "Tempo disponibile per la connessione al sito esaurito."
        elif isinstance(exc, ValueError):
            reason = "Acquisizione rifiutata dai controlli dell'indirizzo o della risposta."
        else:
            reason = "Connessione al sito non riuscita."
        return {"status": "network_error", "reason": reason,
                "error_type": type(exc).__name__}

    @staticmethod
    def _origin(url):
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"

    def _load_robots(self, url):
        try:
            page = self._transport(url, max_bytes=256_000,
                                   user_agent=self._fetcher.user_agent,
                                   before_request=self._assert_anonymous_url)
        except Exception as exc:
            self._policy_failures[self._origin(url)] = self._transport_failure(exc)
            return None
        if page["status"] in {404, 410}:
            return ""
        if page["status"] != 200:
            self._policy_failures[self._origin(url)] = {
                "status": "access_policy_unavailable",
                "reason": f"Regole di accesso del sito non disponibili (HTTP {page['status']}).",
            }
            return None
        return page["body"].decode("utf-8", "replace")

    def _get(self, url, **_kwargs):
        try:
            page = self._transport(url, max_bytes=self._fetcher.max_bytes,
                                   user_agent=self._fetcher.user_agent,
                                   before_request=self._before_redirect)
        except Exception as exc:
            if self._active_failure is None:
                self._active_failure = self._transport_failure(exc)
            raise
        return SimpleNamespace(url=page["url"], status_code=page["status"],
                               headers={"Content-Type": page["content_type"]}, content=page["body"])

    def _before_redirect(self, url):
        try:
            self._assert_anonymous_url(url)
        except ValueError:
            self._active_failure = {"status": "invalid_url",
                                    "reason": "La lettura pubblica anonima non usa credenziali nell'indirizzo."}
            raise
        host = urlsplit(url).hostname or ""
        allowed, reason = self._fetcher._robots_allows(host, url)
        if not allowed:
            self._active_failure = self._policy_failures.get(self._origin(url)) or {
                "status": "robots_blocked", "reason": "Le regole del sito vietano la lettura di questa pagina."}
            raise ValueError(reason)
        policy = self._fetcher._robots_for(host, url)
        delay = float(policy.crawl_delay(self._fetcher.user_agent) or 0)
        rate = policy.request_rate(self._fetcher.user_agent)
        if rate and rate.requests:
            delay = max(delay, rate.seconds / rate.requests)
        if delay > 15:
            self._active_failure = {
                "status": "rate_limited",
                "reason": "Intervallo richiesto dal sito oltre il limite della lettura interattiva.",
            }
            raise ValueError("Intervallo richiesto dal sito oltre il limite della lettura interattiva.")
        self._fetcher.min_interval_seconds = max(2.0, delay)
        self._fetcher._respect_rate_limit(host)

    @staticmethod
    def _assert_anonymous_url(url):
        secret_keys = {"token", "access_token", "api_key", "apikey", "password", "passwd",
                       "authorization", "session", "sessionid", "signature", "x-amz-signature"}
        if any(key.casefold() in secret_keys for key, _ in parse_qsl(urlsplit(url).query)):
            raise ValueError("La lettura pubblica anonima non usa credenziali nell'indirizzo.")

    def read(self, url: str) -> dict:
        try:
            normalized = public_url(url)
            self._assert_anonymous_url(normalized)
        except ValueError:
            return {"url": url, "status": "invalid_url", "text": "",
                    "reason": "Indirizzo pubblico non valido."}
        self._active_failure = None
        fetched = self._fetcher.fetch(normalized)
        result = {"url": normalized, "final_url": fetched.final_url or normalized,
                  "status": fetched.status, "http_status": fetched.http_status,
                  "content_type": fetched.content_type, "fetched_at": fetched.fetched_at,
                  "elapsed_ms": fetched.elapsed_ms, "warnings": list(fetched.warnings),
                  "text": "", "verified_reference": False}
        if fetched.status != "ok":
            failure = self._active_failure or self._policy_failures.get(self._origin(normalized))
            if failure:
                result.update(failure)
                result["warnings"] = [failure["reason"]]
            elif fetched.status == "robots_blocked":
                result["reason"] = "Le regole del sito vietano la lettura di questa pagina."
            return result
        if fetched.http_status != 200:
            return dict(result, status="http_error",
                        reason=f"La pagina richiesta ha restituito HTTP {fetched.http_status}.")
        result["sha256"] = hashlib.sha256(fetched.content).hexdigest()
        try:
            if "html" in fetched.content_type.casefold():
                result.update(read_html_structure(fetched.content, fetched.content_type,
                                                  url=result["final_url"]))
                title = str(result.get("title") or "").strip().casefold()
                # Titoli di risposta tecnica osservabili, non parole generiche
                # come captcha che possono comparire in un vero articolo.
                if len(result["text"]) < 1200 and title in {
                    "request rejected", "access denied", "just a moment...",
                    "iis windows server", "403 forbidden", "verifica di essere umano",
                }:
                    result.update(status="access_interstitial", text="",
                                  reason="Il sito ha restituito una pagina tecnica, non il documento richiesto.")
            else:
                text = extract_text_from_bytes(fetched.content, fetched.content_type,
                                               filename=urlsplit(result["final_url"]).path)
                result.update(text=text, status="read" if text else "empty")
        except Exception:
            result.update(status="extraction_error", reason="Estrazione della fonte non riuscita.")
        return result
