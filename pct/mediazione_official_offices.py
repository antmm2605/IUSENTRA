"""Complete public ROM office inventory; never called from a web request.

URL discovered through the ministry's own btnSedi form on 05/09/2026.
Read-only public consultation, no private cases, credentials or CNS sessions.
"""
from __future__ import annotations

import hashlib
import re
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
import ssl

from lxml import html
from pct.mediazione_directory_repository import utc_now

HOST = "mediazione.giustizia.it"
BASE = f"https://{HOST}/ROM/AlboOdMDettaglioSedi.aspx"


class MinistryRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != "https" or target.netloc.lower() != HOST:
            raise ValueError("Redirect fuori dal registro ministeriale.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_office_page(content: bytes, number: str, page: int = 1) -> tuple[list[dict], int, int, dict, str]:
    doc = html.fromstring(content)
    inputs = {x.get("name"): x.get("value", "") for x in doc.xpath("//input")
              if x.get("type", "").lower() == "hidden" and x.get("name")}
    if inputs.get("hfRom") != number:
        raise ValueError("La risposta non corrisponde all'organismo richiesto.")
    expected = int(inputs["tot2"])
    tables = doc.xpath("//table[@id='gvAlboODM_Sedi']")
    if len(tables) != 1:
        raise ValueError("Tabella sedi ministeriale non trovata.")
    table = tables[0]
    headers = [" ".join(x.text_content().split()) for x in table.xpath(".//th")]
    if headers[:6] != ["Sede Legale", "Indirizzo", "Comune", "CAP", "Prov.", "Regione"]:
        raise ValueError("Le colonne del registro sono cambiate.")
    offices = []
    for row in table.xpath(".//tr"):
        cells = row.xpath("./td")
        values = [" ".join(x.text_content().split()) for x in cells]
        if len(values) < 10 or values[0].casefold() not in {"si", "sì", "no"}:
            continue
        offices.append(dict(zip(
            ("legal", "address", "city", "postal_code", "province", "region", "phone", "fax", "email", "pec"),
            [values[0].casefold() in {"si", "sì"}, *values[1:10]],
        )))
    selectors = table.xpath(".//select")
    pages = max([int(x.get("value")) for s in selectors for x in s.xpath("./option")] or [1])
    selector = selectors[0].get("name") if selectors else ""
    if selectors:
        selected = selectors[0].xpath("./option[@selected]")
        if not selected or int(selected[0].get("value")) != page:
            raise ValueError("Il registro non ha restituito la pagina sedi richiesta.")
    return offices, expected, pages, inputs, selector


def acquire_offices(number: str, *, deadline: float | None = None) -> dict:
    if not re.fullmatch(r"[0-9]{1,6}", number):
        raise ValueError("Numero di registro non valido.")
    url = f"{BASE}?{urlencode({'ROM': number})}"
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), MinistryRedirects())
    deadline = min(deadline or time.monotonic() + 90, time.monotonic() + 90)
    hashes, all_offices = [], []
    fields, selector, total, pages = {}, "", -1, 1
    page = 1
    while page <= pages:
        if time.monotonic() >= deadline:
            raise TimeoutError("Tempo massimo di consultazione sedi raggiunto.")
        body = None
        if page > 1:
            fields.update({"__EVENTTARGET": selector, "__EVENTARGUMENT": "", selector: str(page)})
            body = urlencode(fields).encode("utf-8")
        request = Request(url, data=body, headers={"User-Agent": "IUSENTRA/Mediazione-public-directory", "Accept": "text/html"})
        with opener.open(request, timeout=min(15, max(1, deadline - time.monotonic()))) as response:
            content = response.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError("Risposta ministeriale oltre il limite di sicurezza.")
        offices, expected, page_count, fields, selector = parse_office_page(content, number, page)
        if total >= 0 and (total != expected or pages != page_count):
            raise ValueError("Il registro è cambiato durante la consultazione: ripetere l'acquisizione.")
        total, pages = expected, page_count
        if pages > 100 or expected > 1000:
            raise ValueError("Dimensione registro inattesa, richiesta revisione.")
        all_offices.extend(offices)
        hashes.append(hashlib.sha256(content).hexdigest())
        page += 1
        if page <= pages:
            time.sleep(.15)
    # Preserve co-located/duplicate rows as published: never invent deduplication of seats.
    if len(all_offices) != total:
        raise ValueError(f"Inventario non riconciliato: {len(all_offices)} sedi lette su {total} dichiarate.")
    return {"source_url": url, "checked_at": utc_now(), "offices": all_offices,
            "expected_count": total, "pages": pages,
            "content_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest()}
