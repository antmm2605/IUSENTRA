"""Parser guards from the public CMN FAQ structure observed on 05/09/2026."""
from datetime import datetime, timezone

from pct import mediazione_channel_research as research


def page(body, url="https://organismo.example.test/"):
    return dict(url=url, status=200, body=body.encode(), content_type="text/html; charset=utf-8")


def test_pec_in_filing_answer_does_not_authorize_ministry_contact():
    contacts, apis, text = research.channel_evidence(page('''
      <div>La domanda di mediazione può essere depositata:
        <ul><li>a mezzo P.E.C. a istanze@pec.example.test</li></ul></div>
      <p>Per gli adempimenti al Ministero: ministero@giustiziacert.example.test (PEC).</p>
      <a href="/api-conservazione">API per la conservazione documentale</a>'''))
    filing = next(c for c in contacts if c["address"] == "istanze@pec.example.test")
    ministry = next(c for c in contacts if c["address"].startswith("ministero"))
    assert filing["filing_context"] and filing["pec_explicit"]
    assert not ministry["filing_context"]
    assert "può" in text and not any(c["authorized_for_submission"] for c in contacts)
    assert apis[0]["status"] == "documentazione_da_verificare"


def test_time_budget_keeps_unread_page_in_durable_frontier(monkeypatch):
    monkeypatch.setattr(research, "fetch_public", lambda *a, **k: dict(page("User-agent: *\nCrawl-delay: 100"), content_type="text/plain"))
    result = research.inspect_channels(dict(registration_number="1", name="Prova", website="https://organismo.example.test/"), budget_seconds=1)
    assert result["remaining_urls"] == ["https://organismo.example.test/"]
    assert result["pages"] == []


def test_bounded_run_resumes_unread_pages_instead_of_restarting(monkeypatch):
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        return page("<p>Pagina acquisita</p>", url)
    monkeypatch.setattr(research, "fetch_public", fetch)
    monkeypatch.setattr(research.time, "sleep", lambda _: None)
    last = dict(research_version=research.RESEARCH_VERSION, cycle_started_at=datetime.now(timezone.utc).isoformat(),
                remaining_urls=["https://organismo.example.test/moduli"], pages=[dict(requested_url="https://organismo.example.test/", status=200, parsed=True)])
    result = research.inspect_channels(dict(registration_number="1", name="Prova", website="https://organismo.example.test/", channel_check=last))
    assert "https://organismo.example.test/" not in calls
    assert len(result["pages"]) == 2 and not result["remaining_urls"]
    assert result["pages"][-1]["parsed"] is True


def test_http_error_is_explicit_not_full_success(monkeypatch):
    def fetch(url, **kwargs):
        return dict(page("", url), status=404)
    monkeypatch.setattr(research, "fetch_public", fetch)
    monkeypatch.setattr(research.time, "sleep", lambda _: None)
    result = research.inspect_channels(dict(registration_number="1", name="Prova", website="https://organismo.example.test/"))
    assert result["errors"] and result["status"] == "fonte_non_raggiunta"


def test_cross_domain_redirect_is_not_accepted_as_parsed_source(monkeypatch):
    def fetch(url, **kwargs):
        return page("<p>Inviare domanda via PEC a intruso@pec.example.test</p>", "https://altro.example.test/")
    monkeypatch.setattr(research, "fetch_public", fetch)
    monkeypatch.setattr(research.time, "sleep", lambda _: None)
    result = research.inspect_channels(dict(registration_number="1", name="Prova", website="https://organismo.example.test/"))
    assert not result["contacts"] and result["errors"]
    assert not result["pages"][0].get("parsed")
