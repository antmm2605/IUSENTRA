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


@pytest.mark.parametrize('raw', [b'{"interrotto":', b'[]', b'{"movimento":null}', b'\xff'])
def test_archivio_illeggibile_non_diventa_registro_vuoto(tmp_path, raw):
    path = tmp_path / "prima_nota.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="preservato"):
        GestionePrimaNota(str(path))
    assert path.read_bytes() == raw


@pytest.mark.parametrize('amount', [float('nan'), float('inf'), float('-inf')])
def test_importi_non_finiti_non_sono_movimenti(registro, amount):
    with pytest.raises(ValueError, match="positivo"):
        registro.registra(tipo="INCASSO", importo=amount, categoria="onorari")
    assert registro.registro() == []


@pytest.mark.parametrize('amount', [float('nan'), float('inf'), float('-inf'), 'non numerico'])
def test_importi_riga_banca_non_validi_non_confermano(registro, amount):
    movement = registro.registra(tipo='INCASSO', importo=260, categoria='onorari')
    before = registro.db_path.read_bytes()
    with pytest.raises(ValueError, match='rifiutato'):
        registro.marca_riconciliato(movement.id, riga_estratto_id='riga-1', importo_riga=amount)
    assert registro.db_path.read_bytes() == before
    assert not movement.riconciliato_il


def test_parcelle_non_leggibili_non_diventano_registro_allineato(registro):
    def unavailable():
        raise OSError('fonte non leggibile')
    with pytest.raises(ValueError, match='senza confermare'):
        registro.incassi_da_parcelle(SimpleNamespace(tutte=unavailable))
    assert registro.registro() == []


@pytest.mark.parametrize('permission,expected', [(True, 503), (False, 403)])
def test_api_archivio_illeggibile_non_restituisce_saldi(tmp_path, permission, expected):
    from flask import Flask, g
    from web.bootstrap.prima_nota_routes import register_prima_nota_routes

    source = tmp_path / 'prima_nota.json'
    source.write_bytes(b'{"interrotto":')
    app = Flask(__name__)
    audits = []

    @app.before_request
    def actor():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda _key: permission)

    register_prima_nota_routes(app, {
        'get_prima_nota': lambda: GestionePrimaNota(str(source)),
        'get_fatturazione': lambda: None,
        'audit': lambda *args, **kwargs: audits.append((args, kwargs)),
    })
    response = app.test_client().get('/api/v1/ui/prima-nota')
    assert response.status_code == expected
    payload = response.get_json()
    assert payload['ok'] is False
    assert 'summary' not in payload
    assert 'movimenti' not in payload
    assert source.read_bytes() == b'{"interrotto":'
    assert audits == []


@pytest.mark.parametrize('error,status,code', [('conflict', 409, 'conflict'), ('io', 503, 'outcome_not_confirmed')])
@pytest.mark.parametrize('route', ['/prima-nota/registra', '/prima-nota/riconcilia-parcelle', '/prima-nota/M1/storna', '/prima-nota/riconciliazione/conferma', '/prima-nota/riconciliazione/registra-da-riga'])
def test_api_scritture_conflitto_o_guasto_non_confermano(route, error, status, code):
    from flask import Flask, g
    from web.bootstrap.prima_nota_routes import register_prima_nota_routes
    from pct.prima_nota_repository import PrimaNotaConflict
    app = Flask(__name__)
    audits = []
    @app.before_request
    def actor():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda _key: True)
    def unavailable():
        if error == 'conflict':
            raise PrimaNotaConflict('Registro aggiornato da un altro processo.')
        raise OSError('Percorso interno riservato non da mostrare')
    register_prima_nota_routes(app, {
        'get_prima_nota': unavailable, 'get_fatturazione': lambda: None,
        'audit': lambda *args, **kwargs: audits.append(args),
    })
    response = app.test_client().post(route, json={'rigaId': 'R1', 'movimentoId': 'M1', 'importo': 260, 'motivo': 'Prova'})
    assert response.status_code == status
    payload = response.get_json()
    assert payload['ok'] is False and payload['code'] == code
    assert 'Percorso interno' not in payload['message']
    assert audits == []


@pytest.mark.parametrize('audit_fails', [False, True])
def test_api_persistenza_distinta_da_esito_audit(registro, audit_fails):
    from flask import Flask, g
    from web.bootstrap.prima_nota_routes import register_prima_nota_routes
    app = Flask(__name__)
    @app.before_request
    def actor():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda _key: True, username='prova')
    def audit(*args, **kwargs):
        if audit_fails:
            raise OSError('Audit controllato non disponibile')
    register_prima_nota_routes(app, {'get_prima_nota': lambda: registro, 'get_fatturazione': lambda: None, 'audit': audit})
    response = app.test_client().post('/prima-nota/registra', json={
        'data': '2026-10-08', 'tipo': 'INCASSO', 'importo': 1234.56, 'categoria': 'onorari',
    })
    payload = response.get_json()
    assert len(GestionePrimaNota(str(registro.db_path)).registro()) == 1
    if audit_fails:
        assert response.status_code == 503 and payload['code'] == 'outcome_not_confirmed'
        assert 'prima di riprovare' in payload['message']
    else:
        assert response.status_code == 200 and payload['ok'] is True
        assert '€ 1.234,56' in payload['message']


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


@pytest.mark.parametrize('field,value', [('totale', float('nan')), ('totale', -1), ('data_pagamento', ''), ('id', '')])
def test_lotto_parcelle_incoerente_non_registra_la_prima(registro, field, value):
    bad = _parcella(pid='P2', totale=500)
    setattr(bad, field, value)
    with pytest.raises(ValueError, match='importazione sospesa'):
        registro.incassi_da_parcelle(_FakeFatturazione([_parcella(totale=260), bad]))
    assert registro.registro() == []
    assert not registro.db_path.exists()


def test_lotto_parcelle_salva_una_volta_e_non_duplica_la_stessa_fonte(registro, monkeypatch):
    saves = []
    native = registro._salva
    def save():
        saves.append(len(registro.registro()))
        native()
    monkeypatch.setattr(registro, '_salva', save)
    created = registro.incassi_da_parcelle(_FakeFatturazione([
        _parcella(totale=260), _parcella(totale=260), _parcella(pid='P2', totale=500),
    ]))
    assert len(created) == 2 and saves == [2]
    assert registro.saldi()['incassi'] == 760


def test_lotto_stessa_parcella_importi_discordanti_non_viene_unificato(registro):
    with pytest.raises(ValueError, match='dati discordanti'):
        registro.incassi_da_parcelle(_FakeFatturazione([_parcella(totale=260), _parcella(totale=500)]))
    assert registro.registro() == [] and not registro.db_path.exists()


def test_lotto_fallimento_replace_non_lascia_incassi_parziali(registro, monkeypatch):
    import pct.prima_nota
    def fail(*args):
        raise OSError('Scrittura controllata fallita')
    monkeypatch.setattr(pct.prima_nota.os, 'replace', fail)
    with pytest.raises(OSError, match='Scrittura controllata'):
        registro.incassi_da_parcelle(_FakeFatturazione([_parcella(totale=260), _parcella(pid='P2', totale=500)]))
    assert registro.registro() == [] and not registro.db_path.exists()


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
    assert righe[1].startswith("01/08/2026;INCASSO;")
    assert "1220,50" in righe[1]  # decimali all'italiana
    assert "Rossi Mario" in righe[1]


def test_persistenza_round_trip(tmp_path):
    percorso = str(tmp_path / "prima_nota.json")
    primo = GestionePrimaNota(db_path=percorso)
    primo.registra(tipo="INCASSO", importo=10, categoria="onorari")
    secondo = GestionePrimaNota(db_path=percorso)
    assert len(secondo.registro()) == 1
