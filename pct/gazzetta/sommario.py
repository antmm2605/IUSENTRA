"""Lettura delle pagine ufficiali della Gazzetta: elenco dei fascicoli degli ultimi 30 giorni e sommario di un fascicolo.

Il sommario ufficiale ha sempre la stessa struttura (verificata il 10/11/2026 sulle sei serie):
`div#elenco_hp` con l'intestazione «Serie Generale n. 260 del 7-11-2026», poi in ordine `span.rubrica`
(sezione), `span.emettitore` (ente emanante) e `span.risultato` (un atto: intestazione in `span.data`,
descrizione ufficiale con il codice redazionale fra parentesi e la pagina in `span.pagina`).
Il parsing usa lxml senza rete e senza risolvere entità esterne. Nulla si aggiunge al testo dell'ente.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from lxml import etree, html

from pct.gazzetta import tipi
from pct.gazzetta.serie import HOST_AMMESSI, SITO, Serie
from pct.notiziario.adattatori import collegamento_ufficiale


class SommarioIllegibile(ValueError):
    """La pagina non ha la struttura del sommario ufficiale."""


@dataclass(frozen=True)
class Fascicolo:
    serie: str
    numero: str
    data: str  # AAAA-MM-GG

    @property
    def chiave(self) -> str:
        return f"{self.serie}|{self.data}|{self.numero}"


_INTESTAZIONE = re.compile(r"n\.\s*(\d+)\s+del\s+(\d{1,2})-(\d{1,2})-(\d{4})", re.IGNORECASE)
_CODICE_FINALE = re.compile(r"\(\s*([0-9A-Z][0-9A-Z-]{5,14})\s*\)\s*$")
_PAGINA = re.compile(r"(\d+)")


def _spazi(valore: object) -> str:
    return " ".join(str(valore or "").replace("\xa0", " ").split())


def _albero(contenuto: bytes):
    parser = html.HTMLParser(encoding="utf-8", no_network=True, remove_comments=True)
    try:
        return html.fromstring(contenuto, parser=parser)
    except (etree.ParserError, ValueError) as exc:
        raise SommarioIllegibile("La pagina della Gazzetta Ufficiale non è leggibile.") from exc


def fascicoli_in_elenco(serie: Serie, contenuto: bytes) -> list[Fascicolo]:
    """Fascicoli dell'elenco «ultimi 30 giorni», dal più recente; ogni fascicolo una volta sola."""
    albero = _albero(contenuto)
    visti: dict[str, Fascicolo] = {}
    for href in albero.xpath("//a/@href"):
        parti = urlsplit(str(href))
        if not parti.path.endswith(f"/gazzetta/{serie.percorso}/caricaDettaglio"):
            continue
        valori = parse_qs(parti.query)
        data = (valori.get("dataPubblicazioneGazzetta") or [""])[0]
        numero = (valori.get("numeroGazzetta") or [""])[0]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data) or not numero.isdigit():
            continue
        fascicolo = Fascicolo(serie.codice, str(int(numero)), data)
        visti.setdefault(fascicolo.chiave, fascicolo)
    return sorted(visti.values(), key=lambda f: (f.data, int(f.numero)), reverse=True)


def _intestazione_fascicolo(albero) -> tuple[str, str]:
    testo = _spazi(albero.xpath("string(//div[@id='elenco_hp']//div[contains(@class,'intestazione')])"))
    trovato = _INTESTAZIONE.search(testo)
    if not trovato:
        raise SommarioIllegibile("La pagina non riporta numero e data del fascicolo.")
    numero, giorno, mese, anno = trovato.groups()
    return str(int(numero)), f"{anno}-{int(mese):02d}-{int(giorno):02d}"


def _descrizione(ancora) -> tuple[str, str]:
    copia = html.fromstring(html.tostring(ancora))
    pagina = ""
    for nodo in copia.xpath(".//span[@class='pagina' or @class='riferimento']"):
        if nodo.get("class") == "pagina":
            numero = _PAGINA.search(nodo.text_content() or "")
            pagina = numero.group(1) if numero else ""
        nodo.drop_tree()
    return _spazi(copia.text_content()), pagina


def atti_del_sommario(serie: Serie, fascicolo: Fascicolo, contenuto: bytes, *, acquisito_il: str) -> list[dict]:
    albero = _albero(contenuto)
    numero, data = _intestazione_fascicolo(albero)
    if numero != fascicolo.numero or data != fascicolo.data:
        raise SommarioIllegibile("Il sommario ricevuto non corrisponde al fascicolo richiesto.")
    contenitore = albero.xpath("//div[@id='elenco_hp']")
    if not contenitore:
        raise SommarioIllegibile("La pagina non contiene il sommario del fascicolo.")
    url_sommario = serie.url_sommario(fascicolo.data, fascicolo.numero)
    rubrica = emittente = ""
    atti: list[dict] = []
    for nodo in contenitore[0].iter("span"):
        classe = nodo.get("class") or ""
        if classe == "rubrica":
            rubrica, emittente = _spazi(nodo.text_content()), ""
        elif classe == "emettitore":
            emittente = _spazi(nodo.text_content())
        elif classe == "risultato":
            atto = _atto(serie, fascicolo, nodo, rubrica, emittente, len(atti), url_sommario, acquisito_il)
            if atto:
                atti.append(atto)
    return atti


def _atto(serie: Serie, fascicolo: Fascicolo, nodo, rubrica: str, emittente: str, posizione: int,
          url_sommario: str, acquisito_il: str) -> dict | None:
    ancore = nodo.xpath(".//a[@href]")
    if not ancore:
        return None
    url = collegamento_ufficiale(urljoin(SITO + "/", ancore[0].get("href") or ""), HOST_AMMESSI)
    if not url:
        return None
    intestazione = _spazi(nodo.xpath("string(.//span[@class='data'])")) or _spazi(ancore[0].text_content())
    descrizione, pagina = _descrizione(ancore[1]) if len(ancore) > 1 else ("", "")
    codice = (parse_qs(urlsplit(url).query).get("atto.codiceRedazionale") or [""])[0]
    finale = _CODICE_FINALE.search(descrizione)
    if finale:
        codice = codice or finale.group(1)
        descrizione = descrizione[: finale.start()].rstrip()
    if serie.codice == "S5":
        # Nei contratti pubblici l'intestazione è la stazione appaltante; la sezione è il tipo di avviso.
        emittente, intestazione = intestazione, ""
    if not intestazione and not descrizione:
        return None
    chiave = f"{fascicolo.chiave}|{codice or url}|{posizione if not codice else ''}"
    return {
        "id": "gu_" + hashlib.sha256(chiave.encode("utf-8")).hexdigest()[:24],
        "serie": serie.codice,
        "numero_gu": fascicolo.numero,
        "data_gu": fascicolo.data,
        "rubrica": rubrica,
        "emittente": emittente,
        "intestazione": intestazione,
        "tipo": tipi.tipo_atto(serie.codice, intestazione, emittente),
        "numero_atto": tipi.numero_atto(intestazione),
        "data_atto": tipi.data_atto(intestazione),
        "descrizione": descrizione,
        "codice_redazionale": codice,
        "pagina": pagina,
        "posizione": posizione,
        "url": url,
        "url_sommario": url_sommario,
        "acquisito_il": acquisito_il,
    }


__all__ = ["Fascicolo", "SommarioIllegibile", "atti_del_sommario", "fascicoli_in_elenco"]
