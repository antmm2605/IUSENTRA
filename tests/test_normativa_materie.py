"""Materia e tipo degli atti della biblioteca «Codici e leggi»."""
import json
from pathlib import Path

from lex.normativa import materie as m


def test_ogni_atto_con_collegamento_ufficiale_ha_una_materia_censita():
    links = json.loads(Path('lex/normativa/consultazione_link_ufficiali.json').read_text(encoding='utf-8'))
    mancanti = [urn for urn in links if urn not in m.PER_URN]
    assert mancanti == []
    assert set(m.PER_URN.values()) <= set(m.MATERIE)
    assert set(m.PER_CHIAVE.values()) <= set(m.MATERIE)


def test_materie_dei_principali_atti():
    assert m.materia('1970/300', 'urn:nir:stato:legge:1970-05-20;300', 'Statuto dei lavoratori') == m.LAVORO
    assert m.materia('codice_civile', '', 'Codice civile') == m.CIVILE
    assert m.materia('reg_ue_2016_679', 'urn:nir:unione.europea', 'GDPR') == m.UE
    assert m.materia('codice_deontologico_forense_2026', 'urn:cnf:x', 'Codice deontologico') == m.FORENSE


def test_ripiego_per_parole_e_altre_norme():
    assert m.materia('x', 'urn:nir:stato:legge:2030-01-01;1', 'Disposizioni in materia di imposta di registro') == m.TRIBUTARIO
    assert m.materia('x', 'urn:nir:stato:legge:2030-01-01;2', 'Disposizioni varie') == m.ALTRO


def test_tipo_dell_atto():
    assert m.tipo('Codici', 'codice_civile', 'urn:nir:stato:regio.decreto:1942-03-16;262') == 'Codice'
    assert m.tipo('Leggi e testi unici', 'k', 'urn:nir:stato:decreto.legislativo:2001-06-08;231') == 'Decreto legislativo'
    assert m.tipo('Leggi e testi unici', 'k', 'urn:nir:stato:legge:1970-05-20;300') == 'Legge'
    assert m.tipo('Leggi e testi unici', 'k', 'urn:nir:stato:decreto.del.presidente.della.repubblica:2002-05-30;115') == 'D.P.R.'
    assert m.tipo('Leggi e testi unici', 'k', 'urn:nir:stato:decreto.legge:2014-09-12;132') == 'Decreto-legge'
    assert m.tipo('Regolamenti e attuazione', 'k', 'urn:nir:ministero.sviluppo.economico:decreto:2010-01-13;33') == 'Decreto ministeriale'
