"""Public evidence for every active organism, not an authorization to send.

No case data, cookies, credentials, POST, API probing or TLS bypass. Only linked
public pages; API documentation links remain candidates until contract review.
"""
from __future__ import annotations

import codecs
import hashlib
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from lxml import html

from pct.mediazione_directory_repository import utc_now
from pct.mediazione_public_sources import USER_AGENT, extract_links, fetch_public, public_url

RESEARCH_VERSION = "2026-09-06.1"
EMAIL = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", re.I)
FILING = re.compile(r"(?:deposit|invi|trasmett|trasmission|present)[\w\sàèéìòù,'’/-]{0,65}(?:istanz|domand|modul)|(?:istanz|domand)[\w\sàèéìòù,'’/-]{0,65}(?:deposit|invi|trasmett|present)", re.I)
PEC = re.compile(r"\bP\s*\.?\s*E\s*\.?\s*C\b|posta elettronica certificata", re.I)
API = re.compile(r"\bapi\b|openapi|swagger|web[ -]?service|integrazion[ei] applicativ", re.I)


def document(page):
    content = page["body"]
    charset = re.search(r"charset\s*=\s*[\"']?([\w-]+)", page.get("content_type", ""), re.I)
    encoding = charset.group(1) if charset else None
    if encoding:
        try:
            codecs.lookup(encoding)
        except LookupError:
            encoding = None
    if not encoding:
        try:
            content.decode("utf-8", "strict")
            encoding = "utf-8"
        except UnicodeDecodeError:
            pass
    tree = html.fromstring(content, parser=html.HTMLParser(encoding=encoding), base_url=page["url"])
    for node in tree.xpath("//script|//style|//noscript"):
        node.drop_tree()
    return tree


def channel_evidence(page):
    tree = document(page)
    digest = hashlib.sha256(page["body"]).hexdigest()
    evidence, seen = [], set()
    # Small semantic blocks prevent pairing a ministry PEC in the footer with
    # unrelated filing instructions elsewhere on the page.
    for node in tree.xpath("//p|//li|//td|//address|//a[starts-with(@href, 'mailto:')]"):
        text = " ".join(node.text_content().split())
        if node.tag == "a":
            parent = node.getparent()
            if parent is not None:
                text = " ".join(parent.text_content().split())
        # A filing answer often introduces a list whose PEC item has no verb.
        # Use only its immediately preceding question/paragraph, not the page.
        if node.tag == "li" and node.getparent() is not None:
            listing = node.getparent()
            lead = listing.getprevious()
            lead_text = ""
            if lead is not None and lead.tag in {"p", "h2", "h3", "h4", "strong"}:
                lead_text = " ".join(lead.text_content().split())
            elif lead is None and listing.getparent() is not None:
                lead_text = " ".join((listing.getparent().text or "").split())
            if len(lead_text) <= 400 and FILING.search(lead_text):
                text = lead_text + " " + text
        if not text or len(text) > 1800:
            continue
        addresses = EMAIL.findall(text)
        addresses += EMAIL.findall(node.get("href", ""))
        for address in dict.fromkeys(addresses):
            address = address.rstrip(".,;").lower()
            key = (address, text)
            if key in seen:
                continue
            seen.add(key)
            evidence.append({"address": address, "pec_explicit": bool(PEC.search(text)),
                             "filing_context": bool(FILING.search(text)), "excerpt": text[:700],
                             "source_url": page["url"], "source_sha256": digest,
                             "status": "da_revisionare", "authorized_for_submission": False})
    api_links = []
    for node in tree.xpath("//a[@href]"):
        label = " ".join(node.text_content().split())
        href = node.get("href", "")
        if not API.search(label + " " + href) or href.startswith(("#", "mailto:", "javascript:")):
            continue
        try:
            url = public_url(urljoin(page["url"], href))
        except ValueError:
            continue
        api_links.append({"url": url, "label": label[:200], "source_url": page["url"],
                          "source_sha256": digest, "status": "documentazione_da_verificare"})
    return evidence, api_links, " ".join(tree.text_content().split())


def inspect_channels(row, *, alternatives=(), max_pages=8, budget_seconds=60):
    started = time.monotonic()
    result = {"registration_number": str(row["registration_number"]), "name": row["name"],
              "checked_at": utc_now(), "research_version": RESEARCH_VERSION,
              "status": "da_verificare", "pages": [], "contacts": [], "api_documents": [],
              "resources": [], "errors": [], "remaining_urls": [], "identity_match": False,
              "api_status": "documentazione_non_rilevata", "filing_confirmed": False,
              "registry_contacts": {k: row.get(k, "") for k in ("pec", "email", "phone")}}
    candidates = [row.get("website", ""), *alternatives]
    roots = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            url = public_url(candidate)
            if url not in roots:
                roots.append(url)
        except ValueError as exc:
            result["errors"].append({"url": str(candidate), "error": str(exc)})
    if not roots:
        return dict(result, status="sito_da_ricercare")
    allowed_hosts = {urlsplit(u).hostname.removeprefix("www.") for u in roots}
    def crawlable(value):
        try:
            target = public_url(value)
            return (urlsplit(target).hostname.removeprefix("www.") in allowed_hosts
                    and not re.search(r"\.(pdf|docx?|zip|xlsx?)(?:\?|$)", target, re.I))
        except ValueError:
            return False
    queue = list(roots)
    last = row.get("channel_check") or {}
    cycle_start = last.get("cycle_started_at", "")
    resume = False
    if cycle_start and last.get("research_version") == RESEARCH_VERSION and last.get("remaining_urls"):
        try:
            resume = datetime.fromisoformat(cycle_start) > datetime.now(timezone.utc) - timedelta(days=1)
        except (ValueError, TypeError):
            pass
    result["cycle_started_at"] = cycle_start if resume else result["checked_at"]
    if resume:
        queue = list(last["remaining_urls"])
        for key in ("pages", "contacts", "api_documents", "resources", "errors"):
            result[key] = list(last.get(key, []))
        result["identity_match"] = bool(last.get("identity_match"))
    previous = (row.get("directory_check") or {}).get("resources", [])
    priority = {"procedura": 0, "portale": 1, "modulistica": 2, "sedi": 3, "regolamento": 4, "privacy": 8}
    for link in sorted(previous if not resume else [], key=lambda item: priority.get(item.get("kind"), 6)):
        if link.get("kind") in priority:
            queue.append(link["url"])
    visited = {p.get("requested_url") for p in result["pages"]} if resume else set()
    policies, resources = {}, {r["url"]: r for r in result["resources"]}
    attempted = 0
    while queue and attempted < max_pages and time.monotonic() - started < budget_seconds:
        url = queue.pop(0)
        try:
            url = public_url(url)
            parts = urlsplit(url)
            if url in visited or parts.hostname.removeprefix("www.") not in allowed_hosts:
                continue
            if re.search(r"\.(pdf|docx?|zip|xlsx?)(?:\?|$)", url, re.I):
                continue
            visited.add(url)
            attempted += 1
            origin = f"{parts.scheme}://{parts.netloc}"
            if origin not in policies:
                robots = fetch_public(origin + "/robots.txt", max_bytes=256000)
                if robots["status"] not in {200, 404, 410}:
                    policies[origin] = None
                    result["errors"].append({"url": origin + "/robots.txt", "error": f"HTTP {robots['status']}: accesso automatico non verificato"})
                    continue
                policy = RobotFileParser()
                policy.parse(robots["body"].decode("utf-8", "replace").splitlines() if robots["status"] == 200 else [])
                policy.allow_all = robots["status"] != 200
                policies[origin] = policy
            policy = policies[origin]
            if policy is None or not policy.can_fetch(USER_AGENT, url):
                result["errors"].append({"url": url, "error": "Accesso automatico non consentito dalla fonte"})
                continue
            delay = max(0.4, float(policy.crawl_delay(USER_AGENT) or 0))
            if time.monotonic() - started + delay >= budget_seconds:
                visited.discard(url)
                queue.insert(0, url)
                break
            time.sleep(delay)
            page = fetch_public(url, max_bytes=4000000)
            result["pages"].append({"requested_url": url, "url": page["url"], "status": page["status"],
                                    "sha256": hashlib.sha256(page["body"]).hexdigest(), "read_at": utc_now()})
            if page["status"] != 200 or "html" not in page["content_type"].lower():
                result["errors"].append({"url": url, "error": f"HTTP {page['status']}: pagina HTML non acquisita"})
                continue
            if urlsplit(page["url"]).hostname.removeprefix("www.") not in allowed_hosts:
                result["errors"].append({"url": page["url"], "error": "Reindirizzamento a diverso dominio: titolarità da verificare"})
                continue
            contacts, apis, text = channel_evidence(page)
            result["pages"][-1]["parsed"] = True
            result["contacts"].extend(contacts)
            result["api_documents"].extend(apis)
            result["identity_match"] |= any(len(str(row.get(k) or "")) >= 11 and str(row[k]) in text for k in ("tax_code", "vat_number"))
            links, _ = extract_links(page)
            for link in links:
                resources[link["url"]] = link
            queue.extend(link["url"] for link in sorted(links, key=lambda r: priority.get(r["kind"], 6)) if link["kind"] in priority)
            queue = list(dict.fromkeys(u for u in queue if u not in visited))
            queue.sort(key=lambda candidate: priority.get(resources.get(candidate, {}).get("kind"), 6))
        except Exception as exc:
            result["errors"].append({"url": url, "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
    result["remaining_urls"] = list(dict.fromkeys(u for u in queue if u not in visited and crawlable(u)))
    result["resources"] = list(resources.values())
    result["api_documents"] = list({r["url"]: r for r in result["api_documents"]}.values())
    result["contacts"] = list({(r["address"], r["source_url"], r["excerpt"]): r for r in result["contacts"]}.values())
    result["api_status"] = "documentazione_da_verificare" if result["api_documents"] else "documentazione_non_rilevata"
    result["status"] = ("istruzioni_pec_da_revisionare" if any(c["pec_explicit"] and c["filing_context"] for c in result["contacts"])
                        else "contatti_da_revisionare" if result["contacts"]
                        else "fonti_senza_canale_rilevato" if any(p["status"] == 200 for p in result["pages"])
                        else "fonte_non_raggiunta")
    return result
