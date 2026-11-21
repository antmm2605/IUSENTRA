"""Il testo completo di un atto della Gazzetta Ufficiale, dalla navigazione ufficiale del sito (vista «originario»).

Percorso verificato il 21/11/2026 su atti della Serie generale (una convocazione, 23A00087, e un decreto
legislativo in 34 articoli, 22G00207) e valido per tutte le serie, perché ogni passo segue i collegamenti che la
pagina stessa pubblica:

1. la pagina dell'atto indicata dal sommario (``/atto/<serie>/caricaDettaglioAtto/originario?...``) apre la sessione
   e pubblica il collegamento «Atto completo» (``/atto/vediMenuHTML?...``);
2. «Atto completo» con ``action=select-all``: per un atto senza articoli è già il testo; per un atto in articoli è
   il modulo di stampa con tutti gli articoli selezionati (``form#menuExportForm``);
3. il modulo inviato com'è (``/atto/stampa/<serie>/originario``) restituisce il testo di tutti gli articoli.

Gli avvisi della 5ª Serie speciale (Contratti pubblici) non hanno «Atto completo»: il testo è già nella pagina
dell'atto (verificato il 21/11/2026 su TX26BFF482).

Il testo è quello dei blocchi ``<pre>`` della pagina ufficiale, senza aggiunte; l'intestazione è quella dell'atto.
Solo ``https://www.gazzettaufficiale.it``: un collegamento verso un altro sito ferma la lettura.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from lxml import html

SITO = "https://www.gazzettaufficiale.it"
LIMITE_BYTE = 16 * 1024 * 1024
TIMEOUT = 60


class TestoNonDisponibile(ValueError):
    """La pagina ufficiale non ha restituito il testo dell'atto."""


@dataclass(frozen=True)
class TestoAtto:
    testo: str
    intestazione: str
    url_testo: str
    sha256: str
    articoli: int


def _ufficiale(url: str) -> str:
    parti = urlsplit(url)
    if parti.scheme != "https" or parti.hostname not in {"www.gazzettaufficiale.it", "gazzettaufficiale.it"} \
            or parti.username or parti.password or parti.port not in (None, 443):
        raise TestoNonDisponibile("Collegamento non ufficiale: lettura fermata.")
    return url


def _contenuto(risposta: Any) -> bytes:
    _ufficiale(str(getattr(risposta, "url", "") or SITO))
    if int(getattr(risposta, "status_code", 200)) != 200:
        raise TestoNonDisponibile(f"La Gazzetta Ufficiale ha risposto {risposta.status_code}.")
    contenuto = risposta.content or b""
    if len(contenuto) > LIMITE_BYTE:
        raise TestoNonDisponibile("Pagina oltre il limite di acquisizione.")
    return contenuto


def _albero(contenuto: bytes):
    albero = html.fromstring(contenuto, parser=html.HTMLParser(encoding="utf-8", no_network=True, remove_comments=True))
    for nodo in albero.xpath("//script|//style"):
        nodo.drop_tree()
    return albero


def _spazi(valore: str) -> str:
    return " ".join(str(valore or "").replace("\xa0", " ").split())


def _testo_della_pagina(albero) -> tuple[str, str]:
    blocchi = [nodo.text_content().replace("\xa0", " ").strip("\n") for nodo in albero.xpath("//pre")]
    blocchi = [b.rstrip() for b in blocchi if b.strip()]
    intestazione = _spazi(albero.xpath("string(//div[@id='testa_atto_preview'])"))
    if not intestazione:
        intestazione = _spazi(albero.xpath("string(//*[@id='titolo_atto'])"))
    return "\n\n".join(blocchi), intestazione


def _con_selezione(url: str) -> str:
    parti = urlsplit(url)
    valori = [(k, v) for k, v in parse_qsl(parti.query, keep_blank_values=True) if k != "action"]
    return urlunsplit((parti.scheme, parti.netloc, parti.path, urlencode(valori + [("action", "select-all")]), ""))


def leggi_testo(url_atto: str, *, sessione: Any, timeout: float = TIMEOUT) -> TestoAtto:
    """Legge il testo completo dell'atto dalla pagina ufficiale indicata dal sommario."""
    pagina = _albero(_contenuto(sessione.get(_ufficiale(url_atto), timeout=timeout)))
    menu = next((urljoin(SITO, str(a.get("href"))) for a in pagina.xpath("//a[@href]")
                 if "/atto/vediMenuHTML" in str(a.get("href"))), "")
    if not menu:
        # Avvisi senza articoli (per esempio la 5ª Serie speciale - Contratti): il testo è già nella pagina dell'atto.
        testo, intestazione = _testo_della_pagina(pagina)
        if not testo:
            raise TestoNonDisponibile("La pagina dell'atto non pubblica il testo completo.")
        return TestoAtto(testo=testo, intestazione=intestazione, url_testo=url_atto,
                         sha256=hashlib.sha256(testo.encode("utf-8")).hexdigest(), articoli=0)
    url_menu = _ufficiale(_con_selezione(menu))
    albero = _albero(_contenuto(sessione.get(url_menu, timeout=timeout)))
    articoli = albero.xpath("//input[@name='articoliSelected']")
    url_testo = url_menu
    if articoli:
        moduli = albero.xpath("//form[@id='menuExportForm']")
        if not moduli:
            raise TestoNonDisponibile("Il modulo di stampa dell'atto non è leggibile.")
        url_testo = _ufficiale(urljoin(SITO, str(moduli[0].get("action") or "")))
        dati = [(str(i.get("name")), str(i.get("value") or "")) for i in albero.xpath("//input[@name]")
                if not (str(i.get("type") or "").lower() == "checkbox" and i.get("checked") is None)]
        albero = _albero(_contenuto(sessione.post(url_testo, data=dati, timeout=timeout)))
    testo, intestazione = _testo_della_pagina(albero)
    if not testo:
        raise TestoNonDisponibile("La pagina ufficiale non contiene il testo dell'atto.")
    return TestoAtto(testo=testo, intestazione=intestazione, url_testo=url_testo,
                     sha256=hashlib.sha256(testo.encode("utf-8")).hexdigest(), articoli=len(articoli))


__all__ = ["TestoAtto", "TestoNonDisponibile", "leggi_testo"]
