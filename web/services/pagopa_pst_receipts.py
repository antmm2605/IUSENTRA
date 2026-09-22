"""Recupero pubblico delle RT dal PST: nessun pagamento o accesso autenticato."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = "https://servizipst.giustizia.it"
SEARCH_PATH = "/PST/it/pagopa_altripag.wp"
RECEIPT_PATH = "/PST/do/pagamentitelematici/xmlDetailsBolli.action"
MAX_BYTES = 2 * 1024 * 1024


def _body(response: requests.Response) -> bytes:
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Il PST non ha restituito la ricevuta richiesta.")
    body = bytearray()
    for chunk in response.iter_content(64 * 1024):
        body.extend(chunk)
        if len(body) > MAX_BYTES:
            raise ValueError("La risposta PST supera il limite di 2 MB.")
    return bytes(body)


def recupera_rt(numero_avviso: str, codice_fiscale: str, *, verify: str) -> bytes | None:
    """Un tentativo limitato, con cookie pubblici effimeri e TLS verificato.

    None significa che il PST non pubblica ancora la RT; errori di rete o
    risposte incomplete restano errori, mai conferme di mancato pagamento.
    """
    if not re.fullmatch(r"\d{18}", numero_avviso):
        raise ValueError("Numero avviso non valido.")
    if not re.fullmatch(r"(?:[A-Z0-9]{16}|\d{11})", codice_fiscale):
        raise ValueError("Manca il codice fiscale del debitore dell’avviso.")
    with requests.Session() as http:
        http.verify = verify
        http.headers.update({
            "User-Agent": "IUSENTRA PagoPA PST bridge",
            # Senza lingua il PST può restituire un modulo HTML incompleto.
            "Accept-Language": "it-IT,it;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Origin": ROOT,
            "Referer": ROOT + SEARCH_PATH,
        })
        with http.get(ROOT + SEARCH_PATH, timeout=(5, 15), allow_redirects=False, stream=True) as response:
            _body(response)
        with http.post(
            ROOT + SEARCH_PATH,
            params={"actionPath": "/ExtStr2/do/pagamentitelematici/ricercaAltriPagamenti.action", "currentFrame": "8"},
            files={"codiceFiscalePagatore": (None, codice_fiscale), "crs": (None, numero_avviso)},
            timeout=(5, 15), allow_redirects=False, stream=True,
        ) as response:
            soup = BeautifulSoup(_body(response), "html.parser")
        table = soup.select_one("table#richiesta")
        if table is None:
            raise ValueError("Il PST ha restituito una ricerca incompleta. Recupero da riprovare.")
        links = []
        for row in table.select("tr"):
            if numero_avviso not in row.get_text(" ", strip=True):
                continue
            for link in row.select("a[href]"):
                url = urljoin(ROOT, link["href"])
                parsed = urlparse(url)
                if parsed.scheme == "https" and parsed.netloc == "servizipst.giustizia.it" and parsed.path == RECEIPT_PATH:
                    links.append(url)
        if not links:
            return None
        if len(set(links)) != 1:
            raise ValueError("Il PST restituisce più ricevute per l’avviso: verifica necessaria.")
        with http.get(links[0], timeout=(5, 15), allow_redirects=False, stream=True) as response:
            content = _body(response)
        from pct.pagamenti_giustizia import parse_rt

        rt = parse_rt(content)
        if rt is None or rt.iuv not in {numero_avviso, numero_avviso[1:]}:
            raise ValueError("La risposta PST non contiene la ricevuta dell’avviso richiesto.")
        return content
