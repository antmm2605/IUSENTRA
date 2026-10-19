from datetime import date
from types import SimpleNamespace

import pytest

from pct.schede_compilazione import risolvi_scheda, scheda_per_template
from pct.schede_termini import calcola, data_base

TERMINE = dict(base='udienza', giorni=70, direzione='ritroso', feriale=True)


def fatto(valore, verifica='verificata', campo='udienza', categoria='data'):
    return SimpleNamespace(valore=valore, verifica=verifica, campo=campo, categoria=categoria)


@pytest.mark.parametrize('stato', ['respinta', 'respinto', 'ignorata'])
def test_date_scartate_non_alimentano_scadenze(stato):
    assert data_base(TERMINE, [fatto('2027-04-18', stato)]) is None


def test_date_diverse_non_vengono_scelte_in_ordine():
    fonti = [fatto('2027-04-18'), fatto('2027-05-18')]
    for ordine in (fonti, list(reversed(fonti))):
        with pytest.raises(ValueError, match='discordanti'):
            data_base(TERMINE, ordine)
        scheda = risolvi_scheda(scheda_per_template('CIV_ORD_009'), {}, fatti=ordine)
        voce = next(c for c in scheda['campi'] if c['campo'] == 'termine_costituzione')
        assert voce['stato'] == 'calcolo' and 'valore' not in voce
        assert voce['verifica_avvocato'] and 'discordanti' in voce['spiegazione']


def test_fonti_concordanti_e_qualita_della_data():
    for stato, atteso in [('plausibile', True), ('verificata', False), ('corretta', False)]:
        dati = risolvi_scheda(scheda_per_template('MON_011'), {},
                             fatti=[fatto('2026-07-20', stato, campo='notifica')], oggi=date(2026, 10, 19))
        voce = next(c for c in dati['campi'] if c['campo'] == 'scadenza_opposizione')
        assert voce['valore'] == '29/09/2026' and voce['verifica_avvocato'] is atteso
    assert data_base(TERMINE, [fatto('2027-04-18'), fatto('2027-04-18')]) == date(2027, 4, 18)


def test_notifica_non_prova_comunicazione():
    assert data_base({**TERMINE, 'base': 'comunicazione'},
                     [fatto('2027-04-18', categoria='prova_notifica')]) is None


@pytest.mark.parametrize('giorni', [True, -1, 0, 1.5, '40'])
def test_durate_non_valide_non_diventano_un_giorno(giorni):
    with pytest.raises(ValueError):
        calcola({**TERMINE, 'giorni': giorni}, date(2026, 10, 19))


def test_accoglimento_pieno_non_diventa_parziale():
    from scripts.precedenti.openga import categoria
    assert categoria('ACCOLTO') == 'accolto'
    assert categoria('ACCOGLIE') == 'accolto'
    assert categoria('ACCOLTO IN PARTE') == 'accolto in parte'
    assert categoria('RESPINGE') == 'respinto'


def test_spiegazione_termine_a_ritroso_coerente_con_la_data():
    risultato = calcola(TERMINE, date(2025, 12, 2))
    assert risultato['scadenza'] == '2025-09-23'
    assert 'a ritroso' in risultato['spiegazione']
    assert 'escludendo il giorno' in risultato['spiegazione']
    assert 'giorno successivo' not in risultato['spiegazione']


def test_dispositivo_costituzionale_conservato_integralmente(tmp_path):
    import json
    import sqlite3
    from scripts.precedenti.corte_costituzionale import main
    db = tmp_path / 'biblioteca.db'
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE normative_documents(collection_name TEXT, urn TEXT)')
    conn.commit()
    conn.close()
    testo = 'Dichiara non fondata la questione. ' * 160
    raw = tmp_path / 'Cc_Opendata_Pronunce_2026.json'
    raw.write_bytes(json.dumps([{'anno_pronuncia': 2026, 'numero_pronuncia': 1,
                                'dispositivo': testo, 'ecli': 'ECLI:IT:COST:2026:1',
                                'tipologia_pronuncia': 'S', 'data_deposito': '2026-01-10'}]).encode('cp1252'))
    out = tmp_path / 'pronunce.jsonl'
    assert main(['--raw', str(tmp_path), '--db', str(db), '--out', str(out)]) == 0
    voce = json.loads(out.read_text(encoding='utf-8'))
    assert voce['dispositivo'] == testo.strip() and len(voce['dispositivo']) > 3000
    assert voce['ecli'] == 'ECLI:IT:COST:2026:1'
