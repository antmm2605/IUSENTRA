from scripts.audit_legal_source_delivery import build_audit


def _source(audit, source_id, registry):
    return next(
        row
        for row in audit["sources"]
        if row["source_id"] == source_id and row["registry"] == registry
    )


def test_audit_legal_source_delivery_distingue_fonti_operative_da_attivare_e_buchi():
    audit = build_audit()
    summary = audit["summary"]

    assert summary["total_sources"] >= 400
    assert summary["operational_sources"] >= 300
    assert summary["activation_pending_sources"] >= 1
    assert summary["official_gaps"] <= 10
    assert summary["sources_with_legal_materials"] == summary["total_sources"]
    assert summary["sources_with_articles_and_codes"] == summary["total_sources"]
    assert summary["sources_with_decrees_and_rules"] == summary["total_sources"]
    assert summary["sources_with_case_law_and_hearings"] == summary["total_sources"]

    agenzia = _source(audit, "agenzia_entrate", "lex_official_config")
    assert agenzia["delivery_status"] == "operativa_controllabile"
    assert agenzia["url"].startswith("https://www.agenziaentrate.gov.it/")
    assert "Ricerca Legale" in agenzia["destinations"]
    assert "Lex AI/RAG Legal" in agenzia["destinations"]
    assert "atto tributario" in agenzia["lawyer_use"]
    assert any("D.Lgs. 546/1992" in item for item in agenzia["articles_and_codes"])
    assert any("D.M. 163/2013" in item for item in agenzia["decrees_and_rules"])
    assert any("Sentenze tributarie" in item for item in agenzia["case_law_and_hearings"])

    locale = _source(audit, "fonti_studio_locali", "lex_official_config")
    assert locale["delivery_status"] == "contesto_non_ufficiale"
    assert "tenant-aware" in locale["gap_reason"]
    assert any("Documenti del fascicolo" in item for item in locale["legal_materials"])

    codice = _source(audit, "codice_civile", "legal_update_sources")
    assert any("codice civile" in item.lower() for item in codice["articles_and_codes"])
    assert any("D.Lgs. settoriali" in item for item in codice["decrees_and_rules"])
    assert not any("D.Lgs. 546/1992" in item for item in codice["articles_and_codes"])

    openga = _source(audit, "openga_sentenze", "legal_update_sources")
    assert any("RG" in item and "calendario udienze" in item for item in openga["case_law_and_hearings"])
    assert any("ragione decisiva" in item for item in openga["research_steps"])
