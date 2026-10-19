"""Pacchetto Normattiva del 19/10/2026 per la biblioteca «Codici e leggi»."""
import json
from pathlib import Path

from lex.normativa.etichette_atti import ETICHETTE
from lex.normativa.materie import MATERIE, PER_CHIAVE

PACCO = Path('lex/normativa/integrazioni/biblioteca_20261019/atti')


def test_ogni_atto_del_pacchetto_ha_etichetta_materia_e_fonte_ufficiale():
    files = sorted(PACCO.glob('*.jsonl'))
    assert len(files) == 84
    for f in files:
        rows = [json.loads(line) for line in f.read_text(encoding='utf-8').splitlines()]
        key = rows[0]['chiave']
        assert key in ETICHETTE and PER_CHIAVE[key] in MATERIE
        assert all(r['urn'].startswith('urn:nir:') and r['url'].startswith('https://www.normattiva.it/') for r in rows)
        assert all(r['testo'].strip() and r['consolidato_al'] == '2026-10-19' for r in rows)
        assert len({r['articolo'] for r in rows}) == len(rows)


def test_atti_essenziali_presenti():
    for key in ('dpr_917_1986', 'legge_69_2019', 'legge_6_2004', 'legge_220_2012', 'dlgs_101_2018', 'dl_179_2012', 'dm_150_2023'):
        assert (PACCO / f'{key}.jsonl').is_file()


def test_import_deploy_preserva_base_e_riesecuzione_senza_duplicati(tmp_path):
    import sqlite3
    from lex.normativa.consultazione import importa_fonti
    from deploy.hetzner.importa_biblioteca_2440 import importa_biblioteca
    seed = tmp_path / "seed" / "atti"
    seed.mkdir(parents=True)
    row = dict(chiave="codice_civile", urn="urn:nir:stato:regio.decreto:1942-03-16;262",
               titolo_atto="Codice civile", atto="c.c.", articolo="2043", testo="Testo di collaudo da preservare.")
    (seed / "seed.jsonl").write_text(json.dumps(row), encoding="utf-8")
    db = tmp_path / "codici_leggi.sqlite"
    importa_fonti(seed.parent, db, "2026-10-09")
    result = importa_biblioteca(PACCO.parent, db)
    assert result["atti_release_visibili"] == 84 and result["atti_catalogo"] == 85
    assert Path(result["backup"]).is_file()
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT article_text FROM normative_articles WHERE article_number='2043'").fetchone()[0] == row["testo"]
    again = importa_biblioteca(PACCO.parent, db)
    assert again["new_articles"] == 0 and again["new_chunks"] == 0


def test_import_deploy_rifiuta_base_assente_e_pacco_incompleto(tmp_path):
    import pytest
    from deploy.hetzner.importa_biblioteca_2440 import importa_biblioteca
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(RuntimeError, match="Archivio"):
        importa_biblioteca(PACCO.parent, missing)
    assert not missing.exists()
    existing = tmp_path / "existing.sqlite"
    existing.write_bytes(b"prova immutata")
    with pytest.raises(ValueError, match="incompleto"):
        importa_biblioteca(tmp_path, existing)
    assert existing.read_bytes() == b"prova immutata"
