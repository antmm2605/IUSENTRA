from __future__ import annotations

import json


def test_repair_text_encoding_corregge_mojibake_e_caratteri_sostitutivi():
    from pct.utf8_integrity import contains_encoding_artifacts, repair_text_encoding

    testo = "piÃ¹ qualità â€” importo â‚¬ 10, perchĂ© la possibilit� esiste e la Societ� puĂ˛ agire"
    riparato = repair_text_encoding(testo, drop_unresolved=True)

    assert "più qualità — importo € 10, perché la possibilità esiste e la Società può agire" == riparato
    assert contains_encoding_artifacts(riparato) is False
    assert "\ufffd" not in riparato


def test_scan_utf8_integrity_ripara_json_e_scrive_report(tmp_path):
    from pct.utf8_integrity import scan_utf8_integrity

    root = tmp_path / "tenant" / "email"
    root.mkdir(parents=True)
    mailbox = root / "ordinaria.json"
    mailbox.write_text(
        json.dumps(
            {
                "msg-1": {
                    "oggetto": "possibilit\ufffd di accordo",
                    "corpo_testo": "Il cliente puĂ˛ confermare piÃ¹ tardi â€” importo â‚¬ 10.",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "intelligence" / "utf8-report.json"

    report = scan_utf8_integrity([root], repair=True, report_path=report_path)

    assert report["checked_files"] == 1
    assert report["repaired_files"] == 1
    assert report["error_files"] == 0
    repaired = json.loads(mailbox.read_text(encoding="utf-8"))
    assert repaired["msg-1"]["oggetto"] == "possibilità di accordo"
    assert repaired["msg-1"]["corpo_testo"] == "Il cliente può confermare più tardi — importo € 10."
    assert report_path.exists()


def test_lex_output_guards_non_lasciano_mojibake_in_risposta():
    from lex.guards.italian_response_guard import rewrite_or_reject_non_italian_response
    from lex.guards.user_facing_output_guard import check_output_safety

    risposta = rewrite_or_reject_non_italian_response("La possibilit\ufffd c'Ã¨ â€” importo â‚¬ 10.")
    _, sicura = check_output_safety(risposta, workflow="studio_data_lookup", question="cliente")

    assert sicura == "La possibilità c'è — importo € 10."
    assert "\ufffd" not in sicura
    assert "Ã" not in sicura
    assert "â" not in sicura


def test_template_scheduler_include_servizio_utf8():
    from pct.scheduler_registry import default_scheduler_templates

    keys = {template.key for template in default_scheduler_templates({})}

    assert "utf8_integrity_nightly" in keys
