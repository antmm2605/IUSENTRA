from pct.template_atti_master_catalog import load_catalogo_master
from pct.template_atti_inventory import build_template_inventory, template_inventory_stats
from pct.template_cartabia_rules import (
    AREA_EVIDENCE_IDS,
    ensure_cartabia_metadata,
    verifica_cartabia_template,
)


def test_master_templates_hanno_metadati_cartabia_strict_e_fonti():
    templates = load_catalogo_master()["template"]

    assert len(templates) == 420
    for item in templates:
        enriched = ensure_cartabia_metadata(item)
        assert enriched["cartabia_profile"]
        assert enriched["processo_area"]
        assert enriched["stato_conformita"]
        assert enriched["normativa_riferimento"]
        assert enriched["controlli_cartabia"]
        assert enriched["controlli_redazionali"]
        assert enriched["prefill_bindings"]
        assert enriched["source_evidence_ids"]
        assert enriched["richiede_verifica_avvocato"] is False
        assert set(enriched["source_evidence_ids"]) <= {
            evidence_id for values in AREA_EVIDENCE_IDS.values() for evidence_id in values
        }
        verifica_modello = verifica_cartabia_template(enriched)
        assert verifica_modello["stato_conformita"] == "cartabia_ready"
        assert verifica_modello["richiede_verifica_avvocato"] is False
        assert verifica_modello["missing_fields"] == []
        assert verifica_modello["controlli_bloccanti"] == []


def test_cartabia_ready_vietato_senza_fonte_normativa_documentata():
    item = {
        "codice": "TEST_SENZA_FONTE",
        "titolo": "Template area non documentata",
        "cartabia_profile": "profilo_non_documentato",
        "processo_area": "area_non_documentata",
        "stato_conformita": "cartabia_ready",
        "source_evidence_ids": [],
        "required_prefill_fields": ["cliente"],
        "cartabia_required_fields": ["cliente"],
    }

    enriched = ensure_cartabia_metadata(item)
    result = verifica_cartabia_template(enriched, payload={"cliente": "Cliente Test"})

    assert enriched["stato_conformita"] == "cartabia_review_required"
    assert enriched["richiede_verifica_avvocato"] is True
    assert enriched["fonte_regole"] == "fonte ufficiale non documentata"
    assert result["ok"] is False
    assert result["richiede_verifica_avvocato"] is True
    assert "fonte_normativa" in result["missing_fields"]
    assert any(issue["codice"] == "fonte_normativa_mancante" for issue in result["controlli_bloccanti"])


def test_verifica_cartabia_dati_concreti_blocca_solo_in_modalita_compilazione():
    item = ensure_cartabia_metadata(load_catalogo_master()["template"][0])

    modello = verifica_cartabia_template(item)
    compilazione = verifica_cartabia_template(item, payload={}, strict_data_check=True)

    assert modello["stato_conformita"] == "cartabia_ready"
    assert modello["richiede_verifica_avvocato"] is False
    assert modello["controlli_bloccanti"] == []
    assert compilazione["stato_conformita"] == "cartabia_ready"
    assert compilazione["richiede_verifica_avvocato"] is True
    assert compilazione["controlli_bloccanti"]


def test_template_con_copie_fonte_riconciliate_diventa_pronto_come_modello():
    records = build_template_inventory()
    source_records = build_template_inventory(include_source_duplicates=True)
    stats = template_inventory_stats(records, source_records=source_records)

    assert stats["cartabia_ready"] == stats["detected_total"] == 1320
    assert stats["cartabia_review_required"] == 0
    reconciled = [
        record
        for record in records
        if any("copie fonte riconciliate" in warning for warning in record.get("warnings", []))
    ]
    assert reconciled
    assert stats["duplicate_conflict_templates"] == 0
    assert all(record["stato_conformita"] == "cartabia_ready" for record in reconciled)


def test_cartabia_ready_di_template_non_dipende_da_fascicolo_esistente():
    records = build_template_inventory()
    assert records
    assert all(record["stato_conformita"] == "cartabia_ready" for record in records)


def test_aree_specifiche_hanno_controlli_non_generici():
    templates = [ensure_cartabia_metadata(item) for item in load_catalogo_master()["template"]]

    famiglia = [item for item in templates if item["processo_area"] == "famiglia_minori"]
    adr = [item for item in templates if item["processo_area"] == "adr"]
    penali = [item for item in templates if item["processo_area"] == "penale"]
    tributari = [item for item in templates if item["processo_area"] == "tributario"]
    amministrativi = [item for item in templates if item["processo_area"] == "amministrativo"]

    assert famiglia and all({"figli_minori", "documentazione_reddituale", "piano_genitoriale"} <= set(item["required_prefill_fields"]) for item in famiglia)
    assert adr and all({"tipo_adr", "organismo_adr", "valore_causa"} <= set(item["required_prefill_fields"]) for item in adr)
    assert penali and all({"assistito_imputato_indagato", "fase_procedimento"} <= set(item["required_prefill_fields"]) for item in penali)
    assert tributari and all({"atto_impugnato", "ente_impositore", "valore_causa"} <= set(item["required_prefill_fields"]) for item in tributari)
    assert amministrativi and all({"provvedimento_impugnato", "amministrazione_resistente"} <= set(item["required_prefill_fields"]) for item in amministrativi)
