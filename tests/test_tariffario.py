from pct.tariffario import Fase, Grado, Materia, calcola_compenso


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
