"""Riconciliazione bancaria: parser CSV robusto, abbinamenti mai automatici.

Fail-closed: righe malformate scartate con avviso, ambigui non abbinati,
un movimento per una sola riga, conferma sempre manuale (marca_riconciliato).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct.prima_nota import GestionePrimaNota
from pct.riconciliazione_bancaria import (
    parse_estratto_csv,
    proponi_abbinamenti,
)


# --- Parser CSV ------------------------------------------------------------------


def test_csv_italiano_con_importo_unico():
    testo = "Data contabile;Descrizione;Importo\n01/08/2026;Bonifico Rossi Mario saldo parcella;1.220,50\n03/08/2026;pagoPA contributo unificato;-237,00\n"
    righe, avvisi = parse_estratto_csv(testo)
    assert avvisi == []
    assert len(righe) == 2
    assert righe[0].data == "2026-08-01"
    assert righe[0].importo == 1220.50
    assert righe[0].verso == "INCASSO"
    assert righe[1].importo == -237.00
    assert righe[1].verso == "PAGAMENTO"


def test_csv_con_colonne_dare_avere_e_virgole():
    testo = "Data,Causale,Addebiti,Accrediti\n2026-08-05,Canone software,49.00,\n2026-08-06,Incasso cliente,,\"1,000.00\"\n"
    righe, _avvisi = parse_estratto_csv(testo)
    assert len(righe) == 2
    assert righe[0].importo == -49.00
    assert righe[1].importo == 1000.00


def test_righe_malformate_scartate_con_avviso():
    testo = "Data;Importo;Descrizione\nnon-data;100,00;ok\n01/08/2026;;senza importo\n01/08/2026;50,00;valida\n"
    righe, avvisi = parse_estratto_csv(testo)
    assert len(righe) == 1
    assert righe[0].importo == 50.0
    assert len(avvisi) == 2


def test_transazioni_identiche_legittime_conservate_con_id_distinti():
    # Due marche da bollo uguali nello stesso giorno sono reali: niente scarto,
    # id distinti ma stabili tra import ripetuti (fix da review multi-agente).
    testo = "Data;Importo;Descrizione\n01/08/2026;-16,00;MARCA DA BOLLO\n01/08/2026;-16,00;MARCA DA BOLLO\n"
    prima, avvisi = parse_estratto_csv(testo)
    seconda, _ = parse_estratto_csv(testo)
    assert len(prima) == 2
    assert avvisi == []
    assert prima[0].id != prima[1].id
    assert [r.id for r in prima] == [r.id for r in seconda]


def test_importo_migliaia_italiano_senza_decimali():
    # '1.220' e' milleduecentoventi, non 1,22 (fix da review multi-agente).
    testo = "Data;Importo;Descrizione\n01/08/2026;1.220;Bonifico\n"
    righe, _ = parse_estratto_csv(testo)
    assert righe[0].importo == 1220.00


def test_importo_virgola_migliaia_ambiguo_scartato():
    testo = "Data;Importo;Descrizione\n01/08/2026;1,000;Ambiguo anglosassone\n"
    righe, avvisi = parse_estratto_csv(testo)
    assert righe == []
    assert any("ambiguo" in a for a in avvisi)


def test_segno_meno_in_coda_riconosciuto():
    # '234,56-' e' un addebito, non un incasso (fix da review multi-agente).
    testo = "Data;Importo;Descrizione\n01/08/2026;234,56-;Addebito notazione coda\n"
    righe, _ = parse_estratto_csv(testo)
    assert righe[0].importo == -234.56
    assert righe[0].verso == "PAGAMENTO"


def test_rettifica_negativa_in_avere_scartata_con_avviso():
    testo = "Data;Descrizione;Addebiti;Accrediti\n05/08/2026;Storno bonifico;;-100,00\n"
    righe, avvisi = parse_estratto_csv(testo)
    assert righe == []
    assert any("rettifica" in a.casefold() or "storno" in a.casefold() for a in avvisi)


def test_colonna_movimento_non_e_importo():
    righe, avvisi = parse_estratto_csv("Data;Movimento;Descrizione\n01/08/2026;12345;Operazione\n")
    assert righe == []
    assert "Intestazioni non riconosciute" in avvisi[0]


def test_intestazioni_sconosciute_errore_chiaro():
    righe, avvisi = parse_estratto_csv("Colonna1;Colonna2\nA;B\n")
    assert righe == []
    assert "Intestazioni non riconosciute" in avvisi[0]


def test_hash_riga_stabile_tra_import():
    testo = "Data;Importo;Descrizione\n01/08/2026;50,00;Bonifico\n"
    prima, _ = parse_estratto_csv(testo)
    seconda, _ = parse_estratto_csv(testo)
    assert prima[0].id == seconda[0].id  # idempotenza tra import ripetuti


# --- Motore di abbinamento --------------------------------------------------------


def _movimento(mid="M1", tipo="INCASSO", importo=1220.50, data="2026-08-01", riconciliato=""):
    return SimpleNamespace(id=mid, tipo=tipo, importo=importo, data=data, riconciliato_il=riconciliato)


def _riga_incasso():
    righe, _ = parse_estratto_csv("Data;Importo;Descrizione\n02/08/2026;1.220,50;Bonifico Rossi\n")
    return righe[0]


def test_match_unico_entro_tolleranza():
    proposte = proponi_abbinamenti([_riga_incasso()], [_movimento()])
    assert proposte[0].tipo == "abbinamento"
    assert proposte[0].movimento_id == "M1"


def test_verso_e_importo_devono_coincidere():
    fuori_verso = _movimento(tipo="PAGAMENTO")
    fuori_importo = _movimento(mid="M2", importo=999.0)
    proposte = proponi_abbinamenti([_riga_incasso()], [fuori_verso, fuori_importo])
    assert proposte[0].tipo == "nuovo_movimento"


def test_fuori_tolleranza_non_abbina():
    lontano = _movimento(data="2026-08-20")
    proposte = proponi_abbinamenti([_riga_incasso()], [lontano], tolleranza_giorni=3)
    assert proposte[0].tipo == "nuovo_movimento"


def test_candidati_multipli_diventano_ambiguo():
    proposte = proponi_abbinamenti(
        [_riga_incasso()],
        [_movimento(), _movimento(mid="M2", data="2026-08-03")],
    )
    assert proposte[0].tipo == "ambiguo"
    assert set(proposte[0].candidati) == {"M1", "M2"}


def test_un_movimento_abbinabile_a_una_sola_riga_e_vince_il_delta_minimo():
    # Il movimento del 02/08 deve abbinarsi alla riga del 02/08 (delta 0),
    # non alla prima che capita nel file (fix da review multi-agente).
    righe, _ = parse_estratto_csv(
        "Data;Importo;Descrizione\n01/08/2026;50,00;Prima\n02/08/2026;50,00;Seconda\n"
    )
    proposte = proponi_abbinamenti(righe, [_movimento(importo=50.0, data="2026-08-02")])
    per_data = {p.riga.data: p for p in proposte}
    assert per_data["2026-08-02"].tipo == "abbinamento"
    assert per_data["2026-08-01"].tipo == "nuovo_movimento"


def test_movimenti_cassa_e_storni_esclusi_dal_matching():
    in_cassa = SimpleNamespace(id="MC", tipo="INCASSO", importo=1220.50, data="2026-08-02", riconciliato_il="", metodo="cassa", note="", storno_di="")
    storno = SimpleNamespace(id="MS", tipo="INCASSO", importo=1220.50, data="2026-08-02", riconciliato_il="", metodo="banca", note="Storno di X: errore", storno_di="X")
    proposte = proponi_abbinamenti([_riga_incasso()], [in_cassa, storno])
    assert proposte[0].tipo == "nuovo_movimento"


def test_movimenti_gia_riconciliati_esclusi():
    proposte = proponi_abbinamenti([_riga_incasso()], [_movimento(riconciliato="2026-08-10T10:00:00")])
    assert proposte[0].tipo == "nuovo_movimento"


# --- Conferma sul registro --------------------------------------------------------


def test_marca_riconciliato_e_una_sola_volta(tmp_path):
    registro = GestionePrimaNota(db_path=str(tmp_path / "pn.json"))
    movimento = registro.registra(data="2026-08-01", tipo="INCASSO", importo=1220.5, categoria="onorari")
    esito = registro.marca_riconciliato(movimento.id, riga_estratto_id="abc123")
    assert esito.riconciliato_il
    assert esito.riga_estratto_id == "abc123"
    assert registro.non_riconciliati() == []
    with pytest.raises(ValueError, match="gia' riconciliato"):
        registro.marca_riconciliato(movimento.id, riga_estratto_id="altro")
    riletto = GestionePrimaNota(db_path=str(tmp_path / "pn.json"))
    assert riletto.non_riconciliati() == []  # persistito


def test_conferma_valida_importo_e_verso_server_side(tmp_path):
    # Il client non e' fidato: importo/verso incoerenti → rifiuto (fix review).
    registro = GestionePrimaNota(db_path=str(tmp_path / "pn.json"))
    movimento = registro.registra(data="2026-08-01", tipo="INCASSO", importo=100.0, categoria="onorari")
    with pytest.raises(ValueError, match="importo"):
        registro.marca_riconciliato(movimento.id, riga_estratto_id="r1", importo_riga=999.0)
    with pytest.raises(ValueError, match="verso"):
        registro.marca_riconciliato(movimento.id, riga_estratto_id="r1", verso_riga="PAGAMENTO")
    esito = registro.marca_riconciliato(movimento.id, riga_estratto_id="r1", importo_riga=100.0, verso_riga="INCASSO")
    assert esito.riconciliato_il


def test_stessa_riga_non_riconcilia_due_movimenti(tmp_path):
    registro = GestionePrimaNota(db_path=str(tmp_path / "pn.json"))
    primo = registro.registra(data="2026-08-01", tipo="INCASSO", importo=100.0, categoria="onorari")
    secondo = registro.registra(data="2026-08-01", tipo="INCASSO", importo=100.0, categoria="onorari")
    registro.marca_riconciliato(primo.id, riga_estratto_id="r1")
    with pytest.raises(ValueError, match="altro movimento"):
        registro.marca_riconciliato(secondo.id, riga_estratto_id="r1")


def test_storni_e_stornati_non_riconciliabili_e_fuori_conteggio(tmp_path):
    registro = GestionePrimaNota(db_path=str(tmp_path / "pn.json"))
    movimento = registro.registra(data="2026-08-01", tipo="INCASSO", importo=100.0, categoria="onorari")
    storno = registro.storna(movimento.id, motivo="Errore")
    assert storno.storno_di == movimento.id  # campo strutturato (fix review)
    with pytest.raises(ValueError, match="storn"):
        registro.marca_riconciliato(storno.id, riga_estratto_id="r1")
    with pytest.raises(ValueError, match="storn"):
        registro.marca_riconciliato(movimento.id, riga_estratto_id="r1")
    assert registro.non_riconciliati() == []  # niente rumore da storni/stornati


def test_contanti_fuori_dal_conteggio_non_riconciliati(tmp_path):
    registro = GestionePrimaNota(db_path=str(tmp_path / "pn.json"))
    registro.registra(data="2026-08-01", tipo="INCASSO", importo=50.0, categoria="onorari", metodo="cassa")
    banca = registro.registra(data="2026-08-01", tipo="INCASSO", importo=70.0, categoria="onorari", metodo="banca")
    assert [m.id for m in registro.non_riconciliati()] == [banca.id]


def test_storno_di_movimento_riconciliato_segnala_in_nota(tmp_path):
    registro = GestionePrimaNota(db_path=str(tmp_path / "pn.json"))
    movimento = registro.registra(data="2026-08-01", tipo="INCASSO", importo=100.0, categoria="onorari")
    registro.marca_riconciliato(movimento.id, riga_estratto_id="r9")
    storno = registro.storna(movimento.id, motivo="Importo errato")
    assert "riconciliato" in storno.note
    assert "r9" in storno.note


def test_export_csv_neutralizza_formule(tmp_path):
    registro = GestionePrimaNota(db_path=str(tmp_path / "pn.json"))
    registro.registra(
        data="2026-08-01", tipo="INCASSO", importo=10.0, categoria="onorari",
        controparte="=HYPERLINK(\"http://evil\")", causale="@SUM(A1)",
    )
    csv_text = registro.esporta_csv()
    assert "'=HYPERLINK" in csv_text
    assert "'@SUM" in csv_text
