from pct.strumenti_legali import GestioneStrumentiLegali


def _gestore(tmp_path):
    return GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tabelle_normative.json"))


def test_contributo_unificato_civile_appello(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "civile_ordinario",
            "cu_grado": "appello",
            "cu_valore": "10000",
            "cu_anticipazione_forfettaria": "1",
        }
    )

    assert result["base"] == 355.5
    assert result["anticipazione_forfettaria"] == 27.0
    assert result["totale"] == 382.5


def test_interessi_legali_2025_su_anno_intero(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_interessi(
        {
            "int_tipo": "legali",
            "int_capitale": "1000",
            "int_data_inizio": "2025-01-01",
            "int_data_fine": "2025-12-31",
        }
    )

    assert result["total_interest"] == 20.0
    assert result["total_amount"] == 1020.0
    assert len(result["segments"]) == 1


def test_interessi_mora_commerciale_2026_primo_semestre(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_interessi(
        {
            "int_tipo": "mora_commerciale",
            "int_capitale": "1000",
            "int_data_inizio": "2026-01-01",
            "int_data_fine": "2026-06-30",
        }
    )

    assert result["segments"][0]["reference_rate"] == 2.15
    assert result["segments"][0]["rate"] == 10.15
    assert result["total_interest"] == 50.33


def test_nota_precisazione_credito_generata_con_residuo(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.genera_nota_precisazione_credito(
        {
            "note_creditore": "Mario Rossi",
            "note_debitore": "Beta Srl",
            "note_titolo": "fatture insolute",
            "note_capitale": "1000",
            "note_interessi_tipo": "manuale",
            "note_interessi_manual": "10",
            "note_spese_vive": "5",
            "note_compensi": "100",
            "note_cpa_perc": "4",
            "note_iva_perc": "22",
            "note_acconti": "100",
            "note_luogo": "Roma",
            "note_data": "2026-04-01",
            "note_avvocato": "Avv. Test",
        }
    )

    assert result["totale_lordo"] == 1141.88
    assert result["residuo"] == 1041.88
    assert "NOTA DI PRECISAZIONE DEL CREDITO" in result["rendered_text"]


def test_pignoramento_pensione_ordinario_usa_minimo_vitale_2026(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.simula_pignoramento(
        {
            "pig_tipo_reddito": "pensione",
            "pig_tipo_credito": "ordinario",
            "pig_importo_netto": "1500",
        }
    )

    assert result["minimo_protetto"] == 819.36
    assert result["base_pignorabile"] == 680.64
    assert result["quota_massima"] == 136.13


def test_ctu_vacazioni_calcola_prima_e_successive(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_ctu(
        {
            "ctu_modalita": "vacazioni",
            "ctu_vacazioni": "5",
            "ctu_spese": "0",
            "ctu_cpa_perc": "0",
            "ctu_iva_perc": "0",
        }
    )

    assert result["onorario_base"] == 47.28
    assert result["totale"] == 47.28
