"""Rilettura offline puntuale delle catene acquisite da un lettore precedente.

Non importa dati, non corregge corpi e non è una funzione della stesura online.
La prova viene scritta soltanto dopo il confronto di tutti i fotogrammi e articoli.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import sqlite3
import zipfile

from lex.normativa.biblioteca.fabbisogno import norm_articolo
from lex.normativa.normattiva_akn_importer import parse_akn
from lex.normativa.testi_archiviati import leggi_testo
from lex.normativa.versioni_akn import impronta_lettore


def _impronta(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


class ArchivioRiscontrato:
    """Un archivio già riscontrato interamente, con protezione dalle modifiche."""
    def __init__(self, path: Path, expected: str):
        self.path=Path(path).resolve(strict=True)
        with self.path.open("rb") as stream:
            digest=hashlib.file_digest(stream,"sha256").hexdigest()
        if digest!=expected:
            raise ValueError("SHA dell'archivio primario discordante")
        self.sha256=digest
        self.stat=self.path.stat()
        self.zip=zipfile.ZipFile(self.path)

    def verifica_stabilita(self):
        current=self.path.stat()
        if (current.st_size,current.st_mtime_ns,current.st_ino)!=(self.stat.st_size,self.stat.st_mtime_ns,self.stat.st_ino):
            raise ValueError("Archivio modificato durante la riconvalida")

    def close(self):
        self.zip.close()


def riconvalida_catena(conn: sqlite3.Connection, *, chain_id: str,
                       archivio: ArchivioRiscontrato, cartella_prove: Path, commit: bool = True, verifica_prosecuzione=None, attesta_sql: bool = True, massimo_xml_byte: int = 512*1024**2) -> dict:
    """Confronto integrale su una copia candidata predisposta dall'operatore."""
    if not isinstance(massimo_xml_byte,int) or not 1<=massimo_xml_byte<=512*1024**2:raise ValueError("Limite XML non valido")
    if not attesta_sql and commit:raise ValueError("La sola lettura richiede commit=False")
    columns={row[1] for row in conn.execute("PRAGMA table_info(normative_akn_chains)")}
    if not {"riscontro_lettore_sha256","riscontro_contenuti_sha256"}<=columns:
        raise ValueError("Schema candidato non predisposto alla riconvalida")
    reader=impronta_lettore()
    cur=conn.cursor();cur.row_factory=sqlite3.Row
    chain=cur.execute("SELECT * FROM normative_akn_chains WHERE id=? AND completa=1",(chain_id,)).fetchone()
    if chain is None or chain["zip_sha256"]!=archivio.sha256:
        raise ValueError("Catena o archivio primario discordanti")
    editions=cur.execute("SELECT * FROM normative_akn_editions WHERE chain_id=? ORDER BY ordinal",(chain_id,)).fetchall()
    if not editions or len(editions)!=chain["versioni"] or [e["ordinal"] for e in editions]!=list(range(len(editions))):
        raise ValueError("Fotogrammi SQL incompleti")
    archivio.verifica_stabilita()
    proofs=[]
    for edition in editions:
        if verifica_prosecuzione:verifica_prosecuzione()
        with archivio.zip.open(edition["xml_entry"]) as stream:
            payload=stream.read(massimo_xml_byte+1)
        if len(payload)>massimo_xml_byte:
            raise ValueError("XML oltre il limite di lettura")
        if hashlib.sha256(payload).hexdigest()!=edition["xml_sha256"]:
            raise ValueError("SHA XML primario discordante")
        doc=parse_akn(payload,zip_path=archivio.path,entry=edition["xml_entry"],
                      collection_name="Normattiva AKN multiversione",analizza_pertinenza=False)
        if verifica_prosecuzione:verifica_prosecuzione()
        frame=re.search(r"_VIGENZA_(\d{4}-\d{2}-\d{2})_V",edition["xml_entry"])
        expected_day=frame[1] if frame else doc.redazione_id
        expected_end=editions[edition["ordinal"]+1]["dal"] if edition["ordinal"]+1<len(editions) else None
        if (edition["dal"]!=expected_day or edition["al_escluso"]!=expected_end
                or edition["tipo_edizione"]!=doc.vigenza):
            raise ValueError("Intervallo o tipo formale dell'edizione discordante")
        if (doc.urn!=chain["urn"] or doc.redazione_id!=edition["espressione_dal"]
                or doc.data_pubblicazione!=edition["data_gu"]
                or doc.xml_decodificato_sha256!=edition["xml_decodificato_sha256"]
                or doc.codifica_trasporto!=edition["codifica_trasporto"]
                or (doc.titolo or "")!=edition["titolo"]
                or doc.text_content!=leggi_testo(edition["testo_atto"])):
            raise ValueError("Identità, versione o corpo dell'edizione discordanti")
        if edition["ordinal"]==0 and doc.qualita_corpo!="testo_acquisito":
            raise ValueError("Originale privo del corpo riscontrato")
        rows=cur.execute("SELECT * FROM normative_akn_articles WHERE edition_id=? ORDER BY ordinal",(edition["id"],)).fetchall()
        if len(rows)!=len(doc.articles):
            raise ValueError("Numero di articoli discordante")
        source=[];stored=[]
        for ordinal,(row,article) in enumerate(zip(rows,doc.articles)):
            if verifica_prosecuzione and ordinal%512==0:verifica_prosecuzione()
            native=(ordinal,norm_articolo(article.article_number or ""),article.partizione,
                    article.localizzatore_xml,article.article_title or "",article.article_text,
                    hashlib.sha256(article.article_text.encode()).hexdigest(),article.struttura_normativa,
                    int(article.solo_intestazione_xml))
            previous=(row["ordinal"],row["numero"],row["partizione"],row["localizzatore_xml"],
                      row["rubrica"],leggi_testo(row["testo"]),row["sha256_testo"],
                      json.loads(leggi_testo(row["struttura_json"])),row["solo_intestazione"])
            if native!=previous:
                raise ValueError("Corpo, partizione, ordine o impronta dell'articolo discordanti")
            source.append(native);stored.append(previous)
        proofs.append({"edition_id":edition["id"],"xml_entry":edition["xml_entry"],
            "xml_sha256":edition["xml_sha256"],"sha256_campi_origine":_impronta(stored),
            "sha256_campi_runtime":_impronta(source),"articoli":len(rows),"riscontro":"identico"})
    archivio.verifica_stabilita()
    report={"schema":1,"chain_id":chain_id,"urn":chain["urn"],"zip_sha256":archivio.sha256,
            "lettore_origine":chain["lettore_sha256"],"lettore_runtime":reader,
            "utc":datetime.now(timezone.utc).isoformat(),"confronti":proofs,
            "esito":"verificato","applicabilita_giuridica_certificata":False}
    raw=json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    digest=hashlib.sha256(raw).hexdigest()
    output=Path(cartella_prove)/chain_id[:2];output.mkdir(parents=True,exist_ok=True)
    path=output/(chain_id+"-"+digest+".json")
    with path.open("xb") as stream:stream.write(raw)
    if attesta_sql:
        conn.execute("UPDATE normative_akn_chains SET riscontro_lettore_sha256=?,riscontro_contenuti_sha256=? WHERE id=?",
                     (reader,digest,chain_id))
        if commit:conn.commit()
    return {"chain_id":chain_id,"lettore_runtime":reader,"sha256":digest,"file":str(path),
            "versioni":len(editions),"articoli":sum(p["articoli"] for p in proofs)}
