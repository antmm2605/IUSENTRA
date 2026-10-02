"""Collegamenti del documento: destinazioni esplicite, testo e HTML sicuri."""

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

_ADDRESS = re.compile(r"(?:https?://|www\.)[^\s<>\"']+|[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}", re.IGNORECASE)


def safe_link(value: object) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 2048 or any(ord(char) < 32 for char in raw):
        return ""
    if raw.startswith("www."):
        raw = "https://" + raw
    try:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            return raw
        if parsed.scheme.lower() in {"mailto", "tel"} and parsed.path:
            return raw
    except ValueError:
        pass
    return ""


def text_address(text: str) -> str:
    match = _ADDRESS.fullmatch(text.rstrip(".,;:!?)]}"))
    if not match:
        return ""
    address = match.group()
    return safe_link("mailto:" + address if "@" in address and "://" not in address else address)


def anchor_attributes(href: str) -> str:
    return f'href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"'


def linkify_text(text: str) -> str:
    parts, end = [], 0
    for match in _ADDRESS.finditer(text):
        raw = match.group().rstrip(".,;:!?)]}")
        href = text_address(raw)
        parts.append(escape(text[end:match.start()]))
        parts.append(f'<a {anchor_attributes(href)}>{escape(raw)}</a>' if href else escape(raw))
        parts.append(escape(match.group()[len(raw):]))
        end = match.end()
    parts.append(escape(text[end:]))
    return "".join(parts)


class _LinkActivator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.anchor_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchor_depth += 1
            attributes = dict(attrs)
            href = safe_link(attributes.get("href"))
            if href:
                attributes.update(href=href, target="_blank", rel="noopener noreferrer", referrerpolicy="no-referrer")
                self.parts.append('<a ' + ' '.join(f'{key}="{escape(value or "", quote=True)}"' for key, value in attributes.items()) + '>')
                return
        self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag == "a":
            self.anchor_depth = max(0, self.anchor_depth - 1)
        self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        self.parts.append(escape(data) if self.anchor_depth else linkify_text(data))


def activate_links(body: str) -> str:
    # Il corpo arriva esclusivamente dai renderer sanitizzati del lettore.
    parser = _LinkActivator()
    parser.feed(body)
    parser.close()
    return "".join(parser.parts)
