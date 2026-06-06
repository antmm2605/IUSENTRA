from scripts.audit_legal_practice_matrix import build_audit


def test_matrice_pratica_legale_ha_copertura_dichiarabile_100():
    audit = build_audit()

    assert audit["summary"]["declared_coverage_status"] == "100%"
    assert audit["summary"]["coverage_percent"] == 100.0
    assert audit["summary"]["issues"] == 0
    assert audit["summary"]["cards"] >= 25
    assert audit["summary"]["references"] >= 90


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
    ):
        assert references[reference_id]["covered"], reference_id
