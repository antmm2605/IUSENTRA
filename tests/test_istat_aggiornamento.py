"""Indici FOI scaricati dal servizio ufficiale ISTAT e aggiornati in automatico.

Il file di prova contiene le righe nazionali reali scaricate il 31/10/2026 da
esploradati.istat.it (flusso IT1,169_748_DF_DCSP_FOI1B2025_1), più una riga con i
tabacchi (00), una provinciale (ITC11) e una variazione congiunturale (6) da scartare.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pct.istat_aggiornamento import aggiorna_foi, confronta, leggi_csv, url_dati
from pct.normative_tables import GestioneTabelleNormative as NormativeTables
from pct.strumenti_legali import GestioneStrumentiLegali

CSV = (Path(__file__).parent / "dati" / "istat" / "foi_2026_05_09.csv").read_text(encoding="utf-8")


def test_legge_solo_indice_e_variazione_nazionali_senza_tabacchi():
    valori = leggi_csv(CSV)
    assert valori[(2026, 7)] == {"index": 103.1, "variation_yoy": 2.8}
    assert valori[(2026, 9)] == {"index": 104.3, "variation_yoy": 4.0}
    assert len(valori) == 5


def test_url_del_servizio_ufficiale():
    assert url_dati(date(2026, 1, 1)).startswith(
        "https://esploradati.istat.it/SDMXWS/rest/data/IT1,169_748_DF_DCSP_FOI1B2025_1,1.0/?startPeriod=2026-01"
    )


def test_valori_fuori_misura_o_rettifiche_non_entrano_in_silenzio():
    esistenti = [{"year": 2026, "month": 6, "index": 102.8, "base": 2025}]
    rettifica = confronta(esistenti, {(2026, 6): {"index": 102.9, "variation_yoy": 2.9}})
    assert not rettifica.nuovi and rettifica.discordanze
    assurdo = confronta(esistenti, {(2026, 7): {"index": 503.1, "variation_yoy": 2.8}})
    assert assurdo.bloccato
    salto = confronta(esistenti, {(2026, 8): {"index": 103.7, "variation_yoy": 3.4}})
    assert salto.bloccato and "07/2026" in salto.bloccato


def test_scarica_aggiorna_e_i_calcolatori_usano_i_mesi_nuovi(tmp_path):
    db = str(tmp_path / "tabelle.json")
    norme = NormativeTables(db)
    gestore = GestioneStrumentiLegali(normative_db_path=db)
    dati = {"loc_canone": "1000", "loc_perc_adeguamento": "75", "loc_anno_base": "2025",
            "loc_mese_base": "8", "loc_anno_fine": "2026", "loc_mese_fine": "8"}
    try:
        gestore.calcola_adeguamento_canone(dati)
        prima = "calcolato"
    except ValueError:
        prima = "manca agosto 2026"
    assert prima == "manca agosto 2026"

    url_chiamati: list[str] = []
    esito = aggiorna_foi(norme, lambda url: url_chiamati.append(url) or CSV, oggi=date(2026, 10, 31))
    assert esito["esito"] == "aggiornata" and esito["nuovi"] == ["07/2026", "08/2026", "09/2026"]
    assert url_chiamati and "esploradati.istat.it" in url_chiamati[0]

    dopo = GestioneStrumentiLegali(normative_db_path=db).calcola_adeguamento_canone(dati)
    assert dopo["variazione_foi"] == 3.4  # variazione annua pubblicata dall'ISTAT per agosto 2026
    assert dopo["canone_aggiornato"] == 1025.5  # 1.000 × (1 + 3,4% × 75%)

    di_nuovo = aggiorna_foi(NormativeTables(db), lambda url: CSV, oggi=date(2026, 10, 31))
    assert di_nuovo["esito"] == "gia_aggiornata"


def test_fonte_non_raggiungibile_non_tocca_la_tabella(tmp_path):
    norme = NormativeTables(str(tmp_path / "tabelle.json"))
    prima = list(norme.rows("istat_foi"))

    def irraggiungibile(url: str) -> str:
        raise OSError("rete")

    assert aggiorna_foi(norme, irraggiungibile, oggi=date(2026, 10, 31))["esito"] == "fonte_non_raggiungibile"
    assert list(norme.rows("istat_foi")) == prima


def test_si_interroga_la_fonte_solo_se_manca_un_mese_gia_pubblicato():
    from pct.istat_aggiornamento import mese_atteso, serve_aggiornare

    assert mese_atteso(date(2026, 10, 31)) == (2026, 9)
    assert mese_atteso(date(2026, 10, 10)) == (2026, 8)
    assert mese_atteso(date(2026, 1, 5)) == (2025, 11)
    righe = [{"year": 2026, "month": 9}]
    assert not serve_aggiornare(righe, date(2026, 10, 31))
    assert serve_aggiornare([{"year": 2026, "month": 6}], date(2026, 10, 31))
