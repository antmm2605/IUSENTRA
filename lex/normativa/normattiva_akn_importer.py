"""Adattatore AKN ufficiale per l'importatore e gli indici Normattiva nativi.

Non trasforma allegati in articoli del corpo principale. Le date provengono da
FRBRWork/FRBRExpression oppure da una firma testuale esplicita riscontrata;
mai dalla data del download o da numeri indovinati.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from lex.normativa.normattiva_importer import ArticleRecord, DocumentRecord, clean_text, detect_topics, relevance_score, topic_names
from lex.normativa.struttura import percorso_xml

NS={"a":"http://docs.oasis-open.org/legaldocml/ns/akn/3.0"}


@dataclass
class ArticoloAKN(ArticleRecord):
    localizzatore_xml: str = ""
    partizione: str = "corpo_principale"


@dataclass
class DocumentoAKN(DocumentRecord):
    xml_decodificato_sha256: str = ""
    codifica_trasporto: str = "xml"
    qualita_corpo: str = "da_verificare"
    articoli_non_integrali: tuple[str,...] = ()
    identita_non_datata: bool = False
    identita_pubblicazione: tuple[str,str] | None = None
    urn_originale_akn: str = ""
    data_atto_riscontro: dict | None = None


def decodifica_xml_akn(raw: bytes) -> tuple[bytes, str]:
    """Un solo livello Base64 canonico; il payload ufficiale originale resta intatto."""
    if raw.lstrip().startswith(b"<"):
        return raw, "xml"
    compact=b"".join(raw.split())
    try:
        decoded=base64.b64decode(compact,validate=True)
    except (ValueError,binascii.Error) as exc:
        raise ValueError("Payload AKN non XML né Base64 canonico") from exc
    if base64.b64encode(decoded)!=compact or not decoded.lstrip().startswith(b"<"):
        raise ValueError("Payload AKN Base64 non canonico o non XML")
    return decoded, "base64"


def parse_akn(xml: bytes, *, zip_path: Path, entry: str, collection_name: str, analizza_pertinenza: bool = True) -> DocumentRecord:
    decoded,encoding=decodifica_xml_akn(xml)
    root=etree.fromstring(decoded,parser=etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=True))
    if etree.QName(root).localname!="akomaNtoso":
        raise ValueError("Risposta non Akoma Ntoso")
    acts=root.xpath("./a:act|./a:doc",namespaces=NS)
    if len(acts)!=1:
        raise ValueError("Partizione principale AKN non univoca")
    act=acts[0]
    def text(node):
        return clean_text(" ".join(node.xpath(".//text()[not(ancestor::a:meta)]",namespaces=NS)))
    def one(query):
        values=act.xpath(query,namespaces=NS)
        return values[0] if len(values)==1 else ""
    urns=[v for v in act.xpath("./a:meta/a:identification/a:FRBRWork/a:FRBRalias/@value",namespaces=NS) if v.startswith("urn:nir:")]
    if len(set(urns))!=1:
        raise ValueError("Identità NIR AKN assente o ambigua")
    urn=urns[0];work_date=one("./a:meta/a:identification/a:FRBRWork/a:FRBRdate/@date")
    version=one("./a:meta/a:identification/a:FRBRExpression/a:FRBRdate/@date")
    from datetime import date
    date.fromisoformat(version)
    match=re.fullmatch(r"urn:nir:([^:]+):([^:]+):(\d{4}-\d{2}-\d{2})(?:;([^;]+))?",urn)
    identita_non_datata=False;identita_pubblicazione=None
    urn_originale_akn=urn;data_atto_riscontro=None
    if match:
        date.fromisoformat(work_date)
        if match[3]!=work_date:
            raise ValueError("Identità e data FRBRWork discordanti")
        tipo,numero=match[2],match[4]
    elif urn=="urn:nir:stato:costituzione" and work_date=="0000-00-00":
        # Alias ufficiale non datato, non una data da ricostruire o indovinare.
        gu_identity=re.search(r"(\d{4}-\d{2}-\d{2})_([0-9A-Z]+)_",entry)
        eli_aliases=act.xpath("./a:meta/a:identification/a:FRBRWork/a:FRBRalias[@name='eli']/@value",namespaces=NS)
        if not gu_identity or len(set(eli_aliases))!=1:
            raise ValueError("Identità non datata priva di riscontro ELI univoco")
        declared=re.fullmatch(r"eli/id/(\d{4})/(\d{2})/(\d{2})/([0-9A-Z]+)/(ORIGINAL|CONSOLIDATED/(\d{8}))",eli_aliases[0])
        if not declared or ("-".join(declared.group(1,2,3)),declared[4])!=gu_identity.group(1,2):
            raise ValueError("Identità ELI e pubblicazione XML discordanti")
        date.fromisoformat(gu_identity[1])
        if declared[5]=="ORIGINAL":
            if not entry.endswith("_ORIGINALE_V0.xml"):
                raise ValueError("Versione ELI originale non coerente col file")
        else:
            frame=re.search(r"_VIGENZA_(\d{4}-\d{2}-\d{2})_V[0-9]+\.xml$",entry)
            if not frame or frame[1].replace("-", "")!=declared[6]:
                raise ValueError("Intervallo ELI consolidato discordante dal file")
            date.fromisoformat(frame[1])
        identita_non_datata=True;identita_pubblicazione=gu_identity.group(1,2)
        tipo,numero="costituzione",None
        # Riscontro testuale esplicito, non la data della Gazzetta o del download.
        source_text=text(act)
        signatures=re.findall(r"Data a Roma, add[iì](?:'|’)?\s+27\s+dicembre\s+1947",source_text,re.I)
        if len(signatures)!=1:
            raise ValueError("Data della firma della Costituzione non riscontrata univocamente")
        work_date="1947-12-27"
        urn=urn+":"+work_date
        data_atto_riscontro={"origine":"firma_nel_testo_ufficiale", "data":work_date,
            "estratto":signatures[0],"localizzatore_xml":act.getroottree().getpath(act),
            "sha256_testo_riscontro":hashlib.sha256(source_text.encode()).hexdigest(),
            "FRBRWork_originale":"0000-00-00", "urn_originale_akn":urn_originale_akn}
    else:
        raise ValueError("Identità e data FRBRWork discordanti")
    digest=hashlib.sha256(xml).hexdigest()
    titles=act.xpath("./a:preface//a:docTitle|./a:preamble//a:docTitle",namespaces=NS)
    title=text(titles[0]) if titles else (
        tipo.replace("."," ").capitalize()+(" "+f"n. {numero}" if numero else "")
        +(" del "+date.fromisoformat(work_date).strftime("%d/%m/%Y") if work_date else ""))
    bodies=act.xpath("./a:body|./a:mainBody",namespaces=NS)
    attachments=act.xpath("./a:attachments/a:attachment",namespaces=NS)
    if not any(text(node) for node in bodies+attachments):
        raise ValueError("Testo del provvedimento AKN vuoto")
    articles=[];components=[]
    def append_article(node, number, partition="corpo_principale"):
        value=text(node)
        if not value:
            return
        headings=node.xpath("./a:heading",namespaces=NS)
        matches=detect_topics(title,value,collection_name=collection_name) if analizza_pertinenza else []
        articles.append(ArticoloAKN(article_number=number,article_title=text(headings[0]) if headings else None,
            article_text=value,topics=topic_names(matches),relevance_score=relevance_score(matches),
            struttura_normativa=percorso_xml(node,urn,version,digest),
            solo_intestazione_xml=not clean_text(" ".join(node.xpath(
                ".//text()[not(ancestor::a:num) and not(ancestor::a:heading) and not(ancestor::a:subheading) and not(ancestor::a:meta)]",
                namespaces=NS))),
            localizzatore_xml=node.getroottree().getpath(node),partizione=partition))
    for body in bodies:
        for article in body.xpath(".//a:article[not(ancestor::a:mod) and not(ancestor::a:attachment) and not(ancestor::a:article)]",namespaces=NS):
            nums=article.xpath("./a:num",namespaces=NS)
            append_article(article,text(nums[0]) if len(nums)==1 else None)
    for attachment in attachments:
        docs=attachment.xpath("./a:doc",namespaces=NS)
        if len(docs)!=1:
            raise ValueError("Allegato AKN senza partizione documentale univoca")
        doc=docs[0];explicit=doc.xpath(".//a:article[not(ancestor::a:mod) and not(ancestor::a:article)]",namespaces=NS)
        if explicit:
            for article in explicit:
                nums=article.xpath("./a:num",namespaces=NS)
                append_article(article,text(nums[0]) if len(nums)==1 else None,doc.get("name") or doc.getroottree().getpath(doc))
        elif "-art. " in (doc.get("name") or ""):
            name=doc.get("name");label=name.rsplit("-art. ",1)[1].strip()
            # Una sola terminazione tipografica, senza cambiare ordine o partizione XML.
            if label.endswith("."):
                label=label[:-1].rstrip()
            arabic=re.fullmatch(r"[0-9]+(?:/[0-9]+)?(?:[a-z]+)?(?:[-.\s]+[0-9a-z]+)*",label,re.I)
            # Le ratifiche conservano gli articoli degli accordi in numeri
            # romani. Non convertirli in arabi: l'identità è quella dell'XML.
            roman_parts=re.fullmatch(r"([MDCLXVI]+)(?:-(bis|ter|quater|quinquies|sexies|septies|octies|novies|decies|undecies|duodecies))?(?: [a-z]\))?",label,re.I)
            roman=roman_parts and re.fullmatch(r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})",roman_parts[1].upper())
            # Etichette espresse nei corpi primari storici: la qualifica resta
            # parte dell'identita, non viene ridotta al solo numero arabo.
            qualificato=re.fullmatch(r"[0-9]+(?:-(?:bis|ter|quater))? \((?:transitorio|aggiunta)\)",label,re.I)
            lettera=re.fullmatch(r"[A-Z]",label)
            sottolettera=re.fullmatch(r"[0-9]+ [a-z]\)",label)
            qualificatore_romano=re.fullmatch(r"[0-9]+ ?\(([MDCLXVI]+)\)",label)
            romano_qualificatore=qualificatore_romano and re.fullmatch(r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})",qualificatore_romano[1])
            speciale=label.casefold() in {"addizionale","transitorio"}
            if not arabic and not roman and not qualificato and not lettera and not sottolettera and not romano_qualificatore and not speciale:
                raise ValueError("Numero dell'articolo dichiarato nell'allegato AKN non valido: "+repr(label))
            annex_bodies=doc.xpath("./a:mainBody|./a:body",namespaces=NS)
            if len(annex_bodies)!=1:
                raise ValueError("Corpo dell'articolo in allegato AKN non univoco")
            append_article(annex_bodies[0],"Art. "+label+".",name.rsplit("-art. ",1)[0])
        else:
            annex_bodies=doc.xpath("./a:mainBody|./a:body",namespaces=NS)
            value=clean_text(" ".join(text(body) for body in annex_bodies))
            if value:
                components.append({"localizzatore_xml":doc.getroottree().getpath(doc),
                                   "testo":value,"sha256_testo":hashlib.sha256(value.encode()).hexdigest()})
    from lex.normativa.qualita_testo import qualita_testo
    incomplete=tuple(a.article_number or a.localizzatore_xml for a in articles
                     if qualita_testo(a.article_text,solo_rubrica=a.solo_intestazione_xml)!="testo_acquisito")
    if articles:
        body_quality="testo_acquisito" if not incomplete else "articoli_non_integrali"
    else:
        body_texts=[value for value in [text(body) for body in bodies]+[item["testo"] for item in components] if value.strip()]
        body_quality="testo_acquisito" if body_texts and all(qualita_testo(value)=="testo_acquisito" for value in body_texts) else "corpo_non_riscontrato"
    full=clean_text(" ".join(text(child) for child in act if isinstance(child.tag,str) and etree.QName(child).localname!="meta"))
    matches=detect_topics(title,full[:50000],collection_name=collection_name) if analizza_pertinenza else []
    # I metadati non possono attribuire a un atto il corpo di un altro.
    # L'export primario 26G00056 contiene un file URN38 con intestazione39.
    declared_numbers=[text(n).strip() for n in act.xpath("./a:preface//a:docNumber",namespaces=NS)]
    def canon_number(value):
        value=re.sub(r"^n[.]?\s*","",value.strip(),flags=re.I)
        annotation=re.fullmatch(r"(.+?)\s*\(Raccolta(?:\s+ufficiale)?\s+([0-9]{4})\)",value,re.I)
        if annotation:
            publication_years={x[:4] for x in act.xpath("./a:meta/a:publication/@date",namespaces=NS) if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",x)}
            if annotation[2] not in ({work_date[:4]}|publication_years):return value.casefold()
            value=annotation[1].strip()
        value=re.sub(r"\s+","",value).strip(".")
        if value.isdecimal():return str(int(value))
        # Solo il numero dell'atto, non i numeri di articoli/allegati.
        # Le intestazioni storiche usano anche la forma additiva CCCC.
        roman=value.upper()
        if re.fullmatch(r"M{0,4}(?:CM|CD|D?C{0,4})(?:XC|XL|L?X{0,4})(?:IX|IV|V?I{0,4})",roman) and roman:
            weights={"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
            numbers=[weights[x] for x in roman]
            return str(sum(-v if i+1<len(numbers) and v<numbers[i+1] else v for i,v in enumerate(numbers)))
        return value.casefold()
    if numero and declared_numbers and {canon_number(n) for n in declared_numbers}!={canon_number(numero)}:
        raise ValueError("Numero nell'intestazione documentale discordante dall'identità NIR: "
                         +repr({"urn":urn,"numeri_intestazione":declared_numbers}))
    declared_dates=set(act.xpath("./a:preface//a:docDate/@date",namespaces=NS))
    iso_dates={d for d in declared_dates if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",d)}
    if iso_dates and iso_dates!={work_date}:
        raise ValueError("Data nell'intestazione documentale discordante dall'identità NIR: "
                         +repr({"urn":urn,"date_intestazione":sorted(iso_dates)}))
    publication_dates=set(act.xpath("./a:meta/a:publication/@date",namespaces=NS))
    if len(publication_dates)>1:
        raise ValueError("Data di pubblicazione AKN non univoca")
    publication=next(iter(publication_dates),"")
    if publication:
        date.fromisoformat(publication)
    gu=re.search(r"(\d{4}-\d{2}-\d{2})_[0-9A-Z]+_",entry)
    if publication and gu and publication!=gu[1]:
        raise ValueError("Pubblicazione XML discordante dal nome del file ufficiale")
    return DocumentoAKN(xml_decodificato_sha256=hashlib.sha256(decoded).hexdigest(),
        identita_non_datata=identita_non_datata,identita_pubblicazione=identita_pubblicazione,
        urn_originale_akn=urn_originale_akn,data_atto_riscontro=data_atto_riscontro,
        codifica_trasporto=encoding,qualita_corpo=body_quality,articoli_non_integrali=incomplete,collection_name=collection_name,zip_path=str(zip_path),xml_entry=entry,
        tipo_atto=tipo,numero=numero,data_atto=work_date,
        data_pubblicazione=publication or (gu[1] if gu else None),titolo=title,urn=urn,redazione_id=version,
        vigenza="ORIGINALE" if "_ORIGINALE_" in entry else "EDIZIONE_ACQUISITA",
        xml_sha256=digest,text_content=full,topics=topic_names(matches),relevance_score=relevance_score(matches),
        is_relevant=bool(matches),articles=articles,componenti=components)
