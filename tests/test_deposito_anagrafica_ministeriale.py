from types import SimpleNamespace

import pytest

from web.services.deposito_anagrafica_ministeriale import (
    _split_nome_cognome,
    anagrafica_xml_se_ricorso,
    contributo_unificato_fascicolo,
    deposito_ministerial_readiness,
    valore_causa_fascicolo,
)


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


def test_indirizzi_mancanti_non_bloccano_anagrafica_sigp_introduttivo():
    xml = anagrafica_xml_se_ricorso(
        tipo_atto="ATTO_DI_CITAZIONE",
        fascicolo=_fascicolo(),
        get_clienti=lambda: _clienti(_cliente(cap="", via="", civico="", comune="", provincia="")),
        get_config_studio=lambda: _config_studio(indirizzo="", city="", province=""),
        operatore="Giuseppe Montagnese",
        datiatto_root_name="Ricorso",
        datiatto_generator_class="Introduttivi_SIGP",
    )

    assert xml is not None
    assert b"AnagraficaProcedimento" in xml
    assert b"sigp/tipi/atti/v3" in xml


def test_indirizzi_mancanti_non_bloccano_anagrafica_cassazione():
    xml = anagrafica_xml_se_ricorso(
        tipo_atto="RICORSO",
        fascicolo=_fascicolo(),
        get_clienti=lambda: _clienti(_cliente(cap="", via="", civico="", comune="", provincia="")),
        get_config_studio=lambda: _config_studio(indirizzo="", city="", province=""),
        operatore="Giuseppe Montagnese",
        datiatto_root_name="Ricorso",
        datiatto_generator_class="ParteCassazione",
    )

    assert xml is not None
    assert b"AnagraficaProcedimento" in xml
    assert b"cassazione/tipi/atti/v13" in xml


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


def test_readiness_deposito_riconosce_esenzione_anagrafica_e_valore_gia_presenti():
    fascicolo = _fascicolo()
    fascicolo.valore_causa = 500.0
    fascicolo.pagamenti = {
        "contributo_unificato": {
            "status": "non_previsto",
            "previsto": False,
            "natura": "esenzione_contributo_unificato",
            "documento_fonte": "Autocertificazione situazione reddituale.PDF",
        }
    }

    contribution = contributo_unificato_fascicolo(fascicolo)
    readiness = deposito_ministerial_readiness(
        fascicolo=fascicolo,
        get_clienti=lambda: _clienti(_cliente()),
        get_config_studio=_config_studio,
        operatore="Giuseppe Montagnese",
    )

    assert contribution["resolved"] is True
    assert contribution["mode"] == "esente"
    assert readiness["contributoUnificato"]["label"] == "Esente"
    assert readiness["anagraficaProcedimento"]["ready"] is True
    assert readiness["valoreCausa"]["ready"] is True
    assert readiness["valoreCausa"]["valueLabel"] == "€ 500,00"


def test_readiness_deposito_pagato_senza_importo_indica_il_dato_mancante():
    fascicolo = _fascicolo()
    fascicolo.valore_causa = 500.0
    fascicolo.pagamenti = {
        "contributo_unificato": {
            "status": "pagato",
            "natura": "pagamento_contributo_unificato",
            "importo": None,
        }
    }

    readiness = deposito_ministerial_readiness(
        fascicolo=fascicolo,
        get_clienti=lambda: _clienti(_cliente()),
        get_config_studio=_config_studio,
        operatore="Giuseppe Montagnese",
    )

    contribution = readiness["contributoUnificato"]
    assert contribution["ready"] is False
    assert contribution["mode"] == "pagato"
    assert contribution["amount"] is None
    assert contribution["message"] == "Inserisci l'importo del contributo unificato pagato per proseguire."


def test_split_nome_cognome_preserva_ordine_e_cognome_composto():
    assert _split_nome_cognome("Avv. Giuseppe Rossi") == ("Giuseppe", "Rossi")
    assert _split_nome_cognome("Giuseppe De Luca") == ("Giuseppe", "De Luca")
    assert _split_nome_cognome("Rossi, Giuseppe") == ("Giuseppe", "Rossi")
