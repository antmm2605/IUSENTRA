"""Testo vigente di un atto da Normattiva in Akoma Ntoso (AKN) e conversione nel formato di ``importa_fonti``.

Percorso ufficiale e pubblico: la pagina ``uri-res/N2Ls?<URN>`` espone data di pubblicazione in Gazzetta e codice
redazionale; ``do/atto/caricaAKN?dataGU=..&codiceRedaz=..&dataVigenza=AAAAMMGG`` restituisce l'atto in AKN vigente
alla data. Nessuna autenticazione, sessione con cookie come nel browser, una richiesta alla volta con pausa e
ripetizione limitata in caso di connessione interrotta. Il lettore nativo conserva gli articoli del corpo e
le partizioni degli allegati, senza confonderne le numerazioni; i testi delle modifiche restano nel loro contesto.
"""
from __future__ import annotations

import hashlib
import html
import re
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from http.cookiejar import CookieJar

from lxml import etree

NS = {"a": "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"}
BASE = "https://www.normattiva.it"
AGENTE = "IUSENTRA-biblioteca-normativa/1.0 (studio legale)"
SIGLA = {"legge": "l.", "decreto.legislativo": "d.lgs.", "decreto.del.presidente.della.repubblica": "d.P.R.",
         "decreto.legge": "d.l.", "regio.decreto": "r.d.", "decreto": "decreto", "legge.costituzionale": "l. cost."}


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
    data_espressione: str = ""
    url_akn_richiesto: str = ""


def _apri(opener, url: str, timeout: float, tentativi: int = 3, pausa: float = 3.0) -> bytes:
    ultimo: Exception | None = None
    for n in range(tentativi):
        try:
            return opener.open(url, timeout=timeout).read()
        except urllib.error.HTTPError as exc:
            if 400<=exc.code<500:
                # Errori di richiesta, accesso e quota non sono disconnessioni.
                # Non cambiare canale, cookie o identità per forzare questa risposta.
                raise
            ultimo=exc
            time.sleep(pausa*(n+1))
        except Exception as exc:  # noqa: BLE001 - connessioni interrotte dal server: si riprova con pausa crescente
            ultimo = exc
            time.sleep(pausa * (n + 1))
    raise RuntimeError(f"Normattiva non raggiungibile ({type(ultimo).__name__})") from ultimo


def nuovo_opener():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", AGENTE)]
    return opener


def scarica(urn: str, data_vigenza: str, *, opener=None, timeout: float = 90.0,
            identita_gu: tuple[str, str] | None = None) -> AttoScaricato:
    """``data_vigenza`` AAAAMMGG. Solleva ``ValueError`` se la pagina non espone l'AKN o la risposta non e' AKN."""
    opener = opener or nuovo_opener()
    if identita_gu is not None:
        from datetime import date
        if (not isinstance(identita_gu,tuple) or len(identita_gu)!=2
                or not all(isinstance(x,str) for x in identita_gu)):
            raise ValueError("Identità GU non strutturata")
        publication,redaz=identita_gu
        if date.fromisoformat(publication).isoformat()!=publication or not re.fullmatch(r"[0-9A-Z]{4,16}",redaz):
            raise ValueError("Identità GU non valida")
        if not re.fullmatch(r"urn:nir:[^:]+:[^:]+:[0-9]{4}-[0-9]{2}-[0-9]{2}(?:;[^;]+)?",urn):
            raise ValueError("La lettura GU diretta richiede l'identità NIR completa")
        gu=publication.replace("-","")
        # Il download AKN usa il contesto dell'atto nella sessione pubblica.
        # Inizializzarlo con la GU esatta evita il risolutore ambiguo per URN.
        dettaglio=(f"{BASE}/atto/caricaDettaglioAtto?atto.dataPubblicazioneGazzetta={publication}"
                   f"&atto.codiceRedazionale={redaz}")
        pagina=_apri(opener,dettaglio,timeout).decode("utf-8","replace")
        collegamenti=re.findall(r"caricaAKN\?dataGU=(\d{8})&amp;codiceRedaz=([0-9A-Z]+)",pagina)
        if (gu,redaz) not in collegamenti:
            raise ValueError("La pagina della GU esatta non espone il testo AKN richiesto")
        t=re.search(r"<title>([^<]*)",pagina)
    else:
        pagina = _apri(opener, f"{BASE}/uri-res/N2Ls?{urn}", timeout).decode("utf-8", "replace")
        m = re.search(r"caricaAKN\?dataGU=(\d{8})&amp;codiceRedaz=([0-9A-Z]+)", pagina)
        t = re.search(r"<title>([^<]*)", pagina)
        if not m:
            raise ValueError(f"{urn}: atto non trovato su Normattiva o senza testo AKN")
        gu, redaz = m.groups()
    url_akn = f"{BASE}/do/atto/caricaAKN?dataGU={gu}&codiceRedaz={redaz}&dataVigenza={data_vigenza}"
    xml = _apri(opener, url_akn, timeout)
    if b"<akomaNtoso" not in xml[:3000]:
        raise ValueError(f"{urn}: la risposta non e' Akoma Ntoso")
    from datetime import datetime, date
    requested=datetime.strptime(data_vigenza,"%Y%m%d").date()
    parsed=etree.fromstring(xml,parser=etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=True))
    expressions=parsed.xpath("./a:act/a:meta/a:identification/a:FRBRExpression/a:FRBRdate/@date",namespaces=NS)
    if len(expressions)!=1:
        raise ValueError("Data della versione AKN principale assente o ambigua")
    if identita_gu is not None:
        from lex.testi_ufficiali import _urn_canonico
        from lex.normativa.metadati_akn_riscontrati import leggi_documento
        document,_=leggi_documento(xml)
        if _urn_canonico(document.urn)!=_urn_canonico(urn):
            raise ValueError("Identità NIR della risposta diretta discordante")
        if document.data_pubblicazione!=identita_gu[0]:
            raise ValueError("Pubblicazione XML discordante dalla GU richiesta")
        elis=parsed.xpath("./a:act/a:meta/a:identification/a:FRBRWork/a:FRBRalias/@value|./a:doc/a:meta/a:identification/a:FRBRWork/a:FRBRalias/@value",namespaces=NS)
        eli=[value for value in elis if value.startswith("eli/")]
        stem="eli/id/"+identita_gu[0].replace("-","/")+"/"+identita_gu[1]+"/"
        if len(eli)!=1 or not eli[0].startswith(stem):
            raise ValueError("Identità ELI discordante dalla GU richiesta")
    expression=date.fromisoformat(expressions[0])
    if expression>requested:
        raise ValueError("La fonte ha restituito una versione successiva alla data richiesta")
    titolo = html.unescape(t.group(1)).replace(" - Normattiva", "").strip() if t else ""
    url = (f"{BASE}/atto/caricaDettaglioAtto?atto.dataPubblicazioneGazzetta={gu[:4]}-{gu[4:6]}-{gu[6:]}"
           f"&atto.codiceRedazionale={redaz}")
    return AttoScaricato(urn, xml, titolo, gu, redaz, data_vigenza, url, hashlib.sha256(xml).hexdigest(),expression.isoformat(),url_akn)


def _testo(el) -> str:
    t = " ".join(x.strip() for x in el.itertext() if x.strip())
    return re.sub(r"\s+([,.;:)])", r"\1", re.sub(r"\s+", " ", t)).strip()


def _numero(num: str) -> str:
    v = re.sub(r"^art(icolo)?\.?\s*", "", num.strip().lower()).strip(" .")
    return re.sub(r"[\s\-]", "", v)


def converti(atto: AttoScaricato, chiave: str, raccolto_il: str) -> list[dict]:
    """Unico lettore AKN nativo; parti ed espressione letterali, fonte immutata."""
    from lex.normativa.metadati_akn_riscontrati import leggi_documento
    from lex.normativa.qualita_testo import qualita_testo
    from .fabbisogno import norm_articolo
    from .identita import chiave_partizione
    from lex.testi_ufficiali import _urn_canonico
    if hashlib.sha256(atto.xml).hexdigest()!=atto.sha256_xml:
        raise ValueError("Impronta del payload AKN discordante")
    doc,riscontro=leggi_documento(atto.xml)
    urn=doc.urn
    if atto.data_gu or atto.codice_redazionale:
        from lex.normativa.normattiva_akn_importer import decodifica_xml_akn
        decoded,_=decodifica_xml_akn(atto.xml)
        root=etree.fromstring(decoded,etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=True))
        gu=atto.data_gu
        if not re.fullmatch(r"[0-9]{8}",gu) or doc.data_pubblicazione!=gu[:4]+"-"+gu[4:6]+"-"+gu[6:]:
            raise ValueError("Pubblicazione del testo AKN discordante dalla provenienza")
        elis=root.xpath("./a:act/a:meta/a:identification/a:FRBRWork/a:FRBRalias/@value|./a:doc/a:meta/a:identification/a:FRBRWork/a:FRBRalias/@value",namespaces=NS)
        eli=[x for x in elis if x.startswith("eli/")]
        prefix="eli/id/"+gu[:4]+"/"+gu[4:6]+"/"+gu[6:]+"/"+atto.codice_redazionale+"/"
        if len(eli)!=1 or not eli[0].startswith(prefix):raise ValueError("ELI del testo AKN discordante dalla provenienza")
    def identita(value):
        return re.fullmatch(r"urn:nir:([^:]+):([^:]+):(\d{4}(?:-\d{2}-\d{2})?)(?:;([^;]+))?",_urn_canonico(value))
    richiesto,trovato=identita(atto.urn_richiesto),identita(urn)
    def numero(value):
        return str(int(value)) if value and value.isdecimal() else value
    if (not richiesto or not trovato or (richiesto[1],richiesto[2])!=(trovato[1],trovato[2])
            or richiesto[3][:4]!=trovato[3][:4] or numero(richiesto[4])!=numero(trovato[4])
            or (len(richiesto[3])>4 and richiesto[3]!=trovato[3])):
        raise ValueError(f"{atto.urn_richiesto}: identita' dell'atto AKN discordante ({urn})")
    from datetime import datetime,date
    richiesta=datetime.strptime(atto.data_vigenza,"%Y%m%d").date().isoformat()
    if date.fromisoformat(doc.redazione_id)>date.fromisoformat(richiesta):
        raise ValueError("Espressione AKN successiva alla data richiesta")
    from .riferimenti import PARTIZIONI_CODICI
    prefissi = PARTIZIONI_CODICI
    parts={a.partizione for a in doc.articles}
    selected=None
    if chiave in prefissi:
        matches={part for part in parts if part.casefold()==prefissi[chiave].casefold()}
        if len(matches)==1:selected=next(iter(matches))
        elif parts=={"corpo_principale"}:selected="corpo_principale"
        else:raise ValueError("Partizione del codice non riscontrata univocamente nell'XML")
    tipo=trovato[2];num=trovato[4] or "";data=trovato[3]
    kind="d.P.R." if (trovato[1],tipo)==("presidente.repubblica","decreto") else (
        "d.m." if trovato[1].startswith("ministero.") and tipo=="decreto" else SIGLA.get(tipo,tipo))
    sigla=f"{kind} {num}/{data[:4]}" if num else f"{kind} del {data}"
    from collections import Counter
    omonimi=Counter((a.partizione,norm_articolo(a.article_number or "")) for a in doc.articles)
    righe=[];visti=set()
    for art in doc.articles:
        if selected is not None and art.partizione!=selected:continue
        nr=norm_articolo(art.article_number or "")
        if not nr:raise ValueError("Articolo privo di identità letterale")
        part=art.partizione
        key=chiave if selected is not None or part=="corpo_principale" or len(parts)==1 else (
            chiave_partizione(chiave,part))
        if omonimi[(part,nr)]>1:
            key=chiave_partizione(chiave,part,art.localizzatore_xml)
        if (key,nr) in visti:raise ValueError("Articoli privi di localizzatore univoco")
        visti.add((key,nr))
        title=prefissi.get(chiave) if selected is not None else (doc.titolo if part=="corpo_principale" else doc.titolo+" — "+part)
        provenance={"chiave_base_acquisizione":chiave,"vigenza_richiesta":richiesta,"sha256_akn":atto.sha256_xml,
            "sha256_payload_ufficiale":atto.sha256_xml,"sha256_xml_letto":doc.xml_sha256,
            "sha256_xml_decodificato":doc.xml_decodificato_sha256,"codice_redazionale":atto.codice_redazionale,
            "data_gu":atto.data_gu,"data_espressione_akn":doc.redazione_id,
            "url_akn_richiesto":atto.url_akn_richiesto,"partizione_xml":part,
            "localizzatore_xml":art.localizzatore_xml,"urn_originale_akn":doc.urn_originale_akn,
            "data_atto_riscontro":doc.data_atto_riscontro,"identita_pubblicazione":doc.identita_pubblicazione,
            "applicabilita_al_fascicolo_verificata":False}
        if riscontro:provenance["metadati_tecnici_riscontrati"]=riscontro
        righe.append({"chiave":key,"atto":sigla,"articolo":nr,"rubrica":art.article_title or "",
            "testo":art.article_text,"titolo_atto":title,"data_atto":data,"urn":urn,
            "vigenza":"EDIZIONE_ACQUISITA","fonte_testo":"Normattiva (Akoma Ntoso, lettore nativo)",
            "url":atto.url,"consolidato_al":doc.redazione_id,"raccolto_il":raccolto_il,
            "senza_testo":qualita_testo(art.article_text,solo_rubrica=art.solo_intestazione_xml)!="testo_acquisito",
            "struttura_normativa":art.struttura_normativa,"provenienza_integrazione":provenance})
    return righe
