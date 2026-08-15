"""Test del Lotto 2B-1 strumenti legali: finanza, famiglia, patrimonio.

Copre i 13 tool aggiunti con la seconda tranche dell'inventario catalogo:
TAEG (art. 121 T.U.B.), surroga (art. 120-quater T.U.B.), rivalutazione su
media annua ISTAT, rendimento BOT e pronti contro termine, grado di
parentela (artt. 74-78 c.c.), pensione di reversibilità (Tab. F L.
335/1995), imposte di successione (D.L. 262/2006), valore catastale, IMU
(L. 160/2019), imposte di compravendita, riparto spese e categorie
catastali.
"""

from __future__ import annotations

import pytest

from pct.strumenti_legali import GestioneStrumentiLegali


@pytest.fixture()
def gestore(tmp_path):
    return GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tabelle_normative.json"))


class TestTaeg:
    def test_taeg_senza_spese_coincide_col_tan(self, gestore):
        esito = gestore.calcola_taeg(
            {
                "taeg_capitale": "100000",
                "taeg_tan": "3",
                "taeg_durata_anni": "20",
                "taeg_rate_anno": "12",
            }
        )
        # Senza costi il TAEG e' il TAN composto sui periodi mensili: (1+0.25%)^12-1 ≈ 3.04%
        assert 3.0 <= esito["taeg"] <= 3.1

    def test_spese_alzano_il_taeg(self, gestore):
        base = {
            "taeg_capitale": "100000",
            "taeg_tan": "3",
            "taeg_durata_anni": "20",
            "taeg_rate_anno": "12",
        }
        pulito = gestore.calcola_taeg(dict(base))
        caricato = gestore.calcola_taeg({**base, "taeg_spese_iniziali": "2000", "taeg_spese_rata": "3"})
        assert caricato["taeg"] > pulito["taeg"]
        assert caricato["erogato_netto"] == pytest.approx(98000.0)

    def test_input_invalidi(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_taeg({"taeg_capitale": "0", "taeg_tan": "3", "taeg_durata_anni": "10"})
        with pytest.raises(ValueError):
            gestore.calcola_taeg(
                {"taeg_capitale": "1000", "taeg_tan": "3", "taeg_durata_anni": "10", "taeg_spese_iniziali": "1000"}
            )


class TestSurroga:
    def test_tasso_piu_basso_conviene(self, gestore):
        esito = gestore.calcola_surroga(
            {
                "sur_debito_residuo": "120000",
                "sur_tan_attuale": "4.5",
                "sur_anni_residui": "18",
                "sur_tan_nuovo": "2.8",
            }
        )
        assert esito["conveniente"] is True
        assert esito["risparmio_totale"] > 0
        assert esito["rata_nuova"] < esito["rata_attuale"]

    def test_allungamento_durata_avvisato(self, gestore):
        esito = gestore.calcola_surroga(
            {
                "sur_debito_residuo": "120000",
                "sur_tan_attuale": "3.0",
                "sur_anni_residui": "10",
                "sur_tan_nuovo": "2.9",
                "sur_anni_nuovi": "25",
            }
        )
        testo = " ".join(esito["warnings"]).lower()
        assert "durata" in testo

    def test_offerta_peggiore_segnalata(self, gestore):
        esito = gestore.calcola_surroga(
            {
                "sur_debito_residuo": "100000",
                "sur_tan_attuale": "2.0",
                "sur_anni_residui": "10",
                "sur_tan_nuovo": "4.0",
            }
        )
        assert esito["conveniente"] is False
        assert any("non" in w.lower() for w in esito["warnings"])


class TestRivalutazioneMedia:
    def test_media_annua_su_anni_coperti(self, gestore):
        esito = gestore.calcola_rivalutazione_media(
            {"rivm_importo": "10000", "rivm_anno_base": "2023", "rivm_anno_target": "2024", "rivm_tipo": "FOI"}
        )
        assert esito["importo_rivalutato"] > 10000
        assert esito["coefficiente"] == pytest.approx(
            esito["media_anno_target"] / esito["media_anno_base"], rel=1e-4
        )

    def test_anno_scoperto_fail_closed(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_rivalutazione_media(
                {"rivm_importo": "10000", "rivm_anno_base": "1990", "rivm_anno_target": "2024"}
            )

    def test_anno_target_parziale_stima_provvisoria(self, gestore):
        esito = gestore.calcola_rivalutazione_media(
            {"rivm_importo": "10000", "rivm_anno_base": "2024", "rivm_anno_target": "2025"}
        )
        assert esito["stima_provvisoria"] is True
        assert any("PROVVISORIA" in w for w in esito["warnings"])

    def test_anno_base_parziale_fail_closed(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_rivalutazione_media(
                {"rivm_importo": "10000", "rivm_anno_base": "2025", "rivm_anno_target": "2025"}
            )

    def test_importo_liquidabile_mai_sotto_nominale(self, gestore):
        esito = gestore.calcola_rivalutazione_media(
            {"rivm_importo": "10000", "rivm_anno_base": "2023", "rivm_anno_target": "2024"}
        )
        assert esito["importo_liquidabile"] >= esito["importo_base"]


class TestTitoliRendimenti:
    def test_bot_rendimento_e_imposta(self, gestore):
        esito = gestore.calcola_rendimento_bot(
            {"bot_prezzo": "98.5", "bot_giorni": "180", "bot_nominale": "10000"}
        )
        # Scarto 1,5 per 100 → 150 sul nominale; imposta sostitutiva 12,5% = 18,75,
        # anticipata alla sottoscrizione e quindi inclusa nell'esborso.
        assert esito["imposta_sostitutiva"] == pytest.approx(18.75)
        assert esito["aliquota_imposta"] == 12.5
        assert esito["esborso_totale"] == pytest.approx(9850 + 18.75)
        assert esito["rendimento_netto_annuo"] < esito["rendimento_lordo_annuo"]

    def test_bot_commissioni_possono_azzerare(self, gestore):
        esito = gestore.calcola_rendimento_bot(
            {"bot_prezzo": "99.9", "bot_giorni": "90", "bot_commissioni": "0.5"}
        )
        assert esito["guadagno_netto"] < 0
        assert esito["warnings"]

    def test_pct_ritenuta_26(self, gestore):
        esito = gestore.calcola_pronti_contro_termine(
            {"pct_prezzo_pronti": "10000", "pct_prezzo_termine": "10150", "pct_giorni": "90"}
        )
        assert esito["aliquota_ritenuta"] == 26.0
        assert esito["ritenuta_fiscale"] == pytest.approx(39.0)
        assert esito["provento_netto"] == pytest.approx(111.0)


class TestGradoParentela:
    @pytest.mark.parametrize(
        "relazione,grado_atteso",
        [
            ("genitore_figlio", 1),
            ("nonno_nipote", 2),
            ("fratelli", 2),
            ("zio_nipote", 3),
            ("cugini", 4),
            ("cugini_secondi", 6),
        ],
    )
    def test_relazioni_tipiche(self, gestore, relazione, grado_atteso):
        esito = gestore.calcola_grado_parentela({"par_relazione": relazione})
        assert esito["grado"] == grado_atteso

    def test_manuale_linea_retta(self, gestore):
        esito = gestore.calcola_grado_parentela(
            {"par_relazione": "manuale", "par_linea": "retta", "par_generazioni_su": "3"}
        )
        assert esito["grado"] == 3

    def test_oltre_sesto_grado_avvisato(self, gestore):
        esito = gestore.calcola_grado_parentela(
            {"par_relazione": "manuale", "par_linea": "collaterale", "par_generazioni_su": "4", "par_generazioni_giu": "4"}
        )
        assert esito["grado"] == 8
        assert any("77" in w or "sesto" in w for w in esito["warnings"])

    def test_collaterale_richiede_entrambi_i_rami(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_grado_parentela(
                {"par_relazione": "manuale", "par_linea": "collaterale", "par_generazioni_su": "2"}
            )


class TestReversibilita:
    @pytest.mark.parametrize(
        "coniuge,figli,attesa",
        [("1", "0", 60.0), ("1", "1", 80.0), ("1", "2", 100.0), ("0", "1", 70.0), ("0", "2", 80.0), ("0", "3", 100.0)],
    )
    def test_aliquote_tabella_f(self, gestore, coniuge, figli, attesa):
        esito = gestore.calcola_reversibilita(
            {"rev_pensione_annua": "10000", "rev_coniuge": coniuge, "rev_figli": figli}
        )
        assert esito["aliquota"] == attesa

    def test_salvaguardia_di_fascia(self, gestore):
        # Reddito appena oltre 3 volte il minimo: la riduzione piena del 25%
        # porterebbe il trattamento sotto quello spettante al limite di fascia
        # → clausola di salvaguardia (art. 1, c. 41, terzo periodo, L. 335/1995).
        esito = gestore.calcola_reversibilita(
            {
                "rev_pensione_annua": "20000",
                "rev_coniuge": "1",
                "rev_reddito_beneficiario": "23500",
                "rev_trattamento_minimo": "7800",
            }
        )
        assert esito["riduzione_cumulo"] == pytest.approx(100.0)  # 23500 - 23400
        assert any("salvaguardia" in w for w in esito["warnings"])

    def test_salvaguardia_in_cascata_seconda_fascia(self, gestore):
        # Reddito appena oltre 4 volte il minimo (31.300 con TM 7.800 → 4TM=31.200):
        # riduzione piena 40% = 4.800; salvaguardia: t(31.200) − 100.
        # t(31.200) = max(12.000×0.75, 12.000 − (31.200−23.400)) = 9.000
        # → t(31.300) = max(7.200, 9.000 − 100) = 8.900; riduzione = 3.100.
        esito = gestore.calcola_reversibilita(
            {
                "rev_pensione_annua": "20000",
                "rev_coniuge": "1",
                "rev_reddito_beneficiario": "31300",
                "rev_trattamento_minimo": "7800",
            }
        )
        assert esito["reversibilita_spettante"] == pytest.approx(8900.0)
        assert esito["riduzione_cumulo"] == pytest.approx(3100.0)

    @pytest.mark.parametrize("reddito", ["3100", "5100", "9000", "50000"])
    def test_cap_corte_cost_162_2022_mai_violato(self, gestore, reddito):
        # Corte Cost. 162/2022: la decurtazione non può eccedere i redditi
        # aggiuntivi. Con la salvaguardia di fascia in cascata la garanzia è
        # strutturale: la verifichiamo come proprietà su più fasce.
        esito = gestore.calcola_reversibilita(
            {
                "rev_pensione_annua": "200000",
                "rev_coniuge": "1",
                "rev_reddito_beneficiario": reddito,
                "rev_trattamento_minimo": "1000",
            }
        )
        assert esito["riduzione_cumulo"] <= float(reddito) + 0.01

    def test_figli_escludono_cumulo(self, gestore):
        esito = gestore.calcola_reversibilita(
            {
                "rev_pensione_annua": "20000",
                "rev_coniuge": "1",
                "rev_figli": "1",
                "rev_reddito_beneficiario": "100000",
            }
        )
        assert esito["riduzione_cumulo"] == 0.0

    def test_cumulo_senza_minimo_fail_closed(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_reversibilita(
                {"rev_pensione_annua": "20000", "rev_coniuge": "1", "rev_reddito_beneficiario": "50000"}
            )


class TestImposteSuccessione:
    def test_coniuge_franchigia_milione(self, gestore):
        esito = gestore.calcola_imposte_successione(
            {"succ_quota": "1200000", "succ_rapporto": "coniuge_linea_retta"}
        )
        assert esito["franchigia"] == 1_000_000.0
        assert esito["imponibile"] == 200_000.0
        assert esito["imposta_successione"] == pytest.approx(8000.0)

    def test_fratello_franchigia_centomila(self, gestore):
        esito = gestore.calcola_imposte_successione(
            {"succ_quota": "150000", "succ_rapporto": "fratello_sorella"}
        )
        assert esito["imposta_successione"] == pytest.approx(3000.0)  # 50.000 x 6%

    def test_handicap_franchigia_maggiorata(self, gestore):
        esito = gestore.calcola_imposte_successione(
            {"succ_quota": "1400000", "succ_rapporto": "altro", "succ_handicap": "1"}
        )
        assert esito["franchigia"] == 1_500_000.0
        assert esito["imposta_successione"] == 0.0

    def test_ipocatastali_su_immobili(self, gestore):
        esito = gestore.calcola_imposte_successione(
            {"succ_quota": "500000", "succ_rapporto": "coniuge_linea_retta", "succ_valore_immobili": "300000"}
        )
        assert esito["imposta_ipotecaria"] == pytest.approx(6000.0)
        assert esito["imposta_catastale"] == pytest.approx(3000.0)

    def test_prima_casa_ipocatastali_fisse(self, gestore):
        esito = gestore.calcola_imposte_successione(
            {
                "succ_quota": "500000",
                "succ_rapporto": "coniuge_linea_retta",
                "succ_valore_immobili": "300000",
                "succ_prima_casa": "1",
            }
        )
        assert esito["imposta_ipotecaria"] == 200.0
        assert esito["imposta_catastale"] == 200.0


class TestCatastaleImu:
    def test_valore_catastale_prima_casa(self, gestore):
        esito = gestore.calcola_valore_catastale(
            {"cat_rendita": "1000", "cat_gruppo": "abitazione_prima_casa"}
        )
        assert esito["valore_catastale"] == pytest.approx(115_500.0)  # 1000 x 1.05 x 110

    def test_valore_catastale_gruppo_b_per_ambito(self, gestore):
        registro = gestore.calcola_valore_catastale({"cat_rendita": "1000", "cat_gruppo": "gruppo_b"})
        successione = gestore.calcola_valore_catastale(
            {"cat_rendita": "1000", "cat_gruppo": "gruppo_b", "cat_ambito": "successione"}
        )
        # La rivalutazione +40% ex D.L. 262/2006 vale solo per registro/ipocatastali.
        assert registro["moltiplicatore"] == 168.0
        assert successione["moltiplicatore"] == 140.0

    def test_imu_detrazione_per_residenti_non_per_quota(self, gestore):
        esito = gestore.calcola_imu(
            {
                "imu_rendita": "2000",
                "imu_gruppo": "a_non_a10",
                "imu_aliquota": "0.5",
                "imu_abitazione_principale": "1",
                "imu_lusso": "1",
                "imu_quota": "70",
                "imu_residenti": "2",
            }
        )
        # Art. 1, c. 749, L. 160/2019: detrazione in parti uguali tra i residenti,
        # indipendentemente dalla quota di possesso (100 a testa, non 140/60).
        assert esito["detrazione"] == pytest.approx(100.0)

    def test_imu_abitazione_principale_esente(self, gestore):
        esito = gestore.calcola_imu(
            {"imu_rendita": "1000", "imu_gruppo": "a_non_a10", "imu_aliquota": "0.86", "imu_abitazione_principale": "1"}
        )
        assert esito["esito"] == "Esente"

    def test_imu_ordinaria(self, gestore):
        esito = gestore.calcola_imu({"imu_rendita": "1000", "imu_gruppo": "a_non_a10", "imu_aliquota": "0.86"})
        assert esito["base_imponibile"] == pytest.approx(168_000.0)  # 1000 x 1.05 x 160
        assert esito["imposta_annua"] == pytest.approx(1444.8)

    def test_imu_lusso_con_detrazione(self, gestore):
        esito = gestore.calcola_imu(
            {
                "imu_rendita": "2000",
                "imu_gruppo": "a_non_a10",
                "imu_aliquota": "0.5",
                "imu_abitazione_principale": "1",
                "imu_lusso": "1",
            }
        )
        assert esito["detrazione"] == pytest.approx(200.0)
        assert esito["imposta_annua"] == pytest.approx(2000 * 1.05 * 160 * 0.005 - 200)

    def test_categorie_catastali(self, gestore):
        tutte = gestore.tabella_categorie_catastali({})
        gruppo_a = gestore.tabella_categorie_catastali({"catcat_gruppo": "A"})
        assert tutte["totale"] > 40
        assert gruppo_a["totale"] == 11


class TestCompravendita:
    def test_prima_casa_da_privato_prezzo_valore(self, gestore):
        esito = gestore.calcola_imposte_compravendita(
            {
                "comp_regime": "privato",
                "comp_prezzo": "250000",
                "comp_valore_catastale": "130000",
                "comp_prima_casa": "1",
            }
        )
        assert esito["base_imponibile"] == 130_000.0
        registro = next(r for r in esito["dettaglio"] if r["voce"] == "Imposta di registro")
        assert registro["importo"] == pytest.approx(2600.0)  # 2%
        assert esito["totale_imposte"] == pytest.approx(2700.0)

    def test_minimo_registro_mille_euro(self, gestore):
        esito = gestore.calcola_imposte_compravendita(
            {"comp_regime": "privato", "comp_prezzo": "30000", "comp_valore_catastale": "20000", "comp_prima_casa": "1"}
        )
        registro = next(r for r in esito["dettaglio"] if r["voce"] == "Imposta di registro")
        assert registro["importo"] == 1000.0

    def test_iva_prima_casa(self, gestore):
        esito = gestore.calcola_imposte_compravendita(
            {"comp_regime": "iva", "comp_prezzo": "250000", "comp_prima_casa": "1"}
        )
        iva = next(r for r in esito["dettaglio"] if r["voce"] == "IVA")
        assert iva["importo"] == pytest.approx(10_000.0)  # 4%
        assert esito["totale_imposte"] == pytest.approx(10_600.0)

    def test_lusso_esclude_prima_casa(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_imposte_compravendita(
                {"comp_regime": "privato", "comp_prezzo": "500000", "comp_prima_casa": "1", "comp_lusso": "1"}
            )


class TestRipartoSpese:
    def test_millesimi_quadratura(self, gestore):
        esito = gestore.calcola_riparto_spese(
            {
                "rip_importo": "1000",
                "rip_criterio": "millesimi",
                "rip_quote": "Interno 1: 333; Interno 2: 333; Interno 3: 334",
            }
        )
        assert sum(r["importo"] for r in esito["riparto"]) == pytest.approx(1000.0)

    def test_millesimi_non_a_mille_avvisati(self, gestore):
        esito = gestore.calcola_riparto_spese(
            {"rip_importo": "900", "rip_criterio": "millesimi", "rip_quote": "A: 400; B: 500"}
        )
        assert any("1000" in w for w in esito["warnings"])

    def test_nomi_duplicati_rifiutati(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_riparto_spese(
                {"rip_importo": "900", "rip_criterio": "persone", "rip_quote": "A: 2; A: 3"}
            )

    def test_formato_invalido_rifiutato(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_riparto_spese(
                {"rip_importo": "900", "rip_criterio": "persone", "rip_quote": "senza valore"}
            )

    def test_migliaia_italiane_nelle_quote(self, gestore):
        # «1.500» in un campo di testo italiano sono millecinquecento, non 1,5.
        esito = gestore.calcola_riparto_spese(
            {"rip_importo": "2000", "rip_criterio": "giorni", "rip_quote": "A: 1.500; B: 500"}
        )
        importo_a = next(r for r in esito["riparto"] if r["nome"] == "A")["importo"]
        assert importo_a == pytest.approx(1500.0)

    def test_resto_maggiore_distribuisce_arrotondamenti(self, gestore):
        esito = gestore.calcola_riparto_spese(
            {"rip_importo": "100", "rip_criterio": "persone", "rip_quote": "A: 1; B: 1; C: 1"}
        )
        importi = sorted(r["importo"] for r in esito["riparto"])
        assert sum(importi) == pytest.approx(100.0)
        # 33,33 + 33,33 + 33,34: lo scarto va a UNA voce, non tutto sull'ultima.
        assert importi == [33.33, 33.33, 33.34]


class TestRegistrazioneLotto2B:
    TOOLS = {
        "taeg": "calcola_taeg",
        "surroga": "calcola_surroga",
        "rivalutazione_media": "calcola_rivalutazione_media",
        "rendimento_bot": "calcola_rendimento_bot",
        "pronti_contro_termine": "calcola_pronti_contro_termine",
        "grado_parentela": "calcola_grado_parentela",
        "reversibilita": "calcola_reversibilita",
        "imposte_successione": "calcola_imposte_successione",
        "valore_catastale": "calcola_valore_catastale",
        "imu": "calcola_imu",
        "imposte_compravendita": "calcola_imposte_compravendita",
        "riparto_spese": "calcola_riparto_spese",
        "categorie_catastali": "tabella_categorie_catastali",
    }

    def test_tool_methods_e_metodi_reali(self):
        from web.blueprints.strumenti_legali import TOOL_METHODS

        for tool_id, metodo in self.TOOLS.items():
            assert TOOL_METHODS.get(tool_id) == metodo, f"{tool_id} non registrato"
            assert hasattr(GestioneStrumentiLegali, metodo), f"{metodo} mancante"

    def test_catalogo_e_schemi_react(self, gestore):
        from pct.calcolatori.schema import SCHEMI_CALCOLATORI

        ids_catalogo = {m["id"] for m in gestore.catalogo_moduli()}
        for tool_id in self.TOOLS:
            assert tool_id in ids_catalogo, f"{tool_id} fuori dal catalogo moduli"
            assert tool_id in SCHEMI_CALCOLATORI, f"{tool_id} senza schema React"
            assert SCHEMI_CALCOLATORI[tool_id]["campi"], f"{tool_id} con schema vuoto"

    def test_fonti_dichiarate_su_ogni_tool(self, gestore):
        esempi = {
            "taeg": {"taeg_capitale": "1000", "taeg_tan": "3", "taeg_durata_anni": "5"},
            "surroga": {"sur_debito_residuo": "1000", "sur_tan_attuale": "3", "sur_anni_residui": "5", "sur_tan_nuovo": "2"},
            "rivalutazione_media": {"rivm_importo": "1000", "rivm_anno_base": "2023", "rivm_anno_target": "2024"},
            "rendimento_bot": {"bot_prezzo": "99", "bot_giorni": "180"},
            "pronti_contro_termine": {"pct_prezzo_pronti": "1000", "pct_prezzo_termine": "1010", "pct_giorni": "90"},
            "grado_parentela": {"par_relazione": "fratelli"},
            "reversibilita": {"rev_pensione_annua": "10000", "rev_coniuge": "1"},
            "imposte_successione": {"succ_quota": "100000", "succ_rapporto": "coniuge_linea_retta"},
            "valore_catastale": {"cat_rendita": "500", "cat_gruppo": "abitazione_altri"},
            "imu": {"imu_rendita": "500", "imu_gruppo": "c1", "imu_aliquota": "0.86"},
            "imposte_compravendita": {"comp_regime": "privato", "comp_prezzo": "100000"},
            "riparto_spese": {"rip_importo": "100", "rip_criterio": "persone", "rip_quote": "A: 2; B: 3"},
            "categorie_catastali": {},
        }
        from web.blueprints.strumenti_legali import TOOL_METHODS

        for tool_id, payload in esempi.items():
            esito = getattr(gestore, TOOL_METHODS[tool_id])(payload)
            assert esito.get("sources"), f"{tool_id} senza fonti dichiarate"
            for fonte in esito["sources"]:
                assert fonte.get("title") and fonte.get("url"), f"{tool_id}: fonte incompleta"

    def test_catalogo_applicazioni_lotto2b(self):
        from pct.applicazioni_catalogo import _LOTTO2B_DEEP_LINKS, catalogo_applicazioni
        from web.blueprints.strumenti_legali import TOOL_METHODS

        entries = {e["id"]: e for e in catalogo_applicazioni()}
        for slug, override in _LOTTO2B_DEEP_LINKS.items():
            entry = entries.get(slug)
            assert entry is not None, f"voce '{slug}' scomparsa dal catalogo"
            assert entry["status"] == override["status"], f"{slug}: status non applicato"
            tool = (override.get("params") or {}).get("tool")
            if tool:
                assert tool in TOOL_METHODS, f"{slug}: tool '{tool}' inesistente"
