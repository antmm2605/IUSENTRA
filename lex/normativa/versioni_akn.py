"""Archivio locale multiversione AKN, separato dagli indici di ricerca corrente.

Le edizioni storiche non vengono mescolate alla classifica corrente. Una lettura
puntuale usa l'intervallo della successione ufficiale e conserva testo, partizione,
SHA XML, ZIP e data di ricezione. Non decide le disposizioni transitorie del caso.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from lxml import etree

from lex.normativa.normattiva_akn_importer import parse_akn
from lex.normativa.biblioteca.fabbisogno import norm_articolo
from lex.normativa.testi_archiviati import archivia_testo,leggi_testo,CODEC


from functools import lru_cache


@lru_cache(maxsize=1)
def impronta_lettore() -> str:
    """Versione riproducibile dei lettori, indipendente dal percorso del PC."""
    root=Path(__file__).parent
    files=("versioni_akn.py","normattiva_akn_importer.py","struttura.py",
           "qualita_testo.py","biblioteca/fabbisogno.py","testi_archiviati.py")
    sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
    return hashlib.sha256(json.dumps(sources,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def assicura_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS normative_akn_chains (
        id TEXT PRIMARY KEY, urn TEXT NOT NULL, autorita TEXT NOT NULL,
        tipo TEXT NOT NULL, numero TEXT NOT NULL, anno INTEGER NOT NULL,
        zip_path TEXT NOT NULL, zip_sha256 TEXT NOT NULL,
        acquisita_utc TEXT NOT NULL, acquisita_giorno_it TEXT NOT NULL,
        completa INTEGER NOT NULL DEFAULT 0, versioni INTEGER NOT NULL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS normative_akn_chain_identity ON normative_akn_chains(autorita,tipo,numero,anno,completa);
    CREATE INDEX IF NOT EXISTS normative_akn_chain_urn ON normative_akn_chains(urn,completa,acquisita_utc);
    CREATE TABLE IF NOT EXISTS normative_akn_editions (
        id INTEGER PRIMARY KEY, chain_id TEXT NOT NULL REFERENCES normative_akn_chains(id),
        ordinal INTEGER NOT NULL, dal TEXT NOT NULL, espressione_dal TEXT NOT NULL, al_escluso TEXT,
        xml_entry TEXT NOT NULL, xml_sha256 TEXT NOT NULL, data_gu TEXT,
        titolo TEXT NOT NULL, testo_atto TEXT NOT NULL, tipo_edizione TEXT NOT NULL,
        UNIQUE(chain_id,ordinal));
    CREATE INDEX IF NOT EXISTS normative_akn_editions_range ON normative_akn_editions(chain_id,dal,al_escluso);
    CREATE TABLE IF NOT EXISTS normative_akn_articles (
        id INTEGER PRIMARY KEY, edition_id INTEGER NOT NULL REFERENCES normative_akn_editions(id),
        ordinal INTEGER NOT NULL, numero TEXT NOT NULL, partizione TEXT NOT NULL,
        localizzatore_xml TEXT NOT NULL, rubrica TEXT NOT NULL, testo TEXT NOT NULL,
        sha256_testo TEXT NOT NULL, struttura_json TEXT NOT NULL, solo_intestazione INTEGER NOT NULL DEFAULT 0,
        UNIQUE(edition_id,ordinal));
    CREATE INDEX IF NOT EXISTS normative_akn_articles_exact ON normative_akn_articles(edition_id,numero,partizione);
    """)
    conn.execute("CREATE TABLE IF NOT EXISTS normative_akn_storage_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT OR REPLACE INTO normative_akn_storage_meta(key,value) VALUES('text_codec',?)",(CODEC,))
    if "lettore_sha256" not in {row[1] for row in conn.execute("PRAGMA table_info(normative_akn_chains)")}:
        conn.execute("ALTER TABLE normative_akn_chains ADD COLUMN lettore_sha256 TEXT NOT NULL DEFAULT ''")
    if "tipo_origine" not in {row[1] for row in conn.execute("PRAGMA table_info(normative_akn_chains)")}:
        conn.execute("ALTER TABLE normative_akn_chains ADD COLUMN tipo_origine TEXT NOT NULL DEFAULT 'ricerca_asincrona'")
    chain_columns={row[1] for row in conn.execute("PRAGMA table_info(normative_akn_chains)")}
    for name in ("riscontro_lettore_sha256", "riscontro_contenuti_sha256"):
        if name not in chain_columns:
            conn.execute("ALTER TABLE normative_akn_chains ADD COLUMN "+name+" TEXT NOT NULL DEFAULT ''")
    if "espressione_dal" not in {row[1] for row in conn.execute("PRAGMA table_info(normative_akn_editions)")}:
        conn.execute("ALTER TABLE normative_akn_editions ADD COLUMN espressione_dal TEXT")
    edition_columns={row[1] for row in conn.execute("PRAGMA table_info(normative_akn_editions)")}
    if "xml_decodificato_sha256" not in edition_columns:
        conn.execute("ALTER TABLE normative_akn_editions ADD COLUMN xml_decodificato_sha256 TEXT")
    if "codifica_trasporto" not in edition_columns:
        conn.execute("ALTER TABLE normative_akn_editions ADD COLUMN codifica_trasporto TEXT NOT NULL DEFAULT 'xml'")
    if "identita_provenienza_json" not in {row[1] for row in conn.execute("PRAGMA table_info(normative_akn_editions)")}:
        conn.execute("ALTER TABLE normative_akn_editions ADD COLUMN identita_provenienza_json TEXT NOT NULL DEFAULT '{}'")
    if "solo_intestazione" not in {row[1] for row in conn.execute("PRAGMA table_info(normative_akn_articles)")}:
        conn.execute("ALTER TABLE normative_akn_articles ADD COLUMN solo_intestazione INTEGER NOT NULL DEFAULT 0")


def _ordina_fotogrammi_riscontrati(archive, entries):
    """Recupera indici di confezione duplicati, non fotogrammi mancanti.

    L'ordinale memorizzato è distinto dall'indice nel nome originale. Nessun
    file viene riscritto e ogni data rimane quella attestata nel relativo XML.
    """
    from lex.normativa.normattiva_akn_importer import decodifica_xml_akn
    from datetime import date
    if len(entries)!=max(i for i,_ in entries)+1:
        raise ValueError("Quantità di fotogrammi diversa dalla confezione: recupero non ammesso")
    originals=[(i,n) for i,n in entries if i==0 and n.endswith("_ORIGINALE_V0.xml")]
    if len(originals)!=1:
        raise ValueError("Originale non univoco: recupero non ammesso")
    frames=[];urns=set();ns={"a":"http://docs.oasis-open.org/legaldocml/ns/akn/3.0"}
    for index,name in entries:
        with archive.open(name) as stream:
            payload=stream.read(64*1024**2+1)
        if len(payload)>64*1024**2:
            raise ValueError("XML oltre il limite di lettura")
        xml,_=decodifica_xml_akn(payload)
        root=etree.fromstring(xml,etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=True))
        acts=root.xpath("./a:act|./a:doc",namespaces=ns)
        if len(acts)!=1:
            raise ValueError("Partizione principale non univoca")
        act=acts[0]
        aliases={x for x in act.xpath("./a:meta/a:identification/a:FRBRWork/a:FRBRalias/@value",namespaces=ns) if x.startswith("urn:nir:")}
        expression=set(act.xpath("./a:meta/a:identification/a:FRBRExpression/a:FRBRdate/@date",namespaces=ns))
        if len(aliases)!=1 or len(expression)!=1:
            raise ValueError("Identità o espressione non univoca")
        urns.update(aliases);expr=next(iter(expression));date.fromisoformat(expr)
        match=re.search(r"_VIGENZA_(\d{4}-\d{2}-\d{2})_V",name)
        frame=match[1] if match else expr;date.fromisoformat(frame)
        if expr>frame:
            raise ValueError("Espressione successiva al fotogramma")
        frames.append({"entry":name,"indice_confezione":index,"fotogramma":frame,
                       "espressione":expr,"payload_sha256":hashlib.sha256(payload).hexdigest()})
    if len(urns)!=1:
        raise ValueError("Atti diversi nella stessa confezione: nessun accorpamento")
    frames.sort(key=lambda f:(f["fotogramma"],f["indice_confezione"]!=0,f["entry"]))
    if frames[0]["entry"]!=originals[0][1]:
        raise ValueError("Originale non iniziale")
    days=[f["fotogramma"] for f in frames[1:]]
    if len(set(days))!=len(days):
        raise ValueError("Fotogrammi con data duplicata: nessuna scelta arbitraria")
    return [(i,f["entry"]) for i,f in enumerate(frames)],{f["entry"]:f for f in frames}


def importa_multiversione(conn: sqlite3.Connection, *, archivio: Path,
                          sha256_atteso: str, acquisita_utc: str,
                          tipo_origine: str = "ricerca_asincrona",
                          identita_selezionate: set[tuple[str, str]] | None = None,
                          riconcilia_indici_confezione: bool = False) -> dict:
    if tipo_origine not in {"ricerca_asincrona","raccolta_ufficiale_preconfezionata"}:
        raise ValueError("Tipo di provenienza dell'archivio AKN non riconosciuto")
    stamp=datetime.fromisoformat(acquisita_utc)
    if stamp.tzinfo is None:
        raise ValueError("Timestamp di ricezione con fuso obbligatorio")
    acquisita_utc=stamp.astimezone(timezone.utc).isoformat()
    day=stamp.astimezone(ZoneInfo("Europe/Rome")).date()
    with Path(archivio).open("rb") as stream:
        digest=hashlib.file_digest(stream,"sha256").hexdigest()
    if digest!=sha256_atteso:
        raise ValueError("Impronta ZIP multiversione discordante")
    if identita_selezionate is not None:
        from datetime import date
        if not identita_selezionate:
            raise ValueError("Selezione di recupero vuota")
        for identity in identita_selezionate:
            if not isinstance(identity, tuple) or len(identity) != 2:
                raise ValueError("Identità di recupero non strutturata")
            date.fromisoformat(identity[0])
            if not re.fullmatch(r"[0-9A-Z]+", identity[1]):
                raise ValueError("Codice GU di recupero non valido")
    assicura_schema(conn)
    lettore=impronta_lettore()
    report={"atti_importati":0,"versioni_importate":0,"articoli_importati":0,"gia_presenti":0,"errori":[],"lettore_sha256":lettore}
    with zipfile.ZipFile(archivio) as archive:
        names=archive.namelist()
        if not any(name.lower().endswith(".xml") for name in names):
            report["errori"].append({"archivio":str(archivio),"errore":"Esportazione senza documenti XML: cartelle e ZIP ricevuti non sono testi normativi"})
            return report
        groups={}
        for name in names:
            if not name.lower().endswith(".xml"):
                continue
            match=re.search(r"(\d{4}-\d{2}-\d{2})_([0-9A-Z]+)_(?:ORIGINALE|VIGENZA_\d{4}-\d{2}-\d{2})_V(\d+)\.xml$",name)
            if not match:
                report["errori"].append({"entry":name,"errore":"Nome versione ufficiale non riconosciuto"});continue
            # Non mescolare due directory di atti diversi con lo stesso
            # codice GU errato nella confezione primaria.
            folder=name.rsplit("/",1)[0] if "/" in name else ""
            groups.setdefault((match[1],match[2],folder),[]).append((int(match[3]),name))
        if identita_selezionate is not None:
            missing = identita_selezionate - {key[:2] for key in groups}
            if missing:
                raise ValueError("Identità richieste assenti nello ZIP originale: " + repr(sorted(missing)))
            groups = {key: value for key, value in groups.items() if key[:2] in identita_selezionate}
            report["identita_selezionate"] = [list(key) for key in sorted(identita_selezionate)]
        for group_identity,entries in groups.items():
            identity=group_identity[:2]
            entries.sort()
            indexes=[index for index,name in entries]
            packaging_proof={}
            if indexes!=list(range(len(entries))) or "_ORIGINALE_V0.xml" not in entries[0][1]:
                if not riconcilia_indici_confezione:
                    report["errori"].append({"identita_gu":identity,"errore":"Successione delle versioni incompleta o duplicata"});continue
                try:
                    entries,packaging_proof=_ordina_fotogrammi_riscontrati(archive,entries)
                except (ValueError,etree.XMLSyntaxError) as exc:
                    report["errori"].append({"identita_gu":identity,"errore":"Confezione non riconciliabile: "+str(exc)});continue
            chain=hashlib.sha256(json.dumps([digest,group_identity,acquisita_utc,lettore],separators=(",",":")).encode()).hexdigest()
            if conn.execute("SELECT completa FROM normative_akn_chains WHERE id=? AND completa=1",(chain,)).fetchone():
                report["gia_presenti"]+=1;continue
            conn.execute("SAVEPOINT catena")
            urn=None;previous=None;previous_day=None;versions=0;articles=0
            try:
                for index,name in entries:
                    doc=parse_akn(archive.read(name),zip_path=Path(archivio),entry=name,
                                  collection_name="Normattiva AKN multiversione",analizza_pertinenza=False)
                    if index==0 and doc.qualita_corpo!="testo_acquisito":
                        raise ValueError("Originale senza corpo integrale riscontrato: "+doc.qualita_corpo
                                         +" "+json.dumps(doc.articoli_non_integrali[:10],ensure_ascii=False))
                    if doc.data_pubblicazione!=identity[0]:
                        raise ValueError("Pubblicazione XML discordante dal gruppo GU")
                    if urn is None:
                        urn=doc.urn
                        parsed=re.fullmatch(r"urn:nir:([^:]+):([^:]+):(\d{4})-\d{2}-\d{2}(?:;([^;]+))?",urn)
                        if not parsed:
                            raise ValueError("Identità normativa non strutturata")
                        conn.execute("INSERT INTO normative_akn_chains (id,urn,autorita,tipo,numero,anno,zip_path,zip_sha256,acquisita_utc,acquisita_giorno_it) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (chain,urn,parsed[1],parsed[2],parsed[4] or "",int(parsed[3]),str(archivio),digest,acquisita_utc,day.isoformat()))
                        conn.execute("UPDATE normative_akn_chains SET tipo_origine=?,lettore_sha256=? WHERE id=?",(tipo_origine,lettore,chain))
                    frame=re.search(r"_VIGENZA_(\d{4}-\d{2}-\d{2})_V",name)
                    frame_day=frame[1] if frame else doc.redazione_id
                    from datetime import date
                    date.fromisoformat(frame_day)
                    # Un nuovo fotogramma può mantenere l'espressione testuale
                    # precedente se cambia soltanto l'apparato delle modifiche.
                    # V0 può già dichiarare la decorrenza differita che V1
                    # riporta nel nome. Conserviamo entrambi: V0 ha intervallo
                    # vuoto, V1 resta la sola edizione leggibile da quella data.
                    # Altri duplicati o retrocessioni non sono accettati.
                    initial_same_day=(index==1 and frame_day==previous_day
                                      and doc.redazione_id==frame_day)
                    if (doc.urn!=urn or doc.redazione_id>frame_day
                            or (previous_day and frame_day<=previous_day and not initial_same_day)):
                        raise ValueError("Identità o successione dei fotogrammi ufficiali discordante: "
                                         +json.dumps({"entry":name,"urn":doc.urn,"urn_iniziale":urn,
                                                      "espressione":doc.redazione_id,"fotogramma":frame_day,
                                                      "precedente":previous_day},ensure_ascii=False))
                    if previous is not None:
                        conn.execute("UPDATE normative_akn_editions SET al_escluso=? WHERE id=?",(frame_day,previous))
                    previous=conn.execute("INSERT INTO normative_akn_editions (chain_id,ordinal,dal,espressione_dal,al_escluso,xml_entry,xml_sha256,data_gu,titolo,testo_atto,tipo_edizione) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (chain,index,frame_day,doc.redazione_id,None,name,doc.xml_sha256,doc.data_pubblicazione,doc.titolo or "",archivia_testo(doc.text_content),doc.vigenza)).lastrowid
                    conn.execute("UPDATE normative_akn_editions SET xml_decodificato_sha256=?,codifica_trasporto=? WHERE id=?",
                                 (doc.xml_decodificato_sha256,doc.codifica_trasporto,previous))
                    identita_provenienza={"urn_originale_akn":getattr(doc,"urn_originale_akn",doc.urn),
                        "data_atto_riscontro":getattr(doc,"data_atto_riscontro",None),
                        "identita_pubblicazione":getattr(doc,"identita_pubblicazione",None),
                        "identita_metadata_non_datata":getattr(doc,"identita_non_datata",False),
                        "ordine_fotogramma_riscontro":packaging_proof.get(name)}
                    conn.execute("UPDATE normative_akn_editions SET identita_provenienza_json=? WHERE id=?",
                                 (json.dumps(identita_provenienza,ensure_ascii=False),previous))
                    previous_day=frame_day;versions+=1
                    for ordinal,article in enumerate(doc.articles):
                        conn.execute("INSERT INTO normative_akn_articles (edition_id,ordinal,numero,partizione,localizzatore_xml,rubrica,testo,sha256_testo,struttura_json,solo_intestazione) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (previous,ordinal,norm_articolo(article.article_number or ""),article.partizione,article.localizzatore_xml,
                             article.article_title or "",archivia_testo(article.article_text),hashlib.sha256(article.article_text.encode()).hexdigest(),
                             archivia_testo(json.dumps(article.struttura_normativa,ensure_ascii=False)),int(article.solo_intestazione_xml)))
                        articles+=1
                conn.execute("UPDATE normative_akn_chains SET completa=1,versioni=? WHERE id=?",(versions,chain))
                conn.execute("RELEASE catena");conn.commit()
                report["atti_importati"]+=1;report["versioni_importate"]+=versions;report["articoli_importati"]+=articles
            except (ValueError,sqlite3.Error,etree.XMLSyntaxError) as exc:
                conn.execute("ROLLBACK TO catena");conn.execute("RELEASE catena")
                report["errori"].append({"identita_gu":identity,"directory_atto":group_identity[2],"errore":str(exc)[:500]})
    return report


def leggi_versione(conn: sqlite3.Connection, *, urn: str, data_riferimento: str,
                   partizione: str | None = None) -> list[dict]:
    """Tutto il corpo articolato dell'edizione univoca, senza query approssimate."""
    from datetime import date
    date.fromisoformat(data_riferimento)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='normative_akn_chains'").fetchone():
        return []
    parsed=re.fullmatch(r"urn:nir:([^:]+):([^:]+):(\d{4})(?:-\d{2}-\d{2})?(?:;([^;]+))?",urn)
    if not parsed:
        return []
    cursor=conn.cursor();cursor.row_factory=sqlite3.Row
    from lex.testi_ufficiali import _varianti_urn, _urn_canonico
    pairs=[]
    for variant in _varianti_urn(urn):
        value=re.fullmatch(r"urn:nir:([^:]+):([^:]+):(\d{4})(?:-\d{2}-\d{2})?(?:;([^;]+))?",variant)
        if value:pairs.append((value[1],value[2]))
    clauses="("+" OR ".join("(autorita=? AND tipo=?)" for _ in pairs)+") AND numero=? AND anno=? AND completa=1 AND acquisita_giorno_it>=?"
    args=[part for pair in pairs for part in pair]+[parsed[4] or "",int(parsed[3]),data_riferimento]
    chain_columns={row[1] for row in conn.execute("PRAGMA table_info(normative_akn_chains)")}
    if "lettore_sha256" not in chain_columns:
        return []  # archivio precedente: rilettura dagli originali obbligatoria
    from lex.normativa.lettori_attestati import politica_lettori
    policy=politica_lettori(impronta_lettore())
    readers=sorted(policy.lettori)
    clauses+=" AND lettore_sha256 IN ("+",".join("?" for _ in readers)+")"
    args.extend(readers)
    current=impronta_lettore()
    if {"riscontro_lettore_sha256", "riscontro_contenuti_sha256"}<=chain_columns:
        # Un confronto tecnico globale non convalida ogni vecchia catena.
        # La rilettura puntuale di tutti i suoi XML deve aver prodotto la prova.
        clauses+=" AND (lettore_sha256=? OR (riscontro_lettore_sha256=? AND length(riscontro_contenuti_sha256)=64 AND riscontro_contenuti_sha256 NOT GLOB '*[^0-9a-f]*'))"
        args.extend([current,current])
    else:
        clauses+=" AND lettore_sha256=?"
        args.append(current)
    origin_order="CASE WHEN tipo_origine='ricerca_asincrona' THEN 0 ELSE 1 END," if "tipo_origine" in chain_columns else ""
    chains=cursor.execute("SELECT * FROM normative_akn_chains WHERE "+clauses+" ORDER BY acquisita_giorno_it DESC,"+origin_order+"acquisita_utc DESC",args).fetchall()
    if len({_urn_canonico(row["urn"]) for row in chains})!=1:
        return []
    if re.search(r":\d{4}-\d{2}-\d{2}(?:;|$)",urn) and _urn_canonico(chains[0]["urn"])!=_urn_canonico(urn):
        return []
    for chain in chains[:1]:
        editions=cursor.execute("SELECT * FROM normative_akn_editions WHERE chain_id=? AND dal<=? AND (al_escluso IS NULL OR al_escluso>?)",(chain["id"],data_riferimento,data_riferimento)).fetchall()
        if len(editions)!=1:
            continue
        edition=editions[0]
        rows=cursor.execute("SELECT * FROM normative_akn_articles WHERE edition_id=? ORDER BY ordinal",(edition["id"],)).fetchall()
        if partizione is not None:
            rows=[row for row in rows if row["partizione"]==partizione]
        if len({row["numero"] for row in rows})!=len(rows):
            return []  # il chiamante deve dichiarare l'allegato, non indovinarlo
        coverage_end=(date.fromisoformat(chain["acquisita_giorno_it"])+timedelta(days=1)).isoformat()
        identita_provenienza=json.loads(edition["identita_provenienza_json"]) if "identita_provenienza_json" in edition.keys() else {}
        if not isinstance(identita_provenienza,dict):raise ValueError("Provenienza identità non strutturata")
        result=[]
        for row in rows:
            testo=leggi_testo(row["testo"])
            struttura=leggi_testo(row["struttura_json"])
            if hashlib.sha256(testo.encode()).hexdigest()!=row["sha256_testo"]:
                raise ValueError("Testo AKN locale alterato")
            result.append({**dict(row),**identita_provenienza,"politica_lettori_sha256":policy.manifest_sha256,"rapporto_compatibilita_sha256":policy.rapporto_sha256,"testo":testo,"struttura_json":struttura,"urn":chain["urn"],"titolo_atto":edition["titolo"],"versione_dal":edition["dal"],"espressione_dal":edition["espressione_dal"],
                "versione_al_escluso":min(edition["al_escluso"] or coverage_end,coverage_end),"xml_sha256":edition["xml_sha256"],
                "xml_entry":edition["xml_entry"],
                "xml_decodificato_sha256":edition["xml_decodificato_sha256"] or edition["xml_sha256"],
                "codifica_trasporto":edition["codifica_trasporto"],"zip_sha256":chain["zip_sha256"],"acquisita_utc":chain["acquisita_utc"],
                "data_gu":edition["data_gu"],"tipo_origine":chain["tipo_origine"] if "tipo_origine" in chain_columns else "ricerca_asincrona",
                "catena_completa":True,"lettore_sha256":chain["lettore_sha256"],
                "lettore_riscontro_sha256":chain["riscontro_lettore_sha256"] if "riscontro_lettore_sha256" in chain_columns else "",
                "rilettura_catena_sha256":chain["riscontro_contenuti_sha256"] if "riscontro_contenuti_sha256" in chain_columns else ""})
        return result
    return []
