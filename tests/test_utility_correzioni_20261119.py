"""Correzioni delle utility di /strumenti-legali/ (collaudo lotti 1-3, 19/11/2026).

Ogni test riporta l'esempio calcolato a mano e la norma o la fonte ufficiale
da cui viene il dato.
"""
from __future__ import annotations

from datetime import date

import pytest

from pct.normative_tables import GestioneTabelleNormative
from pct.strumenti_legali import GestioneStrumentiLegali


@pytest.fixture()
def norme(tmp_path):
    return GestioneTabelleNormative(db_path=str(tmp_path / "tabelle.json"))


@pytest.fixture()
def gestore(tmp_path):
    return GestioneStrumentiLegali(normative_db_path=str(tmp_path / "strumenti.json"))


# ── Usura: 4° trimestre 2026 ────────────────────────────────────────────
# Fonte: D.M. MEF 28/09/2026, Allegato A, G.U. n. 227 del 30/09/2026, pag. 42
# (rilevazione 1 aprile - 30 giugno 2026, applicazione 1 ottobre - 31 dicembre 2026).


@pytest.mark.parametrize(
    "categoria,tegm,soglia",
    [
        ("credito_personale", 12.08, 19.1000),  # 12,08 x 1,25 + 4 = 19,10
        ("credito_revolving", 16.50, 24.5000),  # 24,625 > 16,50 + 8: soglia limitata a 24,50
        ("scoperti_senza_affidamento_fino_1500", 16.08, 24.0800),  # 24,10 > 24,08: limite di 8 punti
        ("mutui_ipotecari_fisso", 4.52, 9.6500),  # 4,52 x 1,25 + 4 = 9,65
        ("cessione_quinto_fino_15000", 14.23, 21.7875),
    ],
)
def test_soglie_quarto_trimestre_2026(norme, categoria, tegm, soglia):
    riga = norme.usura_soglia_per_categoria(categoria, date(2026, 11, 18))
    assert riga["quarter"] == "2026-Q4"
    assert not riga.get("fuori_periodo")
    assert (riga["tegm"], riga["soglia"]) == (tegm, soglia)


def test_quarto_trimestre_ha_tutte_le_24_categorie(norme):
    categorie = {r["category"] for r in norme.rows("tasso_usura") if r["quarter"] == "2026-Q4"}
    assert len(categorie) == 24


def test_verifica_usura_novembre_2026_e_determinata(gestore):
    # 15% su credito personale al 18/11/2026: soglia 19,10%, margine 4,10 punti.
    esito = gestore.verifica_soglia_usura(
        {"usura_categoria": "credito_personale", "usura_tasso": "15", "usura_data": "2026-11-18"}
    )
    assert esito["soglia"] == 19.10
    assert esito["supera_soglia"] is False
    assert round(esito["margine"], 2) == 4.10


def test_la_tendina_usura_offre_tutte_le_categorie_del_decreto():
    from pct.calcolatori.schema import SCHEMI_CALCOLATORI as schemi

    campo = next(c for c in schemi["usura"]["campi"] if c["name"] == "usura_categoria")
    valori = {o["value"] for o in campo["options"]}
    assert len(valori) == 24
    assert {"cessione_quinto_fino_15000", "leasing_strumentale_oltre_25000", "factoring_oltre_50000"} <= valori


# ── Interessi: il giorno iniziale non si computa (art. 2963 c.c.) ──────────


def test_interessi_legali_senza_giorno_in_piu(gestore):
    # 10.000 dal 15/03/2023 al 30/06/2026: 291 gg al 5% (398,63) + 2024 al 2,5% (250)
    # + 2025 al 2% (200) + 181 gg al 1,6% (79,34) = 927,97; prima 1.204 gg e 929,34.
    r = gestore.calcola_interessi({"int_tipo": "legali", "int_capitale": "10000",
                                   "int_data_inizio": "2023-03-15", "int_data_fine": "2026-06-30"})
    assert r["days"] == 1203
    assert [s["days"] for s in r["segments"]] == [291, 366, 365, 181]
    assert r["total_interest"] == 927.97


def test_interessi_stesso_giorno_zero(gestore):
    r = gestore.calcola_interessi({"int_tipo": "legali", "int_capitale": "8000",
                                   "int_data_inizio": "2024-02-20", "int_data_fine": "2024-02-20"})
    assert r["days"] == 0 and r["total_interest"] == 0.0


def test_interessi_mora_609_giorni(gestore):
    # 01/03/2025-31/10/2026: 609 giorni (prima 610), tassi BCE + 8 punti.
    r = gestore.calcola_interessi({"int_tipo": "mora_commerciale", "int_capitale": "10000",
                                   "int_data_inizio": "2025-03-01", "int_data_fine": "2026-10-31"})
    assert r["days"] == 609
    assert r["total_interest"] == 1735.10


def test_interessi_convenzionali_5_per_cento(gestore):
    # 5.000 al 5% dal 01/01/2026 al 30/06/2026: 180 giorni -> 5.000 x 5% x 180/365 = 123,29.
    r = gestore.calcola_interessi({"int_tipo": "convenzionale", "int_tasso": "5", "int_capitale": "5000",
                                   "int_data_inizio": "2026-01-01", "int_data_fine": "2026-06-30"})
    assert r["days"] == 180 and r["total_interest"] == 123.29


def test_interessi_art_1284_comma_4_dalla_domanda(gestore):
    # 10.000: legali 2% dal 02/01 al 31/12/2025 (364 gg) = 199,45; dalla domanda (31/12/2025)
    # saggio D.Lgs. 231/2002 del 1° sem. 2026 (BCE 2,15 + 8 = 10,15%) per 181 gg = 503,33.
    r = gestore.calcola_interessi({"int_tipo": "legali_1284_4", "int_capitale": "10000",
                                   "int_data_inizio": "2025-01-01", "int_data_fine": "2026-06-30",
                                   "int_data_domanda": "2025-12-31"})
    assert [(s["days"], s["rate"], s["interest"]) for s in r["segments"]] == [(364, 2.0, 199.45), (181, 10.15, 503.33)]
    assert r["total_interest"] == 702.78


def test_interessi_art_1284_comma_4_richiede_la_data_della_domanda(gestore):
    with pytest.raises(ValueError, match="domanda giudiziale"):
        gestore.calcola_interessi({"int_tipo": "legali_1284_4", "int_capitale": "1000",
                                   "int_data_inizio": "2025-01-01", "int_data_fine": "2025-06-30"})


def test_interessi_con_acconto_imputazione_1194(gestore):
    # 10.000 legali dal 01/01/2024 al 31/12/2025, acconto di 3.000 il 01/01/2025.
    # Fino al 01/01/2025: 365/366 x 2,5% = 249,32 + 1 gg al 2% = 0,55 -> 249,87 a interessi,
    # 2.750,13 a capitale; residuo 7.249,87 x 2% x 364/365 = 144,60.
    r = gestore.calcola_interessi_acconti({"acc_tipo": "legali", "acc_capitale": "10000",
                                           "acc_data_inizio": "2024-01-01", "acc_data_fine": "2025-12-31",
                                           "acc_acconti": "01/01/2025 3000,00\n"})
    imp = r["imputazioni"][0]
    assert (imp["quota_interessi"], imp["quota_capitale"]) == (249.87, 2750.13)
    assert (r["residuo_capitale"], r["residuo_interessi"]) == (7249.87, 144.60)


# ── TFR: art. 2120 c.c. e art. 3, comma 15, L. 297/1982 ────────────────


def test_tfr_cinque_anni_ipotesi_due_per_cento(gestore):
    # Quota 30.000/13,5 = 2.222,22 - 0,50% di 30.000 (150) = 2.072,22; coefficiente 1,5 + 75% x 2 = 3%.
    # 2.072,22 -> 4.206,61 -> 6.405,03 -> 8.669,40 -> 11.001,70.
    r = gestore.calcola_tfr({"tfr_retribuzione_annua": "30000", "tfr_anni_servizio": "5", "tfr_inflazione_perc": "2"})
    assert [x["fondo_fine_periodo"] for x in r["dettaglio_annuale"]] == [2072.22, 4206.61, 6405.03, 8669.40, 11001.70]
    assert r["totale_lordo"] == 11001.70


def test_tfr_senza_trattenuta_tre_anni(gestore):
    # 2.222,22 -> 2.222,22 x 1,03 + 2.222,22 = 4.511,11 -> 4.511,11 x 1,03 + 2.222,22 = 6.868,66.
    r = gestore.calcola_tfr({"tfr_retribuzione_annua": "30000", "tfr_anni_servizio": "3",
                             "tfr_inflazione_perc": "2", "tfr_trattenuta_050": "0"})
    assert r["totale_lordo"] == 6868.66
    assert r["rivalutazione"] == 202.00


def test_tfr_con_date_usa_gli_indici_istat(gestore):
    # 27.000 dal 01/01/2023 al 31/12/2025: quota 2.000 - 135 = 1.865.
    # Dic. 2024: FOI 120,2 / 118,9 = +1,0934% -> 1,5 + 0,82 = 2,320017%; 1.865 x 2,320017% = 43,27.
    # Dic. 2025: FOI 121,5 / 120,2 = +1,0815% -> 2,311148%; 3.773,27 x 2,311148% = 87,21.
    r = gestore.calcola_tfr({"tfr_retribuzione_annua": "27000", "tfr_data_assunzione": "2023-01-01",
                             "tfr_data_cessazione": "2025-12-31"})
    tassi = [x["tasso_rivalutazione_perc"] for x in r["dettaglio_annuale"]]
    assert tassi == [0.0, 2.320017, 2.311148]
    assert r["totale_lordo"] == 5725.48
    assert all(x["origine_indice"] in {"ISTAT", "nessun fondo da rivalutare"} for x in r["dettaglio_annuale"])


def test_tfr_cessazione_ottobre_2026_usa_il_foi_di_ottobre(gestore):
    # Fondo 3.773,10 al 31/12/2025; 10 mesi nel 2026: 1,5 x 10/12 = 1,25 + 75% x
    # (105,4 x 1,214 / 121,5 - 1) = 3,9849 -> 5,234938%; rivalutazione 197,52.
    r = gestore.calcola_tfr({"tfr_retribuzione_annua": "27000", "tfr_data_assunzione": "2024-01-01",
                             "tfr_data_cessazione": "2026-10-31"})
    ultimo = r["dettaglio_annuale"][-1]
    assert (ultimo["mesi"], ultimo["tasso_rivalutazione_perc"], ultimo["rivalutazione"]) == (10, 5.234938, 197.52)


def test_tfr_indice_non_pubblicato_si_dichiara(gestore):
    with pytest.raises(ValueError, match="non ancora"):
        gestore.calcola_tfr({"tfr_retribuzione_annua": "27000", "tfr_data_assunzione": "2025-01-01",
                             "tfr_data_cessazione": "2026-12-31"})
    stima = gestore.calcola_tfr({"tfr_retribuzione_annua": "27000", "tfr_data_assunzione": "2025-01-01",
                                 "tfr_data_cessazione": "2026-12-31", "tfr_inflazione_perc": "2"})
    assert stima["dettaglio_annuale"][-1]["origine_indice"] == "ipotesi"
    assert any("non è ancora pubblicato" in a for a in stima["warnings"])


# ── Indici FOI ufficiali ISTAT (SDMX, letti il 19/11/2026) ─────────────


def test_foi_ottobre_2026_pubblicato(norme):
    assert norme.istat_index_pubblicato("foi", 2026, 10) == {"index": 105.4, "base": 2025}
    # Riscontro col tendenziale ISTAT +5,4% su ottobre 2025 (121,4 in base 2015).
    assert round(norme.istat_index("foi", 2026, 10) / 121.4 - 1, 3) == 0.054


def test_rivalutazione_senza_mese_finale_usa_ultimo_indice(gestore):
    r = gestore.calcola_rivalutazione_istat({"riv_importo": "1000", "riv_anno_base": "2025", "riv_mese_base": "10"})
    assert any("10/2026" in n for n in r["notes"])
    assert r["importo_rivalutato"] == 1054.0


# ── Premorienza: anni di calendario ─────────────────────────────────────


def test_premorienza_due_anni_esatti():
    from pct.calcolatori import danno_premorienza

    # 01/01/2023 - 01/01/2025 = due anni esatti (731 giorni per il bisestile, non tre anni).
    r = danno_premorienza.calcola({"pm_perc_ip": "30", "pm_data_lesione": "2023-01-01",
                                   "pm_data_decesso": "2025-01-01", "pm_eta": "50"})
    assert r["anni_sopravvivenza"] == 2
    assert r["totale"] == 16504.0
    r3 = danno_premorienza.calcola({"pm_perc_ip": "30", "pm_data_lesione": "2023-01-01",
                                    "pm_data_decesso": "2025-01-02", "pm_eta": "50"})
    assert r3["anni_sopravvivenza"] == 3  # l'anno iniziato conta per intero


# ── Prescrizione nello scadenziario: il sabato non proroga (art. 2963 c.c.) ─


def test_prescrizione_scadenziario_sabato_non_proroga():
    from pct.scadenziario import calcola_scadenza_avanzata, profilo_da_preset

    sabato = calcola_scadenza_avanzata("2016-11-21", profilo_da_preset("prescrizione_ordinaria"))
    assert str(sabato.legal_due_at).startswith("2026-11-21")  # sabato: resta
    domenica = calcola_scadenza_avanzata("2016-11-22", profilo_da_preset("prescrizione_ordinaria"))
    assert str(domenica.legal_due_at).startswith("2026-11-23")  # domenica: lunedì
    cinque = calcola_scadenza_avanzata("2021-11-21", profilo_da_preset("prescrizione_breve_5anni"))
    assert str(cinque.legal_due_at).startswith("2026-11-21")


# ── Procedibilità: art. 8 L. 24/2017 ────────────────────────────────────


def test_responsabilita_sanitaria_atp_o_mediazione():
    from pct.calcolatori import procedibilita_adr

    r = procedibilita_adr.calcola({"adr_materia": "responsabilita_medica", "adr_procedimento": "ordinario",
                                   "adr_data_avvio": "2026-11-10"})
    assert r["condizione_procedibilita"] is True
    assert r["strumento"] == "ctp_o_mediazione"
    assert "696-bis" in r["motivo"] and "24/2017" in r["motivo"]
    # 6 mesi dal deposito: 10/05/2027 (art. 8, comma 3).
    assert r["passaggi"][1]["data"] == "10/05/2027"
    atp = procedibilita_adr.calcola({"adr_materia": "responsabilita_medica", "adr_procedimento": "ctp_696bis"})
    assert atp["condizione_procedibilita"] is True


# ── Nota di precisazione: spese generali 15% ────────────────────────────


def test_nota_credito_spese_generali(gestore):
    # Compensi 2.000 + 15% = 300; CPA 4% su 2.300 = 92; IVA 22% su 2.392 = 526,24.
    r = gestore.genera_nota_precisazione_credito({
        "note_creditore": "Alfa", "note_debitore": "Beta", "note_capitale": "10000",
        "note_interessi_tipo": "manuale", "note_interessi_manual": "0", "note_compensi": "2000",
        "note_cpa_perc": "4", "note_iva_perc": "22"})
    voci = {v["label"].split(" ")[0] + " " + v["label"].split(" ")[1]: v["amount"] for v in r["breakdown"] if " " in v["label"]}
    assert voci["Spese generali"] == 300.0
    assert voci["CPA 4,00%"] == 92.0 and voci["IVA 22,00%"] == 526.24
    assert r["totale_lordo"] == 12918.24


# ── Codice fiscale: carattere di controllo ──────────────────────────────


def test_codice_fiscale_controllo_errato(gestore):
    assert gestore.calcola_codice_fiscale({"cf_codice": "RSSMRA80A01E506G"})["data_nascita"] == "1980-01-01"
    with pytest.raises(ValueError, match="carattere di controllo"):
        gestore.calcola_codice_fiscale({"cf_codice": "RSSMRA80A41E506X"})


# ── Testi giuridici corretti ────────────────────────────────────────────


def test_nessuna_norma_inesistente_citata(gestore):
    r = gestore.calcola_rivalutazione_istat({"riv_importo": "10000", "riv_anno_base": "2025", "riv_mese_base": "6",
                                             "riv_anno_fine": "2020", "riv_mese_fine": "1"})
    testo = " ".join(r["notes"] + r["warnings"])
    assert "24 L. 431/1998" not in testo
    assert "deflazione" not in testo and "devalutazione" in testo


def test_imposta_registro_note_corrette(gestore):
    r = gestore.calcola_imposta_registro({"reg_tipo_atto": "sentenza_condanna", "reg_valore": "50000", "reg_parti": "2"})
    testo = " ".join(r["notes"] + r["warnings"])
    assert r["imposta"] == 1500.0
    assert "irrevocabilit" not in testo
    assert "impugnato" in testo and "art. 40" in testo
    lodo = gestore.calcola_imposta_registro({"reg_tipo_atto": "lodo_arbitrale", "reg_valore": "50000"})
    assert "lett. b" in lodo["norma"]


def test_canone_75_per_cento_norma_giusta(gestore):
    r = gestore.calcola_adeguamento_canone({"loc_canone": "800", "loc_perc_adeguamento": "75",
                                            "loc_anno_base": "2024", "loc_mese_base": "6",
                                            "loc_anno_fine": "2025", "loc_mese_fine": "6"})
    testo = " ".join(r["notes"])
    assert "art. 32 L. 392/1978" in testo and "cedolare secca" in testo
    assert r["canone_aggiornato"] == 809.0


def test_usufrutto_coefficiente_spiegato(gestore):
    r = gestore.calcola_usufrutto({"usu_valore_piena": "200000", "usu_eta": "65", "usu_quota_perc": "100"})
    assert r["coefficiente"] == 20.0 and r["saggio_riferimento"] == 2.5
    assert any("2,5%" in n and "5-ter" in n for n in r["notes"])


def test_pena_cita_art_134(gestore):
    r = gestore.calcola_pena_riti_alternativi({"pena_anni": "3", "pena_rito": "abbreviato",
                                               "pena_attenuanti_generiche": "1", "pena_mancata_impugnazione": "1"})
    testo = " ".join(r["notes"])
    assert "art. 134 c.p." in testo and "132, comma 2" not in testo


# ── Collegamenti delle card ─────────────────────────────────────────────


def test_card_aprono_il_calcolatore_giusto():
    from pct.applicazioni_catalogo import catalogo_applicazioni
    from web.services import react_applicazioni_bridge as bridge

    catalogo = {voce["id"]: voce for voce in catalogo_applicazioni()}
    assert bridge.strumento_voce(catalogo["interessi_e_acconti"])[0] == "interessi_acconti"
    assert bridge.strumento_voce(catalogo["interessi_a_tasso_fisso"]) == ("interessi", {"int_tipo": "convenzionale"})
    assert bridge.strumento_voce(catalogo["interessi_1284_cc"]) == ("interessi", {"int_tipo": "legali_1284_4"})
    assert bridge.strumento_voce(catalogo["conversione_pena"])[0] == "pena_riti_alternativi"
    for voce in ("risarcimento_inail", "calcolo_fine_pena", "rendimento_buoni_postali", "danno_parentale_roma",
                 "calcolo_superficie_commerciale", "codice_di_procedura_penale"):
        assert bridge.tipo_voce(catalogo[voce]) == "non_disponibile", voce
