"""Indirizzamento puntuale delle letture precedenti a una rettifica tecnica.

Non riattiva le vecchie righe nell'indice e non le promuove a Fonti correnti.
Gli ID AUTOINCREMENT rimossi continuano a puntare al loro snapshot originale.
"""
from __future__ import annotations
import hashlib,json


def assicura_indice(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS normative_import_legacy_refs (
        tipo TEXT NOT NULL CHECK(tipo IN ('articolo','chunk')),
        legacy_id INTEGER NOT NULL, snapshot_sha256 TEXT NOT NULL,
        document_id INTEGER NOT NULL, sha256_testo TEXT NOT NULL,
        PRIMARY KEY(tipo,legacy_id,snapshot_sha256),
        FOREIGN KEY(snapshot_sha256) REFERENCES normative_import_history(snapshot_sha256))""")
    conn.execute('CREATE INDEX IF NOT EXISTS idx_normative_legacy_snapshot ON normative_import_legacy_refs(snapshot_sha256)')


def indicizza_snapshot(conn,payload,digest):
    doc=payload['documento'];rows=[]
    for key,kind,text_key in [('articoli','articolo','article_text'),('chunk','chunk','chunk_text')]:
        seen=set()
        for row in payload[key]:
            if not isinstance(row['id'],int) or row['id']<=0 or row['document_id']!=doc['id'] or row['id'] in seen:raise ValueError('Riferimento storico di altro documento o duplicato')
            seen.add(row['id']);text=row.get(text_key) or ''
            if not isinstance(text,str):raise ValueError('Testo storico non serializzato')
            rows.append((kind,row['id'],digest,doc['id'],hashlib.sha256(text.encode()).hexdigest()))
    assicura_indice(conn)
    conn.executemany('INSERT OR IGNORE INTO normative_import_legacy_refs VALUES(?,?,?,?,?)',rows)
    actual=[tuple(x) for x in conn.execute('SELECT tipo,legacy_id,snapshot_sha256,document_id,sha256_testo FROM normative_import_legacy_refs WHERE snapshot_sha256=?',(digest,))]
    if sorted(actual)!=sorted(rows):raise ValueError('Indice storico discordante dallo snapshot')
    return len(rows)


def indicizza_storico(conn,progresso=None):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='normative_import_history'").fetchone():return {'snapshot':0,'riferimenti':0}
    assicura_indice(conn);out={'snapshot':0,'riferimenti':0}
    cursor=conn.execute("""SELECT h.document_id,h.xml_sha256,h.snapshot_sha256,h.snapshot_json
        FROM normative_import_history h WHERE NOT EXISTS(
        SELECT 1 FROM normative_import_legacy_refs r WHERE r.snapshot_sha256=h.snapshot_sha256) ORDER BY h.id""")
    for docid,xmlsha,digest,raw in cursor:
        if hashlib.sha256(raw.encode()).hexdigest()!=digest:raise ValueError('Snapshot di importazione alterato')
        data=json.loads(raw)
        if data['documento']['id']!=docid or data['documento']['xml_sha256']!=xmlsha:raise ValueError('Identita dello snapshot discordante')
        out['riferimenti']+=indicizza_snapshot(conn,data,digest);out['snapshot']+=1
        if out['snapshot']%100==0 and progresso:progresso(dict(out))
    return out


def leggi_riferimenti_precedenti(conn,tipo,ident,sha=''):
    """Lookup indicizzato: mai scansione globale dello storico in una richiesta."""
    if tipo not in {'articolo','chunk'} or not isinstance(ident,int) or ident<=0:raise ValueError('Riferimento storico non valido')
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='normative_import_legacy_refs'").fetchone():return []
    sql="""SELECT r.document_id,r.sha256_testo,h.snapshot_sha256,h.snapshot_json
       FROM normative_import_legacy_refs r JOIN normative_import_history h
       ON h.snapshot_sha256=r.snapshot_sha256 WHERE r.tipo=? AND r.legacy_id=?"""
    args=[tipo,ident]
    if sha:sql+=' AND r.sha256_testo=?';args.append(sha)
    records=[]
    for docid,digest,snapshot,raw in conn.execute(sql,args):
        if hashlib.sha256(raw.encode()).hexdigest()!=snapshot:raise ValueError('Snapshot della lettura precedente alterato')
        payload=json.loads(raw);doc=payload['documento']
        if doc['id']!=docid:raise ValueError('Documento del riferimento storico discordante')
        key,text_key=('articoli','article_text') if tipo=='articolo' else ('chunk','chunk_text')
        found=[x for x in payload[key] if x['id']==ident and x['document_id']==docid]
        if len(found)!=1 or hashlib.sha256((found[0].get(text_key) or '').encode()).hexdigest()!=digest:raise ValueError('Riga storica diversa dal riferimento archiviato')
        records.append({'record':found[0],'snapshot':payload,'snapshot_sha256':snapshot,'sha256_testo':digest})
    return records
