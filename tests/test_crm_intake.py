"""CRM intake lead: pipeline, verifica conflitti art. 24 CDF, conversione.

Fail-closed: niente incarico (VINTO) ne' conversione in cliente senza la
verifica conflitti; match su CF = certo, match solo su nome = da valutare;
lead perso richiede il motivo.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct.crm_intake import (
    GestioneCrmIntake,
    STATI_LEAD,
    verifica_conflitto_interessi,
)


class _Repo:
    def __init__(self, rows):
        self._rows = rows

    def tutti(self, stato=None):
        return list(self._rows)


def _cliente(nome="Rossi Mario", cf="RSSMRA80A01F205X"):
    return SimpleNamespace(id="C1", denominazione=nome, nome="", cognome="", codice_fiscale=cf, partita_iva="")


def _controparte(nome="Alfa S.r.l.", piva="01234567890", tipo="CONTROPARTE"):
    return SimpleNamespace(
        id="S1", ragione_sociale=nome, nome="", cognome="",
        codice_fiscale="", partita_iva=piva, tipo=tipo,
    )


# --- Verifica conflitti -----------------------------------------------------------


def test_controparte_con_piva_uguale_e_potenziale_conflitto():
    esito = verifica_conflitto_interessi(
        denominazione="Alfa S.r.l.",
        partita_iva="01234567890",
        get_soggetti=lambda: _Repo([_controparte()]),
    )
    assert esito["livello"] == "potenziale_conflitto"
    assert esito["riscontri"][0]["tipo"] == "controparte"
    assert esito["riscontri"][0]["certo"] is True
    assert "art" in esito["fonte"].lower() or "CDF" in esito["fonte"]


def test_omonimia_senza_codici_e_da_valutare():
    esito = verifica_conflitto_interessi(
        denominazione="alfa s.r.l.",  # case-insensitive
        get_soggetti=lambda: _Repo([_controparte()]),
    )
    assert esito["livello"] == "da_valutare"
    assert esito["riscontri"][0]["certo"] is False


def test_cliente_esistente_segnalato_ma_non_conflitto_certo():
    esito = verifica_conflitto_interessi(
        denominazione="Rossi Mario",
        codice_fiscale="RSSMRA80A01F205X",
        get_clienti=lambda: _Repo([_cliente()]),
    )
    assert esito["livello"] == "da_valutare"
    assert esito["riscontri"][0]["tipo"] == "cliente_esistente"
    assert esito["riscontri"][0]["certo"] is True


def test_nessun_riscontro():
    esito = verifica_conflitto_interessi(
        denominazione="Verdi Anna",
        get_clienti=lambda: _Repo([_cliente()]),
        get_soggetti=lambda: _Repo([_controparte()]),
    )
    assert esito["livello"] == "nessuno"
    assert esito["riscontri"] == []


# --- Pipeline ---------------------------------------------------------------------


@pytest.fixture
def crm(tmp_path):
    return GestioneCrmIntake(db_path=str(tmp_path / "leads.json"))


def test_pipeline_completa(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca", fonte="sito_studio", materia="lavoro")
    assert lead.stato == "NUOVO"
    crm.cambia_stato(lead.id, "CONTATTATO")
    crm.cambia_stato(lead.id, "APPUNTAMENTO")
    crm.cambia_stato(lead.id, "PREVENTIVO")
    colonne = crm.pipeline()
    assert [l.id for l in colonne["PREVENTIVO"]] == [lead.id]
    assert set(colonne) >= set(STATI_LEAD)


def test_vinto_richiede_verifica_conflitti(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca")
    with pytest.raises(ValueError, match="art. 24"):
        crm.cambia_stato(lead.id, "VINTO")
    crm.verifica_conflitti(lead.id)
    assert crm.cambia_stato(lead.id, "VINTO").stato == "VINTO"


def test_perso_richiede_motivo(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca")
    with pytest.raises(ValueError, match="motivo"):
        crm.cambia_stato(lead.id, "PERSO")
    esito = crm.cambia_stato(lead.id, "PERSO", motivo_perso="Ha scelto altro studio")
    assert esito.motivo_perso == "Ha scelto altro studio"


def test_conversione_solo_dopo_verifica_e_idempotente(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca", email="l.bianchi@example.com")
    creati = []

    def crea_cliente(dati):
        creati.append(dati)
        return {"id": "CL-9"}

    with pytest.raises(ValueError, match="verifica conflitti"):
        crm.converti_in_cliente(lead.id, crea_cliente=crea_cliente)
    crm.verifica_conflitti(lead.id)
    esito = crm.converti_in_cliente(lead.id, crea_cliente=crea_cliente)
    assert esito.cliente_id == "CL-9"
    assert esito.stato == "VINTO"
    # seconda conversione: nessun duplicato
    di_nuovo = crm.converti_in_cliente(lead.id, crea_cliente=crea_cliente)
    assert di_nuovo.cliente_id == "CL-9"
    assert len(creati) == 1
    assert "intake CRM" in creati[0]["note"]


def test_verifica_conflitti_salvata_sul_lead(crm):
    lead = crm.nuovo(denominazione="Alfa S.r.l.", partita_iva="01234567890")
    esito = crm.verifica_conflitti(lead.id, get_soggetti=lambda: _Repo([_controparte()]))
    riletto = crm.get(lead.id)
    assert riletto.conflitto_verificato is True
    assert riletto.conflitto_esito["livello"] == esito["livello"] == "potenziale_conflitto"


def test_statistiche_e_tasso_conversione(crm):
    a = crm.nuovo(denominazione="A", fonte="passaparola")
    b = crm.nuovo(denominazione="B", fonte="sito_studio")
    crm.nuovo(denominazione="C", fonte="sito_studio")
    crm.verifica_conflitti(a.id)
    crm.cambia_stato(a.id, "VINTO")
    crm.cambia_stato(b.id, "PERSO", motivo_perso="tariffa")
    stats = crm.statistiche()
    assert stats["totale"] == 3
    assert stats["per_fonte"]["sito_studio"] == 2
    assert stats["tasso_conversione"] == 0.5


def test_persistenza_round_trip(tmp_path):
    percorso = str(tmp_path / "leads.json")
    primo = GestioneCrmIntake(db_path=percorso)
    lead = primo.nuovo(denominazione="Bianchi Luca", materia="famiglia")
    secondo = GestioneCrmIntake(db_path=percorso)
    assert secondo.get(lead.id).materia == "famiglia"
