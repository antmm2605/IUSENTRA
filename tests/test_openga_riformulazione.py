from pct.openga_riformulazione import valida


def test_non_inventa_numeri_o_codici():
    assert valida("domanda A012 nel 2024", "richiesta A012 del 2024")
    assert not valida("domanda A012 nel 2024", "richiesta A022 del 2024")
    assert not valida("domanda nel 2024", "richiesta nel 2025")
    assert not valida("domanda nel 2024", "richiesta di 3 interessati nel 2024")


def test_omissione_non_diventa_rifiuto():
    q="Il Comune non risponde alla richiesta di vedere gli atti"
    assert not valida(q,"Diniego di accesso agli atti del Comune")
    assert not valida(q,"Accesso agli atti del Comune")
    assert valida(q,"Silenzio del Comune sulla domanda di visione dei documenti")
    assert valida("Diniego di accesso", "Rifiuto della visione degli atti")


def test_codici_preservati_senza_backtracking_su_input_avversari():
    from pct.openga_riformulazione import codici

    assert codici("A0012B3 abc45 123A _A1 A1_") == {"a0012b3", "abc45"}
    assert codici("A" + "0" * 100000 + "_") == set()
