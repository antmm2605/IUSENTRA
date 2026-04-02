from pct.tariffario import Fase, Grado, Materia, calcola_compenso
from pct.tariffario_catalogo import default_rule_for_practice, profile_lookup_by_rule, rules_for_practice


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
