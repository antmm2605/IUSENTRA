"""Test del Lotto 2B-2: blocco fiscale IRPEF, regimi e utility del pannello.

Copre: IRPEF a scaglioni versionati (art. 11 TUIR), acconto (art. 17
D.P.R. 435/2001), rateazione (art. 20 D.Lgs. 241/1997), detrazioni per
familiari (art. 12 TUIR), per tipo di reddito (art. 13 TUIR con misure
cuneo L. 207/2024), per canoni (art. 16 TUIR), regime forfettario
(L. 190/2014), fattura agente (art. 25-bis D.P.R. 600/1973 + Enasarco) e
prestazione occasionale; più le utility del pannello /applicazioni.
"""

from __future__ import annotations

import pytest

from pct.strumenti_legali import GestioneStrumentiLegali


@pytest.fixture()
def gestore(tmp_path):
    return GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tabelle_normative.json"))


class TestIrpef:
    def test_scaglioni_2026_seconda_aliquota_33(self, gestore):
        esito = gestore.calcola_irpef_lorda({"irpef_reddito": "35000", "irpef_anno": "2026"})
        # 28.000 x 23% + 7.000 x 33% = 6.440 + 2.310
        assert esito["irpef_lorda"] == pytest.approx(8750.0)
        assert esito["aliquota_marginale"] == 33.0

    def test_scaglioni_2025_seconda_aliquota_35(self, gestore):
        esito = gestore.calcola_irpef_lorda({"irpef_reddito": "35000", "irpef_anno": "2025"})
        assert esito["irpef_lorda"] == pytest.approx(8890.0)

    def test_terzo_scaglione(self, gestore):
        esito = gestore.calcola_irpef_lorda({"irpef_reddito": "60000", "irpef_anno": "2026"})
        # 6.440 + 22.000 x 33% + 10.000 x 43% = 6.440 + 7.260 + 4.300
        assert esito["irpef_lorda"] == pytest.approx(18_000.0)
        assert len(esito["dettaglio"]) == 3

    def test_anno_non_versionato_fail_closed(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_irpef_lorda({"irpef_reddito": "30000", "irpef_anno": "2030"})


class TestAcconto:
    def test_sotto_soglia_non_dovuto(self, gestore):
        esito = gestore.calcola_acconto_imposte({"acc_rigo_differenza": "50"})
        assert esito["esito"] == "non dovuto"
        assert esito["acconto_totale"] == 0.0

    def test_unica_soluzione(self, gestore):
        esito = gestore.calcola_acconto_imposte({"acc_rigo_differenza": "200"})
        assert esito["esito"] == "unica soluzione a novembre"
        assert esito["seconda_rata"] == 200.0

    def test_confine_257_52_due_rate(self, gestore):
        # A 257,52 esatti il 40% (103,008) supera i 103 euro della soglia di
        # legge sulla prima rata: due rate, non unica soluzione (art. 17, c. 3,
        # D.P.R. 435/2001; scheda AE).
        esito = gestore.calcola_acconto_imposte({"acc_rigo_differenza": "257.52"})
        assert esito["esito"] == "due rate"

    def test_due_rate_40_60(self, gestore):
        esito = gestore.calcola_acconto_imposte({"acc_rigo_differenza": "1000"})
        assert esito["prima_rata"] == pytest.approx(400.0)
        assert esito["seconda_rata"] == pytest.approx(600.0)

    def test_isa_50_50(self, gestore):
        esito = gestore.calcola_acconto_imposte({"acc_rigo_differenza": "1000", "acc_isa": "1"})
        assert esito["prima_rata"] == pytest.approx(500.0)
        assert esito["seconda_rata"] == pytest.approx(500.0)


class TestRateazione:
    def test_piano_sei_rate(self, gestore):
        esito = gestore.calcola_rateazione_imposte({"rate_importo": "3000", "rate_numero": "6"})
        assert len(esito["piano"]) == 6
        assert esito["piano"][0]["interessi"] == 0.0
        # 0,33% mensile su 500 per (1+2+3+4+5) mesi = 24,75
        assert esito["totale_interessi"] == pytest.approx(24.75)
        # La semplificazione a mesi interi è dichiarata come stima per eccesso
        # e la nota non cita più il regime P.IVA/fine mese abrogato dal
        # D.Lgs. 1/2024.
        assert any("ECCESSO" in w for w in esito["warnings"])
        testo_note = " ".join(esito["notes"])
        assert "1/2024" in testo_note
        assert "fine mese" not in testo_note

    def test_range_rate(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_rateazione_imposte({"rate_importo": "1000", "rate_numero": "10"})


class TestDetrazioniFamiliari:
    def test_coniuge_fascia_media_con_maggiorazione(self, gestore):
        esito = gestore.calcola_detrazioni_familiari({"detfam_reddito": "30000", "detfam_coniuge": "1"})
        # 690 + 20 (fascia 29.200-34.700)
        assert esito["totale_detrazioni"] == pytest.approx(710.0)

    def test_figlio_degressione_con_troncamento(self, gestore):
        esito = gestore.calcola_detrazioni_familiari({"detfam_reddito": "30000", "detfam_figli": "1"})
        # Quoziente 65.000/95.000 = 0,68421... troncato a 0,6842 (art. 12,
        # c. 4, TUIR): 950 x 0,6842 = 649,99 — non 650,00.
        assert esito["totale_detrazioni"] == pytest.approx(649.99)

    def test_due_figli_soglia_aumentata(self, gestore):
        esito = gestore.calcola_detrazioni_familiari({"detfam_reddito": "30000", "detfam_figli": "2"})
        # soglia 110.000: quoziente 80/110 = 0,72727... troncato 0,7272
        assert esito["totale_detrazioni"] == pytest.approx(950.0 * 0.7272 * 2, abs=0.01)

    def test_soglia_conta_tutti_i_figli_a_carico(self, gestore):
        # Circ. AE 4/E/2022: la soglia +15.000 conta anche gli under 21
        # (assegno unico); la detrazione spetta solo per i figli 21-30.
        esito = gestore.calcola_detrazioni_familiari(
            {"detfam_reddito": "100000", "detfam_figli": "1", "detfam_figli_totali": "2"}
        )
        # Soglia 110.000: quoziente 10.000/110.000 = 0,0909 → 950 × 0,0909
        assert esito["totale_detrazioni"] == pytest.approx(950 * 0.0909, abs=0.01)

    def test_soglia_solo_figli_21_30_azzererebbe(self, gestore):
        esito = gestore.calcola_detrazioni_familiari({"detfam_reddito": "100000", "detfam_figli": "1"})
        assert esito["totale_detrazioni"] == 0.0

    def test_reddito_alto_azzera(self, gestore):
        esito = gestore.calcola_detrazioni_familiari({"detfam_reddito": "120000", "detfam_coniuge": "1", "detfam_altri": "1"})
        assert esito["totale_detrazioni"] == 0.0


class TestDetrazioniReddito:
    def test_dipendente_terza_fascia_con_maggiorazione_65(self, gestore):
        esito = gestore.calcola_detrazioni_reddito({"detred_reddito": "30000", "detred_tipo": "dipendente"})
        # 1.910 x tronca4(20.000/22.000 = 0,9090) + 65 = 1.736,19 + 65
        assert esito["detrazione"] == pytest.approx(1801.19, abs=0.01)
        # + ulteriore detrazione 1.000 (20-32k, L. 207/2024)
        assert esito["totale_con_misure_cuneo"] == pytest.approx(2801.19, abs=0.01)

    def test_dipendente_basso_somma_integrativa(self, gestore):
        esito = gestore.calcola_detrazioni_reddito({"detred_reddito": "12000", "detred_tipo": "dipendente"})
        assert esito["detrazione"] == pytest.approx(1955.0)
        somma = next(v for v in esito["dettaglio"] if "integrativa" in v["voce"].lower())
        assert somma["detrazione"] == pytest.approx(12000 * 0.053, abs=0.01)

    def test_pensione_prima_fascia(self, gestore):
        esito = gestore.calcola_detrazioni_reddito({"detred_reddito": "8000", "detred_tipo": "pensione"})
        assert esito["detrazione"] == pytest.approx(1955.0)

    def test_assegno_coniuge_come_pensione(self, gestore):
        pensione = gestore.calcola_detrazioni_reddito({"detred_reddito": "18000", "detred_tipo": "pensione"})
        assegno = gestore.calcola_detrazioni_reddito({"detred_reddito": "18000", "detred_tipo": "assegno_coniuge"})
        assert assegno["detrazione"] == pensione["detrazione"]

    def test_altri_redditi(self, gestore):
        esito = gestore.calcola_detrazioni_reddito({"detred_reddito": "4000", "detred_tipo": "altri_redditi"})
        assert esito["detrazione"] == pytest.approx(1265.0)

    def test_altri_redditi_maggiorazione_50_fascia_11_17k(self, gestore):
        # Art. 13, c. 5, ultimo periodo, TUIR: +50 euro per 11.001-17.000.
        esito = gestore.calcola_detrazioni_reddito({"detred_reddito": "15000", "detred_tipo": "altri_redditi"})
        # 500 + 765 x tronca4(13.000/22.500 = 0,5777) + 50 = 500 + 441,94 + 50
        assert esito["detrazione"] == pytest.approx(991.94, abs=0.01)

    def test_assegno_coniuge_senza_maggiorazione_50(self, gestore):
        # Il rinvio del c. 5-bis e' al solo c. 3: la maggiorazione dell'ultimo
        # periodo non si estende all'assegno dal coniuge.
        pensione = gestore.calcola_detrazioni_reddito({"detred_reddito": "27000", "detred_tipo": "pensione"})
        assegno = gestore.calcola_detrazioni_reddito({"detred_reddito": "27000", "detred_tipo": "assegno_coniuge"})
        assert pensione["detrazione"] == pytest.approx(assegno["detrazione"] + 50.0, abs=0.01)

    def test_somma_integrativa_su_base_dipendente_separata(self, gestore):
        # Gate sul complessivo (18.000 ≤ 20.000), percentuale e base sul solo
        # reddito di lavoro dipendente (14.000 → fascia 5,3%).
        esito = gestore.calcola_detrazioni_reddito(
            {
                "detred_reddito": "18000",
                "detred_tipo": "dipendente",
                "detred_reddito_dipendente": "14000",
            }
        )
        somma = next(v for v in esito["dettaglio"] if "integrativa" in v["voce"].lower())
        assert somma["detrazione"] == pytest.approx(14000 * 0.053, abs=0.01)

    def test_oltre_50000_azzera(self, gestore):
        esito = gestore.calcola_detrazioni_reddito({"detred_reddito": "60000", "detred_tipo": "dipendente"})
        assert esito["detrazione"] == 0.0


class TestDetrazioneCanone:
    def test_ordinario_prima_fascia(self, gestore):
        esito = gestore.calcola_detrazione_canone({"detcan_reddito": "14000", "detcan_tipo": "ordinario"})
        assert esito["detrazione"] == pytest.approx(300.0)

    def test_concordato_seconda_fascia(self, gestore):
        esito = gestore.calcola_detrazione_canone({"detcan_reddito": "20000", "detcan_tipo": "concordato"})
        assert esito["detrazione"] == pytest.approx(247.90)

    def test_giovani_percentuale_canone(self, gestore):
        esito = gestore.calcola_detrazione_canone(
            {"detcan_reddito": "14000", "detcan_tipo": "giovani", "detcan_canone": "8000"}
        )
        # 20% di 8.000 = 1.600 (> 991,60, entro il tetto 2.000)
        assert esito["detrazione"] == pytest.approx(1600.0)

    def test_oltre_soglia_azzera(self, gestore):
        esito = gestore.calcola_detrazione_canone({"detcan_reddito": "40000", "detcan_tipo": "ordinario"})
        assert esito["detrazione"] == 0.0


class TestForfettario:
    def test_professionista(self, gestore):
        esito = gestore.calcola_regime_forfettario(
            {"forf_ricavi": "50000", "forf_gruppo": "professionali", "forf_contributi": "5000"}
        )
        assert esito["reddito_forfettario"] == pytest.approx(39_000.0)
        assert esito["imponibile"] == pytest.approx(34_000.0)
        assert esito["imposta_sostitutiva"] == pytest.approx(5_100.0)

    def test_startup_5_percento(self, gestore):
        esito = gestore.calcola_regime_forfettario(
            {"forf_ricavi": "30000", "forf_gruppo": "professionali", "forf_startup": "1"}
        )
        assert esito["aliquota"] == 5.0
        assert esito["imposta_sostitutiva"] == pytest.approx(30_000 * 0.78 * 0.05)

    def test_fascia_85_100_regime_ancora_applicabile(self, gestore):
        esito = gestore.calcola_regime_forfettario({"forf_ricavi": "90000", "forf_gruppo": "commercio"})
        assert esito["regime_applicabile"] is True
        assert any("85.000" in w and "anno successivo" in w for w in esito["warnings"])

    def test_oltre_100k_fuoriuscita_immediata(self, gestore):
        # Art. 1, c. 71, secondo periodo, L. 190/2014: oltre 100.000 euro
        # l'imposta sostitutiva non e' applicabile per l'anno stesso.
        esito = gestore.calcola_regime_forfettario({"forf_ricavi": "120000", "forf_gruppo": "costruzioni"})
        assert esito["regime_applicabile"] is False
        assert any("IMMEDIATA" in w and "IRPEF ordinaria" in w for w in esito["warnings"])


class TestFatturaAgente:
    def test_base_ordinaria_50(self, gestore):
        esito = gestore.calcola_fattura_agente({"age_provvigioni": "10000"})
        assert esito["ritenuta_acconto"] == pytest.approx(10000 * 0.5 * 0.23)
        assert esito["enasarco_agente"] == pytest.approx(850.0)
        assert esito["netto_a_pagare"] == pytest.approx(10000 + 2200 - 1150 - 850)

    def test_base_ridotta_20_con_collaboratori(self, gestore):
        esito = gestore.calcola_fattura_agente({"age_provvigioni": "10000", "age_collaboratori": "1"})
        assert esito["base_ritenuta_percent"] == 20.0
        assert esito["ritenuta_acconto"] == pytest.approx(10000 * 0.2 * 0.23)


class TestPrestazioneOccasionale:
    def test_con_ritenuta_e_bollo(self, gestore):
        esito = gestore.calcola_prestazione_occasionale({"occ_compenso": "1000"})
        assert esito["ritenuta_acconto"] == pytest.approx(200.0)
        assert esito["bollo"] == 2.0
        assert esito["netto_percepito"] == pytest.approx(798.0)

    def test_rimborsi_concorrono_alla_base_ritenuta(self, gestore):
        # Art. 25 D.P.R. 600/1973: "compensi comunque denominati" — i rimborsi
        # generici entrano nella base della ritenuta.
        esito = gestore.calcola_prestazione_occasionale({"occ_compenso": "1000", "occ_rimborsi": "200"})
        assert esito["base_ritenuta"] == pytest.approx(1200.0)
        assert esito["ritenuta_acconto"] == pytest.approx(240.0)

    def test_anticipazioni_documentate_escluse(self, gestore):
        # R.M. 49/E/2013: le anticipazioni in nome e per conto restano fuori.
        esito = gestore.calcola_prestazione_occasionale(
            {"occ_compenso": "1000", "occ_rimborsi": "200", "occ_anticipazioni": "1"}
        )
        assert esito["base_ritenuta"] == pytest.approx(1000.0)
        assert esito["ritenuta_acconto"] == pytest.approx(200.0)

    def test_sotto_soglia_senza_bollo(self, gestore):
        esito = gestore.calcola_prestazione_occasionale({"occ_compenso": "70"})
        assert esito["bollo"] == 0.0

    def test_committente_privato_senza_ritenuta(self, gestore):
        esito = gestore.calcola_prestazione_occasionale({"occ_compenso": "1000", "occ_sostituto": "0"})
        assert esito["ritenuta_acconto"] == 0.0

    def test_fonte_art_25_non_25bis(self, gestore):
        esito = gestore.calcola_prestazione_occasionale({"occ_compenso": "100"})
        codici = {f["code"] for f in esito["sources"]}
        assert "dpr_600_1973_art25" in codici
        assert "dpr_600_1973_art25bis" not in codici

    def test_gestione_separata_avvisata_anche_se_genuina(self, gestore):
        esito = gestore.calcola_prestazione_occasionale({"occ_compenso": "6000"})
        testo = " ".join(esito["warnings"])
        assert "44" in testo and "269/2003" in testo


class TestUtilityPannello:
    def test_variazione_media_fatturato(self):
        from web.services.applicazioni_runtime import _utility_result

        esito = _utility_result(
            {"id": "variazione_media_fatturato"}, {"utility_valori": "50000; 55000; 52250"}
        )
        media = next(m for m in esito["metrics"] if m["label"] == "Variazione media")
        # +10% e -5% → media +2,5%
        assert "+2,50%" in media["value"]

    def test_ora_inizio_fine_con_pausa(self):
        from web.services.applicazioni_runtime import _utility_result

        esito = _utility_result(
            {"id": "calcolo_ora_inizio_fine_attivita"},
            {"utility_ora_inizio": "09:00", "utility_ora_fine": "17:30", "utility_pausa": "60"},
        )
        netta = next(m for m in esito["metrics"] if m["label"] == "Durata netta")
        assert netta["value"] == "7h 30m"

    def test_frazioni_somma(self):
        from web.services.applicazioni_runtime import _utility_result

        esito = _utility_result(
            {"id": "calcolatore_per_frazioni"},
            {"utility_frazione_a": "3/4", "utility_operazione": "+", "utility_frazione_b": "1/6"},
        )
        risultato = next(m for m in esito["metrics"] if m["label"] == "Risultato")
        assert risultato["value"] == "11/12"

    def test_conversione_ettari(self):
        from web.services.applicazioni_runtime import _utility_result

        esito = _utility_result(
            {"id": "conversione_unita_di_misura"},
            {"utility_valore": "25000", "utility_conversione": "mq_ettari"},
        )
        risultato = next(m for m in esito["metrics"] if m["label"] == "Risultato")
        assert "2,5" in risultato["value"]

    def test_giorni_lavorativi_escludono_festivita(self):
        from web.services.applicazioni_runtime import _utility_result

        # 24/12/2026 (gio) - 28/12/2026 (lun): feriali = gio+ven+lun = 3;
        # il 25/12 (ven) è Natale → lavorativi = 2 (giovedì 24 e lunedì 28).
        esito = _utility_result(
            {"id": "calcolo_giorni_lavorativi"},
            {"utility_data_inizio": "2026-12-24", "utility_data_fine": "2026-12-28"},
        )
        lavorativi = next(m for m in esito["metrics"] if m["label"] == "Giorni lavorativi")
        assert lavorativi["value"] == "2"

    def test_pasqua_e_pasquetta_escluse(self):
        from web.services.applicazioni_runtime import _festivita_nazionali, _pasqua
        from datetime import date

        # Pasqua 2026: 5 aprile (domenica) — verifica del metodo di Gauss.
        assert _pasqua(2026) == date(2026, 4, 5)
        assert date(2026, 4, 6) in _festivita_nazionali(2026)  # lunedì dell'Angelo

    def test_eta_anagrafica_anni_e_mesi(self):
        from web.services.applicazioni_runtime import _utility_result

        esito = _utility_result(
            {"id": "calcolo_eta_anagrafica"},
            {"utility_data_inizio": "1980-03-15", "utility_data_fine": "2026-08-16"},
        )
        eta = next(m for m in esito["metrics"] if m["label"] == "Età")
        assert eta["value"] == "46 anni e 5 mesi"


class TestRegistrazioneLotto2B2:
    TOOLS = {
        "irpef": "calcola_irpef_lorda",
        "acconto_imposte": "calcola_acconto_imposte",
        "rateazione_imposte": "calcola_rateazione_imposte",
        "detrazioni_familiari": "calcola_detrazioni_familiari",
        "detrazioni_reddito": "calcola_detrazioni_reddito",
        "detrazione_canone": "calcola_detrazione_canone",
        "regime_forfettario": "calcola_regime_forfettario",
        "fattura_agente": "calcola_fattura_agente",
        "prestazione_occasionale": "calcola_prestazione_occasionale",
    }

    def test_tool_methods_catalogo_e_schemi(self, gestore):
        from pct.calcolatori.schema import SCHEMI_CALCOLATORI
        from web.blueprints.strumenti_legali import TOOL_METHODS

        ids_catalogo = {m["id"] for m in gestore.catalogo_moduli()}
        for tool_id, metodo in self.TOOLS.items():
            assert TOOL_METHODS.get(tool_id) == metodo, f"{tool_id} non registrato"
            assert hasattr(GestioneStrumentiLegali, metodo), f"{metodo} mancante"
            assert tool_id in ids_catalogo, f"{tool_id} fuori dal catalogo moduli"
            assert SCHEMI_CALCOLATORI.get(tool_id, {}).get("campi"), f"{tool_id} senza schema React"

    def test_fonti_dichiarate(self, gestore):
        esempi = {
            "irpef": {"irpef_reddito": "20000"},
            "acconto_imposte": {"acc_rigo_differenza": "1000"},
            "rateazione_imposte": {"rate_importo": "1000", "rate_numero": "3"},
            "detrazioni_familiari": {"detfam_reddito": "20000", "detfam_coniuge": "1"},
            "detrazioni_reddito": {"detred_reddito": "20000"},
            "detrazione_canone": {"detcan_reddito": "14000"},
            "regime_forfettario": {"forf_ricavi": "20000"},
            "fattura_agente": {"age_provvigioni": "1000"},
            "prestazione_occasionale": {"occ_compenso": "100"},
        }
        from web.blueprints.strumenti_legali import TOOL_METHODS

        for tool_id, payload in esempi.items():
            esito = getattr(gestore, TOOL_METHODS[tool_id])(payload)
            assert esito.get("sources"), f"{tool_id} senza fonti dichiarate"

    def test_catalogo_applicazioni_lotto2b2(self):
        from pct.applicazioni_catalogo import _LOTTO2B2_DEEP_LINKS, catalogo_applicazioni
        from web.blueprints.strumenti_legali import TOOL_METHODS
        from web.services.applicazioni_runtime import _utility_form

        entries = {e["id"]: e for e in catalogo_applicazioni()}
        for slug, override in _LOTTO2B2_DEEP_LINKS.items():
            entry = entries.get(slug)
            assert entry is not None, f"voce '{slug}' scomparsa dal catalogo"
            assert entry["status"] == override["status"], f"{slug}: status non applicato"
            params = override.get("params") or {}
            if override.get("endpoint") == "strumenti_legali.index":
                assert params.get("tool") in TOOL_METHODS, f"{slug}: tool inesistente"
            elif override.get("endpoint") == "applicazioni.dettaglio":
                app_id = params.get("app_id")
                assert app_id in entries, f"{slug}: app_id '{app_id}' non nel catalogo"
                campi = _utility_form(app_id)
                assert campi and campi[0]["name"] != "utility_query", (
                    f"{slug}: la scheda '{app_id}' non ha un pannello utility dedicato"
                )
