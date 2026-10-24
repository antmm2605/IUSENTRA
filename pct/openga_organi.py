"""Riscontro conservativo dell'organo nel testo, indipendente dallo schema URL."""
import re
import unicodedata

from lxml import etree

from pct.openga_documento import DocumentoNonVerificato, parse_official_xml

_REGIONS = {
    "001": ("lazio", "latina"), "003": ("lazio", "roma"),
    "004": ("abruzzo", "aquila"), "005": ("abruzzo", "pescara"),
    "006": ("", "bolzano"), "007": ("basilicata", ""),
    "008": ("calabria", "catanzaro"), "009": ("calabria", "reggio calabria"),
    "010": ("campania", "napoli"), "011": ("campania", "salerno"),
    "012": ("emilia romagna", "bologna"), "013": ("emilia romagna", "parma"),
    "014": ("friuli venezia giulia", ""), "015": ("liguria", ""),
    "016": ("lombardia", "milano"), "017": ("lombardia", "brescia"),
    "018": ("marche", ""), "019": ("molise", ""), "020": ("piemonte", ""),
    "021": ("puglia", "bari"), "022": ("puglia", "lecce"),
    "023": ("sardegna", ""), "024": ("sicilia", "palermo"),
    "025": ("sicilia", "catania"), "026": ("toscana", ""),
    "027": ("", "trento"), "028": ("umbria", ""), "029": ("valle d aosta", ""),
    "030": ("veneto", ""),
}


def _normal(text):
    text = unicodedata.normalize("NFKD", text).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def verifica_organo(raw, row):
    """Solo intestazione dell'organo: non città citate nei fatti o nei difensori."""
    try:
        root = parse_official_xml(raw)
        if root.getroottree().docinfo.doctype:
            return False
        doc = root.find("Provvedimento")
        if doc is None:
            return False
        # L'adunanza contiene il collegio e l'organo, non le parti né l'oggetto.
        header = _normal(" ".join(doc.find("epigrafe/adunanza").itertext()))
        urn = _normal(doc.findtext("meta/descrittori/urn", ""))
        release = _normal(doc.findtext("meta/rilascio", ""))
        disposition = doc.find("dispositivo")
        closing = _normal(" ".join(disposition.itertext())) if disposition is not None else ""
    except (DocumentoNonVerificato, etree.XMLSyntaxError, AttributeError, TypeError):
        return False
    office = str(row.get("sede", ""))
    if office == "002":
        return "consiglio di stato" in header and "consiglio di giustizia" not in header
    if office == "032":
        return "consiglio di giustizia amministrativa" in header and "siciliana" in header
    rule = _REGIONS.get(office)
    if not rule:
        return False
    region, city = rule
    trga = "tribunale regionale di giustizia amministrativa" in header
    if "tribunale amministrativo" not in header and not trga:
        return False
    if office in {"006", "027"}:
        if "tar trentino alto adige" not in urn:
            return False
    elif trga:
        return False
    if region and (region not in header or "tar " + region not in urn):
        return False
    # Tre riscontri documentali ammessi: intestazione, metadato di sede,
    # oppure formula di deliberazione del collegio nel dispositivo.
    # Una città menzionata nei fatti o nella difesa NON soddisfa il controllo.
    city_pattern = r"(?:l )?aquila" if city == "aquila" else re.escape(city)
    deliberation = bool(city and re.search(
        r"\bcosi deciso in " + city_pattern + r"\b(?: nella| in| il| con| all|$)", closing))
    if city and city not in header and " documentiga " + city + " " not in " " + release + " " and not deliberation:
        return False
    return bool(region or city)


def verifica_tipo(raw, row):
    """Confronta la famiglia pubblicata, senza scambiare decreto e sentenza."""
    expected = _normal(str(row.get("tipo", "")))
    families = ("sentenza", "ordinanza", "decreto", "parere")
    family = next((value for value in families if expected.startswith(value)), None)
    if family is None:
        return False
    try:
        root = parse_official_xml(raw)
        actual = _normal(root.findtext("Provvedimento/meta/tipologia", ""))
        return actual.startswith(family)
    except (DocumentoNonVerificato, etree.XMLSyntaxError, TypeError):
        return False
