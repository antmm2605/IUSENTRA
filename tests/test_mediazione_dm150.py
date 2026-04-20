from pct.mediazione_dm150 import (
    ESITO_PRIMO_INCONTRO_CON_ACCORDO,
    ESITO_PRIMO_INCONTRO_SENZA_ACCORDO,
    ESITO_SUCCESSIVI_CON_ACCORDO,
    ESITO_SUCCESSIVI_SENZA_ACCORDO,
    REGIME_OBBLIGATORIA,
    REGIME_VOLONTARIA,
    calcola_costi_mediazione_dm150,
    descrizione_operativa_mediazione_dm150,
)


def test_mediazione_dm150_primo_incontro_senza_accordo_volontaria():
    result = calcola_costi_mediazione_dm150(
        1000,
        regime=REGIME_VOLONTARIA,
        esito=ESITO_PRIMO_INCONTRO_SENZA_ACCORDO,
    )

    assert result.spese_avvio == 40.0
    assert result.spese_mediazione_primo_incontro == 60.0
    assert result.ulteriori_spese_mediazione == 0.0
    assert result.totale_organismo == 100.0


def test_mediazione_dm150_primo_incontro_senza_accordo_obbligatoria_ridotta():
    result = calcola_costi_mediazione_dm150(
        1000,
        regime=REGIME_OBBLIGATORIA,
        esito=ESITO_PRIMO_INCONTRO_SENZA_ACCORDO,
    )

    assert result.riduzione_obbligatoria_applicata is True
    assert result.spese_avvio == 32.0
    assert result.spese_mediazione_primo_incontro == 48.0
    assert result.totale_organismo == 80.0


def test_mediazione_dm150_primo_incontro_con_accordo_applica_maggiorazione_art30():
    result = calcola_costi_mediazione_dm150(
        10000,
        esito=ESITO_PRIMO_INCONTRO_CON_ACCORDO,
    )

    assert result.scaglione == "Da EUR 5.000,01 a EUR 10.000"
    assert result.ulteriori_spese_mediazione == 187.0
    assert result.totale_organismo == 382.0


def test_mediazione_dm150_incontri_successivi_senza_accordo_usa_tabella_a():
    result = calcola_costi_mediazione_dm150(
        10000,
        esito=ESITO_SUCCESSIVI_SENZA_ACCORDO,
    )

    assert result.ulteriori_spese_mediazione == 170.0
    assert result.totale_organismo == 365.0


def test_mediazione_dm150_incontri_successivi_con_accordo_e_art31():
    result = calcola_costi_mediazione_dm150(
        10000,
        esito=ESITO_SUCCESSIVI_CON_ACCORDO,
        art31_comma3_maggiorazione_20=True,
    )

    assert result.art31_comma3_maggiorazione_20 is True
    assert result.ulteriori_spese_mediazione == 255.0
    assert result.totale_organismo == 450.0


def test_mediazione_dm150_valore_indeterminabile_usa_scaglione_riferimento():
    result = calcola_costi_mediazione_dm150(
        0,
        indeterminabile=True,
    )

    assert result.scaglione == "Valore indeterminabile"
    assert result.tabella_a_minimo == 1200.0
    assert result.totale_organismo == 280.0


def test_mediazione_dm150_descrizione_operativa_e_dict_non_vanno_in_ricorsione():
    result = calcola_costi_mediazione_dm150(
        10000,
        esito=ESITO_PRIMO_INCONTRO_CON_ACCORDO,
    )

    payload = result.to_dict()

    assert payload["riferimento_url"].endswith("23G00163&atto.dataPubblicazioneGazzetta=2023-10-31&atto.tipoProvvedimento=DECRETO")
    assert "Costi organismo mediazione D.M. 150/2023" in payload["descrizione_operativa"]
    assert "Accordo raggiunto al primo incontro" in descrizione_operativa_mediazione_dm150(payload)
