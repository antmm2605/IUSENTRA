"""Metadati italiani della GU serie L dall'Ufficio delle pubblicazioni."""

from datetime import date, timedelta
import json
import re
from urllib.parse import urlencode

from pct.notiziario.adattatori import notizia
from pct.notiziario.fonti import Fonte
from pct.notiziario.rete import RequestGet, scarica

_HOST = "publications.europa.eu"
_CELEX = re.compile(r"[0-9A-Z()]+")
_OJ = re.compile(r"http://publications\.europa\.eu/resource/oj/(L_[0-9]+)")


def raccogli_serie_l(fonte: Fonte, *, request_get: RequestGet, oggi: date) -> list[dict]:
    # Modello Act by Act documentato su op.europa.eu/en/web/cellar/the-official-journal-act-by-act.
    dal = oggi - timedelta(days=14)
    query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT DISTINCT ?id ?published ?title ?celex WHERE {{
          ?act cdm:official-journal-act_date_publication ?published; owl:sameAs ?id.
          FILTER (?published >= "{dal}"^^xsd:date && ?published <= "{oggi}"^^xsd:date)
          FILTER (STRSTARTS(STR(?id), "http://publications.europa.eu/resource/oj/L_"))
          FILTER (REGEX(STR(?id), "/L_[0-9]+$"))
          OPTIONAL {{ ?act cdm:resource_legal_id_celex ?celex. }}
          ?expr cdm:expression_belongs_to_work ?act;
            cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ITA>;
            cdm:expression_title ?title.
        }} ORDER BY DESC(?published) DESC(?id) LIMIT {fonte.max_voci}
    """
    parametri = urlencode({"query": query, "format": "application/sparql-results+json"})
    url = f"https://{_HOST}/webapi/rdf/sparql?{parametri}"
    dati = json.loads(scarica(url, (_HOST,), request_get=request_get))
    notizie: dict[str, dict] = {}
    for riga in dati["results"]["bindings"]:
        oj = _OJ.fullmatch(riga["id"]["value"])
        pubblicazione = date.fromisoformat(riga["published"]["value"])
        titolo = " ".join(riga["title"]["value"].split())
        if not oj or not titolo or not dal <= pubblicazione <= oggi:
            continue
        celex = riga.get("celex", {}).get("value", "")
        if _CELEX.fullmatch(celex):
            url_atto = f"https://eur-lex.europa.eu/legal-content/AUTO/?uri=CELEX:{celex}"
            riferimento = f"CELEX {celex}"
        else:
            url_atto = f"https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=OJ:{oj[1]}"
            riferimento = f"GU L {oj[1].removeprefix('L_')}"
        voce = notizia(
            fonte, titolo=titolo, url=url_atto, data=pubblicazione.isoformat(), descrizione="",
            riferimento_ufficiale=riferimento,
        )
        notizie.setdefault(voce["id"], {**voce, "solo_inserimento": True})
    return list(notizie.values())
