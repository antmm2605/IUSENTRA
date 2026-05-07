import pytest

from pct.tariffario import ComplessitaStimata, Fase, Grado, Materia, calcola_compenso


PHASES = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE]


@pytest.mark.parametrize("valore", [520001, 1000000, 5000000])
@pytest.mark.parametrize(
    ("materia", "grado", "profile_code"),
    [
        (Materia.CIVILE_COGN, Grado.TRIBUNALE, "civile_tribunale"),
        (Materia.CIVILE_COGN, Grado.CORTE_APPELLO, "civile_appello"),
        (Materia.LAVORO, Grado.TRIBUNALE, "lavoro_tribunale"),
        (Materia.PREVIDENZA, Grado.TRIBUNALE, "previdenza_tribunale"),
        (Materia.AMMINISTRATIVO, Grado.TAR, "amministrativo_primo_grado"),
        (Materia.AMMINISTRATIVO, Grado.CONSIGLIO_DI_STATO, "amministrativo_appello"),
        (Materia.TRIBUTARIO, Grado.CGT_PRIMO_GRADO, "tributario_primo_grado"),
        (Materia.TRIBUTARIO, Grado.CGT_SECONDO_GRADO, "tributario_appello"),
        (Materia.STRAGIUD, Grado.FUORI_GIUDIZIO, "stragiudiziale"),
        (Materia.MEDIAZIONE, Grado.PROCEDURA_ADR, "mediazione"),
        (Materia.NEGOZIAZIONE_ASSISTITA, Grado.PROCEDURA_ADR, "negoziazione_assistita"),
        (Materia.ARBITRATO, Grado.PROCEDURA_ADR, "arbitrato"),
    ],
)
def test_valori_oltre_520mila_usano_sempre_scaglione_alto(valore, materia, grado, profile_code):
    risultato = calcola_compenso(
        materia,
        grado,
        valore,
        PHASES,
        profile_code=profile_code,
        complessita=ComplessitaStimata.ALTA,
    )
    payload = risultato.to_dict()

    assert "Oltre EUR 520.000" in risultato.scaglione
    assert payload["table_code"]
    assert payload["table_label"]
    assert payload["reference_codes"]
    assert payload["audit_tariffario"]
    assert payload["audit_tariffario"]["scaglione"] == "Oltre EUR 520.000"
    assert payload["audit_tariffario"]["fascia_alta"] is True
    assert payload["compliance_status"] != "fallback_tecnico"
    assert "degradare" in risultato.note.lower()


def test_molto_alta_parametrizza_valore_indeterminabile_in_fascia_alta():
    risultato = calcola_compenso(
        Materia.CIVILE_COGN,
        Grado.TRIBUNALE,
        0,
        PHASES,
        profile_code="civile_tribunale",
        complessita=ComplessitaStimata.MOLTO_ALTA,
    )
    payload = risultato.to_dict()

    assert risultato.valore_calcolo == 520001.0
    assert risultato.complessita_stimata == "molto_alta"
    assert risultato.scaglione == "Oltre EUR 520.000"
    assert payload["audit_tariffario"]["valore_indeterminabile_parametrizzato"] is True
    assert "valore indeterminabile parametrizzato" in risultato.note.lower()
