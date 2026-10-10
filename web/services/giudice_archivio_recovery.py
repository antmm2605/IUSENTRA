"""Recupero puntuale dai testi SQL già letti, nel worker del fascicolo richiesto."""
from __future__ import annotations

import hashlib
import json

VERSIONE = "2026.10.10.giudice-date.v3"


def recupera_da_testi_sql(fascicolo, registro, tenant, repository, *, codice_fiscale_cliente="", limite=200, riscontro_nativo=None):
    from pct.archivio_letture.estrazione_giudice import estrai_giudice
    from pct.archivio_letture.date_campi_modello import CAMPI_DATE, estrai_date_modello
    from web.services.archivio_letture_runtime import _attribuisci

    fid = str(fascicolo.id)
    context = hashlib.sha256(json.dumps({
        "cliente": fascicolo.nome_cliente, "rg": fascicolo.numero_rg, "anno": fascicolo.anno_rg,
        "ufficio": fascicolo.tribunale, "cf": codice_fiscale_cliente,
    }, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    reads = {(r.oggetto_id, r.sha256): r for r in registro.letture(tenant, fid, lettore="motore_documenti") if r.stato == "letto"}
    candidates = [o for o in registro.oggetti(tenant, fid) if o.tipo == "documento" and o.presente
                  and (o.oggetto_id, o.impronta) in reads]
    ready = {}
    for record in sorted(repository.list_documents(tenant, fid), key=lambda r: str(r.updated_at or ""), reverse=True):
        if record.status == "ready":
            ready.setdefault(record.sha256, record)
    pending = []
    for obj in candidates:
        record = next((ready[sha] for sha in (obj.sha256, obj.sha256_archivio) if sha and sha in ready), None)
        sql_version = f"{record.id}:{record.current_version_id}:{record.updated_at}" if record else "assente"
        checkpoint = reads[(obj.oggetto_id, obj.impronta)].esito.get("controllo_metadati", {})
        if checkpoint.get("contesto") != f"{VERSIONE}:{context}" or checkpoint.get("versione_sql") != sql_version:
            pending.append((obj, record, sql_version))
    result = {"controllati": 0, "fatti": 0, "in_attesa_testo": 0, "restano": max(0, len(pending) - limite), "file_letti": 0}
    for obj, record, sql_version in pending[:limite]:
        extracted = repository.get_extracted_text(tenant, fid, record.id, record.current_version_id) if record else None
        text = str(getattr(extracted, "text", "") or "")
        engine = str(getattr(extracted, "extraction_engine", "") or "")
        # Nessuna promozione dell'OCR a testo nativo e nessun abbinamento per nome.
        native = engine in {"pdfplumber", "pypdf", "pymupdf"}
        if (not native and engine.startswith("pdf-inspector:") and riscontro_nativo is not None
                and (estrai_giudice(text, fascicolo=fascicolo, origine="indice", codice_fiscale_cliente=codice_fiscale_cliente)
                     or estrai_date_modello(text, fascicolo=fascicolo, codice_fiscale_cliente=codice_fiscale_cliente))):
            # Il motore PDF condiviso può mescolare native e OCR: il nome
            # del motore non prova l'origine dei caratteri. Riscontro puntuale
            # della sola fonte candidata, prima di ammettere il fatto.
            text = riscontro_nativo(obj, record)
            result["file_letti"] += 1
            native = bool(text)
        if not text.strip() or text.lstrip().startswith("PCTENC") or not native:
            result["in_attesa_testo"] += 1
            registro.registra_controllo_metadati(tenant, fid, obj, versione=VERSIONE,
                esito={"contesto": f"{VERSIONE}:{context}", "versione_sql": sql_version,
                       "giudice_trovato": False, "motivo": "Testo nativo SQL della stessa impronta non disponibile; ripresa al cambio della fonte o del testo archiviato."})
            result["controllati"] += 1
            continue
        new = _attribuisci([
            *estrai_giudice(text, fascicolo=fascicolo, origine="nativo", codice_fiscale_cliente=codice_fiscale_cliente),
            *estrai_date_modello(text, fascicolo=fascicolo, codice_fiscale_cliente=codice_fiscale_cliente),
        ], obj, "documenti")
        previous = [f for f in registro.fatti_oggetto(tenant, obj.tipo, obj.oggetto_id)
                    if f.fascicolo_id == fid and f.sha256 == obj.impronta and f.motore == "documenti"]
        retained = [f for f in previous if not (f.categoria == "metadato_fascicolo" and f.campo in {"giudice", *CAMPI_DATE})]
        if new or len(retained) != len(previous):
            registro.registra_fatti(tenant, fid, obj, "documenti", [*retained, *new], versione=reads[(obj.oggetto_id, obj.impronta)].versione_lettore)
        registro.registra_controllo_metadati(tenant, fid, obj, versione=VERSIONE,
            esito={"contesto": f"{VERSIONE}:{context}", "versione_sql": sql_version, "document_version_id": record.current_version_id,
                   "giudice_trovato": any(f.campo == "giudice" for f in new),
                   "campi_riscontrati": sorted({f.campo for f in new}),
                   "motivo": "Campi riscontrati nel provvedimento." if new else "Nessun campo attribuibile con identità congiunta nella fonte corrente."})
        result["controllati"] += 1
        result["fatti"] += len(new)
    return result


def recupera_giudice(fascicolo, registro, tenant, *, limite=200):
    from web.helpers import get_clienti
    from web.services.document_intelligence_runtime import build_document_ai_service

    client = get_clienti().get(fascicolo.id_cliente) if fascicolo.id_cliente else None
    from web.services.archivio_letture_runtime import _bytes_documento, _testo_nativo

    documents = {str(d.id): d for d in fascicolo.documenti}

    def validate_native(obj, record):
        doc = documents.get(obj.oggetto_id)
        if doc is None:
            return ""
        content = _bytes_documento(str(fascicolo.id), doc)
        if not content or hashlib.sha256(content).hexdigest() not in {obj.sha256, record.sha256}:
            raise ValueError("Fonte cambiata: il riscontro del giudice richiede la nuova impronta.")
        return _testo_nativo(str(fascicolo.id), doc, contenuto=content)

    return recupera_da_testi_sql(fascicolo, registro, tenant, build_document_ai_service().repository,
                               codice_fiscale_cliente=getattr(client, "codice_fiscale", ""), limite=limite,
                               riscontro_nativo=validate_native)
