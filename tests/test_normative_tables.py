from pct.normative_tables import GestioneTabelleNormative


def test_catalogo_normativo_seeded(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    snapshot = gestore.snapshot()

    assert snapshot["totali"] >= 16
    assert snapshot["sincronizzate"] >= 16
    assert any(row["id"] == "interesse_legale" for row in snapshot["tabelle"])
    assert any(row["id"] == "riferimenti_normativi_catalogo" for row in snapshot["tabelle"])
    assert any(row["id"] == "registro_organismi_mediazione" for row in snapshot["tabelle"])
    assert any(row["id"] == "organismi_mediazione_elenco" for row in snapshot["tabelle"])
    assert any(row["id"] == "tariffario_forense_scaglioni" for row in snapshot["tabelle"])
    assert any(row["id"] == "tariffario_forense_profili" for row in snapshot["tabelle"])
    assert any(row["id"] == "tariffario_forense_regole" for row in snapshot["tabelle"])
    assert any(row["id"] == "tariffario_forense_audit" for row in snapshot["tabelle"])
    assert any(row["id"] == "tariffario_forense_opzioni" for row in snapshot["tabelle"])
    assert any(row["id"] == "tariffario_forense_riferimenti" for row in snapshot["tabelle"])
    assert any(row["id"] == "tariffario_forense_fatturazione" for row in snapshot["tabelle"])
    assert snapshot["riferimenti_normativi_totali"] >= 8


def test_catalogo_riferimenti_normativi_include_fonti_preventivo(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    riferimenti = gestore.catalogo_riferimenti_normativi()

    assert any(row["title"] == "D.M. 10 marzo 2014, n. 55" for row in riferimenti)
    mediazione = next(row for row in riferimenti if row["title"] == "D.M. 24 ottobre 2023, n. 150")
    assert "Stragiudiziale" in mediazione["areas"]
    assert "mediazione" in mediazione["tipologie_ids"]


def test_sync_normativo_segnala_verifica_su_fonte_variata(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    report = gestore.sync_from_canonical(
        source_runs={
            "gazzetta_ufficiale": {
                "status": "ok",
                "changed": True,
                "checked_at": "2026-04-01T09:30:00",
            }
        },
        source_ids=["gazzetta_ufficiale"],
    )

    assert report["processed_tables"] >= 1
    assert report["review_required"] >= 1
    assert any(row["sync_status"] == "verifica_richiesta" for row in report["tables"])


def test_sync_normativo_con_source_codes_isola_la_tabella_corretta(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    report = gestore.sync_from_canonical(
        source_runs={
            "gazzetta_ufficiale": {
                "status": "ok",
                "changed": True,
                "checked_at": "2026-04-01T09:30:00",
            }
        },
        source_code_runs={
            "interesse_legale_2026": {
                "status": "ok",
                "changed": True,
                "checked_at": "2026-04-01T09:30:00",
            }
        },
        source_ids=["gazzetta_ufficiale"],
    )

    flagged = {row["id"] for row in report["tables"] if row["sync_status"] == "verifica_richiesta"}

    assert "interesse_legale" in flagged
    assert "mora_commerciale" not in flagged
    assert "contributo_unificato_civile" not in flagged


def test_tabella_registro_mediazione_usa_fonte_ufficiale_ministeriale(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    snapshot = gestore.snapshot()
    row = next(item for item in snapshot["tabelle"] if item["id"] == "registro_organismi_mediazione")
    catalogo = gestore.rows("registro_organismi_mediazione")

    assert row["category"] == "registri_ministeriali"
    assert catalogo[0]["official_info_url"].endswith("mg_3_4_15.page")
    assert "mediazione.giustizia.it" in catalogo[0]["official_registry_url"]


def test_update_table_rows_crea_versione_dinamica_su_elenco_mediazione(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    result = gestore.update_table_rows(
        "organismi_mediazione_elenco",
        [
            {
                "record_id": "abc123",
                "registration_number": "101",
                "name": "Camera Arbitrale Demo",
                "type": "Pubblico",
                "city": "Roma",
                "pec": "demo@pec.example.test",
            }
        ],
        label="Sync demo",
        effective_from="2026-04-01",
        published_at="2026-04-01",
    )
    table = gestore.get_table("organismi_mediazione_elenco")

    assert result["updated"] is True
    assert table["sync_status"] == "sincronizzata"
    assert table["active_version"]["rows"][0]["name"] == "Camera Arbitrale Demo"


def test_tariffario_forense_tables_espongono_profili_opzioni_e_fatturazione(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    scaglioni = gestore.tariffario_scaglioni()
    profili = gestore.tariffario_profili()
    regole = gestore.tariffario_regole()
    audit = gestore.tariffario_audit()
    opzioni = gestore.tariffario_opzioni()
    riferimenti = gestore.tariffario_riferimenti()
    fatturazione = gestore.tariffario_fatturazione()

    assert any(row["table_code"] == "A2" for row in scaglioni)
    assert any(row["profile_code"] == "civile_tribunale" for row in profili)
    assert any(row["rule_code"] == "civile_appello" for row in regole)
    assert any(row["rule_code"] == "giurisdizioni_superiori_corte_edu" for row in audit)
    assert any(row["option_code"] == "spese_generali_15" for row in opzioni)
    assert any(row["reference_code"] == "dlgs127_fattura_elettronica" for row in riferimenti)
    assert any(row["channel_code"] == "fatturapa_xml" for row in fatturazione)
