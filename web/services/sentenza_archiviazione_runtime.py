"""Controllo incrementale delle fonti SQL, condiviso da job e riconvalida esplicita."""
from __future__ import annotations
import hashlib
import json
import time
from typing import Any
from pct.fascicolo_sentenza_archiviazione import RULE, verifica_sentenza_da_archiviare, applica_sentenza_da_archiviare

READER = 'sentenza_da_archiviare'

def _contenuto_firmato_verificato(data: bytes, *, nome: str, sha256: str,
                                 sha256_archivio: str, stored_sha256: str) -> tuple[bytes, str, dict[str, str]]:
    """Distingue contenitore conservato e contenuto CMS, senza cambiare la firma."""
    from pct.firme_cades import inspect_signed_document_bytes

    if not sha256_archivio or stored_sha256 != sha256_archivio:
        raise ValueError('Impronta del file conservato non coincidente con l’inventario SQL.')
    signed = inspect_signed_document_bytes(source_name=nome, data=data)
    payload = signed.payload_bytes
    if not payload or payload == data or hashlib.sha256(payload).hexdigest() != sha256:
        raise ValueError('Impronta dell’originale non coincidente con l’inventario SQL.')
    return payload, signed.status.payload_name or nome, {
        'signed_container_sha256': hashlib.sha256(data).hexdigest(),
        'content_sha256': sha256,
    }

def controlla_fascicolo(*, fascicolo_id: str, limit: int = 25, apply: bool = True, force: bool = False,
                       actor: str = 'motore-sentenze', source_refs: set[tuple[str, str]] | None = None) -> dict[str, Any]:
    from web.helpers import get_fascicoli, get_clienti
    from web.services.archivio_letture_runtime import registro_corrente, tenant_corrente, _bytes_documento, _bytes_allegato_pec
    from web.services.archivio_testo_contenitori import estrai_contenuto
    from web.services.pec_pipeline_runtime import repository_for_current_request
    from web.services.sentenza_economic_runtime import _repo
    manager = get_fascicoli();fascicolo = manager.get(fascicolo_id)
    if fascicolo is None: raise ValueError('Fascicolo non disponibile nello studio.')
    if manager._studio_db is None: raise ValueError('Database SQL del fascicolo non disponibile: nessuna decisione da mirror JSON.')
    client = get_clienti().get(fascicolo.id_cliente) if fascicolo.id_cliente else None
    client_data = client.to_dict() if client is not None else {}
    tenant = tenant_corrente();registro = registro_corrente()
    context = hashlib.sha256(json.dumps({'case':{k:str(getattr(fascicolo,k,'') or '') for k in ('nome_cliente','numero_rg','anno_rg','tribunale','id_cliente')},'client':{k:client_data.get(k) for k in ('nome','cognome','denominazione','codice_fiscale')}},sort_keys=True,ensure_ascii=False,default=str).encode('utf-8')).hexdigest()
    previous = {(r.tipo,r.oggetto_id,r.sha256):r for r in registro.letture(tenant,fascicolo_id,lettore=READER)}
    pending = registro.da_leggere(tenant, fascicolo_id, READER, versione=RULE, tipi=('documento','allegato_pec'))
    inventory = registro.oggetti(tenant,fascicolo_id)
    if source_refs is not None:
        if not source_refs or not source_refs <= {(o.tipo, o.oggetto_id) for o in inventory}:
            raise ValueError('Fonti richieste non presenti nell’inventario del fascicolo.')
    changed_context = [o for o in inventory if o.presente and o.tipo in {'documento','allegato_pec'} and (r:=previous.get((o.tipo,o.oggetto_id,o.impronta))) is not None and r.esito.get('context')!=context]
    candidates = inventory if force else list({(o.tipo,o.oggetto_id):o for o in pending+changed_context}.values())
    if source_refs is not None:
        candidates = [o for o in candidates if (o.tipo, o.oggetto_id) in source_refs]
    sources = [o for o in candidates if force or (r:=previous.get((o.tipo,o.oggetto_id,o.impronta))) is None or r.esito.get('context')!=context or float(r.esito.get('retry_after_epoch') or 0)<=time.time()]
    docs = {d.id: d for d in fascicolo.documenti};mime_cache = {};pec_repo = None
    report = {'fascicolo_id': fascicolo_id,'source_of_truth': getattr(manager._studio_db,'backend_kind','sqlite'),'checked': 0,'changed': 0,
              'pending': len(candidates),'deferred': len(candidates)-len(sources),'results': [],'errors': []}
    for obj in sources[:max(1,limit)]:
        if obj.tipo not in {'documento','allegato_pec'}: continue
        try:
            if not obj.presente: raise ValueError('Fonte non più presente nell’inventario.')
            if obj.tipo == 'documento':
                doc = docs.get(obj.oggetto_id)
                if doc is None: raise ValueError('Documento non più presente nel fascicolo SQL.')
                if obj.sha256:
                    data = _bytes_documento(fascicolo_id,doc)
                else:
                    from pct.document_crypto import decrypt_doc
                    physical = manager.percorso_documento_lettura(fascicolo_id,doc.id)
                    stored = physical.read_bytes()
                    if hashlib.sha256(stored).hexdigest() != obj.sha256_archivio:
                        raise ValueError('Impronta del file conservato non coincidente con l’inventario SQL.')
                    data = decrypt_doc(stored)
                    plain_sha = hashlib.sha256(data).hexdigest()
                    if apply:
                        registro.registra_impronta_contenuto(tenant,fascicolo_id,obj.tipo,obj.oggetto_id,
                            sha256=plain_sha,sha256_archivio=obj.sha256_archivio,dimensione=len(data))
                    obj.sha256 = plain_sha
            else:
                if pec_repo is None: pec_repo = repository_for_current_request()
                data = _bytes_allegato_pec(obj,pec_repo,mime_cache)
            actual_name = str(doc.percorso) if obj.tipo == 'documento' else obj.nome
            container_evidence = {}
            sha = hashlib.sha256(data).hexdigest()
            if sha != obj.sha256:
                if obj.tipo != 'documento':
                    raise ValueError('Impronta dell’originale non coincidente con l’inventario SQL.')
                physical = manager.percorso_documento_lettura(fascicolo_id, doc.id)
                data, actual_name, container_evidence = _contenuto_firmato_verificato(
                    data, nome=actual_name, sha256=obj.sha256, sha256_archivio=obj.sha256_archivio,
                    stored_sha256=hashlib.sha256(physical.read_bytes()).hexdigest())
                sha = hashlib.sha256(data).hexdigest()
            extracted = estrai_contenuto(data,actual_name)
            if extracted.errori: raise ValueError('; '.join(extracted.errori))
            if not extracted.testo.strip() and extracted.esito != 'senza_testo': raise ValueError('Testo della fonte non disponibile.')
            source = {'verified_original': True, 'sha256': sha, 'tenant_id': tenant, 'name': obj.nome,
                      'object_id': obj.oggetto_id, 'document_id':obj.oggetto_id if obj.tipo=='documento' else '',
                      'archive_sha256':obj.sha256_archivio, **container_evidence,
                      'message_id':obj.origine if obj.tipo=='allegato_pec' else ''}
            components = extracted.componenti or [{'testo':extracted.testo,'path':'','name':actual_name,'sha256':sha,
                                                   'esito':extracted.esito,'motivo':extracted.motivo}]
            checks = []
            for component in components:
                component_source = {**source, 'component_path':component['path'], 'component_sha256':component['sha256'],
                                    'component_parent_sha256':component.get('parent_sha256',''),
                                    'root_container_sha256':component.get('root_container_sha256','')}
                if component.get('esito') == 'senza_testo':
                    check = {'eligible':False, 'reason':component['motivo'], 'source':component_source,
                             'esito':'senza_testo'}
                else:
                    check = verifica_sentenza_da_archiviare(fascicolo=fascicolo,testo=component['testo'],fonte=component_source,cliente=client_data)
                result = {'changed':False, 'reason':check['reason']}
                if apply and check['eligible']:
                    result = applica_sentenza_da_archiviare(fascicoli_repository=manager,fascicolo_id=fascicolo_id,verifica=check,actor=actor)
                    if result.get('retry'): raise ValueError(result['reason'])
                    if result['changed']:
                        fascicolo = manager.get(fascicolo_id)
                        _repo().record_decision(tenant_id=tenant,actor_id=actor,kind='fascicolo_da_archiviare',subject_ref=fascicolo_id,
                            decision='da_archiviare',rationale=check['reason'],evidence=check)
                        from web.services.react_fascicoli_cache import clear_react_fascicoli_list_cache
                        from web.services.react_dashboard_cache import clear_dashboard_payload_cache
                        clear_react_fascicoli_list_cache();clear_dashboard_payload_cache()
                checks.append({'check':check,'result':result})
            result = {'changed':any(c['result']['changed'] for c in checks),'reason':'Componenti della fonte verificati separatamente.'}
            if apply:
                old = previous.get((obj.tipo,obj.oggetto_id,obj.impronta))
                reconciliations = list(old.esito.get('reconciliations') or []) if old else []
                previous_components = old.esito.get('components') or [] if old else []
                components_changed = bool(old and previous_components != checks)
                if old and (old.stato == 'errore' or components_changed):
                    reconciliations.append({'previous_state':old.stato,
                        'previous_reason':old.esito.get('reason'), 'previous_attempts':old.esito.get('attempts'),
                        'source_sha256':sha, 'actor':actor, 'at_epoch':time.time(), 'rule':RULE,
                        'previous_components':previous_components,
                        'reason':'Riconvalida puntuale: componenti della fonte aggiornati.' if components_changed else 'Recupero della lettura fallita.'})
                registro.segna_letto(tenant,fascicolo_id,obj,READER,versione=RULE,
                    esito={'context':context,'components':checks,'reconciliations':reconciliations})
            report['checked'] += 1;report['changed'] += int(result['changed'])
            report['results'].append({'source':obj.oggetto_id,'eligible':any(c['check']['eligible'] for c in checks),**result})
        except Exception as exc:
            report['errors'].append({'source':obj.oggetto_id,'reason':str(exc)})
            if apply:
                old = previous.get((obj.tipo,obj.oggetto_id,obj.impronta))
                attempts = int(old.esito.get('attempts') or 0)+1 if old else 1
                registro.segna_letto(tenant,fascicolo_id,obj,READER,versione=RULE,stato='errore',
                    esito={'context':context,'reason':str(exc),'attempts':attempts,
                           'components':old.esito.get('components',[]) if old else [],
                           'reconciliations':old.esito.get('reconciliations',[]) if old else [],
                           'retry_after_epoch':time.time()+min(86400,300*2**min(attempts-1,8))})
    return report
