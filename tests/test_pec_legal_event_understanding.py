from __future__ import annotations

from pct.pec_legal_event_understanding import SCHEMA, build_legal_event_understanding


def _parsed():
    return {
        "headers": {"subject": "Fissazione udienza da remoto", "date": "2026-03-02"},
        "legal_workflow": {
            "family": "comunicazione_cancelleria_civile",
            "family_label": "Cancelleria civile",
            "event_type": "udienza_online",
            "event_label": "Udienza online",
            "priority": "alta",
        },
        "body": {"text": "Udienza da remoto, trattazione ex art. 127-ter. Il link verra' comunicato.", "ics_text": ""},
        "pct_deposit_receipt": {},
    }


def test_vista_unificata_aggrega_segnali():
    report = {"remote_hearing": {"detected": True, "mode_unified": "remoto", "links": [], "times": [], "pdf_required": False}}
    u = build_legal_event_understanding(_parsed(), report)
    assert u["schema"] == SCHEMA
    assert u["classification"]["family"] == "comunicazione_cancelleria_civile"
    assert u["hearing"]["mode"] == "remoto"
    assert u["deadline"]["ok"] is True
    assert u["deadline"]["template_code"] == "CIV_OPPOSIZIONE_127_TER"
    assert u["human_review_required"] is True


def test_web_push_safe_title_niente_pii_e_P0_su_remoto_senza_link():
    report = {"remote_hearing": {"detected": True, "mode_unified": "remoto", "links": [], "pdf_required": False}}
    u = build_legal_event_understanding(_parsed(), report)
    title = u["web_push_safe_title"]
    assert "P0" in title and "remoto" in title.lower()
    # nessun nome/cliente/CF nel titolo push
    assert "@" not in title


def test_senza_report_non_esplode():
    u = build_legal_event_understanding(_parsed(), None)
    assert u["schema"] == SCHEMA
    assert u["hearing"] is None  # nessun remote_hearing nel report
