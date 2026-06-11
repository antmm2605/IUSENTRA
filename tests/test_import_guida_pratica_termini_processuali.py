from __future__ import annotations

import json
from pathlib import Path

from scripts.import_guida_pratica_termini_processuali import collect_terms, import_terms


def test_import_guida_pratica_termini_processuali_classifica_e_importa(tmp_path: Path):
    source = tmp_path / "kb.json"
    source.write_text(
        json.dumps(
            {
                "schede": [
                    {
                        "codice": "TEST001",
                        "denominazione": "Opposizione di prova",
                        "rito": "civile",
                        "termini_processuali": [
                            {
                                "termine": "Opposizione",
                                "giorni": 40,
                                "decorrenza": "notifica decreto",
                                "natura": "perentorio",
                                "norma": "art. 641 c.p.c.",
                            },
                            {
                                "termine": "Diritto imprescrittibile",
                                "natura": "imprescrittibile",
                                "norma": "art. 713 c.c.",
                            },
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = collect_terms([source])
    summary = import_terms(rows, tmp_path / "termini_processuali.json")
    payload = json.loads((tmp_path / "termini_processuali.json").read_text(encoding="utf-8"))

    assert summary["records"] == 2
    assert summary["templates_upserted"] == 1
    assert len(payload["guida_pratica_terms"]) == 2
    assert any(
        item.get("metadata", {}).get("codice_guida") == "TEST001"
        for item in payload["templates"]
        if str(item.get("code", "")).startswith("GP_")
    )
    assert any(item["classificazione_import"] == "informativo_non_calcolabile" for item in payload["guida_pratica_terms"])


def test_import_guida_pratica_termini_processuali_bootstrap_aggiorna_repository_stale(tmp_path: Path):
    source_a = tmp_path / "kb_a.json"
    source_b = tmp_path / "kb_b.json"
    source_a.write_text(
        json.dumps(
            {
                "codici_materia": [
                    {
                        "codice": "TEST_A",
                        "denominazione": "Scheda A",
                        "termini_processuali": [{"termine": "Deposito A", "giorni": 10, "decorrenza": "notifica"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source_b.write_text(
        json.dumps(
            {
                "codici_materia": [
                    {
                        "codice": "TEST_B",
                        "denominazione": "Scheda B",
                        "termini_processuali": [{"termine": "Deposito B", "giorni": 20, "decorrenza": "comunicazione"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    db = tmp_path / "termini_processuali.json"

    import_terms(collect_terms([source_a]), db)
    updated = import_terms(collect_terms([source_a, source_b]), db, only_if_stale=True)
    aligned = import_terms(collect_terms([source_a, source_b]), db, only_if_stale=True)
    payload = json.loads(db.read_text(encoding="utf-8"))

    assert updated["records"] == 2
    assert updated.get("skipped") is not True
    assert aligned["skipped"] is True
    assert {item["codice"] for item in payload["guida_pratica_terms"]} == {"TEST_A", "TEST_B"}
