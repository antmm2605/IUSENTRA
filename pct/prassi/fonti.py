"""Lettura degli elenchi e dei testi della prassi dai siti ufficiali (verificati il 21/11/2026).

Agenzia delle Entrate (``www.agenziaentrate.gov.it/portale``): «Normativa e prassi» → «Circolari» e «Risoluzioni»,
con l'archivio per anno e per mese; ogni documento è «<strong>Circolare n. 16 del 28/06/2024</strong>» seguito dal
collegamento al PDF con l'oggetto. Il testo si legge dal PDF.

INPS (``www.inps.it``): l'elenco «Circolari, messaggi e normativa» è servito da
``/content/scorporati/search/jcr:content.search.<parametri in esadecimale>.json`` (lo stesso usato dalla pagina);
il testo integrale è nel campo ``testoCompleto`` della scheda ``<path>/jcr:content/data/master.json``.
"""
from __future__ import annotations

import html
import io
import json
import re
from typing import Any, Callable, Iterator
from urllib.parse import urljoin, urlsplit

ADE = "https://www.agenziaentrate.gov.it"
ADE_PARTENZE = (
    f"{ADE}/portale/normativa-e-prassi/circolari",
    f"{ADE}/portale/web/guest/normativa-e-prassi/circolari/archivio-circolari",
    f"{ADE}/portale/normativa-e-prassi/risoluzioni",
    f"{ADE}/portale/web/guest/normativa-e-prassi/risoluzioni/archivio-risoluzioni",
)
INPS = "https://www.inps.it"
INPS_ELENCO = "/content/dam/inps-site/it/scorporati/circolari-e-messaggi"
INPS_DETTAGLIO = f"{INPS}/it/it/inps-comunica/atti/circolari-messaggi-e-normativa/dettaglio."

_DOCUMENTO_ADE = re.compile(r"(Circolare|Risoluzione)\s+n\.?\s*°?\s*([0-9]+(?:/[A-Z])?)\s+del\s+(\d{1,2})/(\d{1,2})/(\d{4})", re.I)


def testo_html(frammento: str) -> str:
    frammento = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", frammento or "")
    frammento = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>|</tr>", "\n", frammento)
    testo = html.unescape(re.sub(r"<[^>]+>", " ", frammento))
    return "\n".join(r for r in (" ".join(x.split()) for x in testo.split("\n")) if r)


def testo_pdf(contenuto: bytes) -> str:
    from pypdf import PdfReader

    lettore = PdfReader(io.BytesIO(contenuto))
    pagine = [(p.extract_text() or "") for p in lettore.pages]
    return "\n".join(" ".join(r.split()) for r in "\n".join(pagine).split("\n") if r.strip())


# --- Agenzia delle Entrate -------------------------------------------------------------------------------------

def ade_documenti(pagina: str, url_pagina: str) -> list[dict[str, Any]]:
    """Circolari e risoluzioni elencate in una pagina, ciascuna con il suo PDF e l'oggetto."""
    voci = []
    intestazioni = list(_DOCUMENTO_ADE.finditer(pagina))
    for i, m in enumerate(intestazioni):
        fine = intestazioni[i + 1].start() if i + 1 < len(intestazioni) else min(len(pagina), m.end() + 4000)
        tratto = pagina[m.end():fine]
        pdf = re.search(r'<a [^>]*href="([^"]+?\.pdf[^"]*)"[^>]*>(.*?)</a>', tratto, re.S | re.I)
        if not pdf:
            continue
        tipo, numero, g, mese, anno = m.groups()
        voci.append({"ente": "Agenzia delle Entrate", "tipo": tipo.capitalize(), "numero": numero.upper(),
                     "data": f"{anno}-{int(mese):02d}-{int(g):02d}", "oggetto": testo_html(pdf.group(2)).replace("\n", " "),
                     "url": url_pagina, "url_testo": urljoin(ADE, html.unescape(pdf.group(1)))})
    unici = {}
    for v in voci:
        unici.setdefault((v["tipo"], v["numero"], v["data"]), v)
    return list(unici.values())


def ade_collegamenti(pagina: str) -> list[str]:
    """Le pagine d'elenco dell'archivio (anni e mesi di circolari e risoluzioni), mai i documenti."""
    esito = []
    for href in re.findall(r'href="([^"]+)"', pagina):
        url = urljoin(ADE, html.unescape(href)).split("#")[0].split("?")[0]
        parti = urlsplit(url)
        # Le circolari e risoluzioni «del territorio» (direzioni regionali) restano fuori.
        if parti.hostname != "www.agenziaentrate.gov.it" or "/documents/" in parti.path or "territorio" in parti.path:
            continue
        if re.search(r"(circolari|risoluzioni)", parti.path) and re.search(r"(\d{4}|archivio)", parti.path):
            esito.append(url)
    return list(dict.fromkeys(esito))


# --- INPS ------------------------------------------------------------------------------------------------------

def _esadecimale(valore: str) -> str:
    return "".join(f"{ord(c):x}" for c in str(valore).replace("’", " ").replace("'", " "))


def inps_url_elenco(pagina: int, limite: int = 100) -> str:
    parametri = [INPS_ELENCO, pagina, limite, "giorno", "DESC", "circolari-e-messaggi"]
    selettori = ".".join(_esadecimale(str(p)) for p in parametri if p or p == 0)
    return f"{INPS}/content/scorporati/search/jcr:content.search.{selettori}.json"


def inps_documenti(risposta: dict[str, Any]) -> list[dict[str, Any]]:
    voci = []
    for r in (risposta.get("data") or {}).get("results") or []:
        data = re.search(r"del-(\d{2})-(\d{2})-(\d{4})", str(r.get("selectors") or ""))
        if not data or not r.get("numero") or not r.get("path"):
            continue
        g, m, a = data.groups()
        voci.append({"ente": "INPS", "tipo": str(r.get("tipo") or "").capitalize(), "numero": str(r["numero"]),
                     "data": f"{a}-{m}-{g}", "oggetto": testo_html(str(r.get("oggetto") or "")).replace("\n", " "),
                     "url": f"{INPS_DETTAGLIO}{r['selectors']}.html",
                     "url_testo": f"{INPS}{r['path']}/jcr:content/data/master.json"})
    return voci


def inps_testo(scheda: dict[str, Any], scarica: Callable[[str], Any] | None = None) -> str:
    testo = testo_html(str(scheda.get("testoCompleto") or ""))
    if len(testo) >= 200 or scarica is None:
        return testo
    # Scheda senza testo: il PDF ufficiale fra gli allegati.
    pdf = next((a for a in scheda.get("allegati") or [] if str(a).lower().endswith(".pdf")), "")
    if pdf:
        risposta = scarica(f"{INPS}{pdf}")
        if int(getattr(risposta, "status_code", 200)) == 200:
            return testo_pdf(risposta.content)
    return testo


def inps_pagine(scarica: Callable[[str], Any], *, dalla: int = 0, limite: int = 100) -> Iterator[tuple[int, list[dict]]]:
    pagina = dalla
    while True:
        risposta = scarica(inps_url_elenco(pagina, limite))
        voci = inps_documenti(json.loads(risposta.content))
        if not voci:
            return
        yield pagina, voci
        pagina += 1


__all__ = ["ADE_PARTENZE", "ade_collegamenti", "ade_documenti", "inps_documenti", "inps_pagine", "inps_testo",
           "inps_url_elenco", "testo_html", "testo_pdf"]
