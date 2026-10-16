"""Struttura delle pagine pubbliche, senza eseguire script o azioni del sito."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from lex.sources.extractors import _html_encoding, normalize


def _link(url: str, base_url: str) -> str:
    target = urljoin(base_url, url)
    parts = urlsplit(target)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        return ""
    return target


def _text(node: Tag) -> str:
    return normalize(node.get_text(" ", strip=True))


def read_html_structure(content: bytes, content_type: str, *, url: str) -> dict:
    """Mantiene l'inventario completo; separa navigazione e blocchi consultabili.

    Il risultato descrive solo i byte ricevuti: non certifica autorità della
    fonte, vigenza di una norma o completezza di contenuti caricati via script.
    """
    soup = BeautifulSoup(content, "html.parser", from_encoding=_html_encoding(content_type))
    title = _text(soup.title) if soup.title else ""
    encoding = soup.original_encoding or ""
    for node in soup.select("script,style,noscript,template"):
        node.decompose()
    full_text = _text(soup)
    body = soup.body or soup
    # Conservare i pannelli nascosti: possono contenere note o massime già
    # disponibili nel documento. Nessuna esecuzione del codice della pagina.
    for node in list(body.select('nav,[role="navigation"],[role="banner"]')):
        if node.parent is not None:
            node.decompose()
    for node in list(body.find_all(["div", "section", "ul"])):
        if node.parent is None:
            continue
        names = " ".join([str(node.get("id") or ""), *node.get("class", [])])
        tokens = set(re.split(r"[\s_-]+", names.casefold()))
        if tokens & {"navbar", "navigation", "breadcrumb", "tabs", "header", "footer"}:
            if not node.find(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
                link_text = " ".join(_text(link) for link in node.find_all("a"))
                if len(link_text) > len(_text(node)) / 2:
                    node.decompose()
    # Un aside può essere una nota normativa. Non eliminarlo sulla sola
    # geometria editoriale: escludere solo navigazione dichiarata dal sito.
    for node in list(body.select('header,footer')):
        if node.parent is not None and not node.find_parent(["main", "article"]):
            if not node.find(["h1", "h2", "p"]):
                node.decompose()
    for node in list(body.select('input,button,select,textarea,[role="dialog"][aria-modal="true"]')):
        if node.parent is not None:
            node.decompose()

    candidates = [node for node in body.select('main,article,[role="main"]') if _text(node)]
    # Più articoli nella pagina formano un inventario: non sceglierne uno
    # arbitrariamente e perdere gli altri. Si preferisce il contenitore comune.
    candidate_ids = {id(node) for node in candidates}
    roots = [node for node in candidates if not any(id(parent) in candidate_ids for parent in node.parents)]
    root = roots[0] if len(roots) == 1 else body
    links: list[dict] = []
    seen_links: set[tuple[str, str]] = set()
    for anchor in root.find_all("a", href=True):
        target = _link(str(anchor.get("href")), url)
        label = _text(anchor)
        if target and (target, label) not in seen_links:
            seen_links.add((target, label))
            links.append({"url": target, "label": label})

    blocks: list[dict] = []
    tables: list[dict] = []
    section: list[str] = []
    structural_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "table", "pre"]
    containers = ["div", "section", "aside", "dt", "dd"]
    for node in root.find_all(structural_tags + containers):
        if node.find_parent(["table", "pre", "blockquote"]):
            continue
        if node.name in ["p", *containers] and node.find_parent("li"):
            continue
        if node.name in containers and node.find(structural_tags + containers):
            continue
        if node.name == "table":
            rows = [[_text(cell) for cell in row.find_all(["th", "td"], recursive=False)]
                    for row in node.find_all("tr")]
            rows = [row for row in rows if row]
            if not rows:
                continue
            table = {"rows": rows, "section": list(section)}
            tables.append(table)
            text = "\n".join(" | ".join(row) for row in rows)
            kind = "table"
        else:
            if node.name == "li":
                # Il testo dei sottoelenchi ha blocchi propri: non duplicarlo
                # nel genitore e non alterarne l'ordine nell'inventario.
                text = normalize(" ".join(str(part) for part in node.strings
                                          if part.find_parent("li") is node))
            else:
                text = _text(node)
            if not text:
                continue
            kind = "heading" if node.name.startswith("h") else node.name
            if kind == "heading":
                level = int(node.name[1])
                section = section[:level - 1] + [text]
        blocks.append({"index": len(blocks), "kind": kind, "text": text, "section": list(section),
                       "technical_boilerplate": bool(re.fullmatch(
                           r"(?:Pagina generata|Page generated)\s+in\s+[\d.,]+\s+(?:secondi|seconds?|sec|s)\.?", text, re.I)),
                       "form_context": node.find_parent("form") is not None,
                       "link_only_context": sum(len(_text(link)) for link in node.find_all("a")) > len(text) * 0.8,
                       "heading_level": int(node.name[1]) if kind == "heading" else None})
    text = _text(root)
    if text and not blocks:
        blocks.append({"index": 0, "kind": "text", "text": text, "section": []})
    markdown = []
    for block in blocks:
        prefix = "#" * block["heading_level"] + " " if block["kind"] == "heading" else "- " if block["kind"] == "li" else ""
        markdown.append(prefix + block["text"])
    return {
        "title": title, "encoding": encoding, "text": text,
        "full_text": full_text, "blocks": blocks, "links": links,
        "tables": tables, "markdown": "\n\n".join(markdown),
        "block_count": len(blocks), "full_text_characters": len(full_text),
        "text_characters": len(text), "status": "read" if text else "empty",
    }
