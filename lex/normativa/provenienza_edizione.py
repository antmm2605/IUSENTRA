"""Provenienza dell'edizione acquisita, distinta dalla sua applicabilità al caso."""
from __future__ import annotations

import json


def _oggetto(value):
    if isinstance(value,dict):
        return value
    if isinstance(value,str):
        try:
            decoded=json.loads(value)
        except (ValueError,TypeError):
            return {"metadati_non_decodificabili": True}
        return decoded if isinstance(decoded,dict) else {"metadati_non_decodificabili": True}
    return {}


def edizione_archiviata(metadata: dict, documento: dict | None = None) -> dict:
    """Copia solo identificatori pubblici; niente percorsi o istruzioni del modello.

    Non chiama siti, non sceglie fra edizioni e non trasforma una data di
    acquisizione in una data di vigenza. I campi ignoti restano assenti.
    """
    md=metadata if isinstance(metadata,dict) else {}
    doc=documento or {}
    source=_oggetto(md.get("consultazione_provenienza"))
    consultation=_oggetto(md.get("consultazione_fonte"))
    out={}
    for key in ("vigenza_richiesta","celex_usato","data_consolidato","sha256_akn",
                "sha256_payload_ufficiale","sha256_xml_decodificato","xml_sha256",
                "xml_decodificato_sha256","zip_sha256","xml_entry","codifica_trasporto",
                "lettore_sha256","acquisita_utc","tipo_origine_archivio","chain_id",
                "partizione_xml","localizzatore_xml","versione_formale_dal",
                "versione_formale_al_escluso","espressione_dal",
                "elenco_consolidati_verificato","consolidati_riscontrati",
                "catena_ufficiale_completa","metadati_non_decodificabili",
                "urn_originale_akn","data_atto_riscontro","identita_pubblicazione",
                "identita_metadata_non_datata","politica_lettori_sha256",
                "rapporto_compatibilita_sha256","lettore_proiezione_sha256",
                "ordine_fotogramma_riscontro","lettore_riscontro_sha256","rilettura_catena_sha256",
                "normalizzazione_identita","xml_identita_normalizzata_sha256",
                "metadati_tecnici_riscontrati","sha256_xml_letto",
                "urn_dichiarato_originale","identita_citazione",
                "intervallo_formale_riscontrato","successione_primaria_riscontrata",
                "manifest_acquisizione_sha256","record_acquisizione_sha256",
                "ricezione_dichiarata_manifest","precisione_ricezione"):
        if source.get(key) is not None and source.get(key)!="":out[key]=source[key]
    for target,values in {
        "redazione_id":(doc.get("redazione_id"),md.get("redazione_id")),
        "documento_sha256":(doc.get("xml_sha256"),md.get("document_sha256")),
        "urn":(doc.get("urn"),md.get("urn")),
        "partizione_xml":(out.get("partizione_xml"),md.get("partizione_xml")),
        "localizzatore_xml":(out.get("localizzatore_xml"),md.get("localizzatore_xml")),
        "consolidato_al":(consultation.get("consolidato_al"),),
        "raccolto_il":(consultation.get("raccolto_il"),),
        "url_acquisizione":(consultation.get("url"),),
        "fonte_testo":(consultation.get("fonte_testo"),),
    }.items():
        value=next((v for v in values if v is not None and v!=""),None)
        if value is not None:out[target]=value
    return out


def etichetta_edizione(edizione: dict) -> str:
    parts=[]
    if edizione.get("redazione_id"):parts.append("redazione "+str(edizione["redazione_id"]))
    if edizione.get("celex_usato"):parts.append("CELEX "+str(edizione["celex_usato"]))
    if edizione.get("espressione_dal"):parts.append("espressione "+str(edizione["espressione_dal"]))
    if edizione.get("documento_sha256"):parts.append("XML SHA-256 "+str(edizione["documento_sha256"]))
    return "; ".join(parts) or "edizione da riscontrare"


def riscontro_alla_data(edizione:dict, quando):
    """True/False/None per l'edizione documentata, NON per l'applicabilita legale.

    Non prolunga una fotografia alla data di acquisizione fino al futuro e non
    trasforma una dichiarazione VIGENTE in copertura di qualunque data.
    """
    from datetime import date,datetime
    from zoneinfo import ZoneInfo
    import re
    if not isinstance(edizione,dict) or type(quando) is not date:return None
    def iso(value):
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):return None
        try:return date.fromisoformat(value)
        except ValueError:return None
    def sha(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
    source_sha=next((edizione.get(k) for k in ('sha256_payload_ufficiale','xml_sha256','sha256_akn','documento_sha256') if sha(edizione.get(k))),None)
    correction=edizione.get('normalizzazione_identita') or {}
    trusted_interval=(edizione.get('catena_ufficiale_completa') is True and source_sha is not None) or (
        edizione.get('intervallo_formale_riscontrato') is True and isinstance(correction,dict)
        and sha(correction.get('corpo_c14n_immutato_sha256'))
        and correction.get('xml_originale_sha256')==source_sha)
    technical=edizione.get('metadati_tecnici_riscontrati') or {}
    trusted_interval=trusted_interval or (
        edizione.get('intervallo_formale_riscontrato') is True and isinstance(technical,dict)
        and technical.get('sha256_payload_ufficiale')==source_sha and source_sha is not None
        and technical.get('originale_non_modificato') is True
        and technical.get('derivato_non_esportazione_ufficiale') is True
        and all(sha(technical.get(k)) for k in ('normalizzatore_sha256',
            'corpo_normativo_c14n_immutato_sha256','testo_visibile_immutato_sha256')))
    start=iso(edizione.get('versione_formale_dal'));raw_end=edizione.get('versione_formale_al_escluso');end=iso(raw_end)
    if trusted_interval and start:
        if raw_end and (end is None or end<=start):return None
        if quando<start or (end is not None and quando>=end):return False
        if end is not None:return True
        # L'ultimo fotogramma e riscontrato al piu fino al giorno ricevuto.
        stamp=edizione.get('acquisita_utc')
        try:
            received=datetime.fromisoformat(stamp)
            if received.tzinfo is None:return None
            day=received.astimezone(ZoneInfo('Europe/Rome')).date()
        except (TypeError,ValueError):return None
        return True if quando<=day else None
    point=iso(edizione.get('vigenza_richiesta')) or iso(edizione.get('consolidato_al'))
    if source_sha and point==quando:return True
    return None


def data_acquisizione_documentata(edizione:dict)->str:
    """Data di ricezione, mai data di importazione usata al suo posto."""
    from datetime import datetime,date
    from zoneinfo import ZoneInfo
    import re
    stamp=edizione.get('acquisita_utc')
    if stamp:
        try:
            value=datetime.fromisoformat(stamp)
            if value.tzinfo is None:return ''
            return value.astimezone(ZoneInfo('Europe/Rome')).strftime('%d/%m/%Y')
        except (ValueError,TypeError):return ''
    received=edizione.get('raccolto_il')
    if not isinstance(received,str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',received):return ''
    try:return date.fromisoformat(received).strftime('%d/%m/%Y')
    except ValueError:return ''


def priorita_edizione_archiviata(metadata: dict, documento: dict, quando) -> tuple:
    """Ordina fotografie disponibili, senza certificarne l'applicabilità.

    Un'importazione recente non è una nuova acquisizione. La data letterale
    dell'espressione rimane distinta dal giorno documentato di ricezione.
    """
    from datetime import date, datetime
    if type(quando) is not date:
        raise ValueError("Data di confronto dell'edizione richiesta")
    edition = edizione_archiviata(metadata, documento)
    acquired = data_acquisizione_documentata(edition)
    acquired_iso = datetime.strptime(acquired, "%d/%m/%Y").date().isoformat() if acquired else ""
    version = str(documento.get("redazione_id") or "")
    try:
        version = date.fromisoformat(version).isoformat()
    except ValueError:
        version = ""
    ident = documento.get("id")
    return (riscontro_alla_data(edition, quando) is True, acquired_iso, version,
            ident if type(ident) is int else 0)
