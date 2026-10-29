"""Documento GA in HTML ufficiale: struttura completa e identità, mai pagine generiche.

Il testo resta una trascrizione del corpo pubblicato. Nessuna esecuzione di HTML,
script, DTD o richieste di rete; l'originale conserva la propria impronta separata.
"""
import re
from datetime import datetime

from lxml import etree, html


def is_official_html(raw):
    if not isinstance(raw, bytes):
        return False
    prefix = raw.removeprefix(b"\xef\xbb\xbf").lstrip().lower()
    return prefix.startswith((b"<!doctype html", b"<html"))


def leggi_html(raw):
    from pct.openga_documento import DocumentoNonVerificato

    def reject(message):
        raise DocumentoNonVerificato(message)

    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_000_000:
        reject("HTML vuoto o troppo grande.")
    declarations = re.findall(rb"<!DOCTYPE\b[^>]*>", raw, re.I)
    if (len(declarations) > 1
            or any(not re.fullmatch(rb"<!DOCTYPE\s+html\s*>", d, re.I) for d in declarations)
            or re.search(rb"<!ENTITY\b", raw, re.I)):
        reject("DTD o entità attive non ammesse nel documento HTML.")
    if (not raw.rstrip().lower().endswith(b"</html>")
            or len(re.findall(rb"<body(?:\s|>)", raw, re.I)) != 1
            or len(re.findall(rb"</body\s*>", raw, re.I)) != 1):
        reject("Documento HTML incompleto o con corpo ambiguo.")
    try:
        root = html.fromstring(raw, parser=html.HTMLParser(
            no_network=True, remove_comments=True, recover=True))
    except (etree.ParserError, etree.XMLSyntaxError, ValueError):
        reject("Documento HTML non leggibile.")
    if root.tag != "html" or root.xpath("//script|//iframe|//object|//embed"):
        reject("Struttura HTML non ammessa per il testo ufficiale.")
    bodies = root.xpath("//body")
    if len(bodies) != 1:
        reject("Corpo del documento HTML non univoco.")
    body = bodies[0]
    # La trasformazione ufficiale può pubblicare la data come testo in HEAD:
    # un parser HTML, come il browser, la sposta nel corpo. Le regole di XML
    # restano separate; la data viene riscontrata prima del tag BODY originale.
    opening = re.search(rb"<body(?:\s|>)", raw, re.I)
    publications = re.findall(rb"Pubblicato\s+il\s+([0-9]{2}/[0-9]{2}/[0-9]{4})", raw[:opening.start()], re.I)
    if len(publications) != 1:
        reject("Data di pubblicazione HTML assente o ambigua.")
    publications = [value.decode("ascii") for value in publications]
    for style in body.xpath(".//style"):
        style.drop_tree()
    paragraphs = [" ".join("".join(n.itertext()).split())
                  for n in body.xpath(".//p|.//h1|.//h2|.//h3|"
                      ".//td[not(.//p or .//h1 or .//h2 or .//h3 or .//td or .//th)]|"
                      ".//th[not(.//p or .//h1 or .//h2 or .//h3 or .//td or .//th)]")]
    paragraphs = [p for p in paragraphs if p]
    # Fallire se parti del corpo non appartengono ai blocchi letti: niente
    # perdita silenziosa di contenuti in un layout nuovo o inatteso.
    def compact(text):
        return re.sub(r"\s+", "", text)
    body_text = "".join(body.itertext())
    body_text = re.sub(r"^\s*Pubblicato\s+il\s+" + re.escape(publications[0]), "", body_text, count=1, flags=re.I)
    if compact(body_text) != compact("".join(paragraphs)):
        reject("Contenuto HTML esterno ai blocchi verificati.")
    types = {"SENTENZA", "SENTENZA BREVE", "ORDINANZA", "DECRETO", "PARERE"}
    headings = [(n, p) for n, p in enumerate(paragraphs[:25]) if p.upper() in types]
    if len(headings) != 1:
        reject("Tipo del provvedimento HTML assente o ambiguo.")
    type_index, kind = headings[0]
    header = "\n".join(paragraphs[:type_index])
    decisions = re.findall(r"\bN\.\s*(\d{1,5})\s*/\s*(\d{4})\s+REG\s*\.\s*PROV\s*\.\s*COLL\s*\.", header, re.I)
    appeals = re.findall(r"\bN\.\s*(\d{1,5})\s*/\s*(\d{4})\s+REG\s*\.\s*RIC\s*\.", header, re.I)
    offices = [p for p in paragraphs[:type_index] if re.search(
        r"tribunale amministrativo|consiglio di stato|consiglio di giustizia amministrativa|tribunale regionale di giustizia amministrativa", p, re.I)]
    if len(decisions) != 1 or not appeals or len(offices) != 1:
        reject("Identità e organo del provvedimento HTML non riscontrati.")
    if kind.upper().startswith("SENTENZA") and "REPUBBLICA ITALIANA" not in header.upper():
        reject("Intestazione del provvedimento HTML incompleta.")
    try:
        datetime.strptime(publications[0], "%d/%m/%Y")
    except ValueError:
        reject("Data di pubblicazione HTML non valida.")
    endings = [n for n, p in enumerate(paragraphs) if re.match(r"^P\s*\.\s*Q\s*\.\s*M\s*\.", p, re.I)]
    closings = [n for n, p in enumerate(paragraphs) if re.match(r"^Cos[iì]\s+deciso\s+in\s+", p, re.I)]
    if (len(endings) != 1 or len(closings) != 1
            or not type_index < endings[0] < closings[0] < len(paragraphs) - 1):
        reject("Testo HTML integrale, dispositivo o sottoscrizioni non riscontrati.")
    disposition, closing = endings[0], closings[0]
    sections = {
        "epigrafe": "\n\n".join(paragraphs[:type_index + 1]),
        "motivazione": "\n\n".join(paragraphs[type_index + 1:disposition]),
        "dispositivo": "\n\n".join(paragraphs[disposition:closing]),
        "sottoscrizioni": "\n\n".join(paragraphs[closing:]),
    }
    text = "\n\n".join(value for value in sections.values() if value)
    if compact(text) != compact("".join(paragraphs)) or len(text) < 300:
        reject("Copertura del corpo HTML non dimostrata.")
    number, year = decisions[0]
    return {"anno": int(year), "numero": int(number),
            "ricorsi": tuple(f"{year}{int(number):05d}" for number, year in appeals),
            "tipo": kind, "organo_header": offices[0], "chiusura": paragraphs[closing],
            "pubblicazione": publications[0], "sezioni": sections, "testo": text}
