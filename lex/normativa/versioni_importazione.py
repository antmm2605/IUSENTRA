"""Archivio append-only delle righe rettificate dal medesimo XML ufficiale.

Usato dall'importazione offline della copia candidata. Gli ID restano stabili,
mentre testi, chunk e impronte precedenti restano integralmente recuperabili.
L'indice FTS e quello vettoriale vanno riallineati prima di rendere il DB attivo.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone


def conserva_versione(conn: sqlite3.Connection, *, document_id: int,
                      revisione_parser: str, xml_sha256: str) -> str:
    def rows(query, args):
        cursor=conn.execute(query,args)
        names=[item[0] for item in cursor.description]
        return [dict(zip(names,row)) for row in cursor.fetchall()]
    documents=rows("SELECT * FROM normative_documents WHERE id=?",(document_id,))
    if len(documents)!=1 or documents[0]["xml_sha256"]!=xml_sha256:
        raise ValueError("Identità XML del documento da conservare discordante")
    payload={"documento":documents[0],
             "articoli":rows("SELECT * FROM normative_articles WHERE document_id=? ORDER BY id",(document_id,)),
             "chunk":rows("SELECT * FROM normative_chunks WHERE document_id=? ORDER BY id",(document_id,)),
             "componenti":rows("SELECT * FROM normative_components WHERE document_id=? ORDER BY id",(document_id,))}
    text=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    digest=hashlib.sha256(text.encode()).hexdigest()
    conn.execute("""CREATE TABLE IF NOT EXISTS normative_import_history (
        id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL, xml_sha256 TEXT NOT NULL,
        revisione_parser TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL UNIQUE,
        snapshot_json TEXT NOT NULL, acquisita_il TEXT NOT NULL)""")
    conn.execute("""INSERT OR IGNORE INTO normative_import_history
        (document_id,xml_sha256,revisione_parser,snapshot_sha256,snapshot_json,acquisita_il)
        VALUES (?,?,?,?,?,?)""",(document_id,xml_sha256,revisione_parser,digest,text,
                               datetime.now(timezone.utc).isoformat()))
    from .riferimenti_importazione import indicizza_snapshot
    indicizza_snapshot(conn,payload,digest)
    return digest


def rettifica_da_xml(conn: sqlite3.Connection, *, document_id: int, documento,
                     jsonl_file, revisione_parser: str) -> dict:
    """Rettifica riproducibile nella sola copia candidata già isolata.

    Deve essere racchiusa nella transazione del chiamante. Non modifica archivi
    sorgente, approvazioni o vettori: segnala la necessità di ricostruire l'indice.
    """
    from lex.normativa.normattiva_importer import insert_articles_and_chunks

    existing=conn.execute(
        "SELECT article_key,article_number,article_text FROM normative_articles WHERE document_id=?",
        (document_id,)).fetchall()
    expected={f"normattiva:{documento.xml_sha256}:art{index}":
              (article.article_number,article.article_text)
              for index,article in enumerate(documento.articles,1)}
    changed=any(key not in expected or expected[key]!=(number,text)
                for key,number,text in existing)
    old_components=conn.execute("SELECT localizzatore_xml,testo,sha256_testo FROM normative_components WHERE document_id=?",(document_id,)).fetchall()
    expected_components={item["localizzatore_xml"]:(item["testo"],item["sha256_testo"]) for item in documento.componenti}
    changed = changed or any(expected_components.get(locator)!=(text,digest) for locator,text,digest in old_components)
    current=conn.execute("SELECT text_content FROM normative_documents WHERE id=?",(document_id,)).fetchone()
    archive=None
    if changed or (current and current[0] and current[0]!=documento.text_content):
        archive=conserva_versione(conn,document_id=document_id,
                                 revisione_parser=revisione_parser,xml_sha256=documento.xml_sha256)
    if changed:
        # FTS5 contentless non supporta DELETE SQL. L'indice della copia
        # candidata resta fuori servizio fino alla ricostruzione nativa finale.
        # Non si manipola il formato interno dell'indice né quello attivo.
        conn.execute("DELETE FROM normative_fts_info WHERE document_id=?",(document_id,))
        conn.execute("DELETE FROM normative_chunks WHERE document_id=?",(document_id,))
        conn.execute("DELETE FROM normative_components WHERE document_id=?",(document_id,))
        for key,number,text in existing:
            if key not in expected:
                conn.execute("DELETE FROM normative_articles WHERE document_id=? AND article_key=?",(document_id,key))
    count,chunks=insert_articles_and_chunks(conn,document_id,documento,
            jsonl_file=jsonl_file,max_chunk_chars=1800,only_relevant_articles=False,
            preserva_esistenti=not changed)
    # Il testo integrale dell'atto comprende anche allegati non articolati:
    # conservarlo non li trasforma in articoli del corpo principale.
    if current and current[0]!=documento.text_content:
        conn.execute("UPDATE normative_documents SET text_content=? WHERE id=?",(documento.text_content,document_id))
    return {"rettificato":changed,"snapshot_precedente_sha256":archive,
            "articoli_aggiunti":count,"chunk_aggiunti":chunks,
            "vettori_da_riallineare":changed or chunks>0}
