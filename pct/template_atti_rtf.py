"""Esportazione RTF fedele all'editor atti.

Produce un RTF con formato pagina, margini e orientamento dell'editor, timbro
dello studio nell'intestazione (quindi ripetuto su ogni pagina come nei fogli
dell'editor), interruzioni di pagina, allineamenti e formattazione del testo.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Mapping, Sequence

from pct.template_atti_page_setup import PageSetup, is_page_break_element, mm_to_twips

_ALIGN_COMMANDS = {"left": "\\ql", "center": "\\qc", "right": "\\qr", "justify": "\\qj"}
_BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "li", "tr", "section", "article", "pre", "address"}
_HEADING_SCALE = {"h1": 1.42, "h2": 1.16, "h3": 1.06, "h4": 1.0, "h5": 1.0, "h6": 1.0}
_INLINE_COMMANDS = {
    "strong": "\\b",
    "b": "\\b",
    "em": "\\i",
    "i": "\\i",
    "u": "\\ul",
    "s": "\\strike",
    "strike": "\\strike",
    "del": "\\strike",
    "sub": "\\sub",
    "sup": "\\super",
}
_STYLE_ALIGN = re.compile(r"text-align\s*:\s*(left|right|center|justify)", re.I)


def rtf_escape(value: str) -> str:
    parts: list[str] = []
    for char in str(value or ""):
        code = ord(char)
        if char == "\\":
            parts.append("\\\\")
        elif char == "{":
            parts.append("\\{")
        elif char == "}":
            parts.append("\\}")
        elif char == "\n":
            parts.append("\\line ")
        elif char == "\t":
            parts.append("\\tab ")
        elif char == "\u00a0":
            parts.append("\\~")
        elif code > 0xFFFF:
            encoded = char.encode("utf-16-le")
            for index in range(0, len(encoded), 2):
                unit = int.from_bytes(encoded[index:index + 2], "little")
                parts.append(f"\\u{unit - 65536 if unit > 32767 else unit}?")
        elif code > 127:
            parts.append(f"\\u{code - 65536 if code > 32767 else code}?")
        else:
            parts.append(char)
    return "".join(parts)


def _style_commands(style: str) -> list[str]:
    lowered = (style or "").lower().replace(" ", "")
    commands: list[str] = []
    if "font-weight:bold" in lowered or re.search(r"font-weight:(6|7|8|9)00", lowered):
        commands.append("\\b")
    if "font-style:italic" in lowered:
        commands.append("\\i")
    if "underline" in lowered:
        commands.append("\\ul")
    if "line-through" in lowered:
        commands.append("\\strike")
    return commands


class _RtfBodyWriter(HTMLParser):
    def __init__(self, *, font_size_pt: float, line_height: float, default_align: str) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.font_half_points = int(round(font_size_pt * 2))
        self.space_after_twips = int(round(font_size_pt * 0.82 * 20))
        self.line_twips = int(round(240 * line_height))
        self.default_align = default_align
        self._open_paragraph = False
        self._paragraph_groups = 0
        self._list_stack: list[dict[str, int | str]] = []
        self._pending_page_break = False
        self._skip_depth = 0
        self._inline_stack: list[tuple[str, int]] = []
        self._heading_depth = 0
        self._cell_index = 0

    # -- paragrafi ---------------------------------------------------------
    def _start_paragraph(self, tag: str, attrs: Mapping[str, str]) -> None:
        self._close_paragraph()
        style = attrs.get("style", "")
        match = _STYLE_ALIGN.search(style or "") or _STYLE_ALIGN.search(f"text-align:{attrs.get('align', '')}")
        align = match.group(1).lower() if match else ("center" if tag in {"h1", "h2"} else self.default_align)
        size = self.font_half_points
        space_before = 0
        if tag in _HEADING_SCALE:
            size = int(round(self.font_half_points * _HEADING_SCALE[tag]))
            space_before = int(round(self.space_after_twips * 1.2))
        indent = ""
        if tag == "li" and self._list_stack:
            depth = len(self._list_stack)
            indent = f"\\fi-360\\li{360 + (360 * depth)}"
        elif tag == "blockquote":
            indent = "\\li720\\ri360"
        space_after = int(round(self.space_after_twips * (0.3 if tag == "li" else 1)))
        page_break = "\\pagebb" if self._pending_page_break else ""
        self._pending_page_break = False
        self.parts.append(
            f"{{\\pard\\plain{page_break}{_ALIGN_COMMANDS.get(align, chr(92) + 'qj')}{indent}"
            f"\\sb{space_before}\\sa{space_after}\\sl{self.line_twips}\\slmult1\\f0\\fs{size} "
        )
        self._open_paragraph = True
        self._paragraph_groups = 0
        if tag in _HEADING_SCALE:
            self.parts.append("{\\b ")
            self._paragraph_groups += 1
        if tag == "blockquote":
            self.parts.append("{\\i ")
            self._paragraph_groups += 1
        if tag == "li" and self._list_stack:
            current = self._list_stack[-1]
            if current["kind"] == "ol":
                current["counter"] = int(current["counter"]) + 1
                self.parts.append(f"{current['counter']}.\\tab ")
            else:
                self.parts.append("\\u8226?\\tab ")

    def _ensure_paragraph(self) -> None:
        if not self._open_paragraph:
            self._start_paragraph("p", {})

    def _close_paragraph(self) -> None:
        if not self._open_paragraph:
            return
        while self._inline_stack:
            self._inline_stack.pop()
            self.parts.append("}")
        self.parts.append("}" * self._paragraph_groups)
        self.parts.append("\\par}\n")
        self._open_paragraph = False
        self._paragraph_groups = 0

    # -- parser ------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs_list: Sequence[tuple[str, str | None]]) -> None:
        name = tag.lower()
        attrs = {str(key).lower(): str(value or "") for key, value in attrs_list}
        if name in {"script", "style", "head", "title"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if "data-iu-line-spacer" in attrs:
            return
        if is_page_break_element(name, attrs):
            self._close_paragraph()
            self._pending_page_break = True
            return
        if name == "hr":
            self._close_paragraph()
            self.parts.append("{\\pard\\plain\\brdrb\\brdrs\\brdrw10\\brsp20\\sa120\\fs4 \\par}\n")
            return
        if name in {"ul", "ol"}:
            self._close_paragraph()
            self._list_stack.append({"kind": name, "counter": 0})
            return
        if name == "br":
            self._ensure_paragraph()
            self.parts.append("\\line ")
            return
        if name in {"td", "th"}:
            self._ensure_paragraph()
            if self._cell_index:
                self.parts.append("\\tab ")
            self._cell_index += 1
            if name == "th":
                self.parts.append("{\\b ")
                self._inline_stack.append((name, 1))
            return
        if name in _BLOCK_TAGS:
            if name == "tr":
                self._cell_index = 0
            self._start_paragraph(name, attrs)
            return
        commands = []
        if name in _INLINE_COMMANDS:
            commands.append(_INLINE_COMMANDS[name])
        commands.extend(_style_commands(attrs.get("style", "")))
        if commands:
            self._ensure_paragraph()
            self.parts.append("{" + "".join(commands) + " ")
            self._inline_stack.append((name, 1))
        else:
            self._inline_stack.append((name, 0))

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in {"script", "style", "head", "title"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if name in {"ul", "ol"}:
            self._close_paragraph()
            if self._list_stack:
                self._list_stack.pop()
            return
        if name in _BLOCK_TAGS:
            if name != "tr" or self._open_paragraph:
                self._close_paragraph()
            return
        for index in range(len(self._inline_stack) - 1, -1, -1):
            open_name, groups = self._inline_stack[index]
            if open_name == name:
                closing = self._inline_stack[index:]
                del self._inline_stack[index:]
                self.parts.append("}" * sum(item[1] for item in closing))
                break

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data:
            return
        if not self._open_paragraph and not data.strip():
            return
        self._ensure_paragraph()
        self.parts.append(rtf_escape(re.sub(r"\s*\n\s*", " ", data)))

    def result(self) -> str:
        self._close_paragraph()
        if self._pending_page_break:
            self.parts.append("{\\pard\\plain\\pagebb\\par}\n")
        return "".join(self.parts)


def rtf_body_from_html(html: str, *, font_size_pt: float = 12.0, line_height: float = 1.5, default_align: str = "justify") -> str:
    writer = _RtfBodyWriter(font_size_pt=font_size_pt, line_height=line_height, default_align=default_align)
    writer.feed(html or "")
    writer.close()
    return writer.result()


def rtf_body_from_text(text: str, *, font_size_pt: float = 12.0, line_height: float = 1.5, default_align: str = "justify") -> str:
    size = int(round(font_size_pt * 2))
    line_twips = int(round(240 * line_height))
    space_after = int(round(font_size_pt * 0.82 * 20))
    align = _ALIGN_COMMANDS.get(default_align, "\\qj")
    blocks = [block for block in re.split(r"\n\s*\n", str(text or "").replace("\r\n", "\n")) if block.strip()] or [""]
    return "".join(
        f"{{\\pard\\plain{align}\\sa{space_after}\\sl{line_twips}\\slmult1\\f0\\fs{size} {rtf_escape(block.strip())}\\par}}\n"
        for block in blocks
    )


def _stamp_header(setup: PageSetup, stamp_lines: Sequence[Mapping[str, Any]]) -> str:
    if not stamp_lines:
        return ""
    size = int(round(setup.stamp_font_size_pt * 2))
    line_twips = int(round(240 * setup.stamp_line_height))
    align = _ALIGN_COMMANDS.get(setup.stamp_alignment, "\\qc")
    content = "\\line ".join(
        ("{\\b " + rtf_escape(str(line.get("text") or "")) + "}") if line.get("bold") else rtf_escape(str(line.get("text") or ""))
        for line in stamp_lines
    )
    return f"{{\\header \\pard\\plain{align}\\sl{line_twips}\\slmult1\\f1\\fs{size} {content}\\par}}\n"


def build_rtf_document(
    *,
    setup: PageSetup,
    body_font: str,
    stamp_font: str,
    font_size_pt: float,
    line_height: float,
    text_align: str,
    stamp_lines: Sequence[Mapping[str, Any]],
    html: str = "",
    text: str = "",
) -> str:
    body_font_name = re.sub(r"[;{}\\]", "", body_font or "Times New Roman") or "Times New Roman"
    stamp_font_name = re.sub(r"[;{}\\]", "", stamp_font or "Courier New") or "Courier New"
    body = (
        rtf_body_from_html(html, font_size_pt=font_size_pt, line_height=line_height, default_align=text_align)
        if html
        else rtf_body_from_text(text, font_size_pt=font_size_pt, line_height=line_height, default_align=text_align)
    )
    width = mm_to_twips(setup.width_mm)
    height = mm_to_twips(setup.height_mm)
    margins = (
        f"\\margl{mm_to_twips(setup.margin_left_mm)}\\margr{mm_to_twips(setup.margin_right_mm)}"
        f"\\margt{mm_to_twips(setup.body_top_mm(len(stamp_lines)))}\\margb{mm_to_twips(setup.margin_bottom_mm)}"
    )
    landscape = "\\landscape" if setup.landscape else ""
    section_landscape = "\\lndscpsxn" if setup.landscape else ""
    header_y = mm_to_twips(setup.stamp_top_mm() if setup.stamp_at_top else setup.margin_top_mm)
    return (
        "{\\rtf1\\ansi\\ansicpg1252\\deff0\\uc1\n"
        f"{{\\fonttbl{{\\f0\\froman {body_font_name};}}{{\\f1\\fmodern {stamp_font_name};}}}}\n"
        f"\\paperw{width}\\paperh{height}{margins}{landscape}\\headery{header_y}\\footery720\n"
        f"\\sectd{section_landscape}\\pgwsxn{width}\\pghsxn{height}\\headery{header_y}\n"
        f"\\f0\\fs{int(round(font_size_pt * 2))}\n"
        f"{_stamp_header(setup, stamp_lines)}"
        f"{body}"
        "}"
    )
