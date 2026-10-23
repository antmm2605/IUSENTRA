"""Distingue i metadati OpenGA dal contenuto probatorio della decisione."""

from urllib.parse import urlsplit


def solo_metadati(record):
    record = record or {}
    if record.get("evidence_scope") == "metadata_only":
        return True
    fonte = str(record.get("fonte_codice") or record.get("source_system") or "").lower()
    url = str(record.get("url_pagina_ufficiale") or record.get("url_origine") or "")
    openga = fonte == "openga" or urlsplit(url).hostname == "openga.giustizia-amministrativa.it"
    return bool(openga and not record.get("testo_integrale_presente") and not record.get("testo_integrale"))


def riferimento_metadati_confermato(record):
    record = record or {}
    url = str(record.get("url_pagina_ufficiale") or record.get("url_origine") or "")
    host = urlsplit(url).hostname
    return bool(
        solo_metadati(record)
        and record.get("fonte_ufficiale_confermata")
        and record.get("organo_giudicante")
        and record.get("numero_sentenza")
        and record.get("anno_sentenza")
        and host
        in {"openga.giustizia-amministrativa.it", "www.giustizia-amministrativa.it", "giustizia-amministrativa.it"}
    )


def testo_metadati(record):
    """Non legge mai massima, abstract, motivazione o principio, anche nei vecchi record."""
    parts = ["Solo metadati ufficiali; testo della decisione non disponibile."]
    for key, label in [("oggetto", "Oggetto del ricorso"), ("esito", "Esito riportato nel dataset")]:
        text = " ".join(str(record.get(key) or "").split())
        if text:
            parts.append(f"{label}: {text}")
    parts.append("Questa scheda non documenta motivazioni o principi di diritto.")
    return " ".join(parts)
