"""Bounded anonymous public GETs and evidence extraction, never legal submissions."""
from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import urllib3
from lxml import html

from pct.mediazione_directory_repository import utc_now

USER_AGENT = "Iusentra-Mediazione-Directory/1.0"
MAX_BYTES = 2_000_000
LINK_KINDS = (
    ("modulistica", r"modulistic|moduli.*mediaz|mediaz.*moduli"),
    ("istanza", r"istanza|domanda.*mediaz|mediaz.*domanda"),
    ("adesione", r"adesion"), ("procura", r"procur|delega.*concil"),
    ("proroga", r"prorog"), ("proposta", r"proposta.*concil|concil.*proposta"),
    ("verbale", r"verbale"), ("incarico", r"conferimento.*incarico|incarico.*profession"),
    ("regolamento", r"regolament"),
    ("tariffe", r"tariff|spese.*mediaz|mediaz.*spese|indennit"),
    ("portale", r"deposit[ao]|avvia.*mediaz|mediaz.*online|concilia.*online|accesso.*area.*riservata"),
    ("sedi", r"sedi|dove.siamo|contatti"), ("privacy", r"privacy|riservatezz"),
    ("procedura", r"mediazione.civile|servizio.*mediaz|mediaz.*servizio"),
)


def public_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Sito non indicato nel registro.")
    if "://" not in raw:
        raw = "https://" + raw
    parts = urlsplit(raw)
    if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username
            or parts.password or parts.port not in {None, 80, 443} or "\\" in raw
            or any(ord(c) < 33 for c in raw) or parts.hostname.endswith(".local")):
        raise ValueError("Indirizzo pubblico non valido.")
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def public_addresses(host: str, port: int) -> list[str]:
    addresses = list(dict.fromkeys(r[4][0] for r in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Indirizzo di rete non pubblico: richiesta non eseguita.")
    return addresses


def fetch_public(url: str, *, max_bytes: int = MAX_BYTES) -> dict:
    """Validate every redirect; pin resolved IP while preserving Host and TLS SNI."""
    current = public_url(url)
    started = time.monotonic()
    for _ in range(5):
        parts = urlsplit(current)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        addresses = public_addresses(parts.hostname, port)
        pool_type = urllib3.HTTPSConnectionPool if parts.scheme == "https" else urllib3.HTTPConnectionPool
        options = {"assert_hostname": parts.hostname, "server_hostname": parts.hostname,
                   "cert_reqs": ssl.CERT_REQUIRED} if parts.scheme == "https" else {}
        with pool_type(addresses[0], port=port, timeout=urllib3.Timeout(connect=5, read=6), **options) as pool:
            response = pool.urlopen("GET", urlunsplit(("", "", parts.path or "/", parts.query, "")),
                                    headers={"Host": parts.netloc, "User-Agent": USER_AGENT,
                                             "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"},
                                    redirect=False, retries=False, preload_content=False)
            try:
                if response.status in {301, 302, 303, 307, 308}:
                    current = public_url(urljoin(current, response.headers.get("Location", "")))
                    continue
                body = bytearray()
                for chunk in response.stream(65536):
                    body.extend(chunk)
                    if len(body) > max_bytes or time.monotonic() - started > 25:
                        raise ValueError("Risposta oltre i limiti del controllo pubblico.")
                return {"url": current, "status": response.status,
                        "content_type": response.headers.get("Content-Type", ""), "body": bytes(body)}
            finally:
                response.close()
    raise ValueError("Troppi reindirizzamenti sul sito pubblico.")


def extract_links(page: dict) -> tuple[list[dict], str]:
    if "html" not in page["content_type"].lower():
        return [], ""
    document = html.fromstring(page["body"], base_url=page["url"])
    for node in document.xpath("//script|//style|//noscript"):
        node.drop_tree()
    text = " ".join(document.text_content().split())
    digest = hashlib.sha256(page["body"]).hexdigest()
    links = {}
    for node in document.xpath("//a[@href]"):
        href = node.get("href", "")
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        try:
            target = public_url(urljoin(page["url"], href))
        except ValueError:
            continue
        label = " ".join((node.text_content() or node.get("title") or "").split())[:200]
        # A file in /modulistica/ is not necessarily an instance: its own label wins.
        kind = next((kind for kind, pattern in LINK_KINDS if re.search(pattern, label.lower())), "")
        if not kind:
            kind = next((kind for kind, pattern in LINK_KINDS if re.search(pattern, target.lower())), "")
        if kind:
            links[target] = {"url": target, "label": label or kind.capitalize(), "kind": kind,
                             "source_url": page["url"], "source_sha256": digest,
                             "verification": "link_pubblicato", "target_checked": False}
    return list(links.values()), text


def inspect_organism(row: dict) -> dict:
    result = {"registration_number": str(row["registration_number"]), "checked_at": utc_now(),
              "status": "da_verificare", "resources": [], "pages": [], "errors": [],
              "identity_match": False, "filing_confirmed": False}
    if not row.get("website"):
        return dict(result, status="sito_non_indicato")
    try:
        homepage = public_url(row["website"])
        origin = urlsplit(homepage)
        robots = fetch_public(urljoin(homepage, "/robots.txt"), max_bytes=256_000)
        if robots["status"] not in {200, 404, 410}:
            return dict(result, status="robots_non_verificabile")
        policy = RobotFileParser()
        policy.parse(robots["body"].decode("utf-8", "replace").splitlines() if robots["status"] == 200 else [])
        if robots["status"] != 200:
            policy.allow_all = True
        queue, visited, resources, text_parts = [homepage], set(), {}, []
        while queue and len(visited) < 4:
            url = queue.pop(0)
            if url in visited or not policy.can_fetch(USER_AGENT, url):
                continue
            visited.add(url)
            delay = max(0.3, float(policy.crawl_delay(USER_AGENT) or 0))
            if delay > 10:
                result["errors"].append("Il sito richiede un intervallo superiore al controllo rapido.")
                break
            time.sleep(delay)
            try:
                page = fetch_public(url)
                # A cross-domain redirect is evidence, not proof that ownership is unchanged.
                result["pages"].append({"requested_url": url, "url": page["url"], "status": page["status"],
                                        "sha256": hashlib.sha256(page["body"]).hexdigest()})
                if page["status"] != 200:
                    continue
                links, page_text = extract_links(page)
                text_parts.append(page_text)
                for link in links:
                    resources[link["url"]] = link
                same_domain = [link["url"] for link in links
                               if urlsplit(link["url"]).hostname.removeprefix("www.") == origin.hostname.removeprefix("www.")
                               and link["kind"] in {"modulistica", "procedura", "sedi"}
                               and not re.search(r"\.(pdf|docx?|zip)(?:\?|$)", link["url"], re.I)]
                queue = list(dict.fromkeys(queue + same_domain))
                # Reach the actual forms before FAQ and office pages consume the crawl budget.
                queue.sort(key=lambda candidate: 0 if resources.get(candidate, {}).get("kind") == "modulistica" else 1)
            except Exception as exc:
                result["errors"].append(f"{type(exc).__name__}: {str(exc)[:200]}")
        combined = " ".join(text_parts)
        identifiers = [str(row.get(key) or "").strip() for key in ("tax_code", "vat_number")]
        result["identity_match"] = any(len(value) >= 11 and value in combined for value in identifiers)
        result["resources"] = list(resources.values())
        result["status"] = "fonti_rilevate" if resources else "sito_senza_risorse_rilevate" if text_parts else "sito_non_verificato"
        # Never infer a filing PEC from a generic email, a registry address or a substring.
        return result
    except Exception as exc:
        return dict(result, status="sito_non_verificato", errors=[f"{type(exc).__name__}: {str(exc)[:200]}"])
