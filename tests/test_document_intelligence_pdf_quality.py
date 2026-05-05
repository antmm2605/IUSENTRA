from pct.document_intelligence.pdf_quality import (
    CID_WARNING,
    repair_pdf_cid_placeholders,
    score_extracted_text_quality,
)


def test_pdf_quality_ripara_cid_avvocato():
    repaired, warnings = repair_pdf_cid_placeholders(
        "(cid:65)(cid:118)(cid:118)(cid:111)(cid:99)(cid:97)(cid:116)(cid:111)"
    )

    assert repaired == "Avvocato"
    assert CID_WARNING in warnings


def test_pdf_quality_ripara_cid_pec():
    repaired, warnings = repair_pdf_cid_placeholders("(cid:80)(cid:69)(cid:67)")

    assert repaired == "PEC"
    assert CID_WARNING in warnings


def test_pdf_quality_score_migliora_dopo_repair():
    raw = "(cid:65)(cid:118)(cid:118)(cid:111)(cid:99)(cid:97)(cid:116)(cid:111) PEC"
    before = score_extracted_text_quality(raw)
    repaired, warnings = repair_pdf_cid_placeholders(raw)
    after = score_extracted_text_quality(repaired)

    assert warnings
    assert "(cid:" not in repaired
    assert after.score > before.score
    assert after.cid_placeholders == 0
