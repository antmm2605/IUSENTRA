"""Consultazione dei testi integrali nel repository Normattiva condiviso.

Il pacchetto pubblico è un ingresso esplicito, mai un dataset di risposte AI.
L'importazione conserva versioni precedenti e usa l'importer/FTS già presenti.
"""
from __future__ import annotations

from contextlib import closing
from urllib.parse import urlsplit
from dataclasses import asdict
import argparse
import hashlib
import io
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from lex.normativa.normattiva_importer import (
    ArticleRecord, DocumentRecord, ensure_schema, insert_articles_and_chunks,
    insert_document, migra_schema,
)
from lex.ricerca_giuridica.indice_fts import sincronizza_fts
from lex.ricerca_giuridica.testo import testo_indice

COLLECTION = 'Lex fonti: '
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
    # Keep official titles intact in storage; use concise catalogue labels.
    label = re.split(r'\s+note:|\s+visualizza atto', title, maxsplit=1, flags=re.I)[0]
    label = re.sub(r'\s*\([0-9A-Z]{6,9}\)', '', label)
    parts = label.split(' — ')
    if len(parts) == 2 and parts[0] == parts[1]:
        label = parts[0]
    return label if len(label) <= 150 else label[:147].rstrip() + '…'

def _catalogue_row(row):
    item = dict(row)
    key = item.pop('collection')[len(COLLECTION):]
    item['key'] = key
    item['label'] = _label(key, item['title'])
    item['category'] = 'Regolamenti UE' if key.startswith('reg_ue_') else 'Deontologia' if key.startswith('codice_deontologico') else 'Codici' if (key.startswith('codice_') or (key in CODE_LABELS and item['label'].startswith('Codice ')) or key == '152/2006') else 'Regolamenti e attuazione' if item['label'].startswith('Regolamento ') else 'Costituzione e disposizioni' if key in ('costituzione', 'preleggi', '1368/1941', '318/1942', '271/1989', 'cpa_norme_attuazione', 'cpa_norme_transitorie', 'cpa_norme_coordinamento', 'militari_attuazione_1023_1941') else 'Leggi e testi unici'
    return item



def importa_fonti(directory: Path, db: Path, aggiornato_il: str) -> dict:
    date.fromisoformat(aggiornato_il)
    files = sorted(directory.glob('atti*/*.jsonl'))
    if not files:
        raise ValueError('Nessun file di articoli nel pacchetto')
    prepared = []
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
            source_url = row.get('url', '')
            if source_url:
                parsed = urlsplit(source_url)
                if parsed.scheme != 'https' or parsed.hostname not in (
                    'www.normattiva.it', 'eur-lex.europa.eu', 'publications.europa.eu',
                    'www.gazzettaufficiale.it', 'www.consigliodistrettuale.it',
                    'www.consiglionazionaleforense.it',
                ):
                    raise ValueError('Collegamento della fonte non ammesso')
            if row['urn'] != first['urn'] or row['chiave'] != first['chiave']:
                raise ValueError(f'Atti differenti in {file.name}')
            if not str(row['urn']).startswith(('urn:nir:', 'urn:cnf:')):
                raise ValueError(f'Fonte senza URN in {file.name}')
        if len({r['articolo'] for r in rows}) != len(rows):
            raise ValueError(f'Numero di articolo duplicato in {file.name}')
        prepared.append((file, raw, rows))
    db.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if db.exists():
        backup = db.with_name(db.name + '.' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.bak')
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
                digest = hashlib.sha256(aggiornato_il.encode() + first['chiave'].encode() + raw).hexdigest()
                urn = first['urn']
                doc = DocumentRecord(
                    collection_name=COLLECTION + first['chiave'], zip_path='',
                    xml_entry=str(file.relative_to(directory)), tipo_atto=urn.rsplit(':', 1)[0].rsplit(':', 1)[-1],
                    numero=urn.rsplit(';', 1)[-1] if ';' in urn else '',
                    data_atto=first.get('data_atto'), data_pubblicazione=None,
                    titolo=f"{first['atto']} — {first['titolo_atto']}", urn=urn,
                    redazione_id=aggiornato_il, vigenza=first.get('vigenza', 'EDIZIONE_ACQUISITA'), xml_sha256=digest,
                    text_content='\n\n'.join(r['testo'] for r in rows), topics=[],
                    relevance_score=1, is_relevant=True,
                    articles=[ArticleRecord(r['articolo'], r.get('rubrica') or '', r['testo'], [], 1) for r in rows],
                )
                doc_id = insert_document(conn, doc, store_full_text=True)
                articles, chunks = insert_articles_and_chunks(
                    conn, doc_id, doc, jsonl_file=io.StringIO(), max_chunk_chars=1800,
                    only_relevant_articles=False,
                )
                for source_row in rows:
                    source_url = source_row.get('url', '')
                    if source_url:
                        parsed = urlsplit(source_url)
                        if parsed.scheme != 'https' or parsed.hostname not in (
                            'www.normattiva.it', 'eur-lex.europa.eu', 'publications.europa.eu',
                            'www.gazzettaufficiale.it', 'www.consigliodistrettuale.it',
                            'www.consiglionazionaleforense.it',
                        ):
                            raise ValueError('Collegamento della fonte non ammesso')
                        metadata = {k: source_row[k] for k in ('url', 'fonte_testo', 'consolidato_al', 'raccolto_il', 'senza_testo') if source_row.get(k)}
                        conn.execute('UPDATE normative_chunks SET metadata_json=json_set(metadata_json, ?, ?) '
                                     'WHERE article_id IN (SELECT id FROM normative_articles WHERE document_id=? AND article_number=?)',
                                     ('$.consultazione_fonte', json.dumps(metadata, ensure_ascii=False), doc_id, source_row['articolo']))
                    if source_row.get('senza_testo'):
                        conn.execute('UPDATE normative_chunks SET metadata_json=json_set(metadata_json, ?, ?) '
                                     'WHERE article_id IN (SELECT id FROM normative_articles WHERE document_id=? AND article_number=?)',
                                     ('$.consultazione_senza_testo', 1, doc_id, source_row['articolo']))
                    provenance = source_row.get('provenienza_integrazione')
                    if provenance and provenance.get('vigenza_richiesta'):
                        date.fromisoformat(provenance['vigenza_richiesta'])
                        conn.execute('UPDATE normative_chunks SET metadata_json=json_set(metadata_json, ?, ?) '
                                     'WHERE article_id IN (SELECT id FROM normative_articles WHERE document_id=? AND article_number=?)',
                                     ('$.consultazione_provenienza', json.dumps(provenance, ensure_ascii=False), doc_id, source_row['articolo']))
                report['new_articles'] += articles
                report['new_chunks'] += chunks
            report['fts'] = asdict(sincronizza_fts(conn))
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
                   COUNT(a.id) AS articles
            FROM normative_documents d JOIN normative_articles a ON a.document_id=d.id
            WHERE d.collection_name LIKE ? AND d.id = (
                SELECT x.id FROM normative_documents x WHERE x.collection_name=d.collection_name
                ORDER BY x.redazione_id DESC, x.id DESC LIMIT 1
            ) GROUP BY d.id ORDER BY d.titolo COLLATE NOCASE
        """, (COLLECTION + '%',))]


def articoli(db: Path, *, act: int = 0, query: str = '', article: str = '', category: str = '', offset: int = 0, limit: int = 30) -> dict:
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
    if not ids:
        return {'items': [], 'total': 0}
    where = ['a.document_id IN (' + ','.join('?' for _ in ids) + ')']
    args = list(ids)
    if article.strip():
        value = re.sub(r'[^0-9a-z./]', '', re.sub(r'^art(?:icolo)?\.?\s*', '', article.strip().lower()))
        if not re.fullmatch(r'\d+(?:[a-z]+)?(?:[./]\d+)?', value):
            raise ValueError('Indica un numero di articolo, per esempio 2043 o 473-bis.12.')
        where.append("replace(replace(lower(a.article_number),'-',''),' ','') = ?")
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


def dettaglio(db: Path, article_id: int) -> dict | None:
    with closing(_connect(db)) as conn:
        row = conn.execute('SELECT a.id, a.article_number AS number, a.article_title AS title, '
                           'a.article_text AS text, d.titolo AS act_title, d.urn, d.redazione_id AS updated_at, d.collection_name AS collection '
                           'FROM normative_articles a JOIN normative_documents d ON d.id=a.document_id '
                           'WHERE a.id=? AND d.collection_name LIKE ?', (article_id, COLLECTION + '%')).fetchone()
    if row is None:
        return None
    item = dict(row)
    with closing(_connect(db)) as conn:
        metadata = conn.execute('SELECT metadata_json FROM normative_chunks WHERE article_id=? ORDER BY id LIMIT 1', (article_id,)).fetchone()
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
    # The act link remains reliable also for annexes with repeated article numbers.
    links_path = Path(__file__).with_name('consultazione_link_ufficiali.json')
    links = json.loads(links_path.read_text(encoding='utf-8')) if links_path.exists() else {}
    item['source_url'] = source.get('url') or links.get(item['urn'], 'https://www.normattiva.it/uri-res/N2Ls?' + item['urn'])
    item['updated_at'] = source.get('raccolto_il', item['updated_at']) if not provenance else item['updated_at']
    item['source_label'] = 'EUR-Lex' if 'europa.eu' in item['source_url'] else 'Gazzetta Ufficiale' if 'gazzettaufficiale.it' in item['source_url'] else 'CNF' if item['urn'].startswith('urn:cnf:') else 'Normattiva'
    item['consolidated_at'] = source.get('consolidato_al', '')
    item['act_label'] = _label(item.pop('collection')[len(COLLECTION):], item['act_title'])
    return item


def main():
    parser = argparse.ArgumentParser(description='Importa articoli Normattiva JSONL per consultazione e Lex')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--updated-at', required=True)
    args = parser.parse_args()
    print(json.dumps(importa_fonti(args.source, args.db, args.updated_at), ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
