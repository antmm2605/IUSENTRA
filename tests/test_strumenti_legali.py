import os

from pct.strumenti_legali import GestioneStrumentiLegali


def _gestore(tmp_path):
    return GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tabelle_normative.json"))


def _cfg_web(tmp_path):
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)
    return {
        "TESTING": True,
        "MULTI_TENANT": False,
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
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
    assert any("dpr_115" in source["code"] for source in result["sources"])
    assert any("Articolo+13" in source["url"] for source in result["sources"])


def test_contributo_unificato_civile_valore_non_indicato(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "civile_ordinario",
            "cu_grado": "primo_grado",
            "cu_valore_tipo": "non_indicato",
            "cu_anticipazione_forfettaria": "1",
        }
    )

    assert result["base"] == 1686.0
    assert result["anticipazione_forfettaria"] == 27.0
    assert result["totale"] == 1713.0


def test_contributo_unificato_dati_obbligatori_mancanti_applica_maggiorazione_50(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "civile_ordinario",
            "cu_grado": "primo_grado",
            "cu_valore": "10000",
            "cu_anticipazione_forfettaria": "0",
            "cu_dati_obbligatori_mancanti": "1",
        }
    )

    assert result["base"] == 355.5
    assert result["totale"] == 355.5
    assert result["dati_obbligatori_mancanti"] is True
    assert any(row["code"] == "dati_obbligatori_mancanti_50" for row in result["regole_applicate"])
    assert any("50%" in note for note in result["notes"])


def test_contributo_unificato_sezione_impresa_raddoppia_prima_del_grado(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "civile_ordinario",
            "cu_grado": "appello",
            "cu_valore": "10000",
            "cu_anticipazione_forfettaria": "0",
            "cu_sezione_specializzata_impresa": "1",
        }
    )

    assert result["base"] == 711.0
    assert result["totale"] == 711.0
    assert [row["code"] for row in result["regole_applicate"]] == [
        "sezione_impresa_x2",
        "impugnazione_50",
    ]


def test_contributo_unificato_lavoro_riduzione_meta_e_appello_50(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "lavoro",
            "cu_grado": "appello",
            "cu_valore": "10000",
            "cu_anticipazione_forfettaria": "0",
        }
    )

    assert result["base"] == 177.75
    assert result["totale"] == 177.75
    assert any(row["code"] == "riduzione_meta_lavoro" for row in result["regole_applicate"])
    assert any(row["code"] == "impugnazione_50" for row in result["regole_applicate"])


def test_contributo_unificato_processo_speciale_riduzione_meta(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "processo_speciale_libro_iv",
            "cu_grado": "primo_grado",
            "cu_valore": "10000",
            "cu_anticipazione_forfettaria": "0",
        }
    )

    assert result["base"] == 118.5
    assert result["totale"] == 118.5
    assert any(row["code"] == "riduzione_meta_speciale" for row in result["regole_applicate"])


def test_contributo_unificato_esecuzioni_e_ricerca_beni_art_13(tmp_path):
    gestore = _gestore(tmp_path)

    immobiliare = gestore.calcola_contributo_unificato(
        {"cu_categoria": "esecuzione_immobiliare", "cu_anticipazione_forfettaria": "0"}
    )
    altra_esecuzione = gestore.calcola_contributo_unificato(
        {"cu_categoria": "altri_processi_esecutivi", "cu_anticipazione_forfettaria": "0"}
    )
    mobiliare_sotto_soglia = gestore.calcola_contributo_unificato(
        {"cu_categoria": "esecuzione_mobiliare_sotto_2500", "cu_anticipazione_forfettaria": "0"}
    )
    ricerca_beni = gestore.calcola_contributo_unificato(
        {"cu_categoria": "ricerca_beni_492bis", "cu_anticipazione_forfettaria": "1"}
    )

    assert immobiliare["base"] == 278.0
    assert altra_esecuzione["base"] == 139.0
    assert any(row["code"] == "riduzione_meta_esecuzioni" for row in altra_esecuzione["regole_applicate"])
    assert mobiliare_sotto_soglia["base"] == 43.0
    assert ricerca_beni["base"] == 43.0
    assert ricerca_beni["anticipazione_forfettaria"] == 0.0


def test_contributo_unificato_fallimentare_opposizione_e_cittadinanza(tmp_path):
    gestore = _gestore(tmp_path)

    fallimentare = gestore.calcola_contributo_unificato(
        {"cu_categoria": "procedura_fallimentare", "cu_anticipazione_forfettaria": "0"}
    )
    opposizione = gestore.calcola_contributo_unificato(
        {"cu_categoria": "opposizione_atti_esecutivi", "cu_anticipazione_forfettaria": "0"}
    )
    cittadinanza = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "cittadinanza_italiana",
            "cu_numero_parti_ricorrenti": "3",
            "cu_grado": "appello",
            "cu_anticipazione_forfettaria": "0",
        }
    )

    assert fallimentare["base"] == 851.0
    assert opposizione["base"] == 168.0
    assert cittadinanza["base"] == 1800.0
    assert cittadinanza["numero_parti_ricorrenti"] == 3
    assert all(row["code"] != "impugnazione_50" for row in cittadinanza["regole_applicate"])


def test_contributo_unificato_tributario_cassazione_usa_misura_civile(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "tributario",
            "cu_grado": "cassazione",
            "cu_valore": "10000",
            "cu_valore_tipo": "determinato",
            "cu_anticipazione_forfettaria": "0",
        }
    )

    assert result["base"] == 474.0
    assert any("cassazione tributaria" in note.lower() for note in result["notes"])


def test_contributo_unificato_tributario_valore_non_indicato(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "tributario",
            "cu_grado": "primo_grado",
            "cu_valore_tipo": "non_indicato",
            "cu_anticipazione_forfettaria": "0",
        }
    )

    assert result["base"] == 1500.0
    assert result["totale"] == 1500.0


def test_contributo_unificato_amministrativo_cassazione_raddoppia_importo(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "amministrativo_ordinario",
            "cu_grado": "cassazione",
            "cu_anticipazione_forfettaria": "0",
        }
    )

    assert result["base"] == 1300.0


def test_contributo_unificato_appalti_cassazione_e_non_indicato(tmp_path):
    gestore = _gestore(tmp_path)
    cassazione = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "amministrativo_appalti",
            "cu_grado": "cassazione",
            "cu_valore": "150000",
            "cu_valore_tipo": "determinato",
            "cu_anticipazione_forfettaria": "0",
        }
    )
    non_indicato = gestore.calcola_contributo_unificato(
        {
            "cu_categoria": "amministrativo_appalti",
            "cu_grado": "primo_grado",
            "cu_valore_tipo": "non_indicato",
            "cu_anticipazione_forfettaria": "0",
        }
    )

    assert cassazione["base"] == 4000.0
    assert non_indicato["base"] == 6000.0


def test_contributi_cassa_forense_2026_usa_fonte_ufficiale_e_non_inventa_maternita(tmp_path):
    gestore = _gestore(tmp_path)

    result = gestore.calcola_contributi_cassa_forense(
        {
            "cf_anno": "2026",
            "cf_reddito": "10000",
            "cf_compensi": "10000",
        }
    )

    contributi = {row["tipo"]: row for row in result["contributi"]}
    assert contributi["soggettivo"]["aliquota"] == 17.0
    assert contributi["soggettivo"]["calcolato"] == 2790.0
    assert contributi["integrativo"]["aliquota"] == 4.0
    assert contributi["integrativo"]["calcolato"] == 400.0
    assert contributi["maternita_assistenza"]["status"] == "da_definire"
    assert contributi["maternita_assistenza"]["calcolato"] == 0.0
    assert result["totale"] == 3190.0
    assert any("da definire" in warning for warning in result["warnings"])
    assert any(source["code"] == "cassa_forense_contributi_2026" for source in result["sources"])


def test_verifica_soglia_usura_usa_q2_2026_e_fonte_gu_specifica(tmp_path):
    gestore = _gestore(tmp_path)

    result = gestore.verifica_soglia_usura(
        {
            "usura_categoria": "credito_personale",
            "usura_tasso": "18.20",
            "usura_data": "2026-04-15",
        }
    )

    assert result["quarter"] == "2026-Q2"
    assert result["tegm"] == 11.32
    assert result["soglia"] == 18.15
    assert result["supera_soglia"] is True
    assert result["esito"] == "USURARIO"
    assert any(source["code"] == "mef_tassi_usura_2026_q2" for source in result["sources"])


def test_verifica_soglia_usura_normalizza_alias_storico_carte_revolving(tmp_path):
    gestore = _gestore(tmp_path)

    result = gestore.verifica_soglia_usura(
        {
            "usura_categoria": "carte_credito_revolving",
            "usura_tasso": "24",
            "usura_data": "2026-04-15",
        }
    )

    assert result["categoria_input"] == "carte_credito_revolving"
    assert result["categoria"] == "credito_revolving"
    assert result["quarter"] == "2026-Q2"
    assert result["soglia"] == 24.07
    assert result["supera_soglia"] is False
    assert any("ricondotta alla categoria ufficiale" in note for note in result["notes"])


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
    assert any(row["code"] == "art_27_informazione_cliente" for row in result["presidi_deontologici"])


def test_onorari_forensi_presidia_equo_compenso_e_informativa_scritta(tmp_path):
    gestore = _gestore(tmp_path)
    result = gestore.calcola_onorari_forensi(
        {
            "onorari_materia": "CIVILE_COGN",
            "onorari_grado": "TRIBUNALE",
            "onorari_valore": "10000",
            "onorari_complessita": "media",
            "onorari_bonus_telematico": "0",
            "onorari_includi_spese_generali": "1",
            "onorari_cliente_qualificato": "1",
            "onorari_convenzione_predisposta_avvocato": "1",
            "onorari_equo_compenso_verificato": "0",
            "onorari_informativa_scritta": "0",
            "onorari_fasi": ["STUDIO", "INTRODUTTIVA"],
        }
    )

    codes = {row["code"]: row for row in result["presidi_deontologici"]}
    source_codes = {source["code"] for source in result["sources"]}

    assert result["cliente_qualificato"] is True
    assert codes["art_25bis_cliente_qualificato"]["status"] == "da_verificare"
    assert codes["art_25bis_informativa_scritta"]["status"] == "da_documentare"
    assert any("equo compenso" in warning.lower() for warning in result["warnings"])
    assert any("avviso scritto" in warning.lower() for warning in result["warnings"])
    assert {
        "codice_deontologico_cnf",
        "cdf_art25bis_gazzetta_2026",
        "cdf_circolare_1c_2026",
    }.issubset(source_codes)


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


def test_catalogo_moduli_include_nuovi_e_moduli_storici(tmp_path):
    gestore = _gestore(tmp_path)
    ids = {item["id"] for item in gestore.catalogo_moduli()}

    assert {
        "tfr",
        "onorari_forensi",
        "custodia_cautelare",
        "prescrizione_penale",
        "successione_legittima",
        "cedolare_secca",
        "indennita_licenziamento",
        "piano_ammortamento",
        "prescrizione",
        "danno_biologico",
        "imposta_registro",
    }.issubset(ids)


def test_strumenti_legali_index_renderizza_nuovi_moduli(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        assert login.status_code == 200

        response = client.get("/strumenti-legali/?_legacy=1")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "TFR" in body
    assert "Onorari Forensi" in body
    assert "Custodia Cautelare" in body
    assert "Piano di Ammortamento" in body
    assert "Prescrizione civile" in body
    assert "Danno biologico" in body
    assert "Imposta di registro" in body


# ── Pena, attenuanti e riti alternativi ────────────────────────────────────


def test_pena_abbreviato_delitto_riduce_di_un_terzo(tmp_path):
    """Art. 442, comma 2, c.p.p.: per i delitti la diminuzione è di un terzo."""

    esito = _gestore(tmp_path).calcola_pena_riti_alternativi(
        {"pena_anni": "3", "pena_tipo_reato": "delitto", "pena_rito": "abbreviato"}
    )

    assert esito["pena_base_giorni"] == 3 * 365
    assert esito["pena_finale_giorni"] == 3 * 365 - (3 * 365) // 3
    assert esito["pena_finale_testo"] == "2 anni"
    assert any("442" in passo["riferimento"] for passo in esito["passaggi"])


def test_pena_abbreviato_contravvenzione_riduce_della_meta(tmp_path):
    """Art. 442, comma 2, c.p.p.: per le contravvenzioni la diminuzione è della metà."""

    esito = _gestore(tmp_path).calcola_pena_riti_alternativi(
        {"pena_mesi": "10", "pena_tipo_reato": "contravvenzione", "pena_rito": "abbreviato"}
    )

    assert esito["pena_finale_giorni"] == 150  # 300 giorni ridotti della metà
    assert "met" in " ".join(passo["operazione"] for passo in esito["passaggi"])


def test_pena_mancata_impugnazione_applica_un_sesto_ulteriore(tmp_path):
    """Art. 442, comma 2-bis, c.p.p. introdotto dal D.Lgs. 150/2022."""

    payload = {"pena_anni": "3", "pena_tipo_reato": "delitto", "pena_rito": "abbreviato"}
    senza = _gestore(tmp_path).calcola_pena_riti_alternativi(payload)
    con = _gestore(tmp_path).calcola_pena_riti_alternativi({**payload, "pena_mancata_impugnazione": "1"})

    atteso = senza["pena_finale_giorni"] - senza["pena_finale_giorni"] // 6
    assert con["pena_finale_giorni"] == atteso
    assert any("2-bis" in passo["riferimento"] for passo in con["passaggi"])


def test_pena_continuazione_non_supera_il_triplo(tmp_path):
    """Art. 81, comma 2, c.p.: la pena non è aumentabile oltre il triplo."""

    esito = _gestore(tmp_path).calcola_pena_riti_alternativi(
        {
            "pena_anni": "1",
            "pena_reati_satellite": "20",
            "pena_aumento_per_reato_giorni": "200",
        }
    )

    assert esito["pena_finale_giorni"] == 3 * 365
    assert any("triplo" in avviso for avviso in esito["warnings"])


def test_pena_continuazione_recidiva_reiterata_ha_aumento_minimo(tmp_path):
    """Art. 81, comma 4, c.p.: aumento non inferiore a un terzo per i recidivi reiterati."""

    esito = _gestore(tmp_path).calcola_pena_riti_alternativi(
        {
            "pena_anni": "3",
            "pena_reati_satellite": "1",
            "pena_aumento_per_reato_giorni": "5",
            "pena_recidiva_reiterata": "1",
        }
    )

    base = 3 * 365
    assert esito["pena_finale_giorni"] == base + base // 3
    assert any("un terzo" in avviso for avviso in esito["warnings"])


def test_pena_sospensione_condizionale_segue_l_eta(tmp_path):
    """Art. 163 c.p.: il limite sale a 2 anni e 6 mesi tra i 18 e i 21 anni."""

    gestore = _gestore(tmp_path)
    payload = {"pena_anni": "2", "pena_mesi": "3"}

    adulto = gestore.calcola_pena_riti_alternativi(payload)
    giovane = gestore.calcola_pena_riti_alternativi({**payload, "pena_eta_imputato": "19"})

    def _sospensione(esito):
        return next(voce for voce in esito["benefici"] if voce["istituto"].startswith("Sospensione"))

    assert _sospensione(adulto)["entro_limite"] is False
    assert _sospensione(giovane)["entro_limite"] is True
    assert "163" in _sospensione(giovane)["riferimento"]


def test_pena_richiede_una_pena_base_e_valori_coerenti(tmp_path):
    import pytest

    gestore = _gestore(tmp_path)
    with pytest.raises(ValueError):
        gestore.calcola_pena_riti_alternativi({})
    with pytest.raises(ValueError):
        gestore.calcola_pena_riti_alternativi({"pena_anni": "1", "pena_mesi": "14"})
    with pytest.raises(ValueError):
        gestore.calcola_pena_riti_alternativi({"pena_anni": "1", "pena_rito": "inesistente"})
    with pytest.raises(ValueError):
        # Continuazione senza aumento indicato: non si inventa la misura.
        gestore.calcola_pena_riti_alternativi({"pena_anni": "1", "pena_reati_satellite": "2"})


def test_pena_dichiara_sempre_le_fonti_normative(tmp_path):
    """Principio delle fonti certe: ogni esito porta con sé i riferimenti."""

    esito = _gestore(tmp_path).calcola_pena_riti_alternativi({"pena_anni": "2"})

    assert esito["sources"]
    assert all(voce.get("url", "").startswith("https://www.normattiva.it") for voce in esito["sources"])
    assert all(passo.get("riferimento") for passo in esito["passaggi"])


def test_pena_e_esposta_nel_catalogo_della_suite(tmp_path):
    from web.blueprints.strumenti_legali import TOOL_METHODS

    catalogo = {voce["id"] for voce in _gestore(tmp_path).catalogo_moduli()}
    assert "pena_riti_alternativi" in catalogo
    assert TOOL_METHODS["pena_riti_alternativi"] == "calcola_pena_riti_alternativi"


# ── Indennità di mediazione (D.M. 150/2023) ────────────────────────────────


def test_mediazione_riusa_le_tabelle_ministeriali_versionate(tmp_path):
    """Il calcolo passa dal motore già versionato: nessun valore nuovo introdotto."""

    from pct.mediazione_dm150 import calcola_costi_mediazione_dm150

    esito = _gestore(tmp_path).calcola_indennita_mediazione({"med_valore": "50000"})
    atteso = calcola_costi_mediazione_dm150(50000.0).to_dict()

    assert esito["totale_organismo"] == atteso["totale_organismo"]
    assert esito["scaglione"] == atteso["scaglione"]
    assert esito["sources"][0]["url"].startswith("https://www.gazzettaufficiale.it")


def test_mediazione_obbligatoria_riduce_le_spese(tmp_path):
    """Art. 28 D.M. 150/2023: riduzione per la mediazione obbligatoria o demandata."""

    gestore = _gestore(tmp_path)
    volontaria = gestore.calcola_indennita_mediazione({"med_valore": "50000", "med_regime": "volontaria"})
    obbligatoria = gestore.calcola_indennita_mediazione(
        {"med_valore": "50000", "med_regime": "obbligatoria_demandata"}
    )

    assert obbligatoria["spese_avvio"] < volontaria["spese_avvio"]
    assert obbligatoria["riduzione_obbligatoria_applicata"] is True


def test_mediazione_valore_indeterminabile_e_input_incoerenti(tmp_path):
    import pytest

    gestore = _gestore(tmp_path)
    indeterminabile = gestore.calcola_indennita_mediazione({"med_valore_tipo": "indeterminabile"})
    assert indeterminabile["totale_organismo"] > 0

    with pytest.raises(ValueError):
        gestore.calcola_indennita_mediazione({})
    with pytest.raises(ValueError):
        gestore.calcola_indennita_mediazione({"med_valore": "1000", "med_regime": "inesistente"})
    with pytest.raises(ValueError):
        gestore.calcola_indennita_mediazione({"med_valore": "1000", "med_esito": "inesistente"})


def test_mediazione_e_esposta_nella_suite(tmp_path):
    from web.blueprints.strumenti_legali import TOOL_METHODS

    catalogo = {voce["id"] for voce in _gestore(tmp_path).catalogo_moduli()}
    assert "indennita_mediazione" in catalogo
    assert TOOL_METHODS["indennita_mediazione"] == "calcola_indennita_mediazione"


# ── Suite React schema-driven ──────────────────────────────────────────────


def _client_react(tmp_path):
    from tests.test_web_bootstrap import _cfg_web as _cfg_bootstrap, _seed_tenant_admin, _write_studio_config
    from web.app import create_app

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_bootstrap(tmp_path))
    studio, admin = _seed_tenant_admin(app)
    client = app.test_client()
    client.get("/login")
    client.post(
        "/login",
        data={"username": admin.username, "password": "PasswordSicura!123", "studio_slug": studio.slug},
    )
    return client


def test_api_react_espone_catalogo_e_schema_dei_moduli(tmp_path):
    client = _client_react(tmp_path)
    payload = client.get("/api/v1/ui/strumenti-legali?tool=pena_riti_alternativi").get_json()

    assert payload["totale"] >= 29
    assert payload["totale_in_react"] >= 1
    assert payload["tool_attivo"] == "pena_riti_alternativi"

    pena = next(voce for voce in payload["strumenti"] if voce["id"] == "pena_riti_alternativi")
    assert pena["reso_in_react"] is True
    nomi = {campo["name"] for campo in pena["campi"]}
    assert {"pena_anni", "pena_rito", "pena_tipo_reato"}.issubset(nomi)
    assert all(campo["type"] in {"number", "select", "date", "text"} for campo in pena["campi"])


def test_api_react_lascia_raggiungibili_gli_strumenti_non_migrati(tmp_path):
    """La migrazione è incrementale: nessuno strumento sparisce dalla suite."""

    client = _client_react(tmp_path)
    payload = client.get("/api/v1/ui/strumenti-legali").get_json()

    non_migrati = [voce for voce in payload["strumenti"] if not voce["reso_in_react"]]
    assert non_migrati
    for voce in non_migrati:
        assert voce["href_vista_classica"].endswith("&_legacy=1")
        assert voce["title"]


def test_api_react_calcola_riusa_i_metodi_di_produzione(tmp_path):
    client = _client_react(tmp_path)
    esito = client.post(
        "/api/v1/ui/strumenti-legali/calcola",
        json={
            "tool": "pena_riti_alternativi",
            "dati": {"pena_anni": "3", "pena_tipo_reato": "delitto", "pena_rito": "abbreviato"},
        },
    ).get_json()

    assert esito["ok"] is True
    assert esito["result"]["pena_finale_testo"] == "2 anni"
    assert esito["result"]["sources"]


def test_api_react_calcola_rifiuta_strumenti_senza_schema_e_input_invalidi(tmp_path):
    client = _client_react(tmp_path)

    senza_schema = client.post(
        "/api/v1/ui/strumenti-legali/calcola", json={"tool": "uffici_competenti", "dati": {}}
    ).get_json()
    assert senza_schema["ok"] is False

    input_invalido = client.post(
        "/api/v1/ui/strumenti-legali/calcola", json={"tool": "pena_riti_alternativi", "dati": {}}
    ).get_json()
    assert input_invalido["ok"] is False
    assert "pena base" in input_invalido["errore"].lower()


def test_schema_dichiara_solo_campi_letti_dai_calcolatori(tmp_path):
    """Ogni campo dichiarato deve avere un default nel form state del dominio."""

    from pct.calcolatori.schema import SCHEMI_CALCOLATORI

    stato = _gestore(tmp_path).build_form_state({})
    for tool_id, schema in SCHEMI_CALCOLATORI.items():
        for campo in schema["campi"]:
            assert campo["name"] in stato, f"{tool_id}: campo {campo['name']} senza default"


def test_rotta_strumenti_legali_punta_al_componente_react(tmp_path):
    from web.blueprints.react_shell import _ROUTE_COMPONENTS

    rotte = dict(_ROUTE_COMPONENTS)
    assert rotte["/strumenti-legali"] == "src/components/StrumentiLegaliPage.tsx"


# ── Crediti di lavoro — art. 429, comma 3, c.p.c. ─────────────────────────


def _payload_lavoro(**extra):
    dati = {
        "lav_importo": "10000",
        "lav_data_maturazione": "2023-01-15",
        "lav_data_liquidazione": "2025-03-20",
        "lav_regime": "privato",
        "lav_tipo_indice": "foi",
        "lav_base_interessi": "rivalutato_progressivo",
    }
    dati.update(extra)
    return dati


def test_crediti_lavoro_privato_cumula_rivalutazione_e_interessi(tmp_path):
    """Art. 429, comma 3, c.p.c.: nel lavoro privato le due voci si sommano."""

    result = _gestore(tmp_path).calcola_crediti_lavoro(_payload_lavoro())

    assert result["cumulo_ammesso"] is True
    assert result["rivalutazione_calcolata"] > 0
    assert result["interessi_calcolati"] > 0
    assert result["rivalutazione_riconosciuta"] == result["rivalutazione_calcolata"]
    assert result["interessi_riconosciuti"] == result["interessi_calcolati"]
    atteso = round(
        result["importo_originale"] + result["rivalutazione_calcolata"] + result["interessi_calcolati"], 2
    )
    assert result["totale"] == atteso
    assert result["segments"]


def test_crediti_lavoro_pubblico_impiego_vieta_il_cumulo(tmp_path):
    """Art. 22, comma 36, L. 724/1994: si riconosce solo la voce maggiore."""

    gestore = _gestore(tmp_path)
    privato = gestore.calcola_crediti_lavoro(_payload_lavoro())
    pubblico = gestore.calcola_crediti_lavoro(_payload_lavoro(lav_regime="pubblico"))

    assert pubblico["cumulo_ammesso"] is False
    maggiore = max(pubblico["rivalutazione_calcolata"], pubblico["interessi_calcolati"])
    assert pubblico["totale"] == round(pubblico["importo_originale"] + maggiore, 2)
    assert pubblico["totale"] < privato["totale"]
    assert pubblico["voce_prevalente"] in {"rivalutazione", "interessi"}
    # La voce non prevalente non viene riconosciuta, ma resta visibile come calcolata.
    riconosciute = (pubblico["rivalutazione_riconosciuta"], pubblico["interessi_riconosciuti"])
    assert 0.0 in riconosciute
    assert any("724/1994" in nota for nota in pubblico["notes"])


def test_crediti_lavoro_rifiuta_periodi_e_importi_incoerenti(tmp_path):
    import pytest

    gestore = _gestore(tmp_path)

    with pytest.raises(ValueError, match="importo"):
        gestore.calcola_crediti_lavoro(_payload_lavoro(lav_importo="0"))

    with pytest.raises(ValueError, match="maturazione"):
        gestore.calcola_crediti_lavoro(_payload_lavoro(lav_data_maturazione=""))

    with pytest.raises(ValueError, match="successiva"):
        gestore.calcola_crediti_lavoro(
            _payload_lavoro(lav_data_maturazione="2025-03-20", lav_data_liquidazione="2023-01-15")
        )


def test_crediti_lavoro_dichiara_le_fonti_e_la_decorrenza(tmp_path):
    result = _gestore(tmp_path).calcola_crediti_lavoro(_payload_lavoro())

    urls = " ".join(fonte["title"] for fonte in result["sources"])
    assert "429" in urls
    assert any("maturazione del diritto" in nota for nota in result["notes"])
    assert result["data_maturazione"] == "15/01/2023"


def test_crediti_lavoro_e_esposto_nella_suite(tmp_path):
    from web.blueprints.strumenti_legali import TOOL_METHODS

    catalogo = {voce["id"] for voce in _gestore(tmp_path).catalogo_moduli()}
    assert "crediti_lavoro" in catalogo
    assert TOOL_METHODS["crediti_lavoro"] == "calcola_crediti_lavoro"


# ── Patrocinio a spese dello Stato (artt. 76, 77 e 92 D.P.R. 115/2002) ────


def _payload_patrocinio(**extra):
    dati = {
        "pat_processo": "civile",
        "pat_reddito_richiedente": "10000",
        "pat_redditi_conviventi": "0",
        "pat_familiari_conviventi": "0",
        "pat_solo_reddito_personale": "0",
        "pat_data_riferimento": "2026-01-15",
    }
    dati.update(extra)
    return dati


def test_patrocinio_usa_la_soglia_del_decreto_vigente_alla_data(tmp_path):
    """Art. 77 D.P.R. 115/2002: la soglia cambia con i decreti di adeguamento."""

    gestore = _gestore(tmp_path)

    recente = gestore.verifica_patrocinio_spese_stato(_payload_patrocinio())
    anteriore = gestore.verifica_patrocinio_spese_stato(
        _payload_patrocinio(pat_data_riferimento="2024-03-01")
    )

    assert recente["limite_base"] == 13659.64
    assert "22 aprile 2025" in recente["decreto_soglia"]
    assert anteriore["limite_base"] == 12838.01
    assert "10 maggio 2023" in anteriore["decreto_soglia"]


def test_patrocinio_cumula_i_redditi_dei_conviventi(tmp_path):
    """Art. 76, comma 2: il reddito è la somma di quelli del nucleo convivente."""

    result = _gestore(tmp_path).verifica_patrocinio_spese_stato(
        _payload_patrocinio(pat_redditi_conviventi="6000", pat_familiari_conviventi="2")
    )

    assert result["reddito_rilevante"] == 16000.0
    assert result["ammissibile"] is False
    assert result["incremento_familiari"] == 0.0


def test_patrocinio_penale_eleva_il_limite_per_ogni_convivente(tmp_path):
    """Art. 92: +1.032,91 euro per ognuno dei familiari conviventi."""

    gestore = _gestore(tmp_path)
    civile = gestore.verifica_patrocinio_spese_stato(
        _payload_patrocinio(pat_redditi_conviventi="6000", pat_familiari_conviventi="2")
    )
    penale = gestore.verifica_patrocinio_spese_stato(
        _payload_patrocinio(
            pat_processo="penale", pat_redditi_conviventi="6000", pat_familiari_conviventi="2"
        )
    )

    assert penale["incremento_unitario"] == 1032.91
    assert penale["incremento_familiari"] == 2065.82
    assert penale["limite_applicabile"] == round(civile["limite_applicabile"] + 2065.82, 2)


def test_patrocinio_solo_reddito_personale_esclude_cumulo_ed_elevazione(tmp_path):
    """Art. 76, comma 4: senza cumulo non opera nemmeno l'elevazione dell'art. 92."""

    result = _gestore(tmp_path).verifica_patrocinio_spese_stato(
        _payload_patrocinio(
            pat_processo="penale",
            pat_redditi_conviventi="6000",
            pat_familiari_conviventi="2",
            pat_solo_reddito_personale="1",
        )
    )

    assert result["reddito_rilevante"] == 10000.0
    assert result["incremento_familiari"] == 0.0
    assert any("art. 92" in avviso for avviso in result["warnings"])


def test_patrocinio_si_ferma_sulle_date_non_coperte_e_sugli_input_incoerenti(tmp_path):
    """Fail-closed: nessuna soglia inventata fuori dai decreti caricati."""

    import pytest

    gestore = _gestore(tmp_path)

    with pytest.raises(ValueError):
        gestore.verifica_patrocinio_spese_stato(_payload_patrocinio(pat_data_riferimento="2019-01-01"))
    with pytest.raises(ValueError):
        gestore.verifica_patrocinio_spese_stato(_payload_patrocinio(pat_data_riferimento=""))
    with pytest.raises(ValueError):
        gestore.verifica_patrocinio_spese_stato(_payload_patrocinio(pat_processo="inesistente"))
    with pytest.raises(ValueError):
        # Redditi di conviventi dichiarati senza conviventi.
        gestore.verifica_patrocinio_spese_stato(_payload_patrocinio(pat_redditi_conviventi="5000"))


def test_patrocinio_dichiara_fonti_e_perimetro(tmp_path):
    """Principio delle fonti certe: soglia tracciata e perimetro esplicito."""

    result = _gestore(tmp_path).verifica_patrocinio_spese_stato(_payload_patrocinio())

    assert result["sources"]
    assert all(voce["url"] for voce in result["sources"])
    assert any("Gazzetta Ufficiale" in nota or "GU" in nota for nota in result["notes"])
    assert any("artt. 76 e 92" in avviso for avviso in result["warnings"])


def test_patrocinio_e_esposto_nella_suite(tmp_path):
    from web.blueprints.strumenti_legali import TOOL_METHODS

    catalogo = {voce["id"] for voce in _gestore(tmp_path).catalogo_moduli()}
    assert "patrocinio_spese_stato" in catalogo
    assert TOOL_METHODS["patrocinio_spese_stato"] == "verifica_patrocinio_spese_stato"


# ── Competenza per valore (art. 7 c.p.c.) ─────────────────────────────────


def _payload_competenza(**extra):
    dati = {
        "comp_materia": "beni_mobili",
        "comp_valore": "8000",
        "comp_data_introduzione": "2026-01-15",
    }
    dati.update(extra)
    return dati


def test_competenza_applica_le_soglie_elevate_dalla_riforma(tmp_path):
    """Art. 3, comma 1, D.Lgs. 149/2022: beni mobili fino a 10.000 euro."""

    result = _gestore(tmp_path).calcola_competenza_valore(_payload_competenza())

    assert result["soglia_applicata"] == 10000.0
    assert result["giudice_competente"] == "Giudice di pace"
    assert result["regime"] == "cartabia"


def test_competenza_procedimenti_anteriori_conservano_le_vecchie_soglie(tmp_path):
    """Art. 35, comma 1, D.Lgs. 149/2022 come sostituito dalla L. 197/2022."""

    gestore = _gestore(tmp_path)
    anteriore = gestore.calcola_competenza_valore(
        _payload_competenza(comp_data_introduzione="2023-02-28")
    )
    successivo = gestore.calcola_competenza_valore(
        _payload_competenza(comp_data_introduzione="2023-03-01")
    )

    assert anteriore["soglia_applicata"] == 5000.0
    assert anteriore["giudice_competente"] == "Tribunale"
    assert successivo["soglia_applicata"] == 10000.0
    assert successivo["giudice_competente"] == "Giudice di pace"


def test_competenza_danno_da_circolazione_ha_una_soglia_propria(tmp_path):
    """Art. 7, secondo comma, c.p.c.: 25.000 euro dopo la riforma."""

    gestore = _gestore(tmp_path)
    entro = gestore.calcola_competenza_valore(
        _payload_competenza(comp_materia="danno_circolazione", comp_valore="24000")
    )
    oltre = gestore.calcola_competenza_valore(
        _payload_competenza(comp_materia="danno_circolazione", comp_valore="26000")
    )

    assert entro["soglia_applicata"] == 25000.0
    assert entro["giudice_competente"] == "Giudice di pace"
    assert oltre["giudice_competente"] == "Tribunale"


def test_competenza_rifiuta_valori_e_date_mancanti(tmp_path):
    import pytest

    gestore = _gestore(tmp_path)

    with pytest.raises(ValueError):
        gestore.calcola_competenza_valore(_payload_competenza(comp_valore="0"))
    with pytest.raises(ValueError):
        gestore.calcola_competenza_valore(_payload_competenza(comp_data_introduzione=""))
    with pytest.raises(ValueError):
        gestore.calcola_competenza_valore(_payload_competenza(comp_materia="inesistente"))


def test_competenza_dichiara_fonti_e_perimetro(tmp_path):
    result = _gestore(tmp_path).calcola_competenza_valore(_payload_competenza())

    urls = " ".join(voce["url"] for voce in result["sources"])
    assert "normattiva.it" in urls
    assert "22G00158" in urls
    assert "22G00211" in urls
    assert any("competenza per valore" in avviso for avviso in result["warnings"])


def test_competenza_e_esposta_nella_suite(tmp_path):
    from web.blueprints.strumenti_legali import TOOL_METHODS

    catalogo = {voce["id"] for voce in _gestore(tmp_path).catalogo_moduli()}
    assert "competenza_valore" in catalogo
    assert TOOL_METHODS["competenza_valore"] == "calcola_competenza_valore"


# ── Termini processuali (art. 155 c.p.c.; L. 742/1969) ────────────────────


def _payload_termini(**extra):
    dati = {
        "term_modello": "CIV_APPELLO_BREVE",
        "term_data_evento": "2026-03-10",
        "term_urgente": "0",
        "term_valore_personalizzato": "",
        "term_riferimento": "RG 100/2026",
    }
    dati.update(extra)
    return dati


def test_termini_riusa_il_motore_versionato_del_progetto(tmp_path):
    """Nessuna regola di computo riscritta: l'esito coincide con il motore."""

    from datetime import date

    from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

    template = next(voce for voce in DEFAULT_TEMPLATES if voce.code == "CIV_APPELLO_BREVE")
    atteso = ItalianDeadlineCalculator().calculate_template(date(2026, 3, 10), template)

    result = _gestore(tmp_path).calcola_termini_processuali(_payload_termini())

    giorno, mese, anno = result["scadenza"].split("/")
    assert f"{anno}-{mese}-{giorno}" == atteso["deadline"]
    assert result["riferimento_normativo"] == "Art. 325 c.p.c."


def test_termini_applica_la_sospensione_feriale_di_agosto(tmp_path):
    """L. 742/1969: i giorni dal 1 al 31 agosto non si computano."""

    gestore = _gestore(tmp_path)
    ordinario = gestore.calcola_termini_processuali(_payload_termini(term_data_evento="2026-07-20"))
    urgente = gestore.calcola_termini_processuali(
        _payload_termini(term_data_evento="2026-07-20", term_urgente="1")
    )

    assert ordinario["sospensione_feriale"] is True
    assert urgente["sospensione_feriale"] is False
    # Con la sospensione la scadenza cade oltre agosto, senza no.
    assert ordinario["scadenza"] > urgente["scadenza"]
    assert any("urgente" in avviso.lower() for avviso in urgente["warnings"])


def test_termini_accetta_una_durata_personalizzata(tmp_path):
    result = _gestore(tmp_path).calcola_termini_processuali(
        _payload_termini(term_modello="CUSTOM_PROCESSUALE", term_valore_personalizzato="45")
    )

    assert result["durata"] == 45
    assert any("personalizzata" in nota for nota in result["notes"])


def test_termini_rifiuta_modelli_e_date_non_validi(tmp_path):
    import pytest

    gestore = _gestore(tmp_path)

    with pytest.raises(ValueError):
        gestore.calcola_termini_processuali(_payload_termini(term_modello="INESISTENTE"))
    with pytest.raises(ValueError):
        gestore.calcola_termini_processuali(_payload_termini(term_data_evento=""))


def test_termini_dichiara_fonti_passaggi_e_versione_delle_regole(tmp_path):
    result = _gestore(tmp_path).calcola_termini_processuali(_payload_termini())

    assert result["passaggi"]
    assert result["versione_regole"]
    urls = " ".join(voce["url"] for voce in result["sources"])
    assert "742" in urls or "155" in urls


def test_termini_e_esposto_nella_suite_con_i_modelli_del_motore(tmp_path):
    from web.blueprints.strumenti_legali import TOOL_METHODS

    gestore = _gestore(tmp_path)
    catalogo = {voce["id"] for voce in gestore.catalogo_moduli()}
    modelli = gestore.opzioni_termini_processuali()

    assert "termini_processuali" in catalogo
    assert TOOL_METHODS["termini_processuali"] == "calcola_termini_processuali"
    assert {voce["value"] for voce in modelli} >= {"CIV_APPELLO_BREVE", "CIV_APPELLO_LUNGO"}


# ── Termini di impugnazione (artt. 325 e 327 c.p.c.) ──────────────────────


def _payload_impugnazioni(**extra):
    dati = {
        "imp_mezzo": "appello",
        "imp_data_pubblicazione": "2026-03-10",
        "imp_data_notificazione": "",
        "imp_sospensione_feriale": "applica",
        "imp_riferimento": "RG 100/2026",
    }
    dati.update(extra)
    return dati


def test_impugnazioni_senza_notifica_calcola_solo_il_termine_lungo(tmp_path):
    result = _gestore(tmp_path).calcola_impugnazioni(_payload_impugnazioni())

    assert result["termine_breve"] == ""
    assert result["termine_lungo"]
    assert result["termine_prevalente"] == "lungo"
    assert any("Nessuna notificazione" in nota for nota in result["notes"])


def test_impugnazioni_la_notifica_fa_prevalere_il_termine_breve(tmp_path):
    result = _gestore(tmp_path).calcola_impugnazioni(
        _payload_impugnazioni(imp_data_notificazione="2026-03-20")
    )

    assert result["termine_breve"]
    assert result["termine_prevalente"] == "breve"
    assert result["scadenza_effettiva"] == result["termine_breve"]


def test_impugnazioni_cassazione_usa_il_termine_di_sessanta_giorni(tmp_path):
    gestore = _gestore(tmp_path)
    appello = gestore.calcola_impugnazioni(_payload_impugnazioni(imp_data_notificazione="2026-03-20"))
    cassazione = gestore.calcola_impugnazioni(
        _payload_impugnazioni(imp_mezzo="cassazione", imp_data_notificazione="2026-03-20")
    )

    riga_appello = next(voce for voce in appello["termini"] if voce["termine"] == "Termine breve")
    riga_cassazione = next(voce for voce in cassazione["termini"] if voce["termine"] == "Termine breve")
    assert riga_appello["durata"].startswith("30")
    assert riga_cassazione["durata"].startswith("60")


def test_impugnazioni_la_sospensione_feriale_sposta_la_scadenza(tmp_path):
    """Art. 1 L. 742/1969, con l'esclusione dell'art. 3 come opzione."""

    gestore = _gestore(tmp_path)
    con = gestore.calcola_impugnazioni(_payload_impugnazioni(imp_data_notificazione="2026-07-20"))
    senza = gestore.calcola_impugnazioni(
        _payload_impugnazioni(imp_data_notificazione="2026-07-20", imp_sospensione_feriale="esclusa")
    )

    assert con["sospensione_feriale"] is True
    assert senza["sospensione_feriale"] is False
    assert con["termine_breve"] != senza["termine_breve"]


def test_impugnazioni_rifiuta_date_incoerenti(tmp_path):
    import pytest

    gestore = _gestore(tmp_path)

    with pytest.raises(ValueError):
        gestore.calcola_impugnazioni(_payload_impugnazioni(imp_data_pubblicazione=""))
    with pytest.raises(ValueError):
        gestore.calcola_impugnazioni(_payload_impugnazioni(imp_data_notificazione="2026-01-01"))
    with pytest.raises(ValueError):
        gestore.calcola_impugnazioni(_payload_impugnazioni(imp_mezzo="opposizione"))


# ── Ravvedimento operoso (art. 13 D.Lgs. 472/1997 e 471/1997) ─────────────


def _payload_ravvedimento(**extra):
    dati = {
        "rav_tipo_violazione": "omesso_versamento",
        "rav_imposta": "1000",
        "rav_data_scadenza": "2026-01-16",
        "rav_data_versamento": "2026-02-10",
        "rav_evento": "nessuno",
    }
    dati.update(extra)
    return dati


def test_ravvedimento_applica_il_regime_della_data_di_violazione(tmp_path):
    """Art. 5 D.Lgs. 87/2024: spartiacque al 1 settembre 2024."""

    gestore = _gestore(tmp_path)
    nuovo = gestore.calcola_ravvedimento_operoso(_payload_ravvedimento())
    vecchio = gestore.calcola_ravvedimento_operoso(
        _payload_ravvedimento(rav_data_scadenza="2024-01-16", rav_data_versamento="2024-02-10")
    )

    assert nuovo["regime"] == "dal_2024"
    assert vecchio["regime"] == "ante_2024"
    # 25 giorni di ritardo: sanzione base 12,5% dal 2024, 15% prima.
    assert nuovo["sanzione_percent"] == 12.5
    assert vecchio["sanzione_percent"] == 15.0


def test_ravvedimento_riduzione_di_un_decimo_entro_trenta_giorni(tmp_path):
    """Art. 13, comma 1, lett. a), D.Lgs. 472/1997."""

    result = _gestore(tmp_path).calcola_ravvedimento_operoso(_payload_ravvedimento())

    assert result["riduzione_denominatore"] == 10
    assert result["riduzione_lettera"] == "a"
    # 1000 euro, 12,5% ridotto a 1/10 = 12,50 euro.
    assert result["sanzione_ridotta"] == 12.5
    assert result["totale_da_versare"] > 1000


def test_ravvedimento_sanzione_giornaliera_entro_quindici_giorni(tmp_path):
    """Art. 13 D.Lgs. 471/1997: 0,83% per giorno dal 1 settembre 2024."""

    result = _gestore(tmp_path).calcola_ravvedimento_operoso(
        _payload_ravvedimento(rav_data_versamento="2026-01-18")
    )

    assert result["giorni_ritardo"] == 2
    assert result["sanzione_percent"] == 1.66
    assert result["sanzione_ridotta"] == 1.66


def test_ravvedimento_scaglioni_temporali_e_eventi(tmp_path):
    import pytest

    gestore = _gestore(tmp_path)

    entro_anno = gestore.calcola_ravvedimento_operoso(
        _payload_ravvedimento(rav_data_versamento="2026-06-30")
    )
    oltre_anno = gestore.calcola_ravvedimento_operoso(
        _payload_ravvedimento(rav_data_versamento="2027-06-30")
    )
    dopo_pvc = gestore.calcola_ravvedimento_operoso(_payload_ravvedimento(rav_evento="dopo_pvc"))

    assert entro_anno["riduzione_denominatore"] == 8
    assert oltre_anno["riduzione_denominatore"] == 7
    assert dopo_pvc["riduzione_denominatore"] == 5

    with pytest.raises(ValueError):
        # Lo schema di atto esiste solo nel regime dal 1 settembre 2024.
        gestore.calcola_ravvedimento_operoso(
            _payload_ravvedimento(
                rav_data_scadenza="2024-01-16",
                rav_data_versamento="2024-03-10",
                rav_evento="dopo_schema_atto",
            )
        )


def test_ravvedimento_rifiuta_input_incoerenti_e_dichiara_le_fonti(tmp_path):
    import pytest

    gestore = _gestore(tmp_path)

    with pytest.raises(ValueError):
        gestore.calcola_ravvedimento_operoso(_payload_ravvedimento(rav_imposta="0"))
    with pytest.raises(ValueError):
        gestore.calcola_ravvedimento_operoso(_payload_ravvedimento(rav_data_versamento="2025-12-01"))
    with pytest.raises(ValueError):
        gestore.calcola_ravvedimento_operoso(
            _payload_ravvedimento(rav_tipo_violazione="altra_violazione", rav_sanzione_minima="")
        )

    result = gestore.calcola_ravvedimento_operoso(_payload_ravvedimento())
    urls = " ".join(voce["url"] for voce in result["sources"])
    assert "agenziaentrate.gov.it" in urls
    assert "24G00103" in urls
    assert result["segmenti_interessi"]


# ── Compenso a tempo (art. 22-bis D.M. 55/2014) ───────────────────────────


def _payload_compenso_tempo(**extra):
    dati = {
        "cat_tariffa_oraria": "250",
        "cat_ore": "3",
        "cat_minuti": "40",
        "cat_criterio": "ora_frazione_oltre_30",
        "cat_massimale_ore": "",
        "cat_soglia_ore": "",
        "cat_spese_generali_percent": "15",
    }
    dati.update(extra)
    return dati


def test_compenso_a_tempo_riusa_il_motore_del_preventivatore(tmp_path):
    from pct.compensi_a_tempo import calcola_compenso_a_tempo_art22bis

    atteso = calcola_compenso_a_tempo_art22bis(250.0, 3.0, 40, "ora_frazione_oltre_30")
    result = _gestore(tmp_path).calcola_compenso_a_tempo(_payload_compenso_tempo())

    assert result["ore_fatturabili"] == atteso["ore_fatturabili"]
    assert result["compenso_base"] == atteso["compenso_base"]
    assert result["spese_generali"] == round(result["compenso_base"] * 0.15, 2)


def test_compenso_a_tempo_avvisa_fuori_dal_parametro_e_sui_massimali(tmp_path):
    gestore = _gestore(tmp_path)

    fuori_range = gestore.calcola_compenso_a_tempo(_payload_compenso_tempo(cat_tariffa_oraria="90"))
    oltre_massimale = gestore.calcola_compenso_a_tempo(_payload_compenso_tempo(cat_massimale_ore="2"))

    assert any("22-bis" in avviso for avviso in fuori_range["warnings"])
    assert any("massimale" in avviso for avviso in oltre_massimale["warnings"])


def test_compenso_a_tempo_rifiuta_input_non_validi(tmp_path):
    import pytest

    gestore = _gestore(tmp_path)

    with pytest.raises(ValueError):
        gestore.calcola_compenso_a_tempo(_payload_compenso_tempo(cat_tariffa_oraria="0"))
    with pytest.raises(ValueError):
        gestore.calcola_compenso_a_tempo(_payload_compenso_tempo(cat_ore="0", cat_minuti="0"))
    with pytest.raises(ValueError):
        gestore.calcola_compenso_a_tempo(_payload_compenso_tempo(cat_criterio="a_occhio"))


def test_nuovi_strumenti_sono_esposti_nella_suite(tmp_path):
    from web.blueprints.strumenti_legali import TOOL_METHODS

    catalogo = {voce["id"] for voce in _gestore(tmp_path).catalogo_moduli()}
    for tool_id, metodo in (
        ("impugnazioni", "calcola_impugnazioni"),
        ("ravvedimento_operoso", "calcola_ravvedimento_operoso"),
        ("compenso_a_tempo", "calcola_compenso_a_tempo"),
    ):
        assert tool_id in catalogo
        assert TOOL_METHODS[tool_id] == metodo


# ── Copertura React della suite ───────────────────────────────────────────


def test_ogni_schema_ha_un_metodo_di_calcolo_in_produzione(tmp_path):
    """Uno schema senza metodo esporrebbe un modulo che non calcola nulla."""

    from pct.calcolatori.schema import SCHEMI_CALCOLATORI
    from web.blueprints.strumenti_legali import TOOL_METHODS

    gestore = _gestore(tmp_path)
    for tool_id in SCHEMI_CALCOLATORI:
        assert tool_id in TOOL_METHODS, f"{tool_id} dichiarato senza metodo di calcolo"
        assert hasattr(gestore, TOOL_METHODS[tool_id])


def test_bridge_risolve_le_opzioni_dinamiche_dal_dominio(tmp_path):
    """Materie, gradi e categorie restano una fonte sola: il gestore."""

    from web.services.react_strumenti_legali_bridge import (
        build_react_strumenti_legali_payload,
        sorgenti_opzioni,
    )

    gestore = _gestore(tmp_path)
    payload = build_react_strumenti_legali_payload(
        catalogo=gestore.catalogo_moduli(),
        form_state=gestore.build_form_state({}),
        opzioni=sorgenti_opzioni(gestore),
    )

    onorari = next(voce for voce in payload["strumenti"] if voce["id"] == "onorari_forensi")
    materia = next(campo for campo in onorari["campi"] if campo["name"] == "onorari_materia")
    assert materia["options"], "le materie del D.M. 55/2014 devono arrivare dal gestore"
    assert len(materia["options"]) == len(gestore.opzioni_onorari_forensi()["materie"])

    # Il marcatore interno non deve mai raggiungere il client.
    for voce in payload["strumenti"]:
        for campo in voce["campi"]:
            assert "options_from" not in campo
            if campo["type"] == "select":
                assert campo["options"], f"{voce['id']}.{campo['name']} senza opzioni"


def test_bridge_senza_cataloghi_non_espone_moduli_a_meta(tmp_path):
    """Se le opzioni dinamiche non sono risolvibili resta la vista classica."""

    from web.services.react_strumenti_legali_bridge import build_react_strumenti_legali_payload

    gestore = _gestore(tmp_path)
    payload = build_react_strumenti_legali_payload(
        catalogo=gestore.catalogo_moduli(),
        form_state=gestore.build_form_state({}),
        opzioni={},
    )

    onorari = next(voce for voce in payload["strumenti"] if voce["id"] == "onorari_forensi")
    assert onorari["reso_in_react"] is False
    assert onorari["campi"] == []
    assert onorari["href_vista_classica"].endswith("&_legacy=1")

    # Gli strumenti a opzioni statiche restano invece disponibili in React.
    interessi = next(voce for voce in payload["strumenti"] if voce["id"] == "interessi")
    assert interessi["reso_in_react"] is True


def test_tutti_i_calcolatori_della_suite_sono_migrati_in_react(tmp_path):
    """Solo la ricerca uffici resta fuori: non è un calcolatore ma un motore di ricerca."""

    from pct.calcolatori.schema import SCHEMI_CALCOLATORI

    catalogo = {voce["id"] for voce in _gestore(tmp_path).catalogo_moduli()}
    fuori_schema = catalogo - set(SCHEMI_CALCOLATORI)
    assert fuori_schema == {"uffici_competenti"}
