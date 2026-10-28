"""Consultazione dei testi integrali nel repository Normattiva condiviso.

Il pacchetto pubblico è un ingresso esplicito, mai un dataset di risposte AI.
L'importazione conserva versioni precedenti e usa l'importer/FTS già presenti.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from lex.normativa.etichette_atti import ETICHETTE
from lex.normativa.materie import materia, tipo
from lex.normativa.normattiva_importer import (
    ArticleRecord,
    DocumentRecord,
    ensure_schema,
    insert_articles_and_chunks,
    insert_document,
    migra_schema,
)
from lex.ricerca_giuridica.indice_fts import sincronizza_fts
from lex.ricerca_giuridica.testo import testo_indice

COLLECTION = 'Lex fonti: '
HOST_FONTI_UFFICIALI = frozenset({
    'www.normattiva.it', 'eur-lex.europa.eu', 'publications.europa.eu',
    'www.gazzettaufficiale.it', 'www.consigliodistrettuale.it',
    'www.consiglionazionaleforense.it',
})


def url_ufficiale_valido(value: str) -> bool:
    if not isinstance(value,str):
        return False
    try:
        parsed=urlsplit(value)
        return (parsed.scheme=='https' and parsed.hostname in HOST_FONTI_UFFICIALI
                and parsed.username is None and parsed.password is None)
    except (TypeError,ValueError):
        return False


def url_fonte_da_metadata(metadata: dict) -> str:
    """URL acquisito dalla fonte, non ricostruito da identificatori interni."""
    source=metadata.get('consultazione_fonte') or {}
    if isinstance(source,str):
        try:source=json.loads(source)
        except (TypeError,ValueError):return ''
    if not isinstance(source,dict):return ''
    url=source.get('url')
    return url if isinstance(url,str) and url_ufficiale_valido(url) else ''


# Questi atti della nuova integrazione sono verificati come corpo principale,
# senza numerazioni omonime di allegati. Le altre raccolte conservano il link
# governato dell'atto: il numero da solo non identifica un articolo di allegato.
_CORPI_PRINCIPALI_20261020 = frozenset({
    'dpr_396_2000', 'legge_1185_1967', 'dpr_639_1970', 'dl_269_2003',
    'dlgs_168_2003', 'legge_249_1997', 'legge_481_1995',
})


def _collegamento_articolo(url: str, chiave: str, numero: str) -> str:
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if (chiave not in _CORPI_PRINCIPALI_20261020
            or not re.fullmatch(r'[1-9][0-9]*', numero)
            or parsed.hostname != 'www.normattiva.it'
            or parsed.path != '/atto/caricaDettaglioAtto'
            or {key for key, _ in query} != {'atto.dataPubblicazioneGazzetta', 'atto.codiceRedazionale'}):
        return url
    query.extend([('atto.articolo.numero', numero), ('atto.articolo.sottoArticolo', '1'),
                  ('atto.articolo.tipoArticolo', '0')])
    return urlunsplit(parsed._replace(query=urlencode(query)))


CODE_LABELS = {
    'codice_penale_militare_pace': 'Codice penale militare di pace',
    'codice_penale_militare_guerra': 'Codice penale militare di guerra',
    'ordinamento_militare_66_2010': 'Codice dell’ordinamento militare',
    'postale_156_1973': 'Codice postale e delle telecomunicazioni',
    'incentivi_184_2025': 'Codice degli incentivi',
    'turismo_79_2011': 'Codice del turismo',
    'giustizia_contabile_174_2016': 'Codice della giustizia contabile',
    'protezione_civile_1_2018': 'Codice della protezione civile',
    'contratti_163_2006': 'Codice dei contratti pubblici — 2006 (storico)',
    'militari_attuazione_1023_1941': 'Disposizioni di attuazione dei codici penali militari',
    'navigazione_regolamento_328_1952': 'Regolamento di esecuzione del codice della navigazione',
    'cpp_regolamento_334_1989': 'Regolamento di esecuzione della procedura penale',
    'proprieta_regolamento_33_2010': 'Regolamento di attuazione della proprietà industriale',
    'contratti_regolamento_207_2010': 'Regolamento di esecuzione dei contratti pubblici — 2010',
    'codice_deontologico_forense_2026': 'Codice deontologico forense',
    'codice_civile': 'Codice civile',
    'codice_procedura_civile': 'Codice di procedura civile',
    'codice_penale': 'Codice penale',
    'codice_procedura_penale': 'Codice di procedura penale',
    'codice_processo_amministrativo': 'Codice del processo amministrativo',
    'codice_strada': 'Codice della strada',
    'codice_consumo': 'Codice del consumo',
    'codice_crisi': 'Codice della crisi d’impresa e dell’insolvenza',
    'codice_privacy': 'Codice in materia di protezione dei dati personali',
    '327/1942': 'Codice della navigazione',
    '117/2017': 'Codice del Terzo settore',
    '159/2011': 'Codice antimafia',
    '171/2005': 'Codice della nautica da diporto',
    '198/2006': 'Codice delle pari opportunità',
    '259/2003': 'Codice delle comunicazioni elettroniche',
    '30/2005': 'Codice della proprietà industriale',
    '42/2004': 'Codice dei beni culturali e del paesaggio',
    '209/2005': 'Codice delle assicurazioni private',
    '36/2023': 'Codice dei contratti pubblici — 2023',
    '50/2016': 'Codice dei contratti pubblici — 2016',
    '82/2005': 'Codice dell’amministrazione digitale',
    '152/2006': 'Norme in materia ambientale',
    '175/2024': 'Testo unico della giustizia tributaria',
    '1368/1941': 'Disposizioni di attuazione della procedura civile',
    '318/1942': 'Disposizioni di attuazione del codice civile',
    '271/1989': 'Disposizioni di attuazione della procedura penale',
    'costituzione': 'Costituzione', 'preleggi': 'Preleggi',
    'cpa_norme_attuazione': 'Processo amministrativo — norme di attuazione',
    'cpa_norme_transitorie': 'Processo amministrativo — norme transitorie',
    'cpa_norme_coordinamento': 'Processo amministrativo — norme di coordinamento',
}

def _label(key: str, title: str) -> str:
    if key in CODE_LABELS:
        return CODE_LABELS[key]
    if key in ETICHETTE:
        return ETICHETTE[key]
    # Keep official titles intact in storage; use concise catalogue labels.
    label = re.split(r'\s+note:|\s+visualizza atto', title, maxsplit=1, flags=re.I)[0]
    label = re.sub(r'\s*\([0-9A-Z]{6,9}\)', '', label)
    parts = label.split(' — ')
    if len(parts) == 2 and parts[0] == parts[1]:
        label = parts[0]
    return label if len(label) <= 150 else label[:147].rstrip() + '…'

def _catalogue_row(row):
    item = dict(row)
    from lex.normativa.identita_documento import urn_documento, url_documento
    identity = urn_documento(item['urn'], item['xml_entry'], item['numero'], item['data_atto'])
    publication_url = url_documento(item['urn'], item['xml_entry'], item['data_pubblicazione'])
    item['urn'] = identity or item['urn']
    key = item.pop('collection')[len(COLLECTION):]
    item['key'] = key
    item['label'] = _label(key, item['title'])
    item['category'] = 'Regolamenti UE' if key.startswith('reg_ue_') else 'Deontologia' if key.startswith('codice_deontologico') else 'Codici' if (key.startswith('codice_') or (key in CODE_LABELS and item['label'].startswith('Codice ')) or key == '152/2006') else 'Regolamenti e attuazione' if item['label'].startswith('Regolamento ') else 'Costituzione e disposizioni' if key in ('costituzione', 'preleggi', '1368/1941', '318/1942', '271/1989', 'cpa_norme_attuazione', 'cpa_norme_transitorie', 'cpa_norme_coordinamento', 'militari_attuazione_1023_1941') else 'Leggi e testi unici'
    item['materia'] = materia(key, item.get('urn') or '', item['title'])
    item['tipo'] = tipo(item['category'], key, item.get('urn') or '')
    return item



def _stessa_fonte_archiviata(conn, doc, rows, raw):
    """Riusa anche l'impronta tecnica precedente solo se la Fonte e identica.

    Il cambio di algoritmo o del giorno del comando non duplica i testi. URL,
    acquisizione, versione, corpo o provenienza diversi non passano questo ramo.
    """
    from lex.normativa.provenienza_edizione import _oggetto
    expected={r['articolo']:r for r in rows}
    # Anche l'intero pacchetto (rubriche e struttura comprese) deve coincidere
    # con una firma precedente; non basta la sola uguaglianza del testo.
    first=rows[0];prov=first.get('provenienza_integrazione') or {}
    salts={doc.redazione_id,str(first.get('raccolto_il') or '')[:10],str(prov.get('vigenza_richiesta') or '')[:10]}
    signatures=set()
    for salt in salts:
        try:
            if date.fromisoformat(salt).isoformat()==salt:
                signatures.add(hashlib.sha256(salt.encode()+first['chiave'].encode()+raw).hexdigest())
        except (ValueError,TypeError):pass
    candidates=conn.execute('SELECT id,xml_sha256,text_content,xml_entry FROM normative_documents WHERE collection_name=? AND urn=? AND redazione_id=? AND titolo=? AND tipo_atto=? AND numero=? ORDER BY id',
        (doc.collection_name,doc.urn,doc.redazione_id,doc.titolo,doc.tipo_atto,doc.numero)).fetchall()
    for doc_id,digest,text,entry in candidates:
        if digest not in signatures or text!=doc.text_content:continue
        actual=conn.execute('SELECT a.id,a.article_number,a.article_text,c.metadata_json FROM normative_articles a LEFT JOIN normative_chunks c ON c.article_id=a.id WHERE a.document_id=? ORDER BY a.id,c.id',(doc_id,)).fetchall()
        ids=set();valid=True
        for article_id,number,body,raw in actual:
            ids.add(article_id);row=expected.get(number)
            if row is None or body!=row['testo'] or not raw:valid=False;break
            md=json.loads(raw)
            source={k:row[k] for k in ('url','fonte_testo','consolidato_al','raccolto_il','senza_testo') if row.get(k)}
            prov=row.get('provenienza_integrazione') or {}
            if not prov.get('vigenza_richiesta'):prov={}
            if (_oggetto(md.get('consultazione_fonte'))!=source or _oggetto(md.get('consultazione_provenienza'))!=prov
                    or bool(md.get('consultazione_senza_testo'))!=bool(row.get('senza_testo'))):valid=False;break
        if valid and len(ids)==len(rows):return doc_id,digest,entry
    return None


def importa_fonti(directory: Path, db: Path, aggiornato_il: str) -> dict:
    date.fromisoformat(aggiornato_il)
    files = sorted(directory.glob('atti*/*.jsonl'))
    if not files:
        raise ValueError('Nessun file di articoli nel pacchetto')
    prepared = []
    publication_verified = {}
    puntuali_riscontrati = {}
    identita_riscontrate = {}
    for file in files:
        raw = file.read_bytes()
        rows = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
        if not rows:
            raise ValueError(f'File vuoto: {file.name}')
        first = rows[0]
        required = ('chiave', 'urn', 'titolo_atto', 'articolo', 'testo')
        for row in rows:
            if any(not str(row.get(key) or '').strip() for key in required):
                raise ValueError(f'Articolo incompleto in {file.name}')
            prov_puntuale=row.get('provenienza_integrazione') or {}
            if prov_puntuale.get('file_xml_originale') or prov_puntuale.get('metadati_tecnici_riscontrati'):
                from lex.normativa.metadati_akn_riscontrati import verifica_riga_puntuale
                verifica_riga_puntuale(directory,row,cache=puntuali_riscontrati)
            source_url = row.get('url', '')
            if source_url:
                if not url_ufficiale_valido(source_url):
                    raise ValueError('Collegamento della fonte non ammesso')
            if row['urn'] != first['urn'] or row['chiave'] != first['chiave']:
                raise ValueError(f'Atti differenti in {file.name}')
            if not str(row['urn']).startswith(('urn:nir:', 'urn:cnf:')):
                # Nessun URN fittizio per metadati storici inesatti. Il lettore
                # rilegge le due fonti primarie e confronta il corpo nel pacchetto.
                from lex.normativa.identita_akn_riscontrata import verifica_riga_pacchetto
                checked = verifica_riga_pacchetto(directory, row,cache=identita_riscontrate)
                publication_verified[file] = checked
            version = row.get('consolidato_al') or aggiornato_il
            if date.fromisoformat(version).isoformat() != version:
                raise ValueError(f'Data edizione non canonica in {file.name}')
            if version != (first.get('consolidato_al') or aggiornato_il):
                raise ValueError(f'Edizioni differenti in {file.name}')
            provenance = row.get('provenienza_integrazione') or {}
            if provenance.get('vigenza_richiesta'):
                requested = date.fromisoformat(provenance['vigenza_richiesta'])
                if requested.isoformat() != provenance['vigenza_richiesta'] or requested < date.fromisoformat(version):
                    raise ValueError(f'Data richiesta precedente alla versione o non canonica in {file.name}')
                # EUR-Lex puo restituire un consolidato precedente, con elenco
                # delle versioni verificato. Le due date restano distinte;
                # questo import non attribuisce da solo applicabilita al caso.
        if len({r['articolo'] for r in rows}) != len(rows):
            raise ValueError(f'Numero di articolo duplicato in {file.name}')
        prepared.append((file, raw, rows))
    from lex.normativa.metadati_akn_riscontrati import verifica_cache_puntuali
    verifica_cache_puntuali(puntuali_riscontrati)
    from lex.normativa.identita_akn_riscontrata import verifica_cache_riscontri_identita
    verifica_cache_riscontri_identita(identita_riscontrate)
    db.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if db.exists():
        backup = db.with_name(db.name + '.' + datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f') + '.bak')
        with sqlite3.connect(db) as source, sqlite3.connect(backup) as dest:
            source.backup(dest)
    report = {'files': len(prepared), 'articles': sum(len(r) for _, _, r in prepared),
              'new_articles': 0, 'new_chunks': 0, 'backup': str(backup or ''), 'updated_at': aggiornato_il}
    with sqlite3.connect(db) as conn:
        ensure_schema(conn)
        migra_schema(conn)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_consultazione_chunk_article ON normative_chunks(article_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_consultazione_doc_article ON normative_articles(document_id, article_number)')
        with conn:
            for file, raw, rows in prepared:
                first = rows[0]
                # Date and logical part enter the fingerprint: annexes/preleggi share an URN.
                digest = hashlib.sha256((first.get('consolidato_al') or aggiornato_il).encode() + first['chiave'].encode() + raw).hexdigest()
                urn = first['urn']
                verified_publication = publication_verified.get(file)
                version = first.get('consolidato_al') or aggiornato_il
                doc = DocumentRecord(
                    collection_name=COLLECTION + first['chiave'], zip_path='',
                    xml_entry=str(file.relative_to(directory)), tipo_atto=(verified_publication['tipo_atto'] if verified_publication else urn.rsplit(':', 1)[0].rsplit(':', 1)[-1]),
                    numero=(verified_publication['numero'] if verified_publication else urn.rsplit(';', 1)[-1] if ';' in urn else ''),
                    data_atto=first.get('data_atto'), data_pubblicazione=(verified_publication['data_pubblicazione'] if verified_publication else None),
                    titolo=f"{first['atto']} — {first['titolo_atto']}", urn=urn,
                    redazione_id=version, vigenza=first.get('vigenza', 'EDIZIONE_ACQUISITA'), xml_sha256=digest,
                    text_content='\n\n'.join(r['testo'] for r in rows), topics=[],
                    relevance_score=1, is_relevant=True,
                    articles=[ArticleRecord(r['articolo'], r.get('rubrica') or '', r['testo'], [], 1) for r in rows],
                )
                previous = _stessa_fonte_archiviata(conn, doc, rows, raw)
                if previous:
                    from dataclasses import replace
                    doc_id, old_digest, old_entry = previous
                    doc = replace(doc, xml_sha256=old_digest, xml_entry=old_entry)
                else:
                    doc_id = insert_document(conn, doc, store_full_text=True)
                articles, chunks = insert_articles_and_chunks(
                    conn, doc_id, doc, jsonl_file=io.StringIO(), max_chunk_chars=1800,
                    only_relevant_articles=False,
                )
                for source_row in rows:
                    source_url = source_row.get('url', '')
                    if source_url:
                        if not url_ufficiale_valido(source_url):
                            raise ValueError('Collegamento della fonte non ammesso')
                        metadata = {k: source_row[k] for k in ('url', 'fonte_testo', 'consolidato_al', 'raccolto_il', 'senza_testo') if source_row.get(k)}
                        conn.execute('UPDATE normative_chunks SET metadata_json=json_set(metadata_json, ?, json(?)) '
                                     'WHERE article_id IN (SELECT id FROM normative_articles WHERE document_id=? AND article_number=?)',
                                     ('$.consultazione_fonte', json.dumps(metadata, ensure_ascii=False), doc_id, source_row['articolo']))
                    if source_row.get('senza_testo'):
                        conn.execute('UPDATE normative_chunks SET metadata_json=json_set(metadata_json, ?, ?) '
                                     'WHERE article_id IN (SELECT id FROM normative_articles WHERE document_id=? AND article_number=?)',
                                     ('$.consultazione_senza_testo', 1, doc_id, source_row['articolo']))
                    provenance = source_row.get('provenienza_integrazione')
                    if provenance and provenance.get('vigenza_richiesta'):
                        date.fromisoformat(provenance['vigenza_richiesta'])
                        conn.execute('UPDATE normative_chunks SET metadata_json=json_set(metadata_json, ?, json(?)) '
                                     'WHERE article_id IN (SELECT id FROM normative_articles WHERE document_id=? AND article_number=?)',
                                     ('$.consultazione_provenienza', json.dumps(provenance, ensure_ascii=False), doc_id, source_row['articolo']))
                if any(r.get('struttura_normativa') for r in rows):
                    from lex.normativa.struttura import salva_proiezione
                    salva_proiezione(conn, doc_id, rows)
                report['new_articles'] += articles
                report['new_chunks'] += chunks
            report['fts'] = asdict(sincronizza_fts(conn))
            verifica_cache_puntuali(puntuali_riscontrati)
            verifica_cache_riscontri_identita(identita_riscontrate)
    return report


def _connect(db: Path):
    if not db.is_file():
        raise FileNotFoundError('Archivio normativo non disponibile')
    conn = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def catalogo(db: Path) -> list[dict]:
    with closing(_connect(db)) as conn:
        return [_catalogue_row(r) for r in conn.execute("""
            SELECT d.id, d.titolo AS title, d.collection_name AS collection, d.urn, d.redazione_id AS updated_at,
                   d.xml_entry, d.numero, d.data_atto, d.data_pubblicazione, COUNT(a.id) AS articles
            FROM normative_documents d JOIN normative_articles a ON a.document_id=d.id
            WHERE d.collection_name LIKE ? AND d.id = (
                SELECT x.id FROM normative_documents x WHERE x.collection_name=d.collection_name
                ORDER BY x.redazione_id DESC, x.id DESC LIMIT 1
            ) GROUP BY d.id ORDER BY d.titolo COLLATE NOCASE
        """, (COLLECTION + '%',))]


def articoli(db: Path, *, act: int = 0, query: str = '', article: str = '', category: str = '', offset: int = 0, limit: int = 30, includi_archivio_generale: bool = False) -> dict:
    offset = max(0, offset)
    limit = min(100, max(1, limit))
    acts = catalogo(db)
    # Saved links to an older imported edition still resolve to the same collection.
    if act and not any(r['id'] == act for r in acts):
        with closing(_connect(db)) as conn:
            previous = conn.execute('SELECT collection_name FROM normative_documents WHERE id=?', (act,)).fetchone()
        if previous and previous[0].startswith(COLLECTION):
            key = previous[0][len(COLLECTION):]
            act = next((r['id'] for r in acts if r['key'] == key), act)
    ids = [r['id'] for r in acts if (not act or r['id'] == act) and (not category or r['category'] == category)]
    generale = includi_archivio_generale and not category and bool(query.strip() or article.strip() or act)
    if generale:
        # Ricerca pubblica paginata: nessuna lista di centinaia di migliaia di
        # documenti inviata al browser o enumerata nella richiesta.
        where = ['a.document_id = ?'] if act else ['1=1']
        args = [act] if act else []
    else:
        if not ids:
            return {'items': [], 'total': 0}
        where = ['a.document_id IN (' + ','.join('?' for _ in ids) + ')']
        args = list(ids)
    if article.strip():
        from .biblioteca.identita import numero_articolo, espressione_numero_articolo_sql
        value = numero_articolo(article)
        where.append(espressione_numero_articolo_sql('a.article_number')+' = ?')
        args.append(value)
    if query.strip():
        terms = testo_indice(query[:300]).split()[:12]
        if not terms:
            return {'items': [], 'total': 0}
        where.append('a.id IN (SELECT c.article_id FROM normative_fts f JOIN normative_chunks c ON c.id=f.rowid WHERE normative_fts MATCH ?)')
        args.append(' AND '.join('"' + t.replace('"', '""') + '"' for t in terms))
    clause = ' AND '.join(where)
    with closing(_connect(db)) as conn:
        total = conn.execute('SELECT COUNT(*) FROM normative_articles a WHERE ' + clause, args).fetchone()[0]
        rows = conn.execute('SELECT a.id, a.article_number AS number, a.article_title AS title, d.titolo AS act_title '
                            'FROM normative_articles a JOIN normative_documents d ON d.id=a.document_id WHERE ' + clause +
                            ' ORDER BY d.titolo, a.id LIMIT ? OFFSET ?', [*args, limit, offset]).fetchall()
    return {'items': [dict(r) for r in rows], 'total': total, 'act_id': act}


def dettaglio(db: Path, article_id: int, *, includi_archivio_generale: bool = False) -> dict | None:
    with closing(_connect(db)) as conn:
        row = conn.execute('SELECT a.id, a.article_number AS number, a.article_title AS title, '
                           'a.article_text AS text, a.document_id, d.xml_sha256 AS document_sha256, d.imported_at, d.titolo AS act_title, d.urn, d.redazione_id AS updated_at, d.collection_name AS collection, d.xml_entry, d.data_atto, d.data_pubblicazione, d.numero '
                           'FROM normative_articles a JOIN normative_documents d ON d.id=a.document_id '
                           'WHERE a.id=? AND (? OR d.collection_name LIKE ?)', (article_id, int(includi_archivio_generale), COLLECTION + '%')).fetchone()
    if row is None:
        return None
    item = dict(row)
    with closing(_connect(db)) as conn:
        metadata = conn.execute('SELECT metadata_json FROM normative_chunks WHERE article_id=? ORDER BY id LIMIT 1', (article_id,)).fetchone()
    return _completa_dettaglio(item,metadata)


def _completa_dettaglio(item: dict, metadata=None) -> dict:
    source = {}
    provenance = None
    item['only_heading'] = False
    if metadata:
        item['only_heading'] = bool(json.loads(metadata[0]).get('consultazione_senza_testo'))
        source = json.loads(metadata[0]).get('consultazione_fonte', {})
        source = json.loads(source) if isinstance(source, str) else source
        provenance = json.loads(metadata[0]).get('consultazione_provenienza')
        if provenance:
            provenance = json.loads(provenance) if isinstance(provenance, str) else provenance
            item['updated_at'] = provenance.get('vigenza_richiesta', item['updated_at'])
    # Preservare i collegamenti degli allegati con numerazioni ripetute.
    links_path = Path(__file__).with_name('consultazione_link_ufficiali.json')
    links = json.loads(links_path.read_text(encoding='utf-8')) if links_path.exists() else {}
    from .identita_documento import urn_documento,url_documento
    original_urn=item['urn']
    identity=urn_documento(original_urn,item.get('xml_entry',''),str(item.get('numero') or ''),str(item.get('data_atto') or ''))
    publication_url=url_documento('',item.get('xml_entry',''),str(item.get('data_pubblicazione') or '')) if not identity else ''
    if identity:item['urn']=identity
    national=identity.startswith('urn:nir:') and not identity.startswith('urn:nir:unione.europea:')
    fallback=('https://www.normattiva.it/uri-res/N2Ls?'+identity) if national else publication_url
    item['source_url'] = source.get('url') or links.get(item['urn']) or (fallback if fallback.startswith('https://') else '')
    from .provenienza_edizione import edizione_archiviata
    md=json.loads(metadata[0]) if metadata else {}
    item['source_provenance']={'urn_archiviato':original_urn,'documento_sha256':item.get('document_sha256'),
        'imported_at':item.get('imported_at'),'fonte':source,
        'edizione_archiviata':edizione_archiviata(md,{'urn':original_urn,'xml_sha256':item.get('document_sha256'),'redazione_id':item.get('updated_at')})}
    item['source_url'] = _collegamento_articolo(item['source_url'], item['collection'].removeprefix(COLLECTION), str(item['number']))
    item['updated_at'] = source.get('raccolto_il', item['updated_at']) if not provenance else item['updated_at']
    item['source_label'] = 'EUR-Lex' if 'europa.eu' in item['source_url'] else 'Gazzetta Ufficiale' if 'gazzettaufficiale.it' in item['source_url'] else 'CNF' if item['urn'].startswith('urn:cnf:') else 'Normattiva' if 'normattiva.it' in item['source_url'] else 'Archivio normativo'
    item['consolidated_at'] = source.get('consolidato_al', '')
    item['act_key'] = item['collection'].removeprefix(COLLECTION)
    item['act_label'] = _label(item.pop('collection').removeprefix(COLLECTION), item['act_title'])
    return item


def dettagli_precedenti(db:Path,article_id:int,*,sha:str='') -> list[dict]:
    """Solo consultazione archivistica; non usata dalla ricerca o da prepara()."""
    from .riferimenti_importazione import leggi_riferimenti_precedenti
    from .biblioteca.fabbisogno import norm_articolo
    with closing(_connect(db)) as conn:
        records=leggi_riferimenti_precedenti(conn,'articolo',article_id,sha)
        out=[]
        for record in records:
            article=record['record'];doc=record['snapshot']['documento']
            md=next((c.get('metadata_json') for c in record['snapshot']['chunk'] if c.get('article_id')==article_id),None)
            item={'id':article_id,'document_id':doc['id'],'number':article['article_number'],
                'title':article.get('article_title'),'text':article.get('article_text') or '',
                'act_title':doc.get('titolo'),'urn':doc.get('urn') or '',
                'updated_at':doc.get('redazione_id'),'collection':doc.get('collection_name') or '',
                'xml_entry':doc.get('xml_entry') or '','data_atto':doc.get('data_atto'),
                'data_pubblicazione':doc.get('data_pubblicazione'),'numero':doc.get('numero'),
                'document_sha256':doc.get('xml_sha256'),'imported_at':doc.get('imported_at')}
            item=_completa_dettaglio(item,(md,) if md else None)
            item.update(archived_import=True,snapshot_sha256=record['snapshot_sha256'],
                sha256=record['sha256_testo'],utilizzabile_come_fonte_corrente=False)
            # Il numero non basta a identificare un allegato. Mostrare la parte
            # rettificata solo se stesso XML e riscontro letterale univoco.
            current=conn.execute('SELECT xml_sha256 FROM normative_documents WHERE id=?',(doc['id'],)).fetchone()
            matches=[];old=item['text'].strip()
            if current and current[0]==doc['xml_sha256'] and old:
                row=conn.execute('SELECT article_number,article_text FROM normative_articles WHERE id=? AND document_id=?',(article_id,doc['id'])).fetchone()
                if row and norm_articolo(row[0])==norm_articolo(article['article_number']) and row[1] and (row[1].strip() in old or old in row[1].strip()):
                    matches.append({'tipo':'articolo_rettificato','text':row[1],'sha256':hashlib.sha256(row[1].encode()).hexdigest()})
                for row in conn.execute('SELECT localizzatore_xml,testo,sha256_testo FROM normative_components WHERE document_id=?',(doc['id'],)):
                    if old in row[1]:
                        if hashlib.sha256(row[1].encode()).hexdigest()!=row[2]:raise ValueError('Parte rettificata alterata')
                        matches.append({'tipo':'parte_del_documento_rettificata','localizzatore_xml':row[0],'text':row[1],'sha256':row[2]})
            if len(matches)==1:item['rettifica_corrente']=matches[0]
            out.append(item)
    return out


def main():
    parser = argparse.ArgumentParser(description='Importa articoli Normattiva JSONL per consultazione e Lex')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--updated-at', required=True)
    args = parser.parse_args()
    print(json.dumps(importa_fonti(args.source, args.db, args.updated_at), ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
