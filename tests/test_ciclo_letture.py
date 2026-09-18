"""Il ciclo della lettura: due motori, l'archivio conferma, tutto si ferma.

Il funzionamento voluto: i due motori leggono tutti i fascicoli, l'archivio
registra e conferma, il ciclo si ferma. Si riattiva solo su un documento nuovo,
un documento cambiato o una PEC nuova. Il ciclo non deve spezzarsi mai: un
fascicolo che fallisce resta dichiarato in errore e si riprova, non esce dal
ciclo in silenzio.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pct.archivio_letture.ciclo import (
    DA_LEGGERE,
    FERMO,
    IN_ERRORE,
    RICONCILIAZIONE_ORE,
    stato_ciclo,
)

VERSIONE = "motore.v2"
ORA = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def _riga(**campi):
    base = {"stato": "completa", "versione_lettore": VERSIONE, "impronta": "abc", "aggiornato_il": "2026-09-15T11:00:00Z"}
    return {**base, **campi}


def test_un_fascicolo_mai_letto_e_da_leggere():
    stato = stato_ciclo(None, versione_attesa=VERSIONE, oggi=ORA)
    assert stato.stato == DA_LEGGERE
    assert stato.da_leggere is True
    assert "mai stato letto" in stato.motivo


def test_a_lettura_confermata_il_ciclo_si_ferma():
    stato = stato_ciclo(_riga(), versione_attesa=VERSIONE, impronta_attesa="abc", oggi=ORA)
    assert stato.stato == FERMO
    assert stato.da_leggere is False
    assert "confermato" in stato.motivo
    assert "è fermo" in stato.etichetta


def test_un_documento_nuovo_riattiva_il_ciclo():
    stato = stato_ciclo(_riga(), versione_attesa=VERSIONE, impronta_attesa="impronta-diversa", oggi=ORA)
    assert stato.stato == DA_LEGGERE
    assert "documenti o PEC nuovi" in stato.motivo


def test_regole_nuove_non_compatibili_di_un_motore_rimettono_tutto_da_leggere():
    stato = stato_ciclo(_riga(versione_lettore="motore.v1"), versione_attesa=VERSIONE, impronta_attesa="abc", oggi=ORA)
    assert stato.stato == DA_LEGGERE
    assert "regole del motore sono cambiate" in stato.motivo


def test_regole_compatibili_non_riaprono_un_fascicolo_invariato():
    stato = stato_ciclo(
        _riga(versione_lettore="motore.v1"),
        versione_attesa=VERSIONE,
        impronta_attesa="abc",
        oggi=ORA,
        versione_compatibile=lambda versione: versione == "motore.v1",
    )
    assert stato.stato == FERMO


def test_una_lettura_parziale_non_chiude_il_ciclo():
    stato = stato_ciclo(_riga(stato="parziale"), versione_attesa=VERSIONE, impronta_attesa="abc", oggi=ORA)
    assert stato.stato == DA_LEGGERE
    assert "parziale" in stato.motivo


def test_un_giro_fallito_resta_in_errore_e_si_riprova():
    stato = stato_ciclo(_riga(stato="errore", esito={"motivo": "il registro non si apre"}), versione_attesa=VERSIONE, impronta_attesa="abc", oggi=ORA)
    assert stato.stato == IN_ERRORE
    assert stato.da_leggere is True
    assert stato.motivo == "il registro non si apre"
    assert "si riprova" in stato.etichetta


def test_il_ricontrollo_periodico_non_riapre_un_inventario_invariato():
    """Il server non deve rileggere fascicoli fermi solo perché passa il tempo."""
    vecchia = (ORA - timedelta(hours=RICONCILIAZIONE_ORE + 1)).isoformat().replace("+00:00", "Z")
    stato = stato_ciclo(_riga(aggiornato_il=vecchia), versione_attesa=VERSIONE, impronta_attesa="abc", oggi=ORA)
    assert stato.stato == FERMO


def test_dentro_la_finestra_il_ciclo_resta_fermo():
    recente = (ORA - timedelta(hours=RICONCILIAZIONE_ORE - 1)).isoformat().replace("+00:00", "Z")
    assert stato_ciclo(_riga(aggiornato_il=recente), versione_attesa=VERSIONE, impronta_attesa="abc", oggi=ORA).stato == FERMO


def test_una_data_illeggibile_non_blocca_il_ciclo():
    stato = stato_ciclo(_riga(aggiornato_il="non una data"), versione_attesa=VERSIONE, impronta_attesa="abc", oggi=ORA)
    assert stato.stato == FERMO


@pytest.mark.parametrize("stato_registrato", ["completa", "parziale", "errore"])
def test_lo_stato_ha_sempre_un_etichetta_in_italiano(stato_registrato):
    stato = stato_ciclo(_riga(stato=stato_registrato), versione_attesa=VERSIONE, impronta_attesa="abc", oggi=ORA)
    assert stato.etichetta and stato.etichetta != stato.stato
    assert stato.to_dict()["daLeggere"] is stato.da_leggere
