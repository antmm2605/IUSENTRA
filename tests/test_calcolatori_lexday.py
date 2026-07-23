"""Test dei calcolatori modulari (pct/calcolatori/) e dei nuovi termini.

Copre i moduli introdotti con l'analisi comparativa LexDay:
interessi con acconti, maggior danno, danno parentale, usufrutto,
quote di riserva, assegno di mantenimento, template termini aggiuntivi
e wiring applicativo (catalogo, schemi React, normalizzazione risultati).
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.calcolatori import (  # noqa: E402
    assegno_mantenimento,
    danno_parentale,
    interessi_acconti,
    maggior_danno,
    quote_riserva,
    usufrutto,
)
from pct.normative_tables import GestioneTabelleNormative  # noqa: E402
from pct.termini_processuali import (  # noqa: E402
    DEFAULT_TEMPLATES,
    DeadlinePracticeRepository,
    ItalianDeadlineCalculator,
)

NUOVI_TOOL = (
    "interessi_acconti",
    "maggior_danno",
    "danno_parentale",
    "usufrutto",
    "quote_riserva",
    "assegno_mantenimento",
)


@pytest.fixture()
def norme(tmp_path):
    return GestioneTabelleNormative(db_path=str(tmp_path / "tabelle_normative.json"))


class TestInteressiAcconti:
    def test_imputazione_prima_interessi_poi_capitale(self, norme):
        result = interessi_acconti.calcola(
            {
                "acc_capitale": "10000",
                "acc_data_inizio": "2024-01-01",
                "acc_data_fine": "2025-12-31",
                "acc_tipo": "legali",
                "acc_acconti": "15/06/2024 3000\n2025-03-01;2000",
            },
            norme,
        )
        assert result["numero_acconti"] == 2
        prima = result["imputazioni"][0]
        assert prima["quota_interessi"] > 0
        assert prima["quota_interessi"] + prima["quota_capitale"] == pytest.approx(3000, abs=0.01)
        assert result["residuo_capitale"] < 10000
        assert result["totale_residuo"] == pytest.approx(
            result["residuo_capitale"] + result["residuo_interessi"], abs=0.01
        )

    def test_acconto_copre_tutto_con_eccedenza(self, norme):
        result = interessi_acconti.calcola(
            {
                "acc_capitale": "1000",
                "acc_data_inizio": "2025-01-01",
                "acc_data_fine": "2025-12-31",
                "acc_tipo": "legali",
                "acc_acconti": "30/06/2025 5000",
            },
            norme,
        )
        assert result["residuo_capitale"] == 0
        assert result["residuo_interessi"] == 0
        assert any("eccedenza" in warning.lower() for warning in result["warnings"])

    def test_tasso_1284_comma_4_usa_tabella_mora(self, norme):
        result = interessi_acconti.calcola(
            {
                "acc_capitale": "10000",
                "acc_data_inizio": "2025-02-01",
                "acc_data_fine": "2025-05-31",
                "acc_tipo": "legali_1284_4",
                "acc_acconti": "",
            },
            norme,
        )
        assert "1284" in result["label"]
        assert result["segments"][0]["rate"] > 5  # tasso maggiorato ex D.Lgs. 231/2002

    def test_riga_acconto_malformata(self, norme):
        with pytest.raises(ValueError):
            interessi_acconti.calcola(
                {
                    "acc_capitale": "1000",
                    "acc_data_inizio": "2025-01-01",
                    "acc_data_fine": "2025-12-31",
                    "acc_tipo": "legali",
                    "acc_acconti": "solo-testo-senza-importo",
                },
                norme,
            )

    def test_acconto_fuori_periodo(self, norme):
        with pytest.raises(ValueError):
            interessi_acconti.calcola(
                {
                    "acc_capitale": "1000",
                    "acc_data_inizio": "2025-01-01",
                    "acc_data_fine": "2025-12-31",
                    "acc_tipo": "legali",
                    "acc_acconti": "01/01/2020 100",
                },
                norme,
            )


class TestMaggiorDanno:
    BASE = {
        "md_importo": "10000",
        "md_anno_base": "2024",
        "md_mese_base": "1",
        "md_anno_fine": "2025",
        "md_mese_fine": "3",
        "md_tipo_indice": "foi",
    }

    def test_totale_somma_rivalutato_e_interessi(self, norme):
        result = maggior_danno.calcola({**self.BASE, "md_base_interessi": "rivalutato_annuale"}, norme)
        assert result["importo_rivalutato"] > result["importo_originale"]
        assert result["totale"] == pytest.approx(
            result["importo_rivalutato"] + result["totale_interessi"], abs=0.01
        )

    def test_base_originario_produce_interessi_minori(self, norme):
        originario = maggior_danno.calcola({**self.BASE, "md_base_interessi": "originario"}, norme)
        rivalutato = maggior_danno.calcola({**self.BASE, "md_base_interessi": "rivalutato_annuale"}, norme)
        assert originario["totale_interessi"] < rivalutato["totale_interessi"]

    def test_indice_mancante_blocca(self, norme):
        with pytest.raises(ValueError):
            maggior_danno.calcola(
                {**self.BASE, "md_anno_base": "1990", "md_base_interessi": "originario"}, norme
            )


class TestDannoParentale:
    def test_cap_al_massimale_categoria(self):
        result = danno_parentale.calcola(
            {
                "dp_categoria": "nucleo_primario",
                "dp_eta_vittima": "20",
                "dp_eta_congiunto": "20",
                "dp_convivenza": "1",
                "dp_unico_superstite": "1",
                "dp_qualita_relazione": "eccezionale",
            }
        )
        assert result["punti_totali"] > result["punti_max"]
        assert result["punti_liquidati"] == result["punti_max"]
        assert result["importo"] == pytest.approx(result["massimale_categoria"], abs=0.01)
        assert any("massimo" in warning.lower() for warning in result["warnings"])

    def test_categoria_altri_congiunti_ha_valore_punto_ridotto(self):
        base = {
            "dp_eta_vittima": "45",
            "dp_eta_congiunto": "48",
            "dp_convivenza": "0",
            "dp_unico_superstite": "0",
            "dp_qualita_relazione": "ordinaria",
        }
        primario = danno_parentale.calcola({**base, "dp_categoria": "nucleo_primario"})
        collaterale = danno_parentale.calcola({**base, "dp_categoria": "altri_congiunti"})
        assert collaterale["valore_punto"] < primario["valore_punto"]
        assert collaterale["importo"] < primario["importo"]

    def test_eta_obbligatorie(self):
        with pytest.raises(ValueError):
            danno_parentale.calcola({"dp_categoria": "nucleo_primario", "dp_eta_vittima": "0", "dp_eta_congiunto": "40"})


class TestUsufrutto:
    def test_fasce_eta(self, norme):
        giovane = usufrutto.calcola({"usu_valore_piena": "100000", "usu_eta": "25"}, norme)
        anziano = usufrutto.calcola({"usu_valore_piena": "100000", "usu_eta": "85"}, norme)
        assert giovane["percentuale_usufrutto"] == 90.0
        assert anziano["percentuale_usufrutto"] == 20.0
        assert giovane["valore_usufrutto"] + giovane["valore_nuda_proprieta"] == pytest.approx(100000, abs=0.01)

    def test_quota_parziale(self, norme):
        result = usufrutto.calcola({"usu_valore_piena": "150000", "usu_eta": "55", "usu_quota_perc": "50"}, norme)
        assert result["base_calcolo"] == pytest.approx(75000, abs=0.01)
        assert result["valore_usufrutto"] == pytest.approx(75000 * 0.65, abs=0.01)

    def test_coefficiente_coerente_col_tasso(self, norme):
        result = usufrutto.calcola({"usu_valore_piena": "100000", "usu_eta": "70"}, norme)
        assert result["coefficiente"] == pytest.approx(
            result["percentuale_usufrutto"] / result["tasso_legale"], abs=0.01
        )


class TestQuoteRiserva:
    def test_coniuge_e_piu_figli(self):
        result = quote_riserva.calcola(
            {"ris_patrimonio": "300000", "ris_debiti": "20000", "ris_donazioni": "20000", "ris_coniuge": "1", "ris_figli": "2"}
        )
        assert result["massa"] == pytest.approx(300000, abs=0.01)
        quote = {row["label"]: row["quota_percent"] for row in result["rows"]}
        assert quote["Coniuge"] == 25.0
        assert quote["Figli"] == 50.0
        assert result["disponibile_percent"] == 25.0

    def test_figlio_unico_senza_coniuge(self):
        result = quote_riserva.calcola({"ris_patrimonio": "100000", "ris_figli": "1"})
        assert result["rows"][0]["quota_percent"] == 50.0
        assert result["disponibile"] == pytest.approx(50000, abs=0.01)

    def test_coniuge_e_ascendenti(self):
        result = quote_riserva.calcola({"ris_patrimonio": "100000", "ris_coniuge": "1", "ris_ascendenti": "1"})
        quote = {row["label"]: row["quota_percent"] for row in result["rows"]}
        assert quote["Coniuge"] == 50.0
        assert quote["Ascendenti"] == 25.0

    def test_figli_escludono_ascendenti(self):
        result = quote_riserva.calcola({"ris_patrimonio": "100000", "ris_figli": "2", "ris_ascendenti": "1"})
        labels = [row["label"] for row in result["rows"]]
        assert "Ascendenti" not in labels
        assert any("538" in nota for nota in result["notes"])

    def test_serve_almeno_un_legittimario(self):
        with pytest.raises(ValueError):
            quote_riserva.calcola({"ris_patrimonio": "100000"})


class TestAssegnoMantenimento:
    def test_figli_con_riduzioni(self):
        pieno = assegno_mantenimento.calcola(
            {"man_tipo": "figli", "man_reddito_obbligato": "2500", "man_figli": "2"}
        )
        paritetico = assegno_mantenimento.calcola(
            {"man_tipo": "figli", "man_reddito_obbligato": "2500", "man_figli": "2", "man_collocamento_paritetico": "1"}
        )
        assert paritetico["stima_mensile"] < pieno["stima_mensile"]
        assert pieno["stima_annua"] == pytest.approx(pieno["stima_mensile"] * 12, abs=0.01)

    def test_coniuge_senza_divario_stima_zero(self):
        result = assegno_mantenimento.calcola(
            {"man_tipo": "coniuge", "man_reddito_obbligato": "2000", "man_reddito_beneficiario": "2500"}
        )
        assert result["stima_mensile"] == 0.0

    def test_avvertenza_di_stima_sempre_presente(self):
        result = assegno_mantenimento.calcola({"man_tipo": "figli", "man_reddito_obbligato": "2000", "man_figli": "1"})
        assert any("stima" in warning.lower() for warning in result["warnings"])


class TestNuoviTerminiProcessuali:
    NUOVI_CODICI = (
        "CIV_NOTE_CONCLUSIONI_189",
        "CIV_CONCLUSIONALI_189",
        "CIV_REPLICHE_189",
        "FAM_473BIS_COSTITUZIONE",
        "VR_MEMORIA_183_6_N1",
        "VR_MEMORIA_183_6_N2",
        "VR_MEMORIA_183_6_N3",
        "VR_CONCLUSIONALI_190",
        "VR_REPLICHE_190",
        "CDS_PAGAMENTO_RIDOTTO_5GG",
        "CDS_PAGAMENTO_60GG",
        "CDS_RICORSO_PREFETTO_60GG",
        "CDS_RICORSO_GDP_30GG",
        "ESE_PRECETTO_ADEMPIMENTO_10GG",
        "ESE_PRECETTO_EFFICACIA_90GG",
        "ESE_OPPOSIZIONE_ATTI_617",
        "ESE_ISCRIZIONE_RUOLO_MOBILIARE",
        "ESE_ISCRIZIONE_RUOLO_PRESSO_TERZI",
        "ESE_ISCRIZIONE_RUOLO_IMMOBILIARE",
    )

    def test_template_presenti_nei_default(self):
        codes = {template.code for template in DEFAULT_TEMPLATES}
        for code in self.NUOVI_CODICI:
            assert code in codes, code

    def test_conclusionali_189_a_ritroso(self):
        calc = ItalianDeadlineCalculator()
        template = next(t for t in DEFAULT_TEMPLATES if t.code == "CIV_CONCLUSIONALI_189")
        result = calc.calculate_template(date(2026, 10, 15), template)
        assert result["deadline"] < "2026-10-15"

    def test_vecchio_rito_non_cartabia(self):
        for template in DEFAULT_TEMPLATES:
            if template.code.startswith("VR_"):
                assert template.cartabia_compliant is False

    def test_auto_upgrade_repository_json(self, tmp_path):
        path = tmp_path / "termini.json"
        path.write_text(
            json.dumps(
                {
                    "templates": [{"code": "CIV_APPELLO_BREVE", "name": "esistente"}],
                    "audit_logs": [],
                    "notification_logs": [],
                }
            ),
            encoding="utf-8",
        )
        repo = DeadlinePracticeRepository.json(path)
        codes = {row["code"] for row in repo.list_templates()}
        assert "ESE_OPPOSIZIONE_ATTI_617" in codes
        assert "CIV_REPLICHE_189" in codes
        # Il template preesistente non viene sovrascritto.
        esistente = next(row for row in repo.list_templates() if row["code"] == "CIV_APPELLO_BREVE")
        assert esistente["name"] == "esistente"

    def test_auto_upgrade_repository_sqlite(self, tmp_path):
        repo = DeadlinePracticeRepository.sqlite(tmp_path / "termini.sqlite")
        codes = {row["code"] for row in repo.list_templates()}
        for code in self.NUOVI_CODICI:
            assert code in codes, code


class TestWiringApplicativo:
    def test_schemi_metodi_e_catalogo(self, tmp_path):
        from pct.applicazioni_runtime import TOOL_SCHEMAS
        from pct.strumenti_legali import GestioneStrumentiLegali

        gestore = GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tn.json"))
        catalogo = {modulo["id"] for modulo in gestore.catalogo_moduli()}
        for tool_id in NUOVI_TOOL:
            assert tool_id in TOOL_SCHEMAS, tool_id
            assert tool_id in catalogo, tool_id
            assert hasattr(gestore, TOOL_SCHEMAS[tool_id]["method"]), tool_id

    def test_form_state_copre_i_campi_degli_schemi(self, tmp_path):
        from pct.applicazioni_runtime import TOOL_SCHEMAS
        from pct.strumenti_legali import GestioneStrumentiLegali

        gestore = GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tn.json"))
        state = gestore.build_form_state(gestore.build_prefill())
        for tool_id in NUOVI_TOOL:
            for field in TOOL_SCHEMAS[tool_id]["fields"]:
                assert field["name"] in state, f"{tool_id}.{field['name']}"

    def test_build_tool_result_normalizza_i_nuovi_tool(self, tmp_path):
        from pct.applicazioni_runtime import TOOL_SCHEMAS, build_tool_result
        from pct.strumenti_legali import GestioneStrumentiLegali

        gestore = GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tn.json"))
        payloads = {
            "interessi_acconti": {
                "acc_capitale": "10000",
                "acc_data_inizio": "2024-01-01",
                "acc_data_fine": "2025-12-31",
                "acc_tipo": "legali",
                "acc_acconti": "15/06/2024 3000",
            },
            "maggior_danno": {
                "md_importo": "10000",
                "md_anno_base": "2024",
                "md_mese_base": "1",
                "md_anno_fine": "2025",
                "md_mese_fine": "3",
                "md_tipo_indice": "foi",
                "md_base_interessi": "semisomma",
            },
            "danno_parentale": {
                "dp_categoria": "nucleo_primario",
                "dp_eta_vittima": "45",
                "dp_eta_congiunto": "48",
                "dp_convivenza": "1",
                "dp_unico_superstite": "0",
                "dp_qualita_relazione": "intensa",
            },
            "usufrutto": {"usu_valore_piena": "150000", "usu_eta": "55", "usu_quota_perc": "100"},
            "quote_riserva": {"ris_patrimonio": "500000", "ris_coniuge": "1", "ris_figli": "1"},
            "assegno_mantenimento": {
                "man_tipo": "figli",
                "man_reddito_obbligato": "2500",
                "man_figli": "1",
            },
        }
        for tool_id, payload in payloads.items():
            result = getattr(gestore, TOOL_SCHEMAS[tool_id]["method"])(payload)
            assert result["sources"], tool_id
            normalizzato = build_tool_result(tool_id, result)
            assert normalizzato["metrics"], tool_id

    def test_blueprint_tool_methods_allineati(self):
        from web.blueprints.strumenti_legali import TOOL_METHODS

        for tool_id in NUOVI_TOOL:
            assert tool_id in TOOL_METHODS, tool_id
