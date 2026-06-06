from pathlib import Path

from pct.template_atti_legal_sources import template_atti_sources_for_model


def test_template_atti_fonti_ufficiali_integrabili_sono_tracciate():
    rows = template_atti_sources_for_model(
        model_code="CIV_COM_001",
        model_name="Comparsa di costituzione e risposta civile",
        area="contenzioso civile PCT",
    )

    assert any(row["article"] == "art. 167 c.p.c." for row in rows)
    assert any(row["id"] == "normattiva_dm_217_2023_giustizia_telematica" for row in rows)
    assert all(row["official_url"].startswith("https://") for row in rows)
    assert all(row["last_verified_at"] == "2026-06-06" for row in rows)
    assert any(row["coverage_role"] == "specifica" for row in rows)
    assert any(row["coverage_role"] == "secondaria_collegata" for row in rows)
    assert all("testo" not in row for row in rows)

    doc = Path("docs/specs/ministero/TEMPLATE_ATTI_FONTI_UFFICIALI_2026-06-06.md")
    assert doc.exists()
    body = doc.read_text(encoding="utf-8")
    assert "Normattiva" in body
    assert "EUR-Lex" in body
    assert "Codice deontologico" in body


def test_template_atti_deontologia_equo_compenso_non_sono_fonti_generiche():
    rows = template_atti_sources_for_model(
        model_code="STR_PREV_001",
        model_name="Preventivo professionale con incarico, equo compenso e pagamento",
        area="studio incarichi compensi",
    )

    assert any(row["id"] == "gu_cdf_art_25_bis_equo_compenso_2026" for row in rows)
    assert any(row["id"] == "cnf_cdf_art_25_compensi" for row in rows)
    assert any(row["coverage_role"] == "deontologia" for row in rows)
    assert not all(row["coverage_role"] == "base_comune" for row in rows)


def test_template_atti_cautelari_hanno_fonti_specifiche_non_base_comune():
    rows = template_atti_sources_for_model(
        model_code="TMP-CAUT-004",
        model_name="Ricorso cautelare d'urgenza",
        area="cautelare PCT",
    )

    assert any(row["id"] == "cpc_procedimenti_cautelari_uniformi" for row in rows)
    assert any(row["id"] == "cpc_art_700_urgenza" for row in rows)
    assert any(row["coverage_role"] == "specifica" for row in rows)


def test_template_atti_adr_include_correttivo_e_fonti_attuative():
    rows = template_atti_sources_for_model(
        model_code="ADR_MED_001",
        model_name="Istanza di mediazione civile e commerciale",
        area="ADR mediazione negoziazione assistita",
    )

    assert any(row["id"] == "normattiva_d_lgs_216_2024_correttivo_adr" for row in rows)
    assert any(row["id"] == "normattiva_dm_150_2023_mediazione" for row in rows)
    assert any(row["coverage_role"] == "secondaria_collegata" for row in rows)


def test_template_atti_notifica_sentenza_usa_fonti_specifiche_attestazione():
    rows = template_atti_sources_for_model(
        model_code="CIV_NOT_SENT_001",
        model_name="Notifica sentenza con attestazione di conformità e termine breve",
        area="notifica PEC L. 53/1994 sentenza estratta dal fascicolo informatico",
    )

    assert any(row["id"] == "normattiva_dl_179_2012_art_16_decies_attestazione" for row in rows)
    assert any(row["id"] == "disp_att_cpc_art_196_undecies_attestazione" for row in rows)
    assert any(row["id"] == "pst_dgsia_2024_art_27_attestazione_conformita" for row in rows)
    assert any(row["id"] == "normattiva_cpc_art_285_325_326_sentenza_termine_breve" for row in rows)
    assert any(row["coverage_role"] == "telematica" for row in rows)
    assert not all(row["coverage_role"] == "base_comune" for row in rows)


def test_template_atti_fonti_giurisprudenziali_ufficiali_sono_esposte():
    rows = template_atti_sources_for_model(
        model_code="CIV_GIU_001",
        model_name="Ricerca giurisprudenziale su sentenze, ordinanze, precedenti e questioni costituzionali",
        area="Cassazione SentenzeWeb Corte costituzionale CURIA HUDOC giurisprudenza di merito",
    )
    ids = {row["id"] for row in rows}

    assert "corte_cassazione_sentenzeweb" in ids
    assert "corte_costituzionale_decisioni" in ids
    assert "pst_banca_dati_pubblica_giurisprudenza_merito" in ids
    assert "curia_cgue_giurisprudenza_ue" in ids
    assert "hudoc_cedu_giurisprudenza" in ids
    assert any(row["coverage_role"] == "autorita" for row in rows)


def test_template_atti_fonti_autorita_collegate_per_aree_speciali():
    ip_rows = template_atti_sources_for_model(
        model_code="IPD_MAR_001",
        model_name="Diffida per contraffazione marchio e deposito UIBM",
        area="proprietà industriale marchio brevetto",
    )
    loc_rows = template_atti_sources_for_model(
        model_code="LOC_RIL_001",
        model_name="Diffida locazione con registrazione RLI e cedolare secca",
        area="locazioni abitative Agenzia Entrate",
    )
    imm_rows = template_atti_sources_for_model(
        model_code="IMM_RIC_001",
        model_name="Ricorso protezione internazionale contro diniego della Commissione territoriale",
        area="immigrazione asilo protezione internazionale",
    )

    assert any(row["id"] == "uibm_deposito_telematico_proprieta_industriale" for row in ip_rows)
    assert any(row["id"] == "agenzia_entrate_rli_locazioni" for row in loc_rows)
    assert any(row["id"] == "interno_protezione_internazionale_commissioni" for row in imm_rows)
