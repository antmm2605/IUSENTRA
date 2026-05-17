from __future__ import annotations

import hashlib
from typing import Any

from pct import legal_update_web_verification as verification


class DummyResponse:
    def __init__(self, content: bytes, *, content_type: str, status_code: int = 200) -> None:
        self.content = content
        self.text = content.decode("utf-8", errors="ignore")
        self.status_code = status_code
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(content)),
        }

    def iter_content(self, chunk_size: int = 65536):
        yield self.content


HTML_FIXTURE = """
<html>
  <body>
    <article>
      <h1>Decreto legislativo n. 56 del 2026</h1>
      <a href="/resources/cms/documents/testo-ufficiale.pdf">Scarica PDF ufficiale</a>
      <a href="https://www.gazzettaufficiale.it.evil.test/falso.pdf">Scarica PDF non ufficiale</a>
    </article>
  </body>
</html>
"""


def test_helper_scarica_pdf_ufficiale_e_rifiuta_dominio_simile(monkeypatch):
    source_url = "https://www.gazzettaufficiale.it/eli/id/2026/05/11/26G00056/sg"
    attachment_url = "https://www.gazzettaufficiale.it/resources/cms/documents/testo-ufficiale.pdf"
    pdf_bytes = b"%PDF-1.4\n% test ufficiale\n"
    requested: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        assert "evil.test" not in str(url)
        assert kwargs.get("allow_redirects") is False
        return DummyResponse(pdf_bytes, content_type="application/pdf")

    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(
        verification,
        "_text_from_attachment",
        lambda url, content, content_type: "Decreto legislativo n. 56 del 2026 sulla conciliazione giudiziale.",
    )

    confirmations = verification.extract_official_attachment_confirmations(
        HTML_FIXTURE,
        source_url,
        timeout=2,
        max_bytes=1024 * 1024,
    )

    assert requested == [attachment_url]
    assert len(confirmations) == 1
    row = confirmations[0]
    assert row["official"] is True
    assert row["source_url"] == source_url
    assert row["attachment_url"] == attachment_url
    assert row["title"] == "testo-ufficiale.pdf"
    assert row["attachment_type"] == "pdf"
    assert row["sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert "conciliazione giudiziale" in row["text_excerpt"]
    assert row["context_chars"] > 20


def test_helper_non_usa_testo_generico_come_titolo_allegato(monkeypatch):
    source_url = "https://www.gazzettaufficiale.it/eli/id/2026/05/11/26G00056/sg"
    generic_url = "https://www.gazzettaufficiale.it/resources/cms/documents/notizia-generica.pdf"
    requested: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        return DummyResponse(b"%PDF-1.4\n% test ufficiale\n", content_type="application/pdf")

    monkeypatch.setenv("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_LINKS", "3")
    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(
        verification,
        "_text_from_attachment",
        lambda url, content, content_type: "Decreto legislativo n. 56 del 2026 sulla conciliazione giudiziale.",
    )

    confirmations = verification.extract_official_attachment_confirmations(
        """
        <html><body>
          <a href="/resources/cms/documents/notizia-generica.pdf">Leggi la notizia</a>
        </body></html>
        """,
        source_url,
        timeout=2,
        max_bytes=1024 * 1024,
    )

    generic = next(row for row in confirmations if row["attachment_url"] == generic_url)
    assert generic["title"] == "notizia-generica.pdf"
    assert "Leggi la notizia" not in generic["title"]
    assert "evil.test" not in " ".join(requested)


def test_verifica_web_restituisce_conferma_allegato_ufficiale(monkeypatch):
    source_url = "https://www.gazzettaufficiale.it/scheda/26G00056"
    attachment_url = "https://www.gazzettaufficiale.it/resources/cms/documents/testo-ufficiale.pdf"
    pdf_bytes = b"%PDF-1.4\n% test ufficiale\n"
    requested: list[str] = []

    review = {
        "proposed_action": "NEW_NORMATIVE",
        "title": "Decreto legislativo n. 56 del 2026 sulla conciliazione",
        "source_url": source_url,
        "source_name": "Gazzetta Ufficiale",
        "classification_type": "NORMATIVA_NUOVA",
        "norm_type": "decreto legislativo",
        "norm_number": "56",
        "norm_year": "2026",
        "summary_short": "Aggiorna la conciliazione giudiziale.",
    }
    source = {
        "name": "Gazzetta Ufficiale",
        "code": "gazzetta_ufficiale",
        "category": "normativa",
        "trust_class": "A",
        "is_official": True,
    }

    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_official_sources", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_normattiva", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_gazzetta", lambda query, limit=5: [])
    monkeypatch.setattr(
        "lex.retrieval.official_web.search_recognized_official_web",
        lambda query, source_ids=None, limit_results=5: [
            {
                "title": "Scheda Gazzetta con allegato",
                "url": source_url,
                "source_name": "Gazzetta Ufficiale",
                "excerpt": "Scheda senza testo completo.",
            }
        ],
    )

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        assert "evil.test" not in str(url)
        if str(url) == attachment_url:
            return DummyResponse(pdf_bytes, content_type="application/pdf")
        return DummyResponse(HTML_FIXTURE.encode("utf-8"), content_type="text/html; charset=utf-8")

    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(
        verification,
        "_text_from_attachment",
        lambda url, content, content_type: "Decreto legislativo n. 56 del 2026 sulla conciliazione giudiziale.",
    )

    report = verification.verify_legal_update_against_public_sources(review, source, limit=2)

    attachments = [row for row in report["confirmations"] if row.get("origin") == "allegato_fonte_ufficiale"]
    assert attachments
    assert attachments[0]["source_url"] == source_url
    assert attachments[0]["attachment_url"] == attachment_url
    assert attachments[0]["attachment_type"] == "pdf"
    assert attachments[0]["sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert attachments[0]["official"] is True
    assert attachments[0]["context_chars"] > 20
    assert not any("evil.test" in url for url in requested)
