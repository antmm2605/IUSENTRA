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
