"""Testo vigente di un atto da Normattiva in Akoma Ntoso (AKN) e conversione nel formato di ``importa_fonti``.

Percorso ufficiale e pubblico: la pagina ``uri-res/N2Ls?<URN>`` espone data di pubblicazione in Gazzetta e codice
redazionale; ``do/atto/caricaAKN?dataGU=..&codiceRedaz=..&dataVigenza=AAAAMMGG`` restituisce l'atto in AKN vigente
alla data. Nessuna autenticazione, sessione con cookie come nel browser, una richiesta alla volta con pausa e
ripetizione limitata in caso di connessione interrotta. Solo gli articoli del corpo dell'atto (allegati, componenti
e testi delle modifiche hanno numerazioni proprie).
"""
from __future__ import annotations

import hashlib
import html
import re
import time
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar

from lxml import etree

NS = {"a": "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"}
BASE = "https://www.normattiva.it"
AGENTE = "IUSENTRA-biblioteca-normativa/1.0 (studio legale)"
SIGLA = {"legge": "l.", "decreto.legislativo": "d.lgs.", "decreto.del.presidente.della.repubblica": "d.P.R.",
         "decreto.legge": "d.l.", "regio.decreto": "r.d.", "decreto": "d.m.", "legge.costituzionale": "l. cost."}


@dataclass
class AttoScaricato:
    urn_richiesto: str
    xml: bytes
    titolo_pagina: str
    data_gu: str
    codice_redazionale: str
    data_vigenza: str  # AAAAMMGG
    url: str
    sha256_xml: str


def _apri(opener, url: str, timeout: float, tentativi: int = 3, pausa: float = 3.0) -> bytes:
    ultimo: Exception | None = None
    for n in range(tentativi):
        try:
            return opener.open(url, timeout=timeout).read()
        except Exception as exc:  # noqa: BLE001 - connessioni interrotte dal server: si riprova con pausa crescente
            ultimo = exc
            time.sleep(pausa * (n + 1))
    raise RuntimeError(f"Normattiva non raggiungibile ({type(ultimo).__name__})") from ultimo


def nuovo_opener():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", AGENTE)]
    return opener


def scarica(urn: str, data_vigenza: str, *, opener=None, timeout: float = 90.0) -> AttoScaricato:
    """``data_vigenza`` AAAAMMGG. Solleva ``ValueError`` se la pagina non espone l'AKN o la risposta non e' AKN."""
    opener = opener or nuovo_opener()
    pagina = _apri(opener, f"{BASE}/uri-res/N2Ls?{urn}", timeout).decode("utf-8", "replace")
    m = re.search(r"caricaAKN\?dataGU=(\d{8})&amp;codiceRedaz=([0-9A-Z]+)", pagina)
    t = re.search(r"<title>([^<]*)", pagina)
    if not m:
        raise ValueError(f"{urn}: atto non trovato su Normattiva o senza testo AKN")
    gu, redaz = m.groups()
    xml = _apri(opener, f"{BASE}/do/atto/caricaAKN?dataGU={gu}&codiceRedaz={redaz}&dataVigenza={data_vigenza}", timeout)
    if b"<akomaNtoso" not in xml[:3000]:
        raise ValueError(f"{urn}: la risposta non e' Akoma Ntoso")
    titolo = html.unescape(t.group(1)).replace(" - Normattiva", "").strip() if t else ""
    url = (f"{BASE}/atto/caricaDettaglioAtto?atto.dataPubblicazioneGazzetta={gu[:4]}-{gu[4:6]}-{gu[6:]}"
           f"&atto.codiceRedazionale={redaz}")
    return AttoScaricato(urn, xml, titolo, gu, redaz, data_vigenza, url, hashlib.sha256(xml).hexdigest())


def _testo(el) -> str:
    t = " ".join(x.strip() for x in el.itertext() if x.strip())
    return re.sub(r"\s+([,.;:)])", r"\1", re.sub(r"\s+", " ", t)).strip()


def _numero(num: str) -> str:
    v = re.sub(r"^art(icolo)?\.?\s*", "", num.strip().lower()).strip(" .")
    return re.sub(r"[\s\-]", "", v)


def converti(atto: AttoScaricato, chiave: str, raccolto_il: str) -> list[dict]:
    """Righe JSONL (una per articolo) con URL, data di vigenza e impronta dell'AKN di origine."""
    root = etree.fromstring(atto.xml, parser=etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True))
    urn = next((v for v in root.xpath("//a:FRBRWork/a:FRBRalias/@value", namespaces=NS) if v.startswith("urn:nir:")), "")
    if not urn:
        raise ValueError(f"{atto.urn_richiesto}: URN assente nell'AKN")
    tipo = urn.split(":")[-2]
    numero, data = urn.split(";")[-1], urn.split(":")[-1].split(";")[0]
    titoli = root.xpath("//a:preface//a:docTitle", namespaces=NS)
    titolo = _testo(titoli[0]) if titoli else atto.titolo_pagina
    sigla = f"{SIGLA.get(tipo, tipo)} {numero}/{data[:4]}"
    vig = f"{atto.data_vigenza[:4]}-{atto.data_vigenza[4:6]}-{atto.data_vigenza[6:]}"
    righe, visti = [], set()
    for art in root.xpath("//a:body//a:article[not(ancestor::a:attachment) and not(ancestor::a:component) "
                          "and not(ancestor::a:mod)]", namespaces=NS):
        n = art.find("a:num", NS)
        if n is None:
            continue
        nr = _numero(_testo(n))
        corpo = _testo(art)
        if not nr or nr in visti or not corpo:
            continue
        visti.add(nr)
        h = art.find("a:heading", NS)
        righe.append({
            "chiave": chiave, "atto": sigla, "articolo": nr, "rubrica": _testo(h).strip("() ") if h is not None else "",
            "testo": corpo, "titolo_atto": titolo, "data_atto": data, "urn": urn, "vigenza": "VIGENTE",
            "fonte_testo": "Normattiva (Akoma Ntoso vigente)", "url": atto.url, "consolidato_al": vig,
            "raccolto_il": raccolto_il,
            "provenienza_integrazione": {"vigenza_richiesta": vig, "sha256_akn": atto.sha256_xml,
                                         "codice_redazionale": atto.codice_redazionale, "data_gu": atto.data_gu},
        })
    return righe
