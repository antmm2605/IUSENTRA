"""Lettura verificata del documento pubblico GA, senza approvazione della scheda."""
import re
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import parse_qs, urlsplit

from lxml import etree

from pct.openga_html import is_official_html, leggi_html


class DocumentoNonVerificato(ValueError):
    """Il documento non dimostra l'identità richiesta."""



def parse_official_xml(raw):
    """Ignore an external-only declaration; never load a DTD or expand entities."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_000_000:
        raise DocumentoNonVerificato("Documento vuoto o troppo grande.")
    cleaned = raw
    opening = re.search(rb"<GA(?:\s|>)", raw)
    prefix = raw[:opening.start()] if opening else raw
    if b"<!DOCTYPE" in prefix:
        # Some official legacy documents declare a SYSTEM DTD. Remove only that
        # inert declaration, preserving the original bytes separately for SHA.
        external_only = rb"""<!DOCTYPE\s+GA\s+SYSTEM\s+(?:"[^"<>\[\]]+"|'[^'<>\[\]]+')\s*>"""
        prefix, count = re.subn(external_only, b"", prefix, count=1)
        if count != 1 or b"<!DOCTYPE" in prefix:
            raise DocumentoNonVerificato("DTD attivo o sottoinsieme interno non ammesso.")
        cleaned = prefix + raw[opening.start():] if opening else prefix
    try:
        root = etree.fromstring(cleaned, etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False, recover=False))
    except (ValueError, TypeError, etree.XMLSyntaxError):
        raise DocumentoNonVerificato("XML non valido.") from None
    if root.getroottree().docinfo.doctype or any(isinstance(n, etree._Entity) for n in root.iter()):
        raise DocumentoNonVerificato("Entità e DTD attivi non ammessi.")
    return root


def leggi_documento(raw, *, url, schema, anno, numero, ricorso, acquisita_il):
    """Accetta XML o HTML ufficiale completo con identità e URL concordanti.

    Il chiamante deve aver risolto schema e URL dal catalogo ufficiale. Questa
    funzione non effettua richieste e non certifica l'origine del trasporto.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_000_000:
        raise DocumentoNonVerificato("Documento vuoto o troppo grande.")
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != "mdp.giustizia-amministrativa.it"
            or parts.username or parts.password or parts.port not in (None, 443)
            or parts.path != "/visualizza/" or parts.fragment):
        raise DocumentoNonVerificato("Indirizzo ufficiale non valido.")
    query = parse_qs(parts.query, keep_blank_values=True)
    if any(len(values) != 1 for values in query.values()):
        raise DocumentoNonVerificato("Parametri ambigui.")
    if (type(anno) is not int or type(numero) is not int
            or not 1900 <= anno <= 2100 or not 0 < numero <= 99999
            or not re.fullmatch(r"[0-9]{9}", str(ricorso))):
        raise DocumentoNonVerificato("Identità richiesta non valida.")
    filename = query.get("nomeFile", [""])[0]
    if (query.get("schema") != [schema] or query.get("nrg") != [ricorso]
            or query.get("subDir") != ["Provvedimenti"]
            or not re.fullmatch(f"{anno}{numero:05d}_[0-9]{{2}}[.]html", filename)):
        raise DocumentoNonVerificato("Indirizzo e decisione non corrispondono.")
    try:
        if not re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", acquisita_il):
            raise ValueError()
        datetime.strptime(acquisita_il, "%d/%m/%Y").replace(tzinfo=timezone.utc)
        if is_official_html(raw):
            document = leggi_html(raw)
            if (document["anno"] != anno or document["numero"] != numero
                    or ricorso not in document["ricorsi"]):
                raise DocumentoNonVerificato("Estremi HTML diversi dalla decisione richiesta.")
            text = document["testo"]
            return {"testo": text, "sezioni": document["sezioni"],
                    "raw_sha256": sha256(raw).hexdigest(), "formato_originale": "html",
                    "provenienza": {"tipo": "decisione", "url": url,
                        "versione": document["pubblicazione"], "acquisita_il": acquisita_il,
                        "sha256": sha256(text.encode()).hexdigest(), "testo_integrale": True},
                    "approvazione_avvocato": False}
        root = parse_official_xml(raw)
    except (ValueError, TypeError, etree.XMLSyntaxError) as exc:
        if is_official_html(raw) and isinstance(exc, DocumentoNonVerificato):
            raise
        raise DocumentoNonVerificato("XML o data di acquisizione non validi.") from None
    if root.getroottree().docinfo.doctype or any(isinstance(n, etree._Entity) for n in root.iter()):
        raise DocumentoNonVerificato("Entità e DTD non ammesse.")
    documents = root.findall("Provvedimento") if root.tag == "GA" else []
    if len(documents) != 1:
        raise DocumentoNonVerificato("Non è un singolo provvedimento ufficiale.")
    doc = documents[0]
    fascicoli = doc.findall("meta/descrittori/fascicolo")
    fascicolo = fascicoli[0] if len(fascicoli) == 1 else None
    registri = doc.findall("meta/ricorso")
    try:
        match = (fascicolo is not None and int(fascicolo.get("anno")) == anno
                 and int(fascicolo.get("n")) == numero
                 and any(registro.get("NRG") == ricorso for registro in registri))
    except (TypeError, ValueError):
        match = False
    if not match:
        raise DocumentoNonVerificato("Estremi del testo diversi dalla decisione.")
    publication = doc.findtext("meta/dataPubblicazione", "").strip()
    try:
        datetime.strptime(publication, "%d/%m/%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        raise DocumentoNonVerificato("Data di pubblicazione mancante o non valida.") from None
    # Non includere meta: contiene anche percorsi interni del sistema della fonte.
    sections = {}
    allowed = ("epigrafe", "premessa", "premessaTed", "motivazione",
               "motivazioneTed", "dispositivo", "dispositivoTed",
               "sottoscrizioni", "sottoscrizioniTed")
    for name in allowed:
        nodes = doc.findall(name)
        if len(nodes) > 1:
            raise DocumentoNonVerificato("Sezioni ambigue.")
        if nodes:
            text = " ".join(" ".join(nodes[0].itertext()).split())
            if text:
                sections[name] = text
    if not sections.get("epigrafe") or not sections.get("dispositivo"):
        raise DocumentoNonVerificato("Testo integrale non riscontrato.")
    text = "\n\n".join(sections.values())
    return {
        "testo": text, "sezioni": sections, "raw_sha256": sha256(raw).hexdigest(),
        "provenienza": {"tipo": "decisione", "url": url, "versione": publication,
                       "acquisita_il": acquisita_il, "sha256": sha256(text.encode()).hexdigest(),
                       "testo_integrale": True},
        "approvazione_avvocato": False,
    }
