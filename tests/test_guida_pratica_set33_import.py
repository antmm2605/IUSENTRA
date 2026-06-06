from __future__ import annotations

import json
from pathlib import Path

from lex.contracts import LexRequest
from lex.retrieval.sources.guida_pratica import GuidaPraticaSource
from pct.guida_pratica import GuidaPraticaService
from scripts.import_guida_pratica_termini_processuali import collect_terms


ROOT = Path(__file__).resolve().parents[1]
SET33_MODULES = sorted((ROOT / "pct" / "data" / "legal_knowledge_base_modules").glob("kb_98_set33_p*.json"))


def _records() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in SET33_MODULES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(item for item in payload.get("codici_materia", []) if isinstance(item, dict))
    return rows


def _request(query: str) -> LexRequest:
    return LexRequest(
        tenant_id="tenant-set33",
        user_id="utente-test",
        session_id="sessione-set33",
        query=query,
        metadata={"disable_studio_database_source": True},
    )


def test_set33_files_zip_integrato_in_otto_moduli_e_quaranta_guide():
    rows = _records()

    assert len(SET33_MODULES) == 8
    assert len(rows) == 40
    assert sum(len(item.get("termini_processuali") or []) for item in rows) == 42
    assert {item.get("codice_originale_ricevuto") for item in rows} >= {
        "112005",
        "220285",
        "240075",
        "512160",
        "420001",
    }
    assert all(item.get("guida_interna_non_depositabile") is True for item in rows)
    assert all(item.get("depositabile") is False for item in rows)
    assert all(item.get("codice_deposito_automatico") is False for item in rows)
    assert all(item.get("fonti_verifica_web") for item in rows)


def test_set33_guida_pratica_service_espone_fonti_termini_e_codice_deposito_separato():
    service = GuidaPraticaService()

    guida = service.get_guidance(
        "GUIDA_ACCESSO_GENERALIZZATO_FOIA_RICORSO_AL_TAR_PER_DINIEGO_E_RIESAME_D_LGS_33_240075"
    )

    assert guida["codice_originale_ricevuto"] == "240075"
    assert guida["codice_deposito"]["depositabile"] is False
    assert guida["codice_deposito"]["ufficiale"] is False
    assert "catalogo PST/XSD ufficiale" in guida["codice_deposito"]["messaggio"]
    assert guida["coverage"]["level"] == "curata"
    assert guida["termini_processuali"]
    assert guida["fonti_verifica_web"]
    assert "D.Lgs. 33/2013" in json.dumps(guida, ensure_ascii=False)


def test_set33_scadenziario_importa_i_termini_dai_moduli_versionati():
    rows = collect_terms(SET33_MODULES)
    report = json.loads(
        (ROOT / "artifacts" / "guida-pratica" / "termini-processuali-import-2026-06-07-set33.json").read_text(
            encoding="utf-8"
        )
    )

    assert len(rows) == 42
    assert any(row["codice"].endswith("512160") for row in rows)
    assert any(row["fase_processuale"] == "impugnazione" for row in rows)
    assert report["records"] >= 3567
    assert report["calculable_templates"] >= 1119
    assert report["by_phase"]["notifica"] >= 2171


def test_set33_lex_legge_foia_e_cartella_esattoriale():
    source = GuidaPraticaSource(limit=10)

    foia_query = "Guida pratica FOIA accesso generalizzato ricorso TAR diniego riesame"
    foia_results = source.search([foia_query], _request(foia_query), {})
    assert foia_results
    assert foia_results[0].source_id == (
        "GUIDA_ACCESSO_GENERALIZZATO_FOIA_RICORSO_AL_TAR_PER_DINIEGO_E_RIESAME_D_LGS_33_240075"
    )
    assert "Fonti ufficiali web collegate alla guida" in foia_results[0].content

    cartella_query = "Guida pratica cartella esattoriale prescrizione riscossione"
    cartella_results = source.search([cartella_query], _request(cartella_query), {})
    assert cartella_results
    assert cartella_results[0].source_id == (
        "GUIDA_CARTELLA_ESATTORIALE_PRESCRIZIONE_CONTESTAZIONE_E_SOSPENSIONE_DELLA_RISC_512160"
    )
    assert "Ragionamento operativo Lex da applicare" in cartella_results[0].content


def test_set33_audit_voce_per_voce_non_perde_materiale_utente():
    report = json.loads(
        (
            ROOT
            / "artifacts"
            / "guida-pratica"
            / "guida-pratica-user-material-field-audit-2026-06-07-set33.json"
        ).read_text(encoding="utf-8")
    )
    summary = report["summary"]

    assert "kb_98_set33_p8.json" in summary["modules_checked"]
    assert summary["records_checked"] >= 406
    assert summary["source_fields_present"] >= 6377
    assert summary["lost_from_software"] == 0
    assert summary["missing_full_kb_when_source_present"] == 0
    assert summary["missing_service_when_source_present"] == 0
    assert summary["missing_ui_support_when_source_present"] == 0
    assert summary["missing_lex_support_when_source_present"] == 0
    assert summary["scalar_values_changed_in_service"] == 0
