from pct.clienti import GestioneClienti, StatoCliente, TipoCliente


def test_cliente_potenziale_espone_campi_mancanti_per_conferimento(tmp_path):
    gc = GestioneClienti(db_path=str(tmp_path / "clienti.json"))
    cliente, creato = gc.crea_o_recupera_potenziale(
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
    )
    assert creato is True
    assert cliente.stato == StatoCliente.POTENZIALE
    assert cliente.profilo_minimo_per_preventivo is True
    assert cliente.profilo_completo_per_conferimento is False
    assert "residenza" in cliente.campi_mancanti_per_conferimento
    assert "almeno un recapito" in cliente.campi_mancanti_per_conferimento


def test_crea_o_recupera_potenziale_riusa_cliente_con_stesso_cf(tmp_path):
    gc = GestioneClienti(db_path=str(tmp_path / "clienti.json"))
    primo, creato_primo = gc.crea_o_recupera_potenziale(
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
    )
    secondo, creato_secondo = gc.crea_o_recupera_potenziale(
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
    )
    assert creato_primo is True
    assert creato_secondo is False
    assert primo.id == secondo.id
