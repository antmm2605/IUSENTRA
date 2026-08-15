"""Test del Lotto 2A strumenti legali: utilita' e viste tabellari.

Copre i tool aggiunti con l'inventario del catalogo funzioni del 15/08/2026:
interessi convenzionali (art. 1284 c.3 c.c.), conta giorni, scorporo IVA
(D.P.R. 633/1972), percentuali, codice fiscale (D.M. 23/12/1976, riuso di
pct/codice_fiscale), tabella indici ISTAT e tabella tassi di interesse.
"""

from __future__ import annotations

import pytest

from pct.strumenti_legali import GestioneStrumentiLegali


@pytest.fixture()
def gestore(tmp_path):
    return GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tabelle_normative.json"))


class TestInteressiConvenzionali:
    def test_anno_intero_pro_rata(self, gestore):
        esito = gestore.calcola_interessi(
            {
                "int_tipo": "convenzionale",
                "int_capitale": "10000",
                "int_data_inizio": "2026-01-01",
                "int_data_fine": "2026-12-31",
                "int_tasso": "5",
            }
        )
        assert esito["total_interest"] == pytest.approx(500.0, abs=0.01)
        assert esito["total_amount"] == pytest.approx(10500.0, abs=0.01)
        assert len(esito["segments"]) == 1
        assert esito["segments"][0]["rate"] == 5.0

    def test_warning_forma_scritta_e_usura(self, gestore):
        esito = gestore.calcola_interessi(
            {
                "int_tipo": "convenzionale",
                "int_capitale": "1000",
                "int_data_inizio": "2026-01-01",
                "int_data_fine": "2026-06-30",
                "int_tasso": "8",
            }
        )
        testo = " ".join(esito["warnings"]).lower()
        assert "1284" in testo
        assert "usura" in testo or "108/1996" in testo

    def test_tasso_mancante_o_fuori_range(self, gestore):
        base = {
            "int_tipo": "convenzionale",
            "int_capitale": "1000",
            "int_data_inizio": "2026-01-01",
            "int_data_fine": "2026-06-30",
        }
        with pytest.raises(ValueError):
            gestore.calcola_interessi(dict(base))
        with pytest.raises(ValueError):
            gestore.calcola_interessi({**base, "int_tasso": "250"})


class TestContaGiorni:
    def test_conteggio_base(self, gestore):
        esito = gestore.calcola_conta_giorni(
            {"giorni_data_inizio": "2026-01-01", "giorni_data_fine": "2026-03-01"}
        )
        assert esito["days"] == 59
        assert esito["days_inclusive"] == 60
        assert esito["weeks"] == 8
        assert esito["weeks_remainder_days"] == 3
        assert esito["months_full"] == 2

    def test_date_invertite_normalizzate(self, gestore):
        esito = gestore.calcola_conta_giorni(
            {"giorni_data_inizio": "2026-03-01", "giorni_data_fine": "2026-01-01"}
        )
        assert esito["days"] == 59
        assert esito["start_date"] == "2026-01-01"

    def test_warning_termini_processuali(self, gestore):
        esito = gestore.calcola_conta_giorni(
            {"giorni_data_inizio": "2026-01-01", "giorni_data_fine": "2026-01-02"}
        )
        assert any("termini processuali" in w.lower() for w in esito["warnings"])

    def test_data_mancante(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_conta_giorni({"giorni_data_inizio": "2026-01-01"})


class TestScorporoIva:
    def test_scorporo_22(self, gestore):
        esito = gestore.calcola_scorporo_iva(
            {"iva_importo": "1220", "iva_aliquota": "22", "iva_verso": "scorporo"}
        )
        assert esito["imponibile"] == pytest.approx(1000.0)
        assert esito["iva"] == pytest.approx(220.0)
        assert esito["lordo"] == pytest.approx(1220.0)

    def test_aggiunta_10(self, gestore):
        esito = gestore.calcola_scorporo_iva(
            {"iva_importo": "500", "iva_aliquota": "10", "iva_verso": "aggiunta"}
        )
        assert esito["iva"] == pytest.approx(50.0)
        assert esito["lordo"] == pytest.approx(550.0)

    def test_aliquota_non_vigente_rifiutata(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_scorporo_iva({"iva_importo": "100", "iva_aliquota": "21"})

    def test_importo_non_positivo(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_scorporo_iva({"iva_importo": "0", "iva_aliquota": "22"})


class TestPercentuali:
    def test_quota(self, gestore):
        esito = gestore.calcola_percentuali({"perc_base": "200", "perc_percento": "15"})
        assert esito["quota"] == pytest.approx(30.0)

    def test_incidenza_e_variazione(self, gestore):
        esito = gestore.calcola_percentuali({"perc_base": "200", "perc_parte": "250"})
        assert esito["incidenza"] == pytest.approx(125.0)
        assert esito["variazione"] == pytest.approx(25.0)

    def test_input_insufficienti(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_percentuali({"perc_base": "200"})


class TestCodiceFiscale:
    def test_calcolo_e_decodifica_roundtrip(self, gestore):
        calcolo = gestore.calcola_codice_fiscale(
            {
                "cf_cognome": "Rossi",
                "cf_nome": "Mario",
                "cf_sesso": "M",
                "cf_data_nascita": "1980-01-01",
                "cf_luogo": "Roma",
                "cf_provincia": "RM",
            }
        )
        assert calcolo["operazione"] == "calcolo"
        cf = calcolo["codice_fiscale"]
        assert len(cf) == 16
        decodifica = gestore.calcola_codice_fiscale({"cf_codice": cf})
        assert decodifica["operazione"] == "decodifica"
        assert decodifica["sesso"] == "M"
        assert decodifica["data_nascita"] == "1980-01-01"
        assert decodifica["luogo_nascita"].lower() == "roma"

    def test_codice_malformato(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_codice_fiscale({"cf_codice": "NONVALIDO"})

    def test_dati_insufficienti(self, gestore):
        with pytest.raises(ValueError):
            gestore.calcola_codice_fiscale({"cf_cognome": "Rossi"})


class TestTabelleNormative:
    def test_tabella_istat_struttura(self, gestore):
        esito = gestore.tabella_variazioni_istat({"istat_tipo": "FOI", "istat_anni": "3"})
        assert esito["tipo"] == "foi"
        assert esito["ultimo_disponibile"]["anno"] >= 2024
        assert 1 <= len(esito["anni"]) <= 3
        for blocco in esito["anni"]:
            assert blocco["mesi"], f"anno {blocco['anno']} senza mesi"
            for riga in blocco["mesi"]:
                assert riga["indice"] > 0

    def test_tabella_istat_clamp_anni(self, gestore):
        esito = gestore.tabella_variazioni_istat({"istat_anni": "99"})
        assert len(esito["anni"]) <= 15

    def test_tabella_tassi_vista_filtrata(self, gestore):
        solo_legali = gestore.tabella_tassi_interesse({"tassi_vista": "legali"})
        assert solo_legali["tassi_legali"] and not solo_legali["tassi_moratori"]
        solo_moratori = gestore.tabella_tassi_interesse({"tassi_vista": "moratori"})
        assert solo_moratori["tassi_moratori"] and not solo_moratori["tassi_legali"]

    def test_tabella_tassi_con_fonti(self, gestore):
        esito = gestore.tabella_tassi_interesse({})
        assert esito["tassi_legali"], "storico tassi legali vuoto"
        assert esito["tassi_moratori"], "storico tassi moratori vuoto"
        assert esito["sources"], "fonti ufficiali mancanti"
        for riga in esito["tassi_legali"]:
            assert riga["dal"] < riga["al"]
            assert riga["fonte"].get("url")
        for fonte in esito["sources"]:
            assert fonte.get("title") and fonte.get("url")


class TestRegistrazioneBlueprint:
    def test_tool_methods_include_lotto2a(self):
        from web.blueprints.strumenti_legali import TOOL_METHODS

        attesi = {
            "conta_giorni": "calcola_conta_giorni",
            "scorporo_iva": "calcola_scorporo_iva",
            "percentuali": "calcola_percentuali",
            "codice_fiscale": "calcola_codice_fiscale",
            "tabella_istat": "tabella_variazioni_istat",
            "tabella_tassi": "tabella_tassi_interesse",
        }
        for tool_id, metodo in attesi.items():
            assert TOOL_METHODS.get(tool_id) == metodo
            assert hasattr(GestioneStrumentiLegali, metodo)

    def test_catalogo_moduli_include_lotto2a(self, gestore):
        ids = {m["id"] for m in gestore.catalogo_moduli()}
        for tool_id in ("conta_giorni", "scorporo_iva", "percentuali", "codice_fiscale", "tabella_istat", "tabella_tassi"):
            assert tool_id in ids


class TestCatalogoApplicazioniLotto2A:
    """Guardia fail-closed sulle riclassifiche del Lotto 2A."""

    def test_deep_link_strumenti_puntano_a_tool_reali(self):
        from pct.applicazioni_catalogo import _LOTTO2A_DEEP_LINKS
        from web.blueprints.strumenti_legali import TOOL_METHODS

        for slug, override in _LOTTO2A_DEEP_LINKS.items():
            if override.get("endpoint") == "strumenti_legali.index":
                tool = (override.get("params") or {}).get("tool")
                if tool:
                    assert tool in TOOL_METHODS, f"{slug}: tool '{tool}' inesistente"

    def test_deep_link_schede_puntano_a_voci_con_pannello(self):
        from pct.applicazioni_catalogo import _LOTTO2A_DEEP_LINKS, catalogo_applicazioni
        from web.services.applicazioni_runtime import _utility_form

        ids = {e["id"] for e in catalogo_applicazioni()}
        for slug, override in _LOTTO2A_DEEP_LINKS.items():
            if override.get("endpoint") == "applicazioni.dettaglio":
                app_id = (override.get("params") or {}).get("app_id")
                assert app_id in ids, f"{slug}: app_id '{app_id}' non nel catalogo"
                assert _utility_form(app_id), f"{slug}: la scheda '{app_id}' non ha pannello utility"

    def test_operative_lotto2a_hanno_endpoint(self):
        from pct.applicazioni_catalogo import _LOTTO2A_DEEP_LINKS, catalogo_applicazioni

        entries = {e["id"]: e for e in catalogo_applicazioni()}
        for slug, override in _LOTTO2A_DEEP_LINKS.items():
            entry = entries.get(slug)
            assert entry is not None, f"voce '{slug}' scomparsa dal catalogo"
            assert entry["status"] == override["status"], f"{slug}: status non applicato"
            if entry["status"] == "operativa":
                assert entry.get("endpoint"), f"{slug}: operativa senza endpoint"
