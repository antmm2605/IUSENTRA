"""Test assegnazione deterministica delle attività agli avvocati."""

from pct.daily_plan.assignment import (
    AssignmentCandidates,
    LawyerResolver,
    resolve_assignment,
)

UTENTI = [
    {"id": "u1", "username": "mbianchi", "nome_completo": "Mario Bianchi"},
    {"id": "u2", "username": "lverdi", "nome_completo": "Lucia Verdi"},
    {"id": "u3", "username": "gverdi", "nome_completo": "Giulio Verdi"},
]


def _resolver():
    return LawyerResolver(users=UTENTI)


def test_referente_fascicolo_assegnato():
    """Caso obbligatorio 10: utente referente presente → assegnazione corretta."""
    esito = resolve_assignment(
        AssignmentCandidates(fascicolo_referente="Avv. Mario Bianchi"), _resolver()
    )
    assert esito.user_id == "u1"
    assert esito.source == "referente"
    assert esito.lawyer_label == "Mario Bianchi"


def test_etichetta_con_titoli_e_ordine_invertito():
    esito = resolve_assignment(
        AssignmentCandidates(fascicolo_referente="avv. Bianchi Mario"), _resolver()
    )
    assert esito.user_id == "u1"


def test_cognome_ambiguo_finisce_in_coda_studio():
    """Caso obbligatorio 11: referente assente/ambiguo → coda da assegnare."""
    esito = resolve_assignment(
        AssignmentCandidates(fascicolo_referente="Avv. Verdi"), _resolver()
    )
    assert esito.user_id == ""
    assert esito.source == "coda_studio"
    # l'etichetta resta visibile per chi smista la coda
    assert "Verdi" in esito.lawyer_label


def test_cognome_univoco_risolve():
    esito = resolve_assignment(
        AssignmentCandidates(fascicolo_referente="Bianchi"), _resolver()
    )
    assert esito.user_id == "u1"


def test_catena_agenda_dopo_referente():
    esito = resolve_assignment(
        AssignmentCandidates(
            fascicolo_referente="Sconosciuto Ignoto",
            agenda_avvocato="Lucia Verdi",
        ),
        _resolver(),
    )
    assert esito.user_id == "u2"
    assert esito.source == "agenda"


def test_responsabile_scadenza_id_forte():
    esito = resolve_assignment(
        AssignmentCandidates(responsible_user_id="u3"), _resolver()
    )
    assert esito.user_id == "u3"
    assert esito.source == "responsabile"


def test_responsabile_non_attivo_ignorato():
    esito = resolve_assignment(
        AssignmentCandidates(responsible_user_id="utente-cancellato"), _resolver()
    )
    assert esito.user_id == ""
    assert esito.source == "coda_studio"


def test_dominus_ultimo_prima_della_coda():
    esito = resolve_assignment(
        AssignmentCandidates(fascicolo_dominus="Giulio Verdi"), _resolver()
    )
    assert esito.user_id == "u3"
    assert esito.source == "dominus"


def test_username_risolve():
    assert _resolver().resolve_label("mbianchi") == "u1"


def test_nessun_candidato_coda_studio():
    esito = resolve_assignment(AssignmentCandidates(), _resolver())
    assert esito.user_id == ""
    assert esito.source == "coda_studio"
