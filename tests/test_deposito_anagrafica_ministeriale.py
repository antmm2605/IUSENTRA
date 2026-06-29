from types import SimpleNamespace

import pytest

from web.services.deposito_anagrafica_ministeriale import anagrafica_xml_se_ricorso, valore_causa_fascicolo


def _cliente(
    *,
    codice_fiscale: str = "MRCLCU70A41L840X",
    cap: str = "",
    via: str = "Strada di Saviabona",
    civico: str = "256",
    comune: str = "Vicenza",
    provincia: str = "VI",
):
    return SimpleNamespace(
        tipo="PERSONA_FISICA",
        nome="Lucia",
        cognome="Marchetti",
        ragione_sociale="",
        codice_fiscale=codice_fiscale,
        partita_iva="",
        indirizzo_residenza=SimpleNamespace(
            via=via,
            civico=civico,
            cap=cap,
            comune=comune,
            provincia=provincia,
        ),
        indirizzo_domicilio=None,
        indirizzo_sede_legale=None,
    )


def _fascicolo():
    return SimpleNamespace(
        id_cliente="FDA63E4F",
        nome_cliente="Marchetti Lucia",
        controparte="Ministero dell'Istruzione e del Merito",
        cf_controparte="",
        valore_causa=0,
    )


def _config_studio(*, indirizzo: str = "Via Roma 1", city: str = "Vicenza", province: str = "VI"):
    return SimpleNamespace(
        config=SimpleNamespace(
            studio=SimpleNamespace(
                codice_fiscale_avvocato="MNTGPP70A01L840A",
                avvocato="Giuseppe Montagnese",
                indirizzo=indirizzo,
                city=city,
                province=province,
            ),
            firma=SimpleNamespace(),
        )
    )


def _clienti(cliente):
    return {"FDA63E4F": cliente}


def test_indirizzo_cliente_mancante_non_blocca_anagrafica_ricorso():
    xml = anagrafica_xml_se_ricorso(
        tipo_atto="RICORSO",
        fascicolo=_fascicolo(),
        get_clienti=lambda: _clienti(_cliente(cap="", via="", civico="", comune="", provincia="")),
        get_config_studio=_config_studio,
        operatore="Giuseppe Montagnese",
    )

    assert xml is not None
    assert b"AnagraficaProcedimento" in xml
    assert b"Marchetti" in xml
    assert b"Ministero dell'Istruzione e del Merito" in xml


def test_indirizzo_studio_mancante_non_blocca_anagrafica_ricorso():
    xml = anagrafica_xml_se_ricorso(
        tipo_atto="RICORSO",
        fascicolo=_fascicolo(),
        get_clienti=lambda: _clienti(_cliente()),
        get_config_studio=lambda: _config_studio(indirizzo="", city="", province=""),
        operatore="Giuseppe Montagnese",
    )

    assert xml is not None
    assert b"Giuseppe" in xml
    assert b"Montagnese" in xml


def test_codice_fiscale_cliente_mancante_resta_bloccante_senza_indirizzo_cliente():
    with pytest.raises(ValueError) as exc:
        anagrafica_xml_se_ricorso(
            tipo_atto="RICORSO",
            fascicolo=_fascicolo(),
            get_clienti=lambda: _clienti(
                _cliente(codice_fiscale="", cap="", via="", civico="", comune="", provincia="")
            ),
            get_config_studio=_config_studio,
            operatore="Giuseppe Montagnese",
        )

    message = str(exc.value)
    assert "codice fiscale cliente" in message
    assert "indirizzo cliente" not in message
    assert "CAP cliente" not in message
    assert "comune cliente" not in message
    assert "provincia cliente" not in message
    assert "indirizzo studio" not in message


def test_valore_causa_carta_docente_mim_non_resta_zero():
    fascicolo = SimpleNamespace(
        valore_causa=0.0,
        titolo="Marchetti c. MIM",
        oggetto="Bonus Docente",
        controparte="Avvocatura Distrettuale di Stato di Venezia",
        dati_json={
            "oggetto": "Bonus Docente",
            "valore_causa": 0.0,
            "codice_oggetto_pst": "220050",
        },
    )

    assert valore_causa_fascicolo(fascicolo) == 500.0
