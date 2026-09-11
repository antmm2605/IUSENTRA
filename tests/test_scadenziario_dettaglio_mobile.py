"""Scadenza selezionata: dettaglio leggibile e senza dati tecnici."""

from __future__ import annotations

import re
from pathlib import Path

from pct import pec_legal_event_understanding as understanding


def test_codice_di_accesso_non_letto_da_codice_fiscale_destinatario():
    pattern = understanding._PASSCODE_RE
    assert pattern.search("CodiceFiscaleDestinatario codice_fiscale_destinatario MNTGPP94L01G791A") is None
    assert pattern.search("codice esito 0") is None
    assert pattern.search("Passcode: Ab12Cd") is not None
    assert pattern.search("Passcode: Ab12Cd").group(1) == "Ab12Cd"
    assert pattern.search("Codice di accesso 123456") is not None
    assert pattern.search("Codice di accesso 123456").group(1) == "123456"


def test_dettaglio_scadenza_una_colonna_azioni_e_gruppi():
    page = Path("frontend/src/components/ScadenziarioPage.tsx").read_text(encoding="utf-8")
    facts = Path("frontend/src/features/scadenziario/deadlineDetailFacts.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/ScadenziarioPage.css").read_text(encoding="utf-8")

    assert "function DeadlineFocusDetail" in page
    assert "<DeadlineFocusDetail" in page
    assert "deadlineFactGroups(row, { notificationPresidio })" in page
    assert "deadlineWhatToDo(row)" in page
    assert "<h2>{focusedRow.title}</h2>" not in page
    assert "Cosa fare" in page and "iu-scad-focus-when" in page
    assert "cleanAccessInfo(item.remoteHearingAccessInfo)" in page

    assert "export function plausiblePasscode" in facts
    assert "if (/^testo\\/href/i.test(clean)) return 'Testo o link della comunicazione'" in facts
    assert "'Provvedimento e ufficio'" in facts
    assert "PASSCODE_STOPWORDS" in facts

    focus_rule = css[css.index(".iu-scad-focus-card{") : css.index("}", css.index(".iu-scad-focus-card{"))]
    assert "grid-template-columns:minmax(0,1fr)" in focus_rule
    assert "min-width:260px" not in css
    assert "grid-template-columns:repeat(auto-fill,minmax(180px,1fr))" in css
    mobile = css[css.index("@media(max-width:760px){") :]
    assert re.search(r"\.iu-scad-focus-actions\{\s*order:10;\s*position:sticky;\s*bottom:0;", mobile)
    assert ".iu-scad-focus-back{display:none!important}" in mobile
    assert "env(safe-area-inset-bottom)" in mobile


def test_agenda_non_mostra_codici_o_piattaforme_non_plausibili():
    agenda = Path("frontend/src/components/AgendaPage.tsx").read_text(encoding="utf-8")
    assert "plausiblePasscode(event.remoteHearingPasscode)" in agenda
    assert "readablePlatform(event.remoteHearingPlatform" in agenda
    assert "cleanAccessInfo(event.remoteHearingAccessInfo)" in agenda
    assert "Codice di accesso: ${event.remoteHearingPasscode}" not in agenda
