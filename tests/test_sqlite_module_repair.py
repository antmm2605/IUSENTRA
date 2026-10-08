"""Il recupero SQL crea una copia verificabile e non modifica le fonti."""
import hashlib
import json
import sqlite3

import pytest

from tools.repair_sqlite_module_table import build_candidate


def sources(tmp_path):
    original, recovered = tmp_path / 'original.db', tmp_path / 'records.db'
    with sqlite3.connect(original) as connection:
        connection.executescript('''
            CREATE TABLE native(id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT);
            INSERT INTO native(id,label) VALUES (8,'Dato corrente');
            CREATE INDEX native_label ON native(label);
            CREATE VIEW visible AS SELECT * FROM native;
            CREATE TABLE moduli_dati(nome TEXT PRIMARY KEY,payload_json TEXT);
            CREATE TABLE moduli_json_records(modulo TEXT,record_key TEXT,payload_json TEXT);
            INSERT INTO moduli_dati VALUES ('storico','{"record_entries":3}');
            INSERT INTO moduli_json_records VALUES ('storico','vecchio','{"v":1}');
        ''')
        connection.execute('PRAGMA user_version=17')
        connection.execute('PRAGMA application_id=21')
    with sqlite3.connect(recovered) as connection:
        connection.executescript('CREATE TABLE moduli_json_records(modulo TEXT,record_key TEXT,payload_json TEXT);')
        connection.executemany('INSERT INTO moduli_json_records(rowid,modulo,record_key,payload_json) VALUES (?,?,?,?)',
                               [(12, 'storico', 'a', '{"v":2}'), (19, 'storico', 'b', '{corrotto')])
    return original, recovered


def test_candidate_preserves_native_sql_and_reports_unrecoverable_content(tmp_path):
    original, recovered = sources(tmp_path)
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (original, recovered)]
    target, report = tmp_path / 'candidate.db', tmp_path / 'report.json'
    result = build_candidate(original, recovered, target, report)
    assert result['source_of_truth'] == 'sqlite' and result['live_writes'] == 0
    assert result['invalid_json'] == [{'module': 'storico', 'key': 'b', 'preserved': True}]
    assert result['incomplete_modules']
    assert hashes == [hashlib.sha256(path.read_bytes()).hexdigest() for path in (original, recovered)]
    with sqlite3.connect(target) as connection:
        assert connection.execute('SELECT * FROM visible').fetchall() == [(8, 'Dato corrente')]
        assert connection.execute('SELECT rowid,record_key FROM moduli_json_records ORDER BY rowid').fetchall() == [(12, 'a'), (19, 'b')]
        assert connection.execute('SELECT seq FROM sqlite_sequence WHERE name="native"').fetchone() == (8,)
        assert connection.execute('PRAGMA user_version').fetchone() == (17,)
        assert connection.execute('PRAGMA application_id').fetchone() == (21,)
        assert connection.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    assert json.loads(report.read_text())['live_writes'] == 0


def test_candidate_cannot_overwrite_the_source_or_existing_files(tmp_path):
    original, recovered = sources(tmp_path)
    with pytest.raises(ValueError, match='new, distinct'):
        build_candidate(original, recovered, original, tmp_path / 'report.json')
    target = tmp_path / 'candidate.db'
    target.write_bytes(b'Existing evidence')
    with pytest.raises(ValueError, match='new, distinct'):
        build_candidate(original, recovered, target, tmp_path / 'report.json')
    assert target.read_bytes() == b'Existing evidence'
