from pathlib import Path

from pct.template_atti_legal_sources import template_atti_sources_for_model


def test_template_atti_fonti_ufficiali_integrabili_sono_tracciate():
    rows = template_atti_sources_for_model(model_name="Comparsa di costituzione e risposta civile")

    assert any(row["article"] == "art. 167 c.p.c." for row in rows)
    assert all(row["official_url"].startswith("https://") for row in rows)
    assert all(row["last_verified_at"] == "2026-06-04" for row in rows)
    assert all("testo" not in row for row in rows)

    doc = Path("docs/specs/ministero/TEMPLATE_ATTI_FONTI_UFFICIALI_2026-06-04.md")
    assert doc.exists()
    body = doc.read_text(encoding="utf-8")
    assert "Normattiva" in body
    assert "EUR-Lex" in body
