"""Identita NIR dai metadati strutturati del documento importato.

Gli archivi storici conservano talvolta soltanto «urn:». La fonte originale
resta nei metadati: tipo nel percorso XML, numero e data devono concordare.
Nessuna inferenza dal testo della domanda o da un titolo somigliante.
"""
from __future__ import annotations

import re
from datetime import date

TIPI = {"LEGGE":"legge","DECRETO LEGISLATIVO":"decreto.legislativo",
        "DECRETO-LEGGE":"decreto.legge","DECRETO LEGGE":"decreto.legge",
        "DECRETO DEL PRESIDENTE DELLA REPUBBLICA":"decreto.del.presidente.della.repubblica",
        "REGIO DECRETO":"regio.decreto","REGIO DECRETO-LEGGE":"regio.decreto.legge",
        "DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI":"decreto.del.presidente.del.consiglio.dei.ministri",
        "LEGGE COSTITUZIONALE":"legge.costituzionale"}


def urn_documento(urn: str, xml_entry: str, numero: str, data_atto: str) -> str:
    if str(urn or "").startswith(("urn:nir:","urn:cnf:")):
        return urn
    directory = str(xml_entry or "").split("/",1)[0]
    m = re.fullmatch(r"(.+)_(\d{8})_(\d+)",directory)
    if not m or m[1] not in TIPI or m[3] != str(numero or ""):
        return ""
    when = m[2][:4]+"-"+m[2][4:6]+"-"+m[2][6:]
    try:
        if date.fromisoformat(when).isoformat()!=str(data_atto or "")[:10]:return ""
    except ValueError:
        return ""
    return f"urn:nir:stato:{TIPI[m[1]]}:{when};{int(numero)}"


def url_documento(urn: str, xml_entry: str, data_pubblicazione: str) -> str:
    """Identità ufficiale GU per tipi di atto senza URN ricostruibile.

    Non deduce l'autorità emanante di un decreto generico. Data e codice GU
    devono concordare con i metadati del pacchetto ufficiale.
    """
    if str(urn or "").startswith(("urn:nir:", "urn:cnf:")):
        return urn
    from urllib.parse import urlencode

    name = str(xml_entry or "").rsplit("/", 1)[-1]
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})_([A-Za-z0-9]+)_VIGENZA_.+\.xml", name)
    if not match or match[1] != str(data_pubblicazione or "")[:10]:
        return ""
    try:
        date.fromisoformat(match[1])
    except ValueError:
        return ""
    return "https://www.normattiva.it/atto/caricaDettaglioAtto?" + urlencode({
        "atto.dataPubblicazioneGazzetta": match[1], "atto.codiceRedazionale": match[2]})
