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
