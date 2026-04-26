from pct.compensi_a_tempo import (
    COMPENSO_A_TEMPO_CODE,
    calcola_compenso_a_tempo_art22bis,
    is_compenso_a_tempo,
    normalizza_tipo_compenso,
)


def test_alias_compenso_a_tempo():
    assert is_compenso_a_tempo("Compenso orario")
    assert is_compenso_a_tempo("A ore")
    assert is_compenso_a_tempo("Compenso a tempo")
    assert is_compenso_a_tempo(COMPENSO_A_TEMPO_CODE)
    assert normalizza_tipo_compenso("Compenso orario") == COMPENSO_A_TEMPO_CODE


def test_ora_frazione_oltre_30_arrotonda_solo_se_superiore_a_30_minuti():
    assert calcola_compenso_a_tempo_art22bis(250, 5, 45)["ore_fatturabili"] == 6
    assert calcola_compenso_a_tempo_art22bis(250, 5, 30)["ore_fatturabili"] == 5
    assert calcola_compenso_a_tempo_art22bis(250, 5, 31)["ore_fatturabili"] == 6


def test_effettivo_minuti_e_compenso_base():
    result = calcola_compenso_a_tempo_art22bis(
        250,
        ore_stimate=5,
        minuti_stimati=45,
        criterio_arrotondamento="effettivo_minuti",
    )
    assert result["ore_fatturabili"] == 5.75
    assert result["compenso_base"] == 1437.5
    assert calcola_compenso_a_tempo_art22bis(250, 6)["compenso_base"] == 1500


def test_tariffa_fuori_range_genera_warning_non_errore():
    low = calcola_compenso_a_tempo_art22bis(199, 1)
    high = calcola_compenso_a_tempo_art22bis(501, 1)
    assert low["warnings"]
    assert not low["errors"]
    assert high["warnings"]
    assert not high["errors"]


def test_errori_bloccanti_per_tariffa_o_tempo_non_validi():
    assert calcola_compenso_a_tempo_art22bis(0, 1)["errors"]
    assert calcola_compenso_a_tempo_art22bis(250, 0, 0)["errors"]
