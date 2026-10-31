"""Read only the authenticated studio's existing native corpus; never fetch a source."""
from __future__ import annotations
import hashlib
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit
from web.services.sentenzeweb_reader import text_blocks


def _source_url(value):
    try:
        parsed = urlsplit(str(value or ""))
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and parsed.port in {None,443}:
            return str(value)
    except ValueError:
        pass
    return ""


def search(owner, *, source, query="", limit=20):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}",source):
        raise ValueError("Seleziona una fonte del catalogo.")
    with owner._connect() as connection:
        if not connection.execute("SELECT 1 FROM fonti_giurisprudenza WHERE codice=?",(source,)).fetchone():
            raise ValueError("Fonte senza documenti archiviati.")
    if len(query) > 500:
        raise ValueError("Ricerca troppo lunga.")
    rows = owner.cerca_sentenze(q=query,fonte_codice=source,limit=min(50,max(1,int(limit))),semantica=False)
    ids = [int(row["id"]) for row in rows]
    available = {}
    if ids:
        with owner._connect() as connection:
            sql="SELECT id,length(trim(coalesce(testo_integrale,''))) FROM sentenze WHERE id IN ("+",".join("?" for _ in ids)+")"
            available = {int(row[0]): bool(row[1]) for row in connection.execute(sql,ids)}
    pdfs = {}
    languages = {}
    if ids:
        with owner._connect() as connection:
            sql="SELECT sentenza_id,id,path_locale,sha256,lingua FROM documenti_sentenza WHERE valido=1 AND sentenza_id IN ("+",".join("?" for _ in ids)+") ORDER BY id"
            for document in connection.execute(sql,ids):
                language = str(document["lingua"] or "").strip().lower()
                if language:
                    languages.setdefault(int(document["sentenza_id"]), set()).add(language)
                digest=str(document["sha256"] or "")
                if re.fullmatch(r"[0-9a-f]{64}",digest) and str(document["path_locale"])=="fonti_ufficiali/"+digest+".pdf":
                    pdfs.setdefault(int(document["sentenza_id"]),f"/giurisprudenza/corpus/{int(document['sentenza_id'])}/documenti/{int(document['id'])}/pdf")
    return {"ok":True,"source":source,"records":[{"id":int(row["id"]),"title":row.get("titolo") or "Provvedimento archiviato","authority":row.get("organo_giudicante") or "","date":row.get("data_deposito") or "","decisionDate":row.get("data_sentenza") or "","languages":sorted(languages.get(int(row["id"]),set())),"textAvailable":available.get(int(row["id"]),False),"pdfHref":pdfs.get(int(row["id"]),""),"textHref":f"/giurisprudenza/corpus/{int(row['id'])}/testo"} for row in rows]}


def reader_document(owner, record_id):
    record=owner.get_sentenza(int(record_id))
    if not record:
        return None
    text=str(record.get("testo_integrale") or "")
    if not text.strip():
        return None
    documents=[]
    for document in record.get("documenti",[]):
        if document.get("valido") is False or document.get("valido")==0:
            continue
        documents.append({"id":int(document["id"]),"language":str(document.get("lingua") or ""),"sha256":str(document.get("sha256") or ""),"official":bool(document.get("ufficiale")),"pdfHref":f"/giurisprudenza/corpus/{int(record_id)}/documenti/{int(document['id'])}/pdf" if str(document.get("path_locale") or "").endswith(".pdf") else ""})
    return {"title":record.get("titolo") or "Provvedimento archiviato","display_title":record.get("titolo") or "Provvedimento archiviato","authority":record.get("organo_giudicante") or "","section":record.get("sezione") or "","number":record.get("numero_sentenza") or "","year":record.get("anno_sentenza"),"date":record.get("data_deposito") or "","text":text,"blocks":text_blocks(text),"sha256":hashlib.sha256(text.encode()).hexdigest(),"original_sha256":"","status":"content_unreviewed","text_source_url":_source_url(record.get("url_pagina_ufficiale")),"text_source_official":bool(record.get("fonte_ufficiale_confermata")),"source_notice":str(record.get("note_redazionali") or ""),"documents":documents,"legal_approval_claimed":False}


def open_pdf(owner, record_id, document_id):
    record=owner.get_sentenza(int(record_id))
    if not record:
        return None
    document=next((x for x in record.get("documenti",[]) if int(x["id"])==int(document_id)),None)
    if not document or not document.get("valido",True):
        return None
    relative=Path(str(document.get("path_locale") or ""))
    expected=str(document.get("sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}",expected) or relative.parts!=("fonti_ufficiali",expected+".pdf"):
        raise ValueError("Documento fuori dall'archivio delle fonti.")
    root=Path(owner.db_path).resolve(strict=True).parent
    directory=os.open(root/"fonti_ufficiali",os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        descriptor=os.open(expected+".pdf",os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
        stream=os.fdopen(descriptor,"rb")
    finally:
        os.close(directory)
    try:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or stream.read(5)!=b"%PDF-":
            raise ValueError("Documento conservato inatteso.")
        stream.seek(0)
        digest=hashlib.sha256()
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
        after=os.fstat(stream.fileno())
        if digest.hexdigest()!=expected or (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise ValueError("Integrità del documento non confermata.")
        stream.seek(0)
        return stream
    except BaseException:
        stream.close()
        raise
