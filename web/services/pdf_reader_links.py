"""Link PDF sulle coordinate native, senza alterare pagina o testo."""

from html import escape

from .document_reader_links import anchor_attributes, safe_link, text_address


def page_links(page, document):
    from pdfminer.pdftypes import resolve1

    links = []
    for annotation in page.annots or []:
        data = annotation.get("data") or {}
        action = resolve1(data.get("A")) or {}
        if not isinstance(action, dict):
            continue
        uri = annotation.get("uri") or action.get("URI")
        if isinstance(uri, bytes):
            uri = uri.decode("utf-8", errors="replace")
        href = safe_link(uri)
        if not href:
            destination = data.get("Dest") or action.get("D")
            try:
                if isinstance(destination, (bytes, str)):
                    destination = document.doc.get_dest(destination)
                destination = resolve1(destination)
                if isinstance(destination, dict):
                    destination = resolve1(destination.get("D"))
                if isinstance(destination, list) and destination:
                    target_id = getattr(destination[0], "objid", None)
                    number = next((i for i, target in enumerate(document.pages, 1)
                                   if target.page_obj.pageid == target_id), None)
                    if number:
                        href = f"#reader-page-{number}"
            except (KeyError, TypeError, ValueError):
                pass
        if href and all(annotation.get(key) is not None for key in ("x0", "x1", "top", "bottom")):
            links.append({"href": href, **{key: float(annotation[key]) for key in ("x0", "x1", "top", "bottom")}, "covered": False})
    return links


def word_link(word, links):
    x = (float(word["x0"]) + float(word["x1"])) / 2
    y = (float(word["top"]) + float(word["bottom"])) / 2
    for link in links:
        if link["x0"] <= x <= link["x1"] and link["top"] <= y <= link["bottom"]:
            link["covered"] = True
            return link["href"]
    return text_address(str(word.get("text") or ""))


def link_tag(href):
    if href.startswith("#reader-page-"):
        return f'href="{escape(href, quote=True)}" title="Vai a pagina {href.rsplit("-", 1)[1]}"'
    return anchor_attributes(href) + f' title="Apri collegamento: {escape(href, quote=True)}"'


def non_text_links(links, width, height):
    if width <= 0 or height <= 0:
        return ""
    html = []
    for link in links:
        if link["covered"]:
            continue
        style = (f'left:{100*link["x0"]/width:.5f}%;top:{100*link["top"]/height:.5f}%;'
                 f'width:{100*(link["x1"]-link["x0"])/width:.5f}%;height:{100*(link["bottom"]-link["top"])/height:.5f}%;')
        html.append(f'<a class="reader-document-link" {link_tag(link["href"])} aria-label="Apri collegamento: {escape(link["href"],quote=True)}" style="{style}"></a>')
    return "".join(html)
