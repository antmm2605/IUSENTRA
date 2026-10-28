"""Acquisizione della vista «originario» dalla navigazione ufficiale GU.

Non determina l'applicabilità temporale e non sostituisce una versione richiesta
alla data del fascicolo. Segue soltanto collegamenti pubblicati dal sito ufficiale.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, urljoin, urlsplit

from lxml import html

BASE = "https://www.gazzettaufficiale.it"


@dataclass(frozen=True)
class OriginaleGazzetta:
    data_pubblicazione: str
    codice_redazionale: str
    intestazione: str
    entrata_in_vigore: str | None
    articoli: tuple[dict, ...]
    documenti: tuple[tuple[str, bytes], ...]
    vista_edizione: str = "HTML_GU_ORIGINARIO"
    annotazioni_edizione: str = ""


def _ufficiale(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "www.gazzettaufficiale.it"
            or parsed.port not in (None, 443) or parsed.username or parsed.password):
        raise ValueError("Collegamento GU non ufficiale")
    return url


def _leggi(opener, url: str, timeout: float) -> bytes:
    response = opener.open(_ufficiale(url), timeout=timeout)
    with response:
        _ufficiale(response.geturl())
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("Risposta GU oltre il limite di acquisizione")
    return data


def acquisisci_originale(*, data_gu: date, codice_redazionale: str,
                        intestazione_attesa: str, opener, timeout: float = 90,
                        massimo_articoli: int = 1000) -> OriginaleGazzetta:
    """L'identità attesa deve provenire dal catalogo, mai dai fatti del cliente.

    Restituisce anche i byte originali per l'archivio delle prove. Non scrive DB.
    Partizioni e numerazioni ripetute sono distinte dai parametri degli URL GU.
    """
    if not re.fullmatch(r"[0-9A-Z]{4,16}", codice_redazionale):
        raise ValueError("Codice redazionale GU non valido")
    if not intestazione_attesa.strip() or not 1 <= massimo_articoli <= 1000:
        raise ValueError("Identità o limite di acquisizione assente")
    publication = data_gu.isoformat()
    url = f"{BASE}/eli/id/{data_gu:%Y/%m/%d}/{codice_redazionale}/sg"
    raw = _leggi(opener, url, timeout)
    root = html.fromstring(raw)
    headers = root.xpath('//*[@id="titolo_atto"]')
    if len(headers) != 1:
        raise ValueError("Intestazione GU non univoca")
    header = " ".join(headers[0].text_content().split())
    # Il sito può chiamare «originario» un HTML già integrato da rettifiche.
    # Il parametro URL non prova l'identità con la prima pubblicazione PDF.
    rettifiche = bool(re.search(r"rettific|errata[ -]corrige", header, re.IGNORECASE))
    vista_edizione = "HTML_GU_ORIGINARIO_CON_RETTIFICHE" if rettifiche else "HTML_GU_ORIGINARIO"
    normalize = lambda value: " ".join(value.casefold().split())
    if normalize(intestazione_attesa) not in normalize(header):
        raise ValueError("Tipo, data o numero dell'atto GU discordanti")
    menus = []
    for anchor in root.xpath('//a[@href]'):
        candidate = urljoin(BASE, anchor.get("href"))
        query = parse_qs(urlsplit(candidate).query)
        if (urlsplit(candidate).path == "/atto/vediMenuHTML"
                and query.get("atto.dataPubblicazioneGazzetta") == [publication]
                and query.get("atto.codiceRedazionale") == [codice_redazionale]
                and query.get("tipoVigenza") == ["originario"]):
            menus.append(_ufficiale(candidate))
    menus = list(dict.fromkeys(menus))
    if len(menus) != 1:
        raise ValueError("Menu originale GU non univoco")
    menu_raw = _leggi(opener, menus[0], timeout)
    documents = [(url, raw), (menus[0], menu_raw)]
    links = {}
    for anchor in html.fromstring(menu_raw).xpath('//a[@href]'):
        candidate = urljoin(BASE, anchor.get("href"))
        parsed = urlsplit(candidate)
        if parsed.path != "/atto/serie_generale/caricaArticolo":
            continue
        _ufficiale(candidate)
        query = parse_qs(parsed.query)
        if (query.get("art.codiceRedazionale") != [codice_redazionale]
                or query.get("art.dataPubblicazioneGazzetta") != [publication]
                or query.get("art.versione") != ["1"]):
            raise ValueError("Articolo GU di identità o versione discordante")
        identity = tuple((key, tuple(value)) for key, value in sorted(query.items()))
        links.setdefault(identity, candidate)
    if not links or len(links) > massimo_articoli:
        raise ValueError("Articoli GU assenti o oltre il limite dichiarato")
    articles = []
    for identity, candidate in links.items():
        body_raw = _leggi(opener, candidate, timeout)
        nodes = html.fromstring(body_raw).xpath(
            '//*[contains(concat(" ",normalize-space(@class)," ")," dettaglio_atto_testo ")]/pre')
        text = "\n".join(node.text_content().strip() for node in nodes if node.text_content().strip())
        if not text:
            raise ValueError("Testo originale GU vuoto")
        query = dict(identity)
        articles.append({"url": candidate, "parametri_originali": dict(identity),
                         "numero_xml_gu": query.get("art.idArticolo", ("",))[0],
                         "testo": text, "sha256_testo": hashlib.sha256(text.encode()).hexdigest(),
                         "sha256_html": hashlib.sha256(body_raw).hexdigest(),
                         "edizione": vista_edizione, "annotazioni_edizione": header,
                         "prima_pubblicazione_pdf_verificata": False, "applicabilita_verificata": False})
        documents.append((candidate, body_raw))
    match = re.search(r"Entrata in vigore del provvedimento:\s*(\d{2}/\d{2}/\d{4})", header)
    effective = None
    if match:
        day, month, year = map(int, match[1].split("/"))
        effective = date(year, month, day).isoformat()
    return OriginaleGazzetta(publication, codice_redazionale, header, effective,
                            tuple(articles), tuple(documents), vista_edizione, header)
