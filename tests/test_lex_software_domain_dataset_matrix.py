from __future__ import annotations

import json
from pathlib import Path

from scripts.export_lex_domain_dataset_matrix import load_matrix, main, select_domain


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "lex_software_domain_dataset_matrix.json"

REQUIRED_DOMAINS = {
    "clienti_soggetti",
    "fascicoli_documenti",
    "agenda_scadenze",
    "email_pec",
    "atti_editor",
    "ricerca_legale_giurisprudenza",
    "telematico",
    "pagamenti_fatturazione",
    "impostazioni",
    "backup",
    "privacy_gdpr",
    "sito_studio",
    "amministrazione",
}

FORBIDDEN_PROMISES = {
    "avvia training automatico",
    "salva chain-of-thought",
    "usa dati demo",
    "esegue invii esterni automatici",
}


def test_matrice_lex_copre_tutti_i_domini_richiesti():
    matrix = load_matrix()
    domains = matrix["domains"]

    assert matrix["governance"]["automatic_training"] is False
    assert matrix["governance"]["external_upload_default"] is False
    assert matrix["governance"]["chain_of_thought_storage"] is False
    assert matrix["governance"]["human_review_required_for_fine_tuning"] is True
    assert {domain["id"] for domain in domains} == REQUIRED_DOMAINS


def test_ogni_dominio_dichiara_fonti_permessi_qa_esclusioni_azioni_e_test():
    matrix = load_matrix()

    for domain in matrix["domains"]:
        assert domain["real_data_sources"], domain["id"]
        assert domain["permissions"], domain["id"]
        assert domain["qa_examples_to_generate"], domain["id"]
        assert domain["excluded_data"], domain["id"]
        assert domain["lex_allowed_actions"], domain["id"]
        assert domain["lex_forbidden_actions"], domain["id"]
        assert domain["acceptance_tests"], domain["id"]
        assert all("answer_requirements" in example for example in domain["qa_examples_to_generate"])


def test_matrice_blocca_azioni_dispositive_e_dati_sensibili():
    matrix = load_matrix()
    payload = json.dumps(matrix, ensure_ascii=False).lower()

    assert "automatic_training\": true" not in payload
    assert "password" in payload
    assert "token" in payload
    assert "path" in payload
    assert "tenant" in payload

    dispositive_actions = ("inviare", "depositare", "firmare", "emettere", "pubblicare", "restore")
    forbidden_actions = " ".join(
        action.lower()
        for domain in matrix["domains"]
        for action in domain["lex_forbidden_actions"]
    )
    for action in dispositive_actions:
        assert action in forbidden_actions


def test_documento_markdown_rimanda_alla_matrice_json_e_non_promette_training():
    markdown = (ROOT / "docs" / "LEX_SOFTWARE_DOMAIN_DATASET_MATRIX.md").read_text(encoding="utf-8")

    assert "docs/lex_software_domain_dataset_matrix.json" in markdown
    assert "rag interno" in markdown.lower()
    assert "senza training automatico" in markdown.lower()
    for forbidden in FORBIDDEN_PROMISES:
        assert forbidden not in markdown.lower()


def test_script_read_only_esporta_matrice_e_singolo_dominio(capsys):
    assert main(["--domain", "clienti_soggetti"]) == 0
    domain = json.loads(capsys.readouterr().out)

    assert domain["id"] == "clienti_soggetti"
    assert any("pct/clienti.py" in source for source in domain["real_data_sources"])

    matrix = load_matrix()
    selected = select_domain(matrix, "telematico")
    assert selected["name"] == "Telematico"
