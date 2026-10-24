from pct.openga_organi import verifica_organo


def xml(header, urn="urn:nir:tar.piemonte;sezione.1:sentenza"):
    return (f"<GA><Provvedimento><meta><descrittori><urn>{urn}</urn></descrittori></meta>"
            f"<epigrafe><adunanza>{header}</adunanza><ricorrenti>Roma Milano Torino</ricorrenti>"
            "</epigrafe></Provvedimento></GA>").encode()


def test_court_is_verified_in_header_not_parties():
    raw = xml("Il Tribunale Amministrativo Regionale per il Piemonte")
    assert verifica_organo(raw, {"sede": "020"})
    assert not verifica_organo(raw, {"sede": "003"})
    assert not verifica_organo(raw, {"sede": "002"})


def test_two_seats_need_explicit_city():
    header = "Tribunale Amministrativo Regionale per la Lombardia"
    raw = xml(header, "urn:nir:tar.lombardia;sezione.1:sentenza")
    assert not verifica_organo(raw, {"sede": "016"})
    assert not verifica_organo(raw, {"sede": "017"})
    raw = xml(header + " sede di Brescia", "urn:nir:tar.lombardia;sezione.1:sentenza")
    assert verifica_organo(raw, {"sede": "017"})
    assert not verifica_organo(raw, {"sede": "016"})


def test_official_release_metadata_can_disambiguate_seat():
    raw = xml("Tribunale Amministrativo Regionale per il Lazio", "urn:nir:tar.lazio;sezione.4:sentenza")
    raw = raw.replace(b"</meta>", b"<rilascio>U:/DocumentiGA/Roma/Sezione4/</rilascio></meta>")
    assert verifica_organo(raw, {"sede": "003"})
    assert not verifica_organo(raw, {"sede": "001"})


def test_seat_from_court_deliberation_formula_not_city_in_facts():
    raw = xml("Tribunale Amministrativo Regionale per il Lazio", "urn:nir:tar.lazio;sezione.4B:sentenza")
    raw = raw.replace(b"</Provvedimento>", b"<dispositivo>Cosi deciso in Roma nella camera di consiglio del giorno 6 dicembre 2022.</dispositivo></Provvedimento>")
    assert verifica_organo(raw, {"sede": "003"})
    assert not verifica_organo(raw, {"sede": "001"})
    altered = raw.replace(b"Cosi deciso in Roma", b"Il ricorrente abita in Roma")
    assert not verifica_organo(altered, {"sede": "003"})


def test_decision_family_cannot_be_changed():
    from pct.openga_organi import verifica_tipo
    raw = xml("Tribunale sintetico").replace(b"</meta>", b"<tipologia>Sentenza</tipologia></meta>")
    assert verifica_tipo(raw, {"tipo": "SENTENZA BREVE"})
    assert not verifica_tipo(raw, {"tipo": "ORDINANZA"})
    assert not verifica_tipo(raw, {"tipo": ""})
