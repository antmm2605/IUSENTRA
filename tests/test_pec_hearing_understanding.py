from __future__ import annotations

from urllib.parse import urlparse

from pct.pec_legal_event_understanding import build_legal_event_understanding

from pct.pec_pipeline import (
    AttachmentPayload,
    _is_remote_hearing_url,
    _unified_hearing_mode,
    build_remote_hearing_profile,
    build_validation_report,
    extract_html_hrefs,
    extract_ics_texts,
)


TEAMS = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc/0?context=xyz"


def test_link_udienza_accetta_solo_https_esplicito():
    assert _is_remote_hearing_url(TEAMS)[0] is True
    assert _is_remote_hearing_url(TEAMS.replace("https://", "http://", 1))[0] is False
    assert _is_remote_hearing_url(TEAMS.removeprefix("https://"))[0] is False


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


def test_modalita_unica_taxonomy():
    assert _unified_hearing_mode("trattazione scritta ex art. 127-ter, deposito note scritte", remote_detected=False) == "note_scritte"
    assert _unified_hearing_mode("udienza in presenza aula 3 piano 2 presso il tribunale", remote_detected=False) == "presenza"
    assert _unified_hearing_mode("udienza da remoto in videoconferenza", remote_detected=True) == "remoto"
    assert _unified_hearing_mode("udienza mista, parte in presenza e parte da remoto, aula mvc", remote_detected=True) == "mista"
    assert _unified_hearing_mode("nessun riferimento", remote_detected=False) == ""


def test_profilo_udienza_in_presenza_viene_estratto_senza_falso_remoto():
    parsed = {
        "headers": {"subject": "Decreto di fissazione udienza"},
        "body": {
            "text": "Il giudice fissa l'udienza in presenza in aula 3 per il 20/10/2026 alle ore 09:30.",
            "html_text": "",
            "href_urls": [],
        },
        "procedural_profile": {},
    }

    profile = build_remote_hearing_profile(parsed, [])

    assert profile["detected"] is False
    assert profile["hearing_detected"] is True
    assert profile["mode_unified"] == "presenza"
    assert profile["mode"] == "in presenza"
    assert "20/10/2026 ore 09:30" in profile["times"]
    assert set(profile["hearing_sources"]) == {"Oggetto PEC", "Corpo PEC"}


def test_link_udienza_da_ics_estratto():
    ics = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:x@t\r\n"
        b"DTSTART:20260710T090000\r\nSUMMARY:Udienza\r\n"
        b"DESCRIPTION:Collegamento https://teams.microsoft.com/l/meetup-join/19%3aABC/0\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR"
    )
    att = AttachmentPayload(index=0, filename="invito.ics", content_type="text/calendar", data=ics)
    ics_text = extract_ics_texts([att])
    assert "Collegamento" in ics_text
    parsed = {
        "headers": {"subject": "Fissazione udienza"},
        "body": {"text": "udienza da remoto", "html_text": "", "href_urls": [], "ics_text": ics_text},
        "procedural_profile": {},
    }
    profile = build_remote_hearing_profile(parsed, [])
    links = [str(link.get("url") or "") for link in profile.get("links", [])]
    assert any((urlparse(url).hostname or "") == "teams.microsoft.com" for url in links)
    assert profile.get("mode_unified") == "remoto"


def test_comprensione_preserva_due_udienze_e_associa_il_link_al_blocco_corretto():
    first_link = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_mattina/0"
    second_link = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_pomeriggio/0"
    first_context = f"Udienza del 20/10/2026 ore 09:15 da remoto. Collegamento {first_link}"
    second_context = f"Udienza del 21/10/2026 ore 14:30 da remoto. Collegamento {second_link}"
    parsed = {
        "headers": {"subject": "Decreto di fissazione di due udienze"},
        "body": {"text": f"{first_context}\n{second_context}", "href_urls": []},
        "procedural_profile": {},
        "procedural_dates": [
            {
                "date": "2026-10-20",
                "time": "09:15",
                "label": "Udienza",
                "source": "decreto.pdf",
                "context": first_context,
            },
            {
                "date": "2026-10-21",
                "time": "14:30",
                "label": "Udienza",
                "source": "decreto.pdf",
                "context": second_context,
            },
        ],
    }

    result = build_legal_event_understanding(parsed, {})

    assert [(row["date"], row["time"]) for row in result["hearings"]] == [
        ("2026-10-20", "09:15"),
        ("2026-10-21", "14:30"),
    ]
    assert [row["link"] for row in result["hearings"]] == [first_link, second_link]


def test_comprensione_non_fonde_due_udienze_nello_stesso_slot_con_link_distinti():
    first_link = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_slot_a/0"
    second_link = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_slot_b/0"
    parsed = {
        "headers": {"subject": "Due procedimenti nello stesso slot"},
        "body": {"text": f"Collegamento {first_link}\nCollegamento {second_link}"},
        "procedural_profile": {},
        "procedural_dates": [
            {
                "date": "2026-10-20",
                "raw_date": "20/10/2026",
                "time": "09:15",
                "label": "Udienza",
                "source": "decreto-a.pdf",
                "context": f"RG 100/2026: udienza del 20/10/2026 ore 09:15. {first_link}",
            },
            {
                "date": "2026-10-20",
                "raw_date": "20/10/2026",
                "time": "09:15",
                "label": "Udienza",
                "source": "decreto-b.pdf",
                "context": f"RG 200/2026: udienza del 20/10/2026 ore 09:15. {second_link}",
            },
        ],
    }

    result = build_legal_event_understanding(parsed, {})

    assert len(result["hearings"]) == 2
    assert {row["link"] for row in result["hearings"]} == {first_link, second_link}
