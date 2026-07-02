from __future__ import annotations

from pct.pec_pipeline import build_remote_hearing_profile, build_validation_report, extract_html_hrefs


TEAMS = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc/0?context=xyz"


def test_extract_html_hrefs_dedupe_e_solo_http():
    html = (
        f'<a href="{TEAMS}">Partecipa</a>'
        f'<a href="{TEAMS}">Duplicato</a>'
        '<a href="mailto:cancelleria@giustiziacert.it">mail</a>'
        '<a href="/relativo">rel</a>'
    )
    hrefs = extract_html_hrefs(html)
    assert hrefs == [TEAMS]  # dedup + solo http(s)


def test_link_udienza_solo_in_href_viene_estratto():
    # Bug storico: il corpo HTML tag-stripped perdeva il link nell'href.
    parsed = {
        "headers": {"subject": "Fissazione udienza da remoto"},
        "body": {
            "text": "L'udienza si terra' da remoto in videoconferenza.",
            "html_text": "L'udienza si terra' da remoto Partecipa alla riunione",
            "href_urls": [TEAMS],
        },
        "procedural_profile": {},
    }
    profile = build_remote_hearing_profile(parsed, [])
    assert profile.get("detected") is True
    assert TEAMS in [link.get("url") for link in profile.get("links", [])]


def test_remoto_senza_link_e_P0():
    parsed = {
        "headers": {"subject": "Fissazione udienza da remoto in videoconferenza"},
        "body": {
            "text": "Si comunica che l'udienza si terra' da remoto mediante collegamento audiovisivo. Il link verra' comunicato successivamente.",
            "html_text": "",
            "href_urls": [],
        },
        "procedural_profile": {},
        "legal_workflow": {"event_type": "udienza_online"},
        "fields": {},
    }
    report = build_validation_report(parsed, [])
    issue = next((i for i in report.get("issues", []) if i.get("code") == "remote_hearing_link_missing"), None)
    assert issue is not None
    assert issue.get("severity") == "danger"
    assert issue.get("priority") == "P0"
    assert report.get("severity") == "danger"


def test_remoto_con_link_non_e_P0():
    parsed = {
        "headers": {"subject": "Fissazione udienza da remoto"},
        "body": {
            "text": "Udienza da remoto in videoconferenza.",
            "html_text": "",
            "href_urls": [TEAMS],
        },
        "procedural_profile": {},
        "legal_workflow": {"event_type": "udienza_online"},
        "fields": {},
    }
    report = build_validation_report(parsed, [])
    codes = {i.get("code") for i in report.get("issues", [])}
    assert "remote_hearing_link_missing" not in codes
    assert "remote_hearing_link_detected" in codes
