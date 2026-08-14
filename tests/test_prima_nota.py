"""Prima nota di studio: registro cronologico, storni, riconciliazione, export.

Perimetro fail-closed: registra ed esporta, non calcola imposte; i movimenti
non si cancellano ma si stornano; le anticipazioni ex art. 15 D.P.R. 633/72
hanno categorie dedicate distinte dagli onorari.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct.prima_nota import CATEGORIE, GestionePrimaNota


@pytest.fixture
def registro(tmp_path):
    return GestionePrimaNota(db_path=str(tmp_path / "prima_nota.json"))


# --- Scritture -------------------------------------------------------------------


def test_registra_incasso_e_pagamento(registro):
    incasso = registro.registra(data="2026-08-01", tipo="INCASSO", importo=1220.0, categoria="onorari", controparte="Rossi Mario", causale="Acconto onorari")
    pagamento = registro.registra(data="2026-08-03", tipo="PAGAMENTO", importo=237.0, categoria="anticipazioni_clienti", controparte="pagoPA Giustizia", causale="CU RG 1234/2026")
    assert incasso.importo == 1220.0
    saldi = registro.saldi()
    assert saldi["incassi"] == 1220.0
    assert saldi["pagamenti"] == 237.0
    assert saldi["saldo"] == 983.0
    assert saldi["per_categoria"]["anticipazioni_clienti"] == 237.0
    assert pagamento.metodo == "banca"


def test_importi_non_positivi_rifiutati(registro):
    with pytest.raises(ValueError, match="storno"):
        registro.registra(tipo="INCASSO", importo=-10, categoria="onorari")
    with pytest.raises(ValueError, match="Importo"):
        registro.registra(tipo="INCASSO", importo="dieci", categoria="onorari")


def test_categoria_coerente_col_tipo(registro):
    with pytest.raises(ValueError, match="Categoria"):
        registro.registra(tipo="INCASSO", importo=10, categoria="spese_studio")
    assert "anticipazioni_rimborsate" in CATEGORIE["INCASSO"]
    assert "anticipazioni_clienti" in CATEGORIE["PAGAMENTO"]


def test_data_non_iso_rifiutata(registro):
    with pytest.raises(ValueError, match="Data"):
        registro.registra(data="01/08/2026", tipo="INCASSO", importo=10, categoria="onorari")


# --- Storno ----------------------------------------------------------------------


def test_storno_crea_movimento_contrario_e_non_cancella(registro):
    incasso = registro.registra(data="2026-08-01", tipo="INCASSO", importo=500.0, categoria="onorari")
    storno = registro.storna(incasso.id, motivo="Errore di digitazione", attore="avv.rossi")
    assert storno.tipo == "PAGAMENTO"
    assert storno.importo == 500.0
    assert incasso.id in storno.note
    assert registro.saldi()["saldo"] == 0.0
    assert len(registro.registro()) == 2  # nulla cancellato
    with pytest.raises(ValueError, match="gia' stornato"):
        registro.storna(incasso.id, motivo="doppio storno")


def test_storno_richiede_motivo(registro):
    incasso = registro.registra(tipo="INCASSO", importo=100, categoria="onorari")
    with pytest.raises(ValueError, match="motivo"):
        registro.storna(incasso.id, motivo=" ")


# --- Riconciliazione parcelle ----------------------------------------------------


class _FakeFatturazione:
    def __init__(self, parcelle):
        self._parcelle = parcelle

    def tutte(self):
        return list(self._parcelle)


def _parcella(pid="P1", stato="PAGATA", totale=1220.0, numero="12/2026"):
    return SimpleNamespace(
        id=pid, stato=stato, totale=totale, numero=numero,
        data_pagamento="2026-08-05", intestatario="Rossi Mario",
        id_fascicolo="F1", id_cliente="C1",
    )


def test_incassi_da_parcelle_pagate_idempotente(registro):
    fatturazione = _FakeFatturazione([_parcella(), _parcella(pid="P2", stato="EMESSA")])
    primi = registro.incassi_da_parcelle(fatturazione)
    secondi = registro.incassi_da_parcelle(fatturazione)
    assert len(primi) == 1  # solo la pagata
    assert secondi == []  # idempotente per parcella_id
    movimento = primi[0]
    assert movimento.parcella_id == "P1"
    assert movimento.data == "2026-08-05"
    assert movimento.categoria == "onorari"
    assert "12/2026" in movimento.causale


# --- Registro ed export ----------------------------------------------------------


def test_registro_cronologico_e_filtri(registro):
    registro.registra(data="2026-08-10", tipo="INCASSO", importo=100, categoria="onorari")
    registro.registra(data="2026-08-01", tipo="PAGAMENTO", importo=50, categoria="spese_studio")
    rows = registro.registro()
    assert [m.data for m in rows] == ["2026-08-01", "2026-08-10"]  # ordine cronologico
    assert len(registro.registro(dal="2026-08-05")) == 1
    assert len(registro.registro(tipo="PAGAMENTO")) == 1


def test_export_csv_per_commercialista(registro):
    registro.registra(data="2026-08-01", tipo="INCASSO", importo=1220.5, categoria="onorari", controparte="Rossi Mario", causale="Saldo parcella", documento_riferimento="12/2026")
    csv_text = registro.esporta_csv()
    righe = csv_text.strip().splitlines()
    assert righe[0].startswith("Data;Tipo;Importo")
    assert "1220,50" in righe[1]  # decimali all'italiana
    assert "Rossi Mario" in righe[1]


def test_persistenza_round_trip(tmp_path):
    percorso = str(tmp_path / "prima_nota.json")
    primo = GestionePrimaNota(db_path=percorso)
    primo.registra(tipo="INCASSO", importo=10, categoria="onorari")
    secondo = GestionePrimaNota(db_path=percorso)
    assert len(secondo.registro()) == 1
