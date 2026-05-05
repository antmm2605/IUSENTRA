from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _widget_js() -> str:
    return (REPO_ROOT / "web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")


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
    assert "finalizeRequest('Connessione a Lex non riuscita.')" in widget_js


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


def test_lex_standalone_template_removed_from_repository():
    removed_template_name = "lex_" + "chat.html"
    assert not (REPO_ROOT / "web/templates" / removed_template_name).exists()
