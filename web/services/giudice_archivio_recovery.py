"""Recupero puntuale dai testi SQL già letti, nel worker del fascicolo richiesto."""
from __future__ import annotations

import hashlib
import json
import re

VERSIONE = "2026.10.10.giudice-date.v3"


def recupera_da_testi_sql(fascicolo, registro, tenant, repository, *, codice_fiscale_cliente="", limite=200, riscontro_nativo=None,
                         documenti_economici=(), recupero_economico=None, documenti_contributo=(), recupero_contributo=None):
    from pct.archivio_letture.date_campi_modello import CAMPI_DATE, estrai_date_modello
    from pct.archivio_letture.estrazione_giudice import estrai_giudice
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
    economic_ids = set(documenti_economici) if recupero_economico is not None else set()
    contribution_ids = set(documenti_contributo) if recupero_contributo is not None else set()
    pending = []
    for obj in candidates:
        record = next((ready[sha] for sha in (obj.sha256, obj.sha256_archivio) if sha and sha in ready), None)
        sql_version = f"{record.id}:{record.current_version_id}:{record.updated_at}" if record else "assente"
        checkpoint = reads[(obj.oggetto_id, obj.impronta)].esito.get("controllo_metadati", {})
        expected_context = f"{VERSIONE}:{context}" + (":economia-valuta-v1" if obj.oggetto_id in economic_ids else "")
        if obj.oggetto_id in contribution_ids:
            from pct.archivio_letture.verifica_economica import VERSIONE as versione_contributo
            expected_context += f":contributo-fonti:{versione_contributo}"
        if checkpoint.get("contesto") != expected_context or checkpoint.get("versione_sql") != sql_version:
            pending.append((obj, record, sql_version, expected_context))
    result = {"controllati": 0, "fatti": 0, "in_attesa_testo": 0, "restano": max(0, len(pending) - limite), "file_letti": 0}
    for obj, record, sql_version, expected_context in pending[:limite]:
        extracted = repository.get_extracted_text(tenant, fid, record.id, record.current_version_id) if record else None
        text = str(getattr(extracted, "text", "") or "")
        archived_text = text
        engine = str(getattr(extracted, "extraction_engine", "") or "")
        # Nessuna promozione dell'OCR a testo nativo e nessun abbinamento per nome.
        native = engine in {"pdfplumber", "pypdf", "pymupdf"}
        if (not native and engine.startswith("pdf-inspector:") and riscontro_nativo is not None
                and (obj.oggetto_id in economic_ids or obj.oggetto_id in contribution_ids or estrai_giudice(text, fascicolo=fascicolo, origine="indice", codice_fiscale_cliente=codice_fiscale_cliente)
                     or estrai_date_modello(text, fascicolo=fascicolo, codice_fiscale_cliente=codice_fiscale_cliente))):
            # Il motore PDF condiviso può mescolare native e OCR: il nome
            # del motore non prova l'origine dei caratteri. Riscontro puntuale
            # della sola fonte candidata, prima di ammettere il fatto.
            text = riscontro_nativo(obj, record)
            result["file_letti"] += 1
            native = bool(text)
        if not native and archived_text.strip() and obj.oggetto_id in contribution_ids:
            previous = [f for f in registro.fatti_oggetto(tenant, obj.tipo, obj.oggetto_id)
                        if f.fascicolo_id == fid and f.sha256 == obj.impronta and f.motore == "documenti"]
            fields = {"contributo_unificato", "esenzione_cu_dichiarata", "pagamento_cu_non_verificato"}
            manual = any(f.campo in fields and (f.verifica in {"corretta", "ignorata"}
                         or any(p.get("codice") == "decisione_avvocato" for p in f.prove)) for f in previous)
            recovered = recupero_contributo(obj, record, archived_text) if not manual else []
            if recovered:
                retained = [f for f in previous if f.campo not in fields]
                registro.registra_fatti(tenant, fid, obj, "documenti", [*retained, *_attribuisci(recovered, obj, "documenti")],
                                       versione=reads[(obj.oggetto_id, obj.impronta)].versione_lettore)
                result["fatti"] += len(recovered)
            registro.registra_controllo_metadati(tenant, fid, obj, versione=VERSIONE,
                esito={"contesto": expected_context, "versione_sql": sql_version,
                       "giudice_trovato": False, "campi_riscontrati": sorted({f.campo for f in recovered}),
                       "motivo": "Fonte OCR: verifiche del contributo conservano l'origine ottica; nessun provvedimento promosso a nativo."})
            result["controllati"] += 1
            continue
        if not text.strip() or text.lstrip().startswith("PCTENC") or not native:
            result["in_attesa_testo"] += 1
            registro.registra_controllo_metadati(tenant, fid, obj, versione=VERSIONE,
                esito={"contesto": expected_context, "versione_sql": sql_version,
                       "giudice_trovato": False, "motivo": "Testo nativo SQL della stessa impronta non disponibile; ripresa al cambio della fonte o del testo archiviato."})
            result["controllati"] += 1
            continue
        new = _attribuisci([
            *estrai_giudice(text, fascicolo=fascicolo, origine="nativo", codice_fiscale_cliente=codice_fiscale_cliente),
            *estrai_date_modello(text, fascicolo=fascicolo, codice_fiscale_cliente=codice_fiscale_cliente),
        ], obj, "documenti")
        previous = [f for f in registro.fatti_oggetto(tenant, obj.tipo, obj.oggetto_id)
                    if f.fascicolo_id == fid and f.sha256 == obj.impronta and f.motore == "documenti"]
        economic_updated = False
        if obj.oggetto_id in economic_ids and not any(
                f.campo == "controllo_economico" and f.verifica in {"corretta", "ignorata"} for f in previous):
            economic = recupero_economico(obj, record, text)
            if economic:
                new.extend(_attribuisci(economic, obj, "documenti"))
                economic_updated = True
        contribution_updated = False
        contribution_fields = {"contributo_unificato", "esenzione_cu_dichiarata", "pagamento_cu_non_verificato"}
        if obj.oggetto_id in contribution_ids and not any(
                f.campo in contribution_fields and (f.verifica in {"corretta", "ignorata"} or any(p.get("codice") == "decisione_avvocato" for p in f.prove)) for f in previous):
            contribution = recupero_contributo(obj, record, text)
            if contribution:
                new.extend(_attribuisci(contribution, obj, "documenti"))
                contribution_updated = True
        retained = [f for f in previous if not (f.categoria == "metadato_fascicolo" and f.campo in {"giudice", *CAMPI_DATE})]
        if contribution_updated:
            retained = [f for f in retained if f.campo not in contribution_fields]
        if economic_updated:
            retained = [f for f in retained if f.campo != "controllo_economico"]
        if new or len(retained) != len(previous):
            registro.registra_fatti(tenant, fid, obj, "documenti", [*retained, *new], versione=reads[(obj.oggetto_id, obj.impronta)].versione_lettore)
        registro.registra_controllo_metadati(tenant, fid, obj, versione=VERSIONE,
            esito={"contesto": expected_context, "versione_sql": sql_version, "document_version_id": record.current_version_id,
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
    economic_ids = {key for key, doc in documents.items()
                    if str(getattr(getattr(doc, "tipo", ""), "value", getattr(doc, "tipo", ""))).upper()
                    in {"SENTENZA", "ORDINANZA", "DECRETO", "VERBALE"}}

    contribution_ids = {f.oggetto_id for f in registro.fatti(tenant, str(fascicolo.id), tipo="documento", motore="documenti", verifiche=None)
                        if f.campo in {"contributo_unificato", "esenzione_cu_dichiarata", "pagamento_cu_non_verificato"}}
    # Il nome seleziona una fonte da controllare, non prova l'esenzione.
    # Anche una prima lettura incompleta deve poter recuperare il dichiarante:
    # la conferma richiede comunque dichiarazione e identità nel contenuto.
    contribution_ids.update(key for key, doc in documents.items()
                            if re.search(r"autocertific|reddit|contributo", str(getattr(doc, "nome", "")), re.IGNORECASE))

    def recover_contribution(obj, record, text):
        from pct.archivio_letture.estrazione_importi import importo_contributo_unificato
        from pct.archivio_letture.verifica_economica import identita_autocertificazione, prova_dichiarazione

        meta = {"fascicolo": fascicolo, "codice_fiscale_cliente": getattr(client, "codice_fiscale", ""),
                "documento_id": obj.oggetto_id, "document_hash_sha256": obj.sha256}
        declaration = json.loads(prova_dichiarazione(text)["dettaglio"])
        optical = declaration.get("tipo") == "autocertificazione"
        recovery = None
        if optical and not all(p.get("esito") == "ok" for p in identita_autocertificazione(text, meta)):
            from legal_ocr.motore.autocertificazione import recupera_dichiarante
            doc = documents.get(obj.oggetto_id)
            content = _bytes_documento(str(fascicolo.id), doc) if doc else b""
            if content and hashlib.sha256(content).hexdigest() == obj.sha256:
                try:
                    recovery = recupera_dichiarante(content)
                except (RuntimeError, OSError, ValueError, ImportError) as exc:
                    # Il tentativo fallito resta nel checkpoint della fonte:
                    # non interrompe gli altri presìdi né diventa una conferma.
                    recovery = {"testi": [], "origine": "ocr", "tentativi": [{
                        "esito": "errore", "causa": type(exc).__name__,
                        "motivo": "Recupero del dichiarante non riuscito sulla fonte originale."}]}
                # Si aggiungono solo righe realmente lette. Nessun dato del
                # cliente è passato come suggerimento al motore OCR.
                text += "\n" + "\n".join(recovery["testi"])
        facts = importo_contributo_unificato(text, metadata=meta, origine="ocr" if optical else "nativo")
        if recovery:
            for fact in facts:
                fact.prove.append({"codice": "recupero_dichiarante", "esito": "ok" if recovery["testi"] else "attenzione",
                                   "dettaglio": json.dumps(recovery, ensure_ascii=False)})
        return facts

    def recover_economic(obj, record, text):
        from pct.archivio_letture.estrazione_economica import estrai_controllo_economico
        from web.services.document_intelligence_runtime import apply_sentenza_automation_for_document_text
        from web.services.sentenza_economic_runtime import _cu_tiers, _repo, run_analysis

        doc = documents[obj.oggetto_id]
        metadata = {"fascicolo": fascicolo, "documento_id": obj.oggetto_id,
                    "tipo_documento": str(getattr(getattr(doc, "tipo", ""), "value", getattr(doc, "tipo", ""))),
                    "document_hash_sha256": str(getattr(doc, "hash_sha256", "") or obj.sha256),
                    "codice_fiscale_cliente": getattr(client, "codice_fiscale", ""), "cu_tiers": _cu_tiers()}
        facts = estrai_controllo_economico(text, origine="nativo", metadata=metadata)
        if not facts:
            return []  # Nessun effetto senza identità congiunta dimostrata.
        run_analysis(fascicolo=fascicolo, testo=text, repo=_repo(), tenant_id=tenant,
                     fonte="ARCHIVIO_LETTURE", documento_id=obj.oggetto_id,
                     document_hash_sha256=metadata["document_hash_sha256"], cu_tiers=metadata["cu_tiers"],
                     valore_causa=float(getattr(fascicolo, "valore_causa", 0) or 0), actor_id="archivio-letture")
        apply_sentenza_automation_for_document_text(
            fascicolo_id=str(fascicolo.id), tenant_id=tenant, document_id=record.id, text=text,
            metadata={"documento_id": obj.oggetto_id, "source_id": obj.oggetto_id,
                      "document_id": record.id, "tipo_documento": metadata["tipo_documento"],
                      "filename": getattr(doc, "nome", ""), "sha256": metadata["document_hash_sha256"]},
            actor="archivio-letture")
        return facts

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
                               riscontro_nativo=validate_native, documenti_economici=economic_ids,
                               recupero_economico=recover_economic, documenti_contributo=contribution_ids,
                               recupero_contributo=recover_contribution)
