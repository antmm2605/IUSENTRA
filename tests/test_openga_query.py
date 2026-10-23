import pytest
from pct.openga_query import varianti_query


@pytest.mark.parametrize(
    "word,number", [("ventuno", "21"), ("trentotto", "38"), ("settantanove", "79"), ("novantotto", "98")]
)
def test_numero_in_lettere_crea_solo_variante_additiva(word, number):
    query = f"gara per {word} posti"
    result = varianti_query(query, [])
    assert result == [{"query": f"gara per {number} posti", "motivi": ["numero_in_lettere"]}]
    assert word in query


def test_aggettivo_geografico_deriva_dalle_sedi_senza_filtro_obbligatorio():
    assert varianti_query("tribunale milanese", ["TAR LOMBARDIA - MILANO"])[0]["query"] == "tribunale milano"
    assert varianti_query("tribunale perugino", ["TAR UMBRIA - PERUGIA"])[0]["query"] == "tribunale perugia"
    assert varianti_query("romanzo italiano", ["TAR LAZIO - ROMA"]) == []


def test_nessuna_espansione_tematica_senza_dizionario_governato():
    assert varianti_query("bonus per formazione degli insegnanti", []) == []
    assert varianti_query("accesso a formazione docenti di sostegno", []) == []
    assert varianti_query("carta di credito per aggiornamento software", []) == []
    assert varianti_query("", []) == []


def test_ambiti_suggeriti_non_sono_una_decisione_sulla_competenza():
    from pct.openga_query import sedi_menzionate

    sedi = ["TAR LOMBARDIA - MILANO", "TAR PIEMONTE - TORINO", "TAR UMBRIA - PERUGIA"]
    assert sedi_menzionate("tribunale del lavoro milanese", sedi) == ["TAR LOMBARDIA - MILANO"]
    assert sedi_menzionate("confronto Milano e Torino", sedi) == sedi[:2]
    assert sedi_menzionate("luogo non specificato", sedi) == []
