from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _widget_js() -> str:
    return (REPO_ROOT / "web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")


def _lex_widget_scss() -> str:
    return (REPO_ROOT / "web/static/scss/components/_pct-lex-assistant.scss").read_text(encoding="utf-8")


def test_widget_send_uses_canonical_backend_even_with_bridge_config_present():
    widget_js = _widget_js()
    send_match = re.search(r"function send\(\) \{(?P<body>.*?)\n  function updateBadge", widget_js, re.S)
    assert send_match, "function send() non trovata nel widget Lex"
    send_body = send_match.group("body")

    assert "sendLocal(text);" in send_body
    assert ("sendVia" + "Companion(text)") not in send_body
    assert "if (bridgeConfig)" not in send_body


def test_widget_builds_single_chat_payload_contract():
    widget_js = _widget_js()
    payload_match = re.search(
        r"function buildChatRequestPayload\(text\) \{(?P<body>.*?)\n  function ensureAssistantReady",
        widget_js,
        re.S,
    )
    assert payload_match, "buildChatRequestPayload(text) non trovata"
    payload_body = payload_match.group("body")

    for field in (
        "session_id",
        "messages",
        "fascicolo_id",
        "context_label",
        "page_context",
        "page_path",
        "attachments",
        "mode",
        "page_section",
    ):
        assert field in payload_body
    assert "messagesPayload.push({ role: 'user', content: currentText });" in payload_body
    assert "messagesPayload = messagesPayload.slice(-HISTORY_LIMIT);" in payload_body
    assert "state.attachments.slice()" in payload_body


def test_widget_payload_supersedes_removed_page_payload_without_losing_core_fields():
    removed_page_core_fields = {
        "session_id",
        "messages",
        "fascicolo_id",
        "mode",
        "attachments",
        "page_section",
    }
    widget_core_fields = {
        "session_id",
        "messages",
        "fascicolo_id",
        "context_label",
        "page_context",
        "page_path",
        "attachments",
        "mode",
        "page_section",
    }

    assert removed_page_core_fields <= widget_core_fields
    assert {"context_label", "page_context", "page_path"} <= widget_core_fields


def test_widget_posts_chat_payload_to_canonical_route():
    widget_js = _widget_js()

    assert "fetch(widget.dataset.chatUrl || '/api/assistente/chat'" in widget_js
    assert "body: JSON.stringify(payload)" in widget_js
    assert "if (!response.ok)" in widget_js
    assert "responseErrorMessage(response, body)" in widget_js
    assert "looksLikeHtmlDocument" in widget_js
    assert "Errore di connessione: ' + (error.message" not in widget_js
    assert "finalizeRequest('Lex non ha completato la richiesta.')" in widget_js


def test_legacy_lex_links_open_floating_widget_without_navigation():
    widget_js = _widget_js()

    assert "function openFloatingLexFromLegacyLink(event)" in widget_js
    assert "document.addEventListener('click', openFloatingLexFromLegacyLink)" in widget_js
    assert "href === '#lex'" in widget_js
    assert "url.origin === window.location.origin && url.pathname === '/lex'" in widget_js
    assert "url.origin !== window.location.origin || url.pathname !== '/lex'" in widget_js
    assert "url.searchParams.get('context')" in widget_js
    assert "event.preventDefault()" in widget_js
    assert "applyLexPageContext(detail, { open: true })" in widget_js


def test_floating_lex_icon_is_draggable_across_the_viewport():
    widget_js = _widget_js()
    widget_scss = _lex_widget_scss()

    assert "function startFabDrag(event)" in widget_js
    assert "fab.addEventListener('pointerdown', startFabDrag)" in widget_js
    assert "pct-ai-widget--fab-only" in widget_js
    assert "fabLeft" in widget_js
    assert "fabTop" in widget_js
    assert "state.suppressFabClick = true" in widget_js
    assert "Icona Lex spostata sul browser corrente." in widget_js
    assert "touch-action: none" in widget_scss
    assert "cursor: grab" in widget_scss
    assert "display: none !important" not in widget_scss


def test_base_template_no_longer_contains_disabled_legacy_lex_chat():
    base_template = (REPO_ROOT / "web/templates/base.html").read_text(encoding="utf-8")

    assert "__legacy_lex_disabled__" not in base_template
    assert "onclick=\"pctAI.send()\"" not in base_template
    assert "window.pctAI = {" not in base_template
    assert '{% include "components/pct_ai_widget.html" %}' in base_template


def test_unregistered_legacy_lex_files_removed():
    for legacy_path in ("web/base.html", "web/cartella.html", "web/export_csv.py"):
        assert not (REPO_ROOT / legacy_path).exists()


def test_lex_standalone_template_removed_from_repository():
    removed_template_name = "lex_" + "chat.html"
    assert not (REPO_ROOT / "web/templates" / removed_template_name).exists()
