"""Stime motivate di mantenimento e lite temeraria: conti sui dati, presupposti e valutazioni separati."""

from __future__ import annotations

import pytest

from pct.calcolatori import assegno_mantenimento, lite_temeraria
from pct.calcolatori.stime.scheda import importo_o_intervallo, righe_testo

BILANCIO = "spese correnti del figlio; 800; ordinaria; B; estratti conto\nscuola; 100; ordinaria; A; ricevute"
VALUTAZIONI = {k: "valutata sui documenti" for k in ("mf_val_permanenza", "mf_val_abitazione", "mf_val_cura", "mf_val_esigenze", "mf_val_tenore")}


def _figli(**extra):
    return assegno_mantenimento.calcola({"man_percorso": "figli", "mf_reddito_a": "3000", "mf_reddito_b": "1500", "mf_voci": BILANCIO, **extra})


def test_lettura_di_importi_intervalli_e_righe():
    assert importo_o_intervallo("1.200,50") == (1200.5, 1200.5)
    assert importo_o_intervallo("800-1000") == (800.0, 1000.0)
    assert importo_o_intervallo("non quantificabile") is None
    assert righe_testo("a; 1\n\nb", 3) == [["a", "1", ""], ["b", "", ""]]


def test_esempio_figli_dell_avvocato():
    esito = _figli()
    assert esito["quota_reddituale_A_percentuale"] == pytest.approx(66.67)
    assert esito["contributo_teorico_A"] == pytest.approx(600.0)
    assert esito["trasferimento_di_base_mensile"] == pytest.approx(500.0)
    assert esito["stato"] == "stima_da_verificare"
    assert len(esito["scheda_di_calcolo"]["da_completare"]) == 5


def test_fascia_di_sensibilita_e_non_margine_standard():
    esito = assegno_mantenimento.calcola({"man_percorso": "figli", "mf_reddito_a": "3000", "mf_reddito_b": "1500",
                                          "mf_voci": "spese; 700-900; ordinaria; B\nscuola; 100; ordinaria; A"})
    assert esito["fascia_di_sensibilita"]["da"] == pytest.approx(433.33)
    assert esito["fascia_di_sensibilita"]["a"] == pytest.approx(566.67)


def test_straordinarie_e_assegno_unico_fuori_dal_fabbisogno():
    esito = _figli(mf_voci=BILANCIO + "\nviaggio studio; 300; straordinaria; A", mf_assegno_unico="200")
    assert esito["fabbisogno_ordinario_mensile"] == pytest.approx(900.0)
    assert esito["spese_straordinarie_mensili"] == pytest.approx(300.0)
    assert esito["scheda_di_calcolo"]["dati"]["assegno_unico_mensile"]["importo"] == 200.0


def test_validazione_solo_con_valutazioni_e_motivazione():
    assert _figli(mf_validata="1", mf_motivazione="esaminati")["stato"] == "stima_da_verificare"
    assert _figli(mf_validata="1", **VALUTAZIONI)["stato"] == "stima_da_verificare"
    assert _figli(mf_validata="1", mf_motivazione="esaminati", **VALUTAZIONI)["stato"] == "proposta_validata_dallo_studio"


def test_trasferimento_inverso_quando_a_sostiene_gia_di_piu():
    esito = _figli(mf_voci="spese; 900; ordinaria; A")
    assert esito["direzione_trasferimento"] == "da B ad A"
    assert esito["trasferimento_di_base_mensile"] == pytest.approx(300.0)


def test_separazione_con_addebito_e_divorzio_compensativo():
    sep = assegno_mantenimento.calcola({"man_percorso": "separazione", "mc_fabbisogno": "1400", "mc_risorse_richiedente": "800", "mc_addebito": "si"})
    assert sep["differenza_economica_da_esaminare"] == pytest.approx(600.0)
    assert any("addebitata" in a for a in sep["warnings"])
    div = assegno_mantenimento.calcola({"man_percorso": "divorzio", "mc_fabbisogno": "1400", "mc_risorse_richiedente": "800",
                                        "mc_durata_matrimonio": "20",
                                        "mc_compensative": "rinuncia alla carriera; 300; documenti di lavoro\nvoce senza prova; 100"})
    assert div["scenario_prospettato_dall_avvocato"]["totale"] == pytest.approx(900.0)
    assert len(div["componente_compensativa"]) == 1
    assert div["scheda_di_calcolo"]["dati"]["durata_del_matrimonio_anni"] == 20


def test_lite_temeraria_rami_separati():
    esito = lite_temeraria.calcola({
        "lt_presupposti": "sussistono", "lt_compenso": "4000", "lt_scenario": "elevato", "lt_parti": "2",
        "lt_data_instaurazione": "2024-01-10",
        "lt_danni": "custodia; 1200; fatture; doc. 4; pignoramento revocato; incluso\nimmagine; non quantificabile; ; ; ; incluso",
    })
    assert esito["somme_a_favore_della_parte_comma_3"] == pytest.approx(12000.0)
    assert esito["importo_danni_inclusi_documentati"] == pytest.approx(1200.0)
    assert esito["prospetto_danni_commi_1_2"][1]["importo"] is None
    assert esito["prospetto_danni_commi_1_2"][1]["stato"] == "da verificare"
    assert esito["comma_4_cassa_delle_ammende"]["beneficiario"].startswith("Cassa delle ammende")
    assert "totale" not in esito


def test_lite_temeraria_presupposti_non_sussistenti():
    esito = lite_temeraria.calcola({"lt_presupposti": "non_sussistono", "lt_compenso": "4000"})
    assert "comma_3" not in esito
    assert esito["stato"] == "dati_insufficienti"
