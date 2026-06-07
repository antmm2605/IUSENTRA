from scripts.audit_legal_practice_matrix import build_audit


def test_matrice_pratica_legale_ha_copertura_dichiarabile_100():
    audit = build_audit()

    assert audit["summary"]["declared_coverage_status"] == "100%"
    assert audit["summary"]["coverage_percent"] == 100.0
    assert audit["summary"]["issues"] == 0
    assert audit["summary"]["cards"] >= 25
    assert audit["summary"]["references"] >= 114
    assert audit["summary"]["web_research_declared_status"] == "100%"
    assert audit["summary"]["web_research_registered_references"] >= 24


def test_matrice_pratica_legale_presidia_materie_chiave():
    audit = build_audit()
    cards = {row["id"]: row for row in audit["cards"]}
    references = {row["id"]: row for row in audit["references"]}

    for card_id in (
        "civile_obbligazioni_contratti_responsabilita",
        "civile_notifiche_monitorio_esecuzioni",
        "lavoro_previdenza_inps_inail",
        "famiglia_persone_minori",
        "penale_difesa_rito_pdp",
        "amministrativo_tar_cds_appalti",
        "tributario_ptt_agenzia_entrate",
        "scolastico_docenti_alunni_concorsi",
        "pubblico_impiego_concorsi_mobilita",
        "edilizia_urbanistica_espropri",
        "ambiente_autorizzazioni_rifiuti",
        "contabile_corte_conti_erariale",
        "societario_impresa_231_mercati",
        "proprieta_industriale_autore",
        "immigrazione_cittadinanza_protezione",
        "deontologia_mandato_compensi",
    ):
        assert cards[card_id]["covered"], card_id
        assert cards[card_id]["official_sources"] > 0
        assert cards[card_id]["nominal_references"] > 0
        assert cards[card_id]["case_law_and_hearings"] > 0
        assert cards[card_id]["acts_to_prepare"] > 0
        assert cards[card_id]["lex_questions"] > 0

    for reference_id in (
        "dlgs_164_2024_correttivo_civile",
        "legge_53_1994_notifiche_avvocati",
        "dpr_115_2002_spese_giustizia",
        "dlgs_150_2022_cartabia_penale",
        "pdp_penale_pst",
        "openga_calendario_udienze",
        "openga_decreti_ordinanze_sentenze",
        "legge_300_1970_statuto_lavoratori",
        "legge_604_1966_licenziamenti",
        "cnf_codice_deontologico_2026",
        "dlgs_297_1994_testo_unico_scuola",
        "dlgs_66_2017_inclusione_scolastica",
        "dlgs_165_2001_pubblico_impiego",
        "dpr_487_1994_concorsi_pubblici",
        "dpr_380_2001_testo_unico_edilizia",
        "dlgs_152_2006_codice_ambiente",
        "dlgs_174_2016_giustizia_contabile",
        "dlgs_231_2001_responsabilita_enti",
        "dlgs_30_2005_codice_proprieta_industriale",
        "legge_633_1941_diritto_autore",
        "dlgs_286_1998_testo_unico_immigrazione",
        "dlgs_25_2008_protezione_internazionale",
        "legge_91_1992_cittadinanza",
        "web_dm_206_2025_modifiche_dm217_ppt",
        "web_dlgs_220_2023_riforma_contenzioso_tributario",
        "web_mef_regole_tecniche_ptt_2017",
        "web_openga_calendario_udienze_categoria",
        "web_mim_di_182_2020_pei_linee_guida",
        "web_mim_dm_153_2023_pei_modelli",
        "web_gu_cnf_art25bis_2026_equo_compenso",
        "web_corte_cost_80_2010_sostegno_scolastico",
        "web_corte_cost_275_2016_diritti_disabili_bilancio",
        "web_corte_cost_194_2018_tutele_crescenti_licenziamento",
        "web_corte_cost_128_2024_gmo_fatto_materiale",
        "web_cass_su_9456_2023_testimone_incapace",
        "web_cass_su_6474_2026_notifica_nullita_prescrizione",
        "web_cass_su_35385_2023_assegno_divorzile_convivenza",
        "web_cass_su_36197_2023_prescrizione_crediti_lavoro_pubblico",
        "web_cass_su_14840_2023_messa_alla_prova_enti",
        "web_cass_su_5166_2026_giustizia_riparativa_impugnazione",
        "web_cass_su_34419_2023_crediti_imposta_inesistenti_non_spettanti",
        "web_cass_su_32790_2023_liquidatore_accertamento_tributario",
        "web_cds_ap_10_2020_accesso_civico_appalti",
        "web_cds_ap_12_2020_termini_impugnazione_appalti",
    ):
        assert references[reference_id]["covered"], reference_id


def test_matrice_pratica_legale_ricerche_web_includono_sentenz_nominali():
    audit = build_audit()
    web_rows = [row for row in audit["references"] if row["id"].startswith("web_")]
    sentenze = [row for row in web_rows if row["kind"] == "sentenza"]

    assert len(sentenze) >= 12
    assert all(row["covered"] for row in web_rows)
    assert all(row["verified_on"] == "2026-06-06" for row in web_rows)
    assert all(row["web_search_query"] for row in web_rows)
    assert all(row["practice_steps"] >= 1 for row in web_rows)
    assert all(row["lex_questions"] >= 1 for row in web_rows)
