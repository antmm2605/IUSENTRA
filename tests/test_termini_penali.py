"""Termini penali: art. 172 c.p.p., sospensione feriale, artt. 585, 461, 309, 405-407-bis, 303, 344-bis c.p.p.,
prescrizione per regimi (L. 103/2017, art. 161-bis c.p.). Date verificate a mano sul calendario."""

from __future__ import annotations

import pytest

from pct.termini_penali import custodia, impugnazioni, improcedibilita, indagini


def _impugna(**dati):
    return impugnazioni.calcola(dati)


def test_camera_di_consiglio_quindici_giorni_dall_avviso():
    esito = _impugna(tp_atto="impugnazione_sentenza", tp_motivazione="camera_consiglio", tp_data_evento="2026-03-02")
    assert esito["scadenza"] == "17/03/2026"
    assert esito["scadenze_proposte"][0]["data"] == "2026-03-17"


def test_motivazione_in_quindici_giorni_e_sabato_non_festivo():
    """Deposito entro il 25/06, trenta giorni: 25/07/2026 è sabato e nel penale non si proroga."""
    esito = _impugna(tp_motivazione="quindici_giorni", tp_data_evento="2026-06-10")
    assert esito["scadenza"] == "25/07/2026"
    assert any("25/06/2026" in p["data"] for p in esito["passaggi"])


def test_sospensione_feriale_e_proroga_della_domenica():
    """Pronuncia 20/07: motivazione fino al 04/09 (agosto escluso); +30 = domenica 04/10 → lunedì 05/10."""
    esito = _impugna(tp_motivazione="quindici_giorni", tp_data_evento="2026-07-20")
    assert esito["scadenza"] == "05/10/2026"


def test_assenza_aggiunge_quindici_giorni_e_avviso_tardivo_sposta_la_decorrenza():
    assert _impugna(tp_motivazione="camera_consiglio", tp_data_evento="2026-03-02", tp_assente="1")["scadenza"] == "01/04/2026"
    tardivo = _impugna(tp_motivazione="quindici_giorni", tp_data_evento="2026-02-02", tp_data_avviso_deposito="2026-03-16")
    assert tardivo["scadenza"] == "15/04/2026"


def test_termine_fissato_dal_giudice_deve_stare_fra_16_e_90_giorni():
    with pytest.raises(ValueError, match="90 giorni"):
        _impugna(tp_motivazione="termine_giudice", tp_data_evento="2026-02-02", tp_giorni_deposito="120")
    esito = _impugna(tp_motivazione="termine_giudice", tp_data_evento="2026-02-02", tp_giorni_deposito="60")
    # Deposito 03/04/2026, +45 = 18/05/2026.
    assert esito["scadenza"] == "18/05/2026"


def test_riesame_con_e_senza_rinuncia_alla_sospensione_feriale():
    senza = _impugna(tp_atto="riesame_personale", tp_data_evento="2026-07-28")
    assert senza["scadenza"] == "07/09/2026"
    con = _impugna(tp_atto="riesame_personale", tp_data_evento="2026-07-28", tp_detenuto_rinuncia="1")
    assert con["scadenza"] == "07/08/2026"
    organizzata = _impugna(tp_atto="riesame_reale", tp_data_evento="2026-07-28", tp_criminalita_organizzata="1")
    assert organizzata["scadenza"] == "07/08/2026"


def test_festivita_nazionali_prorogano_il_termine():
    """15 giorni dal 10/12/2026 = Natale; 26 festivo, 27 domenica: lunedì 28/12."""
    assert _impugna(tp_atto="opposizione_decreto_penale", tp_data_evento="2026-12-10")["scadenza"] == "28/12/2026"


def test_opposizione_archiviazione_trenta_giorni_per_i_delitti_con_violenza():
    assert _impugna(tp_atto="opposizione_archiviazione", tp_data_evento="2026-03-02")["scadenza"] == "23/03/2026"
    assert _impugna(tp_atto="opposizione_archiviazione", tp_data_evento="2026-03-02", tp_violenza_persona="1")["scadenza"] == "01/04/2026"


def test_indagini_preliminari_con_agosto_e_407_bis():
    esito = indagini.calcola({"ind_data_iscrizione": "2026-01-15", "ind_tipo": "delitto"})
    termini = {t["termine"]: t["scadenza"] for t in esito["termini"]}
    assert termini["Termine ordinario (art. 405 c. 2)"] == "15/02/2027"
    # 18 mesi = 15/07/2027; +31 giorni di agosto 2026 cadono ad agosto 2027, sospeso anche lui: 15/09/2027.
    assert termini["Durata massima (art. 407)"] == "15/09/2027"
    assert esito["chiusura_indagini"] == "15/02/2027"
    contravvenzione = indagini.calcola({"ind_data_iscrizione": "2026-01-15", "ind_tipo": "contravvenzione"})
    assert contravvenzione["chiusura_indagini"] == "15/07/2026"


def test_custodia_termini_di_fase_e_complessivo():
    esito = custodia.calcola({"cus_fase": "indagini", "cus_data_inizio_fase": "2026-03-10", "cus_pena_massima_anni": "5"})
    assert esito["scadenza_fase"] == "10/06/2026" and esito["scadenza_complessiva"] == "10/03/2028"
    grave = custodia.calcola({"cus_fase": "indagini", "cus_data_inizio_fase": "2026-03-10", "cus_pena_massima_anni": "20"})
    assert grave["scadenza_fase"] == "10/03/2027" and grave["scadenza_complessiva"] == "10/03/2030"
    appello = custodia.calcola({"cus_fase": "appello", "cus_data_inizio_fase": "2026-03-10", "cus_data_inizio_esecuzione": "2025-01-10",
                                "cus_pena_massima_anni": "10", "cus_condanna_anni": "4"})
    assert appello["scadenza_fase"] == "10/03/2027" and appello["scadenza_complessiva"] == "10/01/2029"
    with pytest.raises(ValueError, match="pena inflitta"):
        custodia.calcola({"cus_fase": "cassazione", "cus_data_inizio_fase": "2026-03-10", "cus_pena_massima_anni": "10"})


def test_improcedibilita_termini_e_transitorio():
    esito = improcedibilita.calcola({"imp_data_fatto": "2022-05-01", "imp_grado": "appello", "imp_data_pronuncia": "2025-03-03",
                                     "imp_giorni_motivazione": "15", "imp_data_impugnazione": "2025-04-20"})
    assert esito["decorrenza"] == "16/06/2025" and esito["definizione_entro"] == "16/06/2027"
    vecchia = improcedibilita.calcola({"imp_data_fatto": "2022-05-01", "imp_grado": "appello", "imp_data_pronuncia": "2024-03-04",
                                       "imp_giorni_motivazione": "15", "imp_data_impugnazione": "2024-04-20"})
    assert vecchia["termine"] == "36 mesi"
    with pytest.raises(ValueError, match="1° gennaio 2020"):
        improcedibilita.calcola({"imp_data_fatto": "2019-05-01", "imp_data_pronuncia": "2024-03-04"})


def test_prescrizione_regimi_dopo_la_sentenza():
    from pct.strumenti_legali import GestioneStrumentiLegali

    gestore = GestioneStrumentiLegali()
    base = {"presc_massimo_edittale_anni": "5", "presc_interruzione": "quarto"}
    ordinario = gestore.calcola_prescrizione_penale({**base, "presc_data_fatto": "2016-03-15"})
    assert ordinario["data_prescrizione_base"] == "2022-03-15" and ordinario["data_prescrizione_massima"] == "2023-09-15"
    orlando = gestore.calcola_prescrizione_penale({**base, "presc_data_fatto": "2018-05-10", "presc_scadenza_motivazione_primo": "2022-03-01",
                                                  "presc_dispositivo_appello": "2023-01-10"})
    assert orlando["giorni_sospensione"] == 315 and orlando["data_prescrizione_massima"] == "2026-09-21"
    massimo = gestore.calcola_prescrizione_penale({**base, "presc_data_fatto": "2018-05-10", "presc_scadenza_motivazione_primo": "2022-03-01"})
    assert massimo["giorni_sospensione"] == 549  # un anno e sei mesi dal 01/03/2022 al 01/09/2023
    bloccata = gestore.calcola_prescrizione_penale({**base, "presc_data_fatto": "2021-02-01", "presc_data_sentenza_primo_grado": "2025-06-01"})
    assert "cessato" in bloccata["effetto_sentenza_primo_grado"] and "scadenze_proposte" not in bloccata
    senza_limite = gestore.calcola_prescrizione_penale({**base, "presc_data_fatto": "2021-02-01", "presc_interruzione": "nessun_limite"})
    assert senza_limite["data_prescrizione_massima_it"] == "senza limite"


def test_scadenza_dallo_strumento_allo_scadenziario(tmp_path):
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login
    from web.helpers import get_scadenziario

    app = _app(tmp_path)
    corpo = {"tool": "termini_penali", "dati": {"tp_atto": "impugnazione_sentenza", "tp_motivazione": "camera_consiglio",
                                                 "tp_data_evento": "2099-03-02"}, "indice": 0}
    intestazioni = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    with app.test_client() as client:
        _login(client)
        calcolo = client.post("/api/v1/ui/strumenti-legali/calcola", json=corpo, headers=intestazioni).get_json()
        assert calcolo["ok"] and calcolo["result"]["scadenza"] == "17/03/2099"
        creata = client.post("/api/v1/ui/strumenti-legali/scadenza", json=corpo, headers=intestazioni).get_json()
        assert creata["ok"], creata
        ancora = client.post("/api/v1/ui/strumenti-legali/scadenza", json=corpo, headers=intestazioni).get_json()
        assert ancora["giaPresente"]
        fuori = client.post("/api/v1/ui/strumenti-legali/scadenza", json={**corpo, "indice": 3}, headers=intestazioni)
        assert fuori.status_code == 400
        scaduta = client.post("/api/v1/ui/strumenti-legali/scadenza", headers=intestazioni,
                              json={**corpo, "dati": {**corpo["dati"], "tp_data_evento": "2020-03-02"}})
        assert scaduta.status_code == 409
    with app.test_request_context("/"):
        scadenze = [s for s in get_scadenziario().tutte(solo_aperte=False) if "TERMINE_STRUMENTO" in (s.note or "")]
    assert len(scadenze) == 1 and scadenze[0].data_scadenza.startswith("2099-03-17")
