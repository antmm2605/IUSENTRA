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
