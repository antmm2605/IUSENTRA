from __future__ import annotations

import json


def _chars(*codes: int) -> str:
    return "".join(chr(code) for code in codes)


def test_repair_text_encoding_corregge_mojibake_e_caratteri_sostitutivi():
    from pct.utf8_integrity import contains_encoding_artifacts, repair_text_encoding

    testo = (
        "pi\u00c3\u00b9 qualit\u00e0 \u00e2\u20ac\u201d importo \u00e2\u201a\u00ac 10, "
        "perch\u0102\u00a9 la possibilit\ufffd esiste e la Societ\ufffd pu\u0102\u02db agire"
    )
    riparato = repair_text_encoding(testo, drop_unresolved=True)

    assert (
        "pi\u00f9 qualit\u00e0 \u2014 importo \u20ac 10, perch\u00e9 la possibilit\u00e0 "
        "esiste e la Societ\u00e0 pu\u00f2 agire"
    ) == riparato
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
                    "corpo_testo": (
                        "Il cliente pu\u0102\u02db confermare pi\u00c3\u00b9 tardi "
                        "\u00e2\u20ac\u201d importo \u00e2\u201a\u00ac 10."
                    ),
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
    assert repaired["msg-1"]["oggetto"] == "possibilit\u00e0 di accordo"
    assert repaired["msg-1"]["corpo_testo"] == (
        "Il cliente pu\u00f2 confermare pi\u00f9 tardi \u2014 importo \u20ac 10."
    )
    assert report_path.exists()


def test_lex_output_guards_non_lasciano_mojibake_in_risposta():
    from lex.guards.italian_response_guard import rewrite_or_reject_non_italian_response
    from lex.guards.user_facing_output_guard import check_output_safety

    risposta = rewrite_or_reject_non_italian_response(
        "La possibilit\ufffd c'\u00c3\u00a8 \u00e2\u20ac\u201d importo \u00e2\u201a\u00ac 10."
    )
    _, sicura = check_output_safety(risposta, workflow="studio_data_lookup", question="cliente")

    assert sicura == "La possibilit\u00e0 c'\u00e8 \u2014 importo \u20ac 10."
    assert "\ufffd" not in sicura
    assert _chars(0x00C3) not in sicura
    assert _chars(0x00E2) not in sicura


def test_template_scheduler_include_servizio_utf8():
    from pct.scheduler_registry import default_scheduler_templates

    keys = {template.key for template in default_scheduler_templates({})}

    assert "utf8_integrity_nightly" in keys
