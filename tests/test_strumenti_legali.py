import os

from pct.strumenti_legali import GestioneStrumentiLegali


def _gestore(tmp_path):
    return GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tabelle_normative.json"))


def _cfg_web(tmp_path):
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)
    return {
        "TESTING": True,
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "BACKUP_DIR": str(tmp_path / "backup"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "casella.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
    }


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


def test_tfr_calcola_quota_rivalutazione_e_totale(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_tfr(
        {
            "tfr_retribuzione_annua": "27000",
            "tfr_anni_servizio": "2",
            "tfr_mesi_servizio": "6",
            "tfr_montante_pregresso": "1000",
            "tfr_inflazione_perc": "2",
        }
    )

    assert result["quota_annua"] == 2000.0
    assert result["quota_periodo"] == 5000.0
    assert result["rivalutazione"] == 30.0
    assert result["totale_lordo"] == 6030.0


def test_onorari_forensi_restituisce_fasi_e_riepilogo(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_onorari_forensi(
        {
            "onorari_materia": "CIVILE_COGN",
            "onorari_grado": "TRIBUNALE",
            "onorari_valore": "10000",
            "onorari_complessita": "media",
            "onorari_bonus_telematico": "0",
            "onorari_includi_spese_generali": "1",
            "onorari_fasi": ["STUDIO", "INTRODUTTIVA"],
        }
    )

    assert result["materia"] == "CIVILE_COGN"
    assert len(result["fase_rows"]) == 2
    assert result["riepiloghi"]["base"]["totale_compenso"] > 0
    assert result["livello_suggerito"] == "base"


def test_custodia_cautelare_calcola_timeline_principale(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_custodia_cautelare(
        {
            "custodia_tipo_misura": "carcere",
            "custodia_data_esecuzione": "2026-04-01",
            "custodia_data_istanza_riesame": "2026-04-04",
            "custodia_data_decisione_riesame": "2026-04-10",
        }
    )

    assert result["interrogatorio_entra"] == "2026-04-06"
    assert result["riesame_entra"] == "2026-04-11"
    assert result["decisione_entra"] == "2026-04-14"
    assert result["deposito_entra"] == "2026-05-10"


def test_prescrizione_penale_restituisce_termine_base_e_massimo(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_prescrizione_penale(
        {
            "presc_data_fatto": "2020-01-01",
            "presc_massimo_edittale_anni": "8",
            "presc_massimo_edittale_mesi": "0",
            "presc_contravvenzione": "0",
            "presc_coeff_interruzione": "1.25",
            "presc_giorni_sospensione": "30",
        }
    )

    assert result["regime_label"] == "Delitto"
    assert result["termine_base_anni"] == 8.0
    assert result["data_prescrizione_massima"] > result["data_prescrizione_base"]


def test_successione_legittima_coniuge_e_due_figli(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_successione_legittima(
        {
            "successione_asse": "300000",
            "successione_coniuge": "1",
            "successione_figli": "2",
            "successione_ascendenti": "0",
            "successione_fratelli": "0",
        }
    )

    assert len(result["rows"]) == 2
    assert result["rows"][0]["quota_percent"] == 33.33
    assert result["rows"][1]["per_testa"] == 100000.0


def test_cedolare_secca_calcola_imposta_e_registro_evitato(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_cedolare_secca(
        {
            "cedolare_canone_annuo": "12000",
            "cedolare_aliquota": "21",
            "cedolare_annualita": "2",
        }
    )

    assert result["imposta_annua"] == 2520.0
    assert result["totale_periodo"] == 5040.0
    assert result["registro_evitato"] == 480.0


def test_indennita_licenziamento_jobs_act_calcola_mensilita(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_indennita_licenziamento(
        {
            "lic_retribuzione_mensile": "2000",
            "lic_anni_servizio": "5",
            "lic_mesi_servizio": "0",
            "lic_regime": "jobs_act",
        }
    )

    assert result["mensilita"] == 10.0
    assert result["importo"] == 20000.0


def test_piano_ammortamento_tasso_zero_chiude_residuo(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_piano_ammortamento(
        {
            "amm_capitale": "12000",
            "amm_tasso_annuo": "0",
            "amm_durata_anni": "1",
            "amm_rate_anno": "12",
            "amm_tipo": "francese",
            "amm_data_prima_rata": "2026-01-01",
        }
    )

    assert result["numero_rate"] == 12
    assert result["totale_interessi"] == 0.0
    assert result["schedule"][-1]["residuo"] == 0.0


def test_strumenti_legali_index_renderizza_nuovi_moduli(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        assert login.status_code == 200

        response = client.get("/strumenti-legali/")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "TFR" in body
    assert "Onorari Forensi" in body
    assert "Custodia Cautelare" in body
    assert "Piano di Ammortamento" in body
