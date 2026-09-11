"""Controparti aggiuntive dal form fascicolo: validazione, riuso delle schede e collegamento."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from pct.clienti import Recapiti
from pct.soggetti import GestioneSoggetti, RuoloSoggetto, TipoSoggetto
from web.services.fascicolo_controparti_aggiuntive import (
    collega_controparti_aggiuntive,
    leggi_controparti_aggiuntive,
)


@pytest.fixture
def soggetti(tmp_path):
    return GestioneSoggetti(str(tmp_path / "soggetti.json"), str(tmp_path / "parti.json"))


def _json(*items):
    return json.dumps(list(items))


def test_elenco_vuoto_non_crea_nulla(soggetti):
    assert leggi_controparti_aggiuntive("", gestore_soggetti=soggetti) == []
    assert leggi_controparti_aggiuntive(_json({"nome": "", "identificativo": ""}), gestore_soggetti=soggetti) == []


def test_validazione_con_messaggi_per_l_avvocato(soggetti):
    with pytest.raises(ValueError, match="manca il codice fiscale o la partita IVA"):
        leggi_controparti_aggiuntive(_json({"nome": "Comune di Bari"}), gestore_soggetti=soggetti)
    with pytest.raises(ValueError, match="codice fiscale o partita IVA non valido"):
        leggi_controparti_aggiuntive(_json({"nome": "Comune di Bari", "identificativo": "123"}), gestore_soggetti=soggetti)
    with pytest.raises(ValueError, match="PEC non valida"):
        leggi_controparti_aggiuntive(
            _json({"nome": "Comune di Bari", "identificativo": "80015010723", "pec": "non-una-pec"}),
            gestore_soggetti=soggetti,
        )
    with pytest.raises(ValueError, match="non è più disponibile"):
        leggi_controparti_aggiuntive(_json({"id_soggetto": "inesistente"}), gestore_soggetti=soggetti)
    with pytest.raises(ValueError, match="non è leggibile"):
        leggi_controparti_aggiuntive("{", gestore_soggetti=soggetti)


def test_crea_pa_da_registro_e_difensore_da_reginde(soggetti):
    controparti = leggi_controparti_aggiuntive(
        _json(
            {
                "nome": "COMUNE DI BARI",
                "identificativo": "80015010723",
                "tipo": "PUBBLICA_AMMINISTRAZIONE",
                "pec": "protocollo@pec.comune.bari.it",
                "fonte": "registro_ppaa",
            },
            {
                "nome": "ROSSI MARIO",
                "persona_nome": "Mario",
                "persona_cognome": "Rossi",
                "identificativo": "rssmra80a01h501z",
                "tipo": "PROFESSIONISTA",
                "ruolo": "DIFENSORE_CONTROPARTE",
                "pec": "mario.rossi@pec.avvocati.test",
                "fonte": "reginde",
            },
            {"nome": "COMUNE DI BARI", "identificativo": "80015010723", "fonte": "registro_ppaa"},
        ),
        gestore_soggetti=soggetti,
    )

    esito = collega_controparti_aggiuntive(soggetti, [], "fasc-1", controparti)
    parti = {parte.ruolo: soggetto for parte, soggetto in soggetti.parti_fascicolo("fasc-1")}

    assert len(controparti) == 2
    assert esito.collegate == ("COMUNE DI BARI", "Rossi Mario")
    comune = parti[RuoloSoggetto.CONTROPARTE]
    assert comune.tipo == TipoSoggetto.PUBBLICA_AMMINISTRAZIONE
    assert comune.codice_fiscale == "80015010723"
    assert comune.recapiti.pec == "protocollo@pec.comune.bari.it"
    assert "registro_ppaa" in comune.tag
    difensore = parti[RuoloSoggetto.DIFENSORE_CONTROPARTE]
    assert difensore.codice_fiscale == "RSSMRA80A01H501Z"
    assert (difensore.nome, difensore.cognome, difensore.ordine) == ("Mario", "Rossi", "ReGIndE")


def test_riusa_scheda_esistente_e_completa_solo_la_pec_mancante(soggetti):
    esistente = soggetti.crea(
        tipo=TipoSoggetto.PERSONA_GIURIDICA,
        ragione_sociale="Gamma Costruzioni Srl",
        partita_iva="11122233344",
        recapiti=Recapiti(email="info@gamma.test"),
    )
    controparti = leggi_controparti_aggiuntive(
        _json({"nome": "GAMMA COSTRUZIONI SRL", "identificativo": "11122233344", "pec": "gamma@pec.test", "fonte": "inipec"}),
        gestore_soggetti=soggetti,
    )

    collega_controparti_aggiuntive(soggetti, [], "fasc-2", controparti)
    aggiornato = soggetti.get(esistente.id)

    assert len(soggetti.tutti()) == 1
    assert aggiornato.ragione_sociale == "Gamma Costruzioni Srl"
    assert aggiornato.recapiti.email == "info@gamma.test"
    assert aggiornato.recapiti.pec == "gamma@pec.test"
    assert [parte.id_soggetto for parte, _ in soggetti.parti_fascicolo("fasc-2")] == [esistente.id]


def test_non_collega_come_controparte_il_cliente_dello_studio(soggetti):
    cliente = SimpleNamespace(id="cli-1", nome="", cognome="", ragione_sociale="Alfa Spa", codice_fiscale="", partita_iva="12345678901")
    controparti = leggi_controparti_aggiuntive(
        _json({"nome": "Alfa Spa", "identificativo": "12345678901"}),
        gestore_soggetti=soggetti,
    )

    esito = collega_controparti_aggiuntive(soggetti, [cliente], "fasc-3", controparti)

    assert esito.collegate == ()
    assert esito.escluse_cliente == ("Alfa Spa",)
    assert soggetti.tutti() == []
    assert "coincidono con il cliente" in esito.messaggio()
