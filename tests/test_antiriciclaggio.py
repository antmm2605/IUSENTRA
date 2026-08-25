"""Adeguata verifica antiriciclaggio (D.Lgs. 231/2007 + metodologia CNF).

Verifica: ambito art. 3 c.4 lett. c con esclusione difensiva art. 17 c.7,
griglia CNF a punteggi 1-5 con suggerimento del livello, obbligo rafforzata
per PEP/paesi ad alto rischio (artt. 24-25), scostamento motivato, controllo
costante e conservazione decennale art. 31.
"""

from __future__ import annotations

from datetime import date

import pytest

from pct.antiriciclaggio import (
    GestioneAntiriciclaggio,
    LivelloVerifica,
    MacroArea,
    PRESTAZIONE_DIFENSIVA,
    PRESTAZIONI_IN_AMBITO,
    StatoVerifica,
    griglia_indici_default,
)

OGGI = date(2026, 8, 13)


@pytest.fixture
def gestione(tmp_path):
    return GestioneAntiriciclaggio(db_path=str(tmp_path / "verifiche.json"))


def _scheda(gestione, *, punteggio=1, **campi):
    base = dict(cliente_id="C1", prestazione="trasferimento_immobili", scopo_natura="Compravendita immobile")
    base.update(campi)
    verifica = gestione.nuova(**base)
    if verifica.indici:
        for indice in verifica.indici:
            indice.punteggio = punteggio
        gestione._salva()
    return verifica


# --- Ambito ----------------------------------------------------------------------


def test_catalogo_prestazioni_art3_completo():
    # Le 5 categorie tipizzate dall'art. 3 c.4 lett. c + operazioni dirette.
    assert len(PRESTAZIONI_IN_AMBITO) == 7
    assert "costituzione_enti" in PRESTAZIONI_IN_AMBITO


def test_attivita_difensiva_fuori_ambito(gestione):
    verifica = gestione.nuova(cliente_id="C1", prestazione=PRESTAZIONE_DIFENSIVA)
    assert verifica.in_ambito is False
    assert verifica.indici == []  # nessuna griglia per il fuori ambito
    with pytest.raises(ValueError, match="17"):
        gestione.completa(verifica.id, livello_scelto="ORDINARIA", operatore="avv.rossi")


# --- Griglia CNF e suggerimento --------------------------------------------------


def test_griglia_default_copre_le_tre_macroaree():
    aree = {indice.macro_area for indice in griglia_indici_default()}
    assert aree == {a.value for a in MacroArea}


def test_basso_rischio_suggerisce_semplificata(gestione):
    verifica = _scheda(gestione, punteggio=1)
    assert verifica.livello_suggerito() == LivelloVerifica.SEMPLIFICATA


def test_rischio_medio_suggerisce_ordinaria(gestione):
    verifica = _scheda(gestione, punteggio=3)
    assert verifica.livello_suggerito() == LivelloVerifica.ORDINARIA


def test_rischio_alto_suggerisce_rafforzata(gestione):
    verifica = _scheda(gestione, punteggio=4)
    assert verifica.livello_suggerito() == LivelloVerifica.RAFFORZATA


def test_punteggi_fuori_scala_normalizzati(gestione):
    verifica = _scheda(gestione, punteggio=99)
    assert verifica.punteggio_medio == 5.0  # clampato alla scala CNF 1-5


def test_pep_forza_rafforzata_anche_con_griglia_bassa(gestione):
    verifica = _scheda(gestione, punteggio=1, cliente_pep=True)
    assert verifica.livello_suggerito() == LivelloVerifica.RAFFORZATA


# --- Conferma dell'avvocato ------------------------------------------------------


def test_completa_fissa_livello_scadenza_e_stato(gestione):
    verifica = _scheda(gestione, punteggio=3)
    esito = gestione.completa(
        verifica.id, livello_scelto="ORDINARIA", operatore="avv.rossi", oggi=OGGI
    )
    assert esito.stato == StatoVerifica.COMPLETATA.value
    assert esito.data_verifica == "2026-08-13"
    assert esito.scadenza_controllo > "2028-08-01"  # ordinaria: rinnovo a ~24 mesi
    assert esito.conservazione_fino_al == "2036-08-13"  # art. 31: 10 anni


def test_scostamento_verso_il_basso_richiede_motivazione(gestione):
    verifica = _scheda(gestione, punteggio=4)  # suggerita rafforzata
    with pytest.raises(ValueError, match="motivazione"):
        gestione.completa(verifica.id, livello_scelto="ORDINARIA", operatore="avv.rossi", oggi=OGGI)
    esito = gestione.completa(
        verifica.id,
        livello_scelto="ORDINARIA",
        operatore="avv.rossi",
        motivazione_scostamento="Cliente storico con operazione gia' verificata in precedenza.",
        oggi=OGGI,
    )
    assert esito.livello_scelto == "ORDINARIA"


def test_pep_non_derogabile_nemmeno_con_motivazione(gestione):
    verifica = _scheda(gestione, punteggio=1, cliente_pep=True)
    with pytest.raises(ValueError, match="24-25"):
        gestione.completa(
            verifica.id,
            livello_scelto="ORDINARIA",
            operatore="avv.rossi",
            motivazione_scostamento="qualsiasi motivazione",
            oggi=OGGI,
        )


# --- Controllo costante e persistenza --------------------------------------------


def test_controllo_costante_scaduto_va_in_rinnovo(gestione):
    verifica = _scheda(gestione, punteggio=4, cliente_pep=True)
    gestione.completa(verifica.id, livello_scelto="RAFFORZATA", operatore="avv.rossi", oggi=date(2025, 1, 10))
    # rafforzata: rinnovo a ~12 mesi → al 13/08/2026 e' scaduta
    scadute = gestione.da_rinnovare(oggi=OGGI)
    assert [v.id for v in scadute] == [verifica.id]
    assert gestione.get(verifica.id).stato == StatoVerifica.DA_RINNOVARE.value


def test_persistenza_round_trip(tmp_path):
    percorso = str(tmp_path / "verifiche.json")
    prima = GestioneAntiriciclaggio(db_path=percorso)
    verifica = prima.nuova(
        cliente_id="C9",
        prestazione="gestione_denaro",
        titolare_effettivo={"nome": "Verdi Anna", "criterio": "proprieta_diretta_25"},
    )
    dopo = GestioneAntiriciclaggio(db_path=percorso)
    riletta = dopo.get(verifica.id)
    assert riletta is not None
    assert riletta.titolare_effettivo.nome == "Verdi Anna"
    assert riletta.in_ambito is True
    assert len(riletta.indici) == len(griglia_indici_default())


def test_sql_e_fonte_operativa_e_il_json_e_solo_mirror(tmp_path):
    percorso = tmp_path / "antiriciclaggio" / "verifiche.json"
    gestione = GestioneAntiriciclaggio(db_path=str(percorso), tenant_id="tenant-qa")
    verifica = gestione.nuova(cliente_id="C10", lead_id="L10", prestazione="gestione_denaro")

    assert gestione.source_of_truth == "sqlite"
    assert gestione.per_lead("L10")[0].id == verifica.id
    assert percorso.exists()
    stored = gestione.studio_db.conn.execute(
        "SELECT cliente_id, lead_id, stato FROM aml_verifications WHERE id = ?", (verifica.id,)
    ).fetchone()
    assert stored["cliente_id"] == "C10"
    assert stored["lead_id"] == "L10"
    assert stored["stato"] == StatoVerifica.BOZZA.value


def test_screening_richiede_prova_per_esito_non_disponibile(gestione):
    verifica = gestione.nuova(cliente_id="C11", prestazione="gestione_denaro")
    with pytest.raises(ValueError, match="hash dello snapshot"):
        gestione.registra_evidenza_screening(
            verifica.id,
            provider_key="eu-consolidated-list",
            source_url="https://finance.ec.europa.eu/",
            outcome="NESSUN_RISCONTRO",
        )


def test_screening_e_audit_sono_persistiti(gestione):
    verifica = gestione.nuova(cliente_id="C12", prestazione="gestione_denaro")
    evidence = gestione.registra_evidenza_screening(
        verifica.id,
        provider_key="eu-consolidated-list",
        source_url="https://finance.ec.europa.eu/",
        source_version="2026-01-09",
        snapshot_hash="sha256:qa",
        subject_label="Cliente QA",
        outcome="NON_DISPONIBILE",
        checked_by="avv.rossi",
        note="Fonte non disponibile: nessun esito conclusivo registrato.",
    )

    assert evidence["outcome"] == "NON_DISPONIBILE"
    assert gestione.evidenze_screening(verifica.id)[0]["source_version"] == "2026-01-09"
    assert any(item["event_type"] == "AML_SCREENING_RECORDED" for item in gestione.audit(verifica.id))
