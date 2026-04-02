from pct.tariffario import Fase, Grado, Materia, calcola_compenso
from pct.tariffario_catalogo import (
    TABELLE_SNAPSHOT_META,
    default_rule_for_practice,
    load_tariffario_snapshot,
    profile_lookup_by_rule,
    rules_for_practice,
    tariffario_audit_rows,
    tariffario_rule_rows,
)


def test_tabella_civile_primo_grado_legge_valori_dm147_snapshot():
    risultato = calcola_compenso(
        Materia.CIVILE_COGN,
        Grado.TRIBUNALE,
        10000,
        [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE],
    )

    assert risultato.dettaglio["Studio"] == (459.5, 919.0, 1378.5)
    assert risultato.dettaglio["Introduttiva"] == (388.5, 777.0, 1165.5)
    assert risultato.dettaglio["Istruttoria / Istruzione"] == (840.0, 1680.0, 2520.0)
    assert risultato.dettaglio["Decisionale"] == (850.5, 1701.0, 2551.5)
    assert risultato.totale_base == 5077.0
    assert "tabella 2" in risultato.note.lower()


def test_tabella_tributario_secondo_grado_usa_snapshot_dm147():
    risultato = calcola_compenso(
        Materia.TRIBUTARIO,
        Grado.CGT_SECONDO_GRADO,
        10000,
        [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE],
    )

    assert risultato.dettaglio["Studio"] == (567.0, 1134.0, 1701.0)
    assert risultato.dettaglio["Introduttiva"] == (317.5, 635.0, 952.5)
    assert risultato.dettaglio["Istruttoria / Istruzione"] == (388.5, 777.0, 1165.5)
    assert risultato.dettaglio["Decisionale"] == (709.0, 1418.0, 2127.0)
    assert "tabella 24" in risultato.note.lower()


def test_stragiudiziale_forza_compenso_unico():
    risultato = calcola_compenso(
        Materia.STRAGIUD,
        Grado.FUORI_GIUDIZIO,
        3000,
        [Fase.STUDIO, Fase.INTRODUTTIVA],
    )

    assert risultato.fasi_selezionate == ["Compenso unico"]
    assert risultato.dettaglio["Compenso unico"] == (638.0, 1276.0, 1914.0)
    assert "tabella 25" in risultato.note.lower()


def test_mediazione_tabella_27_usa_snapshot_ufficiale_e_spese_generali_art2():
    risultato = calcola_compenso(
        Materia.MEDIAZIONE,
        Grado.PROCEDURA_ADR,
        10000,
        [Fase.ATTIVAZIONE, Fase.RIVITALIZZAZIONE, Fase.CONCILIAZIONE],
        includi_spese_generali=True,
        perc_spese_generali=0.15,
    )

    assert risultato.scaglione == "Da EUR 5.200 a EUR 26.000"
    assert risultato.dettaglio["Fase di attivazione"] == (220.5, 441.0, 661.5)
    assert risultato.dettaglio["Fase di rivitalizzazione"] == (441.0, 882.0, 1323.0)
    assert risultato.dettaglio["Fase di conciliazione"] == (860.0, 1720.0, 2580.0)
    assert risultato.totale_base == 3043.0
    assert risultato.spese_generali == 456.45
    assert risultato.totale_con_spese == 3499.45
    assert "tabella 27" in risultato.note.lower()
    assert "spese generali art. 2 dm 55/2014: 15% sul compenso base." in risultato.note.lower()


def test_negoziazione_assistita_applica_variazione_pm50_e_bonus_accordo_adr():
    risultato = calcola_compenso(
        Materia.NEGOZIAZIONE_ASSISTITA,
        Grado.PROCEDURA_ADR,
        10000,
        [Fase.ATTIVAZIONE, Fase.NEGOZIAZIONE_TRATTAZIONE, Fase.CONCILIAZIONE],
        includi_spese_generali=True,
        perc_spese_generali=0.15,
        variazioni_fasi={
            Fase.ATTIVAZIONE.value: 1.50,
            Fase.NEGOZIAZIONE_TRATTAZIONE.value: 0.50,
        },
        maggiorazioni_fasi={
            Fase.ATTIVAZIONE.value: 1.30,
            Fase.NEGOZIAZIONE_TRATTAZIONE.value: 1.30,
        },
    )

    assert risultato.dettaglio["Fase di attivazione"] == (286.65, 859.95, 859.95)
    assert risultato.dettaglio["Fase di negoziazione"] == (573.3, 573.3, 1719.9)
    assert risultato.dettaglio["Fase di conciliazione"] == (860.0, 1720.0, 2580.0)
    assert risultato.totale_base == 3153.25
    assert risultato.spese_generali == 472.99
    assert risultato.totale_con_spese == 3626.24
    assert "variazioni per fase applicate" in risultato.note.lower()
    assert "maggiorazioni normative applicate sulle fasi" in risultato.note.lower()
    assert "dm 147/2022: variazione +/-50% tassativa." in risultato.note.lower()


def test_accordo_adr_applica_bonus_automatico_senza_confondere_le_variazioni_manuali():
    risultato = calcola_compenso(
        Materia.NEGOZIAZIONE_ASSISTITA,
        Grado.PROCEDURA_ADR,
        10000,
        [Fase.ATTIVAZIONE, Fase.NEGOZIAZIONE_TRATTAZIONE, Fase.CONCILIAZIONE],
        includi_spese_generali=False,
        maggiorazioni_fasi={
            Fase.ATTIVAZIONE.value: 1.30,
            Fase.NEGOZIAZIONE_TRATTAZIONE.value: 1.30,
        },
    )

    assert risultato.variazioni_fasi == {}
    assert risultato.maggiorazioni_fasi == {
        Fase.ATTIVAZIONE.value: 1.30,
        Fase.NEGOZIAZIONE_TRATTAZIONE.value: 1.30,
    }
    assert risultato.dettaglio["Fase di attivazione"] == (286.65, 573.3, 859.95)
    assert risultato.dettaglio["Fase di negoziazione"] == (573.3, 1146.6, 1719.9)
    assert risultato.totale_base == 3439.9
    assert "accordo adr ex art. 20, comma 1-bis, d.m. 55/2014: +30% automatico" in risultato.note.lower()


def test_penale_appello_applica_coefficiente_ricostruttivo():
    primo_grado = calcola_compenso(
        Materia.PENALE,
        Grado.TRIBUNALE,
        0,
        [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE],
    )
    appello = calcola_compenso(
        Materia.PENALE,
        Grado.CORTE_APPELLO,
        0,
        [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE],
    )

    assert appello.totale_base == round(primo_grado.totale_base * 1.30, 2)
    assert "coefficiente ricostruttivo x1.30" in appello.note


def test_tributario_cassazione_applica_coefficiente_ricostruttivo():
    appello = calcola_compenso(
        Materia.TRIBUTARIO,
        Grado.CGT_SECONDO_GRADO,
        10000,
        [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
    )
    cassazione = calcola_compenso(
        Materia.TRIBUTARIO,
        Grado.CASSAZIONE,
        10000,
        [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
    )

    assert cassazione.totale_base == round(appello.totale_base * 1.60, 2)
    assert "coefficiente ricostruttivo x1.60" in cassazione.note


def test_riepilogo_livello_massimo_calcola_bonus_e_spese():
    risultato = calcola_compenso(
        Materia.CIVILE_COGN,
        Grado.TRIBUNALE,
        10000,
        [Fase.STUDIO, Fase.INTRODUTTIVA],
        bonus_telematico=True,
        includi_spese_generali=True,
        perc_spese_generali=0.15,
    )

    riepilogo = risultato.riepilogo_livello("massimo")

    assert riepilogo["subtotale"] == round(1378.5 + 1165.5, 2)
    assert riepilogo["bonus_telematico"] == round(riepilogo["subtotale"] * 0.30, 2)
    assert riepilogo["spese_generali"] == round((riepilogo["subtotale"] + riepilogo["bonus_telematico"]) * 0.15, 2)


def test_valore_indeterminabile_usa_complessita_stimata_per_scaglione():
    risultato = calcola_compenso(
        Materia.CIVILE_COGN,
        Grado.TRIBUNALE,
        0,
        [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE],
        complessita="media",
    )

    assert risultato.complessita_stimata == "media"
    assert risultato.valore_input == 0
    assert risultato.valore_calcolo == 156000.0
    assert risultato.scaglione == "Da EUR 52.000 a EUR 260.000"
    assert "valore non determinato" in risultato.note.lower()


def test_appello_civile_sdoppia_competenza_tra_tribunale_e_corte_appello():
    rules = rules_for_practice("appello_civile")
    by_code = {row["rule_code"]: row for row in rules}

    assert set(by_code) >= {"civile_appello_da_gdp", "civile_appello"}
    assert by_code["civile_appello_da_gdp"]["grado_input_value"] == "Tribunale"
    assert by_code["civile_appello"]["grado_input_value"] == "Corte d'Appello"

    profile_gdp = profile_lookup_by_rule("civile_appello_da_gdp")
    profile_tribunale = profile_lookup_by_rule("civile_appello")
    assert profile_gdp["table_code"] == "A2"
    assert profile_tribunale["table_code"] == "A12"
    assert default_rule_for_practice("appello_civile")["rule_code"] == "civile_appello"


def test_monitorio_e_opposizione_coprono_anche_competenza_del_giudice_di_pace():
    monitorio = {row["rule_code"]: row for row in rules_for_practice("decreto_ingiuntivo")}
    opposizione = {row["rule_code"]: row for row in rules_for_practice("opposizione_di")}

    assert set(monitorio) >= {"civile_monitorio", "civile_monitorio_gdp"}
    assert monitorio["civile_monitorio"]["grado_input_value"] == "Tribunale"
    assert monitorio["civile_monitorio_gdp"]["grado_input_value"] == "Giudice di Pace"

    profilo_monitorio_gdp = profile_lookup_by_rule("civile_monitorio_gdp")
    assert profilo_monitorio_gdp["table_code"] == "A8"
    assert profilo_monitorio_gdp["calc_mode"] == "compenso_unico"

    assert set(opposizione) >= {"civile_opposizione_monitorio", "civile_opposizione_monitorio_gdp"}
    assert opposizione["civile_opposizione_monitorio"]["grado_input_value"] == "Tribunale"
    assert opposizione["civile_opposizione_monitorio_gdp"]["grado_input_value"] == "Giudice di Pace"


def test_recupero_crediti_e_comparsa_risposta_non_collassano_su_un_unico_grado():
    recupero = {row["rule_code"]: row for row in rules_for_practice("recupero_crediti")}
    comparsa = {row["rule_code"]: row for row in rules_for_practice("comparsa_risposta")}

    assert set(recupero) >= {
        "recupero_crediti_monitorio",
        "recupero_crediti_monitorio_gdp",
        "recupero_crediti_ordinario",
        "recupero_crediti_ordinario_gdp",
    }
    assert default_rule_for_practice("comparsa_risposta")["rule_code"] == "civile_comparsa_risposta"
    assert set(comparsa) >= {"civile_comparsa_risposta", "civile_comparsa_risposta_gdp"}


def test_lavoro_e_previdenza_hanno_tipologie_distinte_per_appello_e_cassazione():
    appello_lavoro = {row["rule_code"]: row for row in rules_for_practice("appello_lavoro")}
    cassazione_lavoro = {row["rule_code"]: row for row in rules_for_practice("cassazione_lavoro")}
    previdenza_primo = {row["rule_code"]: row for row in rules_for_practice("previdenza")}
    appello_previdenza = {row["rule_code"]: row for row in rules_for_practice("appello_previdenza")}
    cassazione_previdenza = {row["rule_code"]: row for row in rules_for_practice("cassazione_previdenza")}

    assert set(appello_lavoro) == {"lavoro_appello"}
    assert set(cassazione_lavoro) == {"lavoro_cassazione"}
    assert default_rule_for_practice("cassazione_lavoro")["rule_code"] == "lavoro_cassazione"
    assert profile_lookup_by_rule("lavoro_cassazione")["table_code"] == "A13"

    assert set(previdenza_primo) == {"previdenza_giudiziale"}
    assert set(appello_previdenza) == {"previdenza_appello"}
    assert set(cassazione_previdenza) == {"previdenza_cassazione"}
    assert default_rule_for_practice("appello_previdenza")["rule_code"] == "previdenza_appello"


def test_audit_tariffario_copre_tutte_le_regole_senza_buchi_strutturali():
    rules = tariffario_rule_rows()
    audit_rows = tariffario_audit_rows()

    assert len(audit_rows) == len(rules)
    assert all(row["snapshot_present"] for row in audit_rows)
    assert all(row["phase_alignment_ok"] for row in audit_rows)
    assert all(row["normative_reference_count"] >= 4 for row in audit_rows)
    assert not [row["rule_code"] for row in audit_rows if row["compliance_status"] == "da_verificare"]


def test_audit_tariffario_giurisdizioni_superiori_separa_le_tre_sedi_su_tabella_14():
    audit_rows = {row["rule_code"]: row for row in tariffario_audit_rows()}

    assert audit_rows["giurisdizioni_superiori_corte_costituzionale"]["table_code"] == "A14"
    assert audit_rows["giurisdizioni_superiori_corte_edu"]["grado_input_value"] == "Corte europea dei diritti dell'uomo"
    assert audit_rows["giurisdizioni_superiori_corte_giustizia_ue"]["grado_input_value"] == "Corte di giustizia UE"
    assert audit_rows["giurisdizioni_superiori_corte_costituzionale"]["compliance_status"] in {"verificata_snapshot", "verificata_seed"}
    assert default_rule_for_practice("cassazione_previdenza")["rule_code"] == "previdenza_cassazione"


def test_tributario_resta_gia_separato_per_primo_grado_appello_e_cassazione():
    ricorso = {row["rule_code"] for row in rules_for_practice("ricorso_tributario")}
    appello = {row["rule_code"] for row in rules_for_practice("appello_tributario")}
    cassazione = {row["rule_code"] for row in rules_for_practice("cassazione_tributaria")}

    assert ricorso == {"tributario_primo_grado"}
    assert appello == {"tributario_secondo_grado"}
    assert cassazione == {"tributario_cassazione"}


def test_esecuzioni_separano_opposizione_all_esecuzione_e_agli_atti():
    opposizione_esecuzione = {row["rule_code"]: row for row in rules_for_practice("opposizione_esecutiva")}
    opposizione_atti = {row["rule_code"]: row for row in rules_for_practice("opposizione_atti_esecutivi")}

    assert set(opposizione_esecuzione) == {"civile_opposizione_esecutiva"}
    assert set(opposizione_atti) == {"civile_opposizione_atti_esecutivi"}
    assert default_rule_for_practice("opposizione_esecutiva")["rule_code"] == "civile_opposizione_esecutiva"
    assert default_rule_for_practice("opposizione_atti_esecutivi")["rule_code"] == "civile_opposizione_atti_esecutivi"
    assert profile_lookup_by_rule("civile_opposizione_esecutiva")["table_code"] == "A2"
    assert profile_lookup_by_rule("civile_opposizione_atti_esecutivi")["table_code"] == "A2"


def test_profili_esecutivi_restano_allineati_a_precetto_e_presso_terzi():
    precetto = {row["rule_code"] for row in rules_for_practice("precetto")}
    presso_terzi = {row["rule_code"] for row in rules_for_practice("esecuzione_terzi")}

    assert precetto == {"esecuzione_precetto"}
    assert presso_terzi == {"esecuzione_presso_terzi"}
    assert profile_lookup_by_rule("esecuzione_precetto")["table_code"] == "A6"
    assert profile_lookup_by_rule("esecuzione_presso_terzi")["table_code"] == "A17"


def test_famiglia_e_volontaria_non_collassano_piu_su_un_unico_contenitore():
    separazione_consensuale = {row["rule_code"] for row in rules_for_practice("separazione_consensuale")}
    separazione_giudiziale = {row["rule_code"] for row in rules_for_practice("separazione_giudiziale")}
    divorzio_congiunto = {row["rule_code"] for row in rules_for_practice("divorzio_congiunto")}
    camerale = {row["rule_code"] for row in rules_for_practice("procedimenti_famiglia")}
    minori = {row["rule_code"] for row in rules_for_practice("procedimenti_minori")}

    assert separazione_consensuale == {"famiglia_separazione_consensuale"}
    assert separazione_giudiziale == {"famiglia_separazione_giudiziale"}
    assert divorzio_congiunto == {"famiglia_divorzio_congiunto"}
    assert camerale == {"famiglia_camerale"}
    assert minori == {"famiglia_procedimenti_minori"}

    assert default_rule_for_practice("procedimenti_famiglia")["rule_code"] == "famiglia_camerale"
    assert default_rule_for_practice("procedimenti_minori")["rule_code"] == "famiglia_procedimenti_minori"
    assert profile_lookup_by_rule("famiglia_camerale")["table_code"] == "A7"
    assert profile_lookup_by_rule("famiglia_procedimenti_minori")["table_code"] == "A2"


def test_famiglia_estende_sottocasi_revisione_reclamo_appello_e_ads():
    modifica = {row["rule_code"] for row in rules_for_practice("modifica_condizioni_famiglia")}
    responsabilita = {row["rule_code"] for row in rules_for_practice("responsabilita_genitoriale")}
    reclamo = {row["rule_code"] for row in rules_for_practice("reclamo_famiglia_minori")}
    appello = {row["rule_code"] for row in rules_for_practice("appello_famiglia_minori")}
    ads = {row["rule_code"] for row in rules_for_practice("amministrazione_sostegno")}

    assert modifica == {"famiglia_modifica_condizioni"}
    assert responsabilita == {"famiglia_responsabilita_genitoriale"}
    assert reclamo == {"famiglia_reclamo"}
    assert appello == {"famiglia_appello_minori"}
    assert ads == {"volontaria_amministrazione_sostegno"}

    assert default_rule_for_practice("reclamo_famiglia_minori")["rule_code"] == "famiglia_reclamo"
    assert default_rule_for_practice("appello_famiglia_minori")["rule_code"] == "famiglia_appello_minori"
    assert default_rule_for_practice("amministrazione_sostegno")["rule_code"] == "volontaria_amministrazione_sostegno"
    assert profile_lookup_by_rule("famiglia_reclamo")["table_code"] == "A12"
    assert profile_lookup_by_rule("famiglia_appello_minori")["table_code"] == "A12"
    assert profile_lookup_by_rule("volontaria_amministrazione_sostegno")["table_code"] == "A7"


def test_tutelare_separa_nomina_modifica_tutela_e_reclamo_del_giudice_tutelare():
    nomina_ads = {row["rule_code"] for row in rules_for_practice("nomina_amministratore_sostegno")}
    modifica_ads = {row["rule_code"] for row in rules_for_practice("modifica_revoca_ads")}
    tutela = {row["rule_code"] for row in rules_for_practice("tutela_curatela")}
    reclamo = {row["rule_code"] for row in rules_for_practice("reclamo_giudice_tutelare")}

    assert nomina_ads == {"volontaria_nomina_ads"}
    assert modifica_ads == {"volontaria_modifica_ads"}
    assert tutela == {"volontaria_tutela_curatela"}
    assert reclamo == {"volontaria_reclamo_giudice_tutelare"}

    assert default_rule_for_practice("nomina_amministratore_sostegno")["rule_code"] == "volontaria_nomina_ads"
    assert default_rule_for_practice("modifica_revoca_ads")["rule_code"] == "volontaria_modifica_ads"
    assert default_rule_for_practice("tutela_curatela")["rule_code"] == "volontaria_tutela_curatela"
    assert default_rule_for_practice("reclamo_giudice_tutelare")["rule_code"] == "volontaria_reclamo_giudice_tutelare"

    assert profile_lookup_by_rule("volontaria_nomina_ads")["table_code"] == "A7"
    assert profile_lookup_by_rule("volontaria_modifica_ads")["table_code"] == "A7"
    assert profile_lookup_by_rule("volontaria_tutela_curatela")["table_code"] == "A7"
    assert profile_lookup_by_rule("volontaria_reclamo_giudice_tutelare")["table_code"] == "A7"


def test_snapshot_tariffario_copre_tabelle_ufficiali_mancanti_e_supplementi_critici():
    snapshot = load_tariffario_snapshot()

    for codice in [
        "A9",
        "A10",
        "A11",
        "A14",
        "A15-1",
        "A15-3",
        "A15-4",
        "A15-5",
        "A19",
        "A20",
        "A15-CONVALIDA",
        "A15-MSORV",
        "A20-BIS",
    ]:
        assert codice in snapshot
        assert codice in TABELLE_SNAPSHOT_META


def test_tariffario_estende_profili_e_regole_ufficiali_non_ancora_tipizzati():
    assert {row["rule_code"] for row in rules_for_practice("istruzione_preventiva")} == {"civile_istruzione_preventiva"}
    assert {row["rule_code"] for row in rules_for_practice("cautelare_civile")} == {"civile_cautelare"}
    assert {row["rule_code"] for row in rules_for_practice("giudizio_corte_conti")} == {"contabile_corte_conti"}
    assert {row["rule_code"] for row in rules_for_practice("giurisdizioni_superiori")} == {
        "giurisdizioni_superiori_corte_costituzionale",
        "giurisdizioni_superiori_corte_edu",
        "giurisdizioni_superiori_corte_giustizia_ue",
    }
    assert {row["rule_code"] for row in rules_for_practice("iscrizione_ipotecaria_tavolare")} == {"affari_ipotecari_tavolari"}
    assert {row["rule_code"] for row in rules_for_practice("apertura_liquidazione_giudiziale")} == {"crisi_impresa_apertura"}
    assert {row["rule_code"] for row in rules_for_practice("accertamento_passivo")} == {"crisi_impresa_passivo"}

    assert default_rule_for_practice("giudice_pace_penale")["rule_code"] == "penale_giudice_pace"
    assert default_rule_for_practice("indagini_difensive")["rule_code"] == "penale_indagini_difensive"
    assert default_rule_for_practice("convalida_arresto")["rule_code"] == "penale_convalida_arresto"
    assert default_rule_for_practice("sorveglianza_penale")["rule_code"] == "penale_sorveglianza_tribunale"
    assert default_rule_for_practice("giurisdizioni_superiori")["rule_code"] == "giurisdizioni_superiori_corte_costituzionale"

    assert profile_lookup_by_rule("contabile_corte_conti")["table_code"] == "A11"
    assert profile_lookup_by_rule("giurisdizioni_superiori_corte_costituzionale")["table_code"] == "A14"
    assert profile_lookup_by_rule("giurisdizioni_superiori_corte_edu")["grado_input_value"] == "Corte europea dei diritti dell'uomo"
    assert profile_lookup_by_rule("giurisdizioni_superiori_corte_giustizia_ue")["grado_input_value"] == "Corte di giustizia UE"
    assert profile_lookup_by_rule("affari_ipotecari_tavolari")["table_code"] == "A19"
    assert profile_lookup_by_rule("crisi_impresa_apertura")["table_code"] == "A20"
    assert profile_lookup_by_rule("crisi_impresa_passivo")["table_code"] == "A20-BIS"
    assert profile_lookup_by_rule("penale_convalida_arresto")["table_code"] == "A15-CONVALIDA"
    assert profile_lookup_by_rule("penale_sorveglianza_magistrato")["table_code"] == "A15-MSORV"


def test_calcolo_crisi_impresa_passivo_legge_tabella_20bis_ufficiale():
    risultato = calcola_compenso(
        Materia.CRISI_IMPRESA,
        Grado.TRIBUNALE_CONCORSUALE,
        10000,
        [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE],
        profile_code="crisi_impresa_passivo",
    )

    assert risultato.dettaglio["Studio"] == (367.5, 735.0, 1102.5)
    assert risultato.dettaglio["Introduttiva"] == (310.0, 620.0, 930.0)
    assert risultato.dettaglio["Istruttoria / Istruzione"] == (672.0, 1344.0, 2016.0)
    assert risultato.dettaglio["Decisionale"] == (672.0, 1344.0, 2016.0)
    assert "tabella 20-bis" in risultato.note.lower()
