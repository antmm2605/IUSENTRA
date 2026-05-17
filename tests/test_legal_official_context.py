from __future__ import annotations

import requests

from web.services.legal_official_context import build_official_context


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
        url: str = "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = {"content-type": content_type, **(headers or {})}
        self.url = url
        self.content = body

    def iter_content(self, chunk_size: int = 65536):
        for index in range(0, len(self.content), chunk_size):
            yield self.content[index : index + chunk_size]


def test_build_official_context_gazzetta_decreto_legislativo_html(monkeypatch):
    html = """
    <!doctype html>
    <html>
      <head><title>Gazzetta Ufficiale</title></head>
      <body>
        <nav>Menu privacy cookie accedi</nav>
        <h1>DECRETO LEGISLATIVO 13 marzo 2026, n. 39</h1>
        <p>DECRETO LEGISLATIVO 13 marzo 2026, n. 39. Attuazione della direttiva
        europea in materia di obblighi organizzativi e controlli interni.</p>
        <p>Art. 1 Oggetto e ambito di applicazione. Il decreto disciplina gli
        adempimenti degli operatori, le verifiche documentali e le responsabilità
        connesse ai procedimenti interessati.</p>
        <p>Art. 2 Entrata in vigore. Le disposizioni entrano in vigore il giorno
        successivo alla pubblicazione nella Gazzetta Ufficiale della Repubblica
        italiana, salvo termini speciali indicati nei singoli articoli.</p>
      </body>
    </html>
    """.encode("utf-8")

    calls: list[dict] = []

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        return FakeResponse(html)

    payload = build_official_context(
        "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
        "Gazzetta D.Lgs. 13 marzo 2026 n. 39",
        request_get=fake_get,
    )

    assert payload["contextCompleted"] is True
    assert "DECRETO LEGISLATIVO 13 marzo 2026, n. 39" in payload["officialContext"]
    assert "Entrata in vigore" in payload["officialContext"]
    assert "Gazzetta D.Lgs. 13 marzo 2026 n. 39" in payload["contextSummary"]
    assert any("decorrenza" in check.lower() for check in payload["operationalChecks"])
    assert any("Riferimento cercato" in point for point in payload["keyPoints"])
    assert payload["warnings"] == []
    assert calls[0]["timeout"] == (2.0, 5.0)
    assert calls[0]["stream"] is True
    assert calls[0]["allow_redirects"] is False


def test_build_official_context_rifiuta_dominio_non_riconosciuto_senza_fetch():
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(b"non deve essere scaricato", url=url)

    payload = build_official_context(
        "https://www.gazzettaufficiale.it.evil.test/eli/id/2026/03/13/26G00039/sg",
        "D.Lgs. 13 marzo 2026 n. 39",
        request_get=fake_get,
    )

    assert calls == []
    assert payload["officialContext"] == ""
    assert payload["contextCompleted"] is False
    assert payload["warnings"] == ["Fonte non inclusa nel catalogo dei domini ufficiali riconosciuti."]


def test_build_official_context_blocca_redirect_a_dominio_simile():
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(
            b"",
            status_code=302,
            url=url,
            headers={"location": "https://www.gazzettaufficiale.it.evil.test/falso.html"},
        )

    payload = build_official_context(
        "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
        "D.Lgs. 13 marzo 2026 n. 39",
        request_get=fake_get,
    )

    assert calls == ["https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg"]
    assert payload["officialContext"] == ""
    assert payload["warnings"] == ["La fonte ufficiale rimanda a un dominio non riconosciuto."]


def test_build_official_context_include_allegato_ufficiale(monkeypatch):
    html = """
    <html>
      <body>
        <h1>DECRETO LEGISLATIVO 13 marzo 2026, n. 39</h1>
        <p>Scheda ufficiale sintetica del provvedimento.</p>
        <a href="/resources/testo.pdf">Scarica PDF ufficiale</a>
      </body>
    </html>
    """.encode("utf-8")

    def fake_get(url, **kwargs):
        return FakeResponse(html)

    def fake_attachments(html_text, source_url, **kwargs):
        assert "Scarica PDF ufficiale" in html_text
        assert source_url.startswith("https://www.gazzettaufficiale.it/")
        return [
            {
                "title": "testo.pdf",
                "text_excerpt": (
                    "Art. 1 Oggetto e ambito di applicazione. Il decreto disciplina "
                    "obblighi organizzativi, controlli interni e responsabilità."
                ),
                "excerpt": "",
            }
        ]

    monkeypatch.setattr("web.services.legal_official_context.extract_official_attachment_confirmations", fake_attachments)

    payload = build_official_context(
        "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
        "D.Lgs. 13 marzo 2026 n. 39",
        request_get=fake_get,
    )

    assert payload["contextCompleted"] is True
    assert "Allegato ufficiale testo.pdf" in payload["officialContext"]
    assert "responsabilità" in payload["officialContext"]


def test_build_official_context_timeout_returns_clean_fallback():
    def fake_get(url, **kwargs):
        raise requests.Timeout("tempo esaurito")

    payload = build_official_context(
        "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
        "Gazzetta D.Lgs. 13 marzo 2026 n. 39",
        request_get=fake_get,
    )

    assert payload == {
        "officialContext": "",
        "contextSummary": "",
        "keyPoints": [],
        "operationalChecks": [
            "Riprova più tardi o apri la fonte ufficiale indicata prima di usare il riferimento in un atto."
        ],
        "contextCompleted": False,
        "warnings": ["Fonte ufficiale non raggiunta entro il tempo massimo."],
    }


def test_build_official_context_http_failure_returns_clean_fallback():
    def fake_get(url, **kwargs):
        return FakeResponse(b"non disponibile", status_code=503, content_type="text/plain")

    payload = build_official_context(
        "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
        "Gazzetta D.Lgs. 13 marzo 2026 n. 39",
        request_get=fake_get,
    )

    assert payload["contextCompleted"] is False
    assert payload["officialContext"] == ""
    assert payload["warnings"] == ["Fonte ufficiale non disponibile: HTTP 503."]
