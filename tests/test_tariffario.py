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
        Grado.CORTE_APPELLO,
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
        Grado.TRIBUNALE,
        3000,
        [Fase.STUDIO, Fase.INTRODUTTIVA],
    )

    assert risultato.fasi_selezionate == ["Compenso unico"]
    assert risultato.dettaglio["Compenso unico"] == (638.0, 1276.0, 1914.0)
    assert "tabella 25" in risultato.note.lower()
