import json
import sqlite3
from pathlib import Path

import pytest

from lex.normativa.consultazione import articoli, catalogo, dettaglio, importa_fonti


def source(tmp_path: Path, text: str = 'La responsabilità riguarda l’avvocato. ' * 100):
    folder = tmp_path / 'pacchetto' / 'atti_codici'
    folder.mkdir(parents=True, exist_ok=True)
    rows = [dict(atto='c.c.', chiave='codice_civile', articolo='2545 quindecies',
                 rubrica='Controllo giudiziario', testo=text,
                 titolo_atto='Codice civile', data_atto='1942-03-16',
                 urn='urn:nir:stato:regio.decreto:1942-03-16;262',
                 provenienza_integrazione={'id_fonte': 'fonte-ufficiale', 'vigenza_richiesta': '2026-10-07'})]
    (folder / 'civile.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    return folder.parent, rows


def test_full_text_suffix_accents_and_provenance(tmp_path):
    package, rows = source(tmp_path)
    db = tmp_path / 'normattiva.sqlite'
    importa_fonti(package, db, '2026-10-09')
    code = catalogo(db)[0]
    assert code['label'] == 'Codice civile'
    result = articoli(db, act=code['id'], article='2545-quindecies', query='responsabilita')
    assert result['total'] == 1
    article = dettaglio(db, result['items'][0]['id'])
    assert article['text'] == rows[0]['testo']
    assert len(article['text']) > 1800
    assert article['updated_at'] == '2026-10-07'
    assert 'atto.codiceRedazionale=042U0262' in article['source_url']


def test_idempotency_and_saved_link_after_new_edition(tmp_path):
    package, _ = source(tmp_path)
    db = tmp_path / 'normattiva.sqlite'
    importa_fonti(package, db, '2026-10-09')
    previous = catalogo(db)[0]['id']
    second = importa_fonti(package, db, '2026-10-09')
    assert second['new_articles'] == 0
    source(tmp_path, 'Testo aggiornato senza perdita della versione precedente.')
    importa_fonti(package, db, '2026-10-10')
    assert len(catalogo(db)) == 1
    result = articoli(db, act=previous, article='2545 quindecies')
    assert result['total'] == 1
    assert dettaglio(db, result['items'][0]['id'])['text'].startswith('Testo aggiornato')


def test_invalid_package_does_not_modify_archive(tmp_path):
    package, rows = source(tmp_path)
    db = tmp_path / 'normattiva.sqlite'
    importa_fonti(package, db, '2026-10-09')
    (package / 'atti_codici' / 'errato.jsonl').write_text(json.dumps(dict(rows[0], testo='')))
    with pytest.raises(ValueError):
        importa_fonti(package, db, '2026-10-10')
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM normative_documents').fetchone()[0] == 1


def test_untrusted_source_url_rejected_before_write(tmp_path):
    package, rows = source(tmp_path)
    row = dict(rows[0], url='https://example.org/not-official')
    (package / 'atti_codici' / 'civile.jsonl').write_text(json.dumps(row))
    db = tmp_path / 'normattiva.sqlite'
    with pytest.raises(ValueError, match='Collegamento'):
        importa_fonti(package, db, '2026-10-09')
    assert not db.exists()


def test_european_source_and_missing_body_marker(tmp_path):
    package, rows = source(tmp_path)
    row = dict(rows[0], chiave='reg_ue_2014_910',
               urn='urn:nir:unione.europea:regolamento:2014-07-23;910',
               url='https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:02014R0910-20241018',
               senza_testo=True)
    (package / 'atti_codici' / 'civile.jsonl').write_text(json.dumps(row))
    db = tmp_path / 'normattiva.sqlite'
    importa_fonti(package, db, '2026-10-09')
    assert catalogo(db)[0]['category'] == 'Regolamenti UE'
    item = dettaglio(db, articoli(db)['items'][0]['id'])
    assert item['source_label'] == 'EUR-Lex'
    assert item['source_url'] == row['url']
    assert item['only_heading'] is True


def test_civil_code_cannot_return_newer_preleggi(tmp_path):
    from lex.testi_ufficiali import riconosci_articolo, testo_articolo
    package, rows = source(tmp_path, 'Art. 1. La capacità giuridica si acquista dalla nascita.')
    row = dict(rows[0], articolo='1')
    (package / 'atti_codici' / 'civile.jsonl').write_text(json.dumps(row))
    db = tmp_path / 'normattiva.sqlite'
    importa_fonti(package, db, '2026-10-09')
    row = dict(row, chiave='preleggi', testo='Art. 1. Sono fonti del diritto le leggi e i regolamenti.')
    (package / 'atti_codici' / 'civile.jsonl').write_text(json.dumps(row))
    importa_fonti(package, db, '2026-10-10')
    result = testo_articolo(db, riconosci_articolo('testo art. 1 c.c.'))
    assert 'capacità giuridica' in result['testo']
    assert 'fonti del diritto' not in result['testo']


def test_collection_filter_scopes_full_text_results(tmp_path):
    package, rows = source(tmp_path)
    european = dict(rows[0], chiave='reg_ue_2014_910', urn='urn:nir:unione.europea:regolamento:2014-07-23;910')
    (package / 'atti_codici' / 'eu.jsonl').write_text(json.dumps(european))
    db = tmp_path / 'normattiva.sqlite'
    importa_fonti(package, db, '2026-10-09')
    assert articoli(db, query='responsabilita')['total'] == 2
    assert articoli(db, query='responsabilita', category='Regolamenti UE')['total'] == 1
    assert articoli(db, category='Deontologia')['total'] == 0
