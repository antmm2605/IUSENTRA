"""Correlazione delle ricevute con identificativi esatti; nessun invio o firma.

Le prove sono lette dal MIME SQL una volta e conservate nei metadati della
PEC; il motore PEC le versa nell'archivio delle letture per le viste del fascicolo.
"""
from __future__ import annotations
import hashlib
import html
import json
import re
from copy import copy
from email import policy
from email.parser import BytesParser
from typing import Any


def canonical(value: Any) -> str:
    return html.unescape(str(value or '')).strip().strip('<> ').lower()


def sent_message_id(deposito: Any) -> str:
    match = re.search(r'Message-ID:\s*<?([^\s<>]+@[^\s<>]+)>?', str(getattr(deposito, 'messaggio', '') or ''), re.I)
    return canonical(match.group(1)) if match else ''


def prepara_correlazioni(fascicolo: Any, messaggi: list[dict], repository: Any) -> int:
    """Solo il job di lettura chiama questa funzione; le GET non aprono MIME."""
    from pct.pec_control_tower import _parse_daticert
    locali = {sent_message_id(d): d for d in fascicolo.depositi_pct if sent_message_id(d) and 'PROVA' not in str(d.stato)}
    edges: dict[str, set[str]] = {}
    modificati = 0
    # Le ricevute native identificano l'invio; i record importati possono
    # essere alias della stessa busta e non devono creare ambiguità fittizie.
    for m in messaggi:
        ref = m.get('archive_receipt_reference') or {}
        dep = locali.get(canonical(ref.get('original_message_id')))
        if dep and ref.get('deposito_id') == dep.id:
            for mid in (ref.get('original_message_id'), ref.get('provider_message_id')):
                if mid: edges.setdefault(canonical(mid), set()).add(dep.id)
    by_busta = {str(d.id_deposito_esterno): d for d in fascicolo.depositi_pct if d.id_deposito_esterno and str(d.stato) == "ACCETTATO_CANCELLERIA"}
    rg = f"{fascicolo.numero_rg}/{fascicolo.anno_rg}"
    for m in messaggi:
        life = m.get('deposit_lifecycle') or {}
        corr = life.get('correlation') or {}
        dep = by_busta.get(str(corr.get('idbusta') or ''))
        if dep and str(corr.get('rg') or '') == rg and (life.get('receipt') or {}).get('outcome_code') is not None and m.get('collegata'):
            mid = canonical(corr.get('source_message_id'))
            if mid and mid not in edges: edges[mid] = {dep.id}
    for m in messaggi:
        ref = dict(m.get('archive_receipt_reference') or {})
        receipt = m.get('pec_receipt') or {}
        original = canonical(receipt.get('original_message_id'))
        if not ref and (original in locali or (m.get("deposit_lifecycle") or {}).get("current_stage", {}).get("id") in {"accettazione_pec", "consegna_pec"}):
            raw, row = repository.original_mime(m['id'])
            if hashlib.sha256(raw).hexdigest() != row['mime_sha256']:
                continue
            for part in BytesParser(policy=policy.default).parsebytes(raw).walk():
                if (part.get_filename() or '').lower() != 'daticert.xml':
                    continue
                data = part.get_payload(decode=True) or b''
                if len(data) > 500000 or b'<!ENTITY' in data.upper() or b'<!DOCTYPE' in data.upper():
                    continue
                cert = _parse_daticert(data)
                provider = canonical(cert.get('identificativo'))
                original_xml = canonical(cert.get('msgid'))
                recipient = str(cert.get('consegna') or cert.get('destinatari') or cert.get('destinatario') or '').strip().lower()
                candidates = edges.get(provider, set())
                dep = locali.get(original_xml) or (next((d for d in by_busta.values() if d.id == next(iter(candidates))), None) if len(candidates) == 1 else None)
                if not dep or not original_xml or not provider or str(dep.pec_destinatario).lower() not in recipient:
                    continue
                ref = {'original_message_id': original_xml, 'provider_message_id': provider, 'deposito_id': dep.id, 'recipient': recipient, 'xml_sha256': hashlib.sha256(data).hexdigest(), 'mime_sha256': row['mime_sha256']}
                break
            if ref:
                m['archive_receipt_reference'] = ref
                with repository.connect() as conn:
                    row = conn.execute('SELECT metadata_json FROM pec_messages WHERE tenant_id=? AND id=?', (repository.tenant_id, m['id'])).fetchone()
                    meta = json.loads(row['metadata_json'] or '{}'); meta['archive_receipt_reference'] = ref
                    conn.execute('UPDATE pec_messages SET metadata_json=? WHERE tenant_id=? AND id=?', (json.dumps(meta, ensure_ascii=False), repository.tenant_id, m['id']))
                    repository.append_audit(conn, action='pec.receipt.identifiers_correlated', resource_type='pec_message', resource_id=m['id'], payload=ref, actor='archivio-letture')
                modificati += 1
        if ref:
            for mid in (ref.get('original_message_id'), ref.get('provider_message_id')):
                if mid:
                    edges.setdefault(canonical(mid), set()).add(str(ref.get('deposito_id') or ''))
    for m in messaggi:
        corr = (m.get('deposit_lifecycle') or {}).get('correlation') or {}
        original = canonical((m.get('pec_receipt') or {}).get('original_message_id'))
        ids = edges.get(canonical(corr.get('source_message_id')), set()) | edges.get(original, set())
        if original in locali:
            ids.add(locali[original].id)
        ref = m.get('archive_receipt_reference') or {}
        if ref.get('deposito_id'): ids.add(ref['deposito_id'])
        if len(ids) != 1:
            continue
        depid = next(iter(ids)); m['archive_deposito_id'] = depid
        with repository.connect() as conn:
            row = conn.execute('SELECT linked_fascicolo_id FROM pec_messages WHERE tenant_id=? AND id=?',(repository.tenant_id,m['id'])).fetchone()
            if row and not row['linked_fascicolo_id']:
                conn.execute('UPDATE pec_messages SET linked_fascicolo_id=?, linked_fascicolo_score=1 WHERE tenant_id=? AND id=?', (fascicolo.id, repository.tenant_id, m['id']))
                repository.append_audit(conn, action='pec.receipt.linked_exact_message_id', resource_type='pec_message', resource_id=m['id'], payload={'fascicolo_id':fascicolo.id,'deposito_id':depid},actor='archivio-letture')
                modificati += 1
            if row and row['linked_fascicolo_id'] not in ('', None, fascicolo.id):
                m.pop('archive_deposito_id',None)
            else:
                m['collegata']=True
                latest = repository.latest_link(conn, m['id']) or {}
                if latest.get('fascicolo_id') != fascicolo.id or latest.get('status') not in {'manuale', 'ricevuta_identificativi_verificati'}:
                    from pct.pec_pipeline import canonical_json, iso_now
                    import uuid
                    parsed = repository.latest_parsed_row(conn, m['id'])
                    if parsed:
                        conn.execute(
                            'INSERT INTO pec_fascicolo_links (id, message_id, parsed_version_id, fascicolo_id, score, status, seeds_json, candidates_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                            (uuid.uuid4().hex, m['id'], parsed['id'], fascicolo.id, 1.0, 'ricevuta_identificativi_verificati', canonical_json({'deposito_id': depid, 'source_message_id': corr.get('source_message_id'), 'reference': ref}), canonical_json([{'id': fascicolo.id, 'score': 1.0, 'reasons': ['Identificativi certificati della ricevuta coincidenti con il deposito']}]), iso_now()),
                        )
                        repository.append_audit(conn, action='pec.receipt.link_recorded', resource_type='pec_message', resource_id=m['id'], payload={'fascicolo_id': fascicolo.id, 'deposito_id': depid}, actor='archivio-letture')
                        modificati += 1
    return modificati


def depositi_da_archivio(fascicolo: Any) -> list[Any]:
    """Proiezione delle ricevute verificate sull'invio, senza modificare la busta."""
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    from pct.formatting import format_datetime_it
    originali=list(getattr(fascicolo,'depositi_pct',[]) or [])
    copie={d.id:copy(d) for d in originali}
    fatti=registro_corrente().fatti(tenant_corrente(),fascicolo.id,categoria='evento')
    refs=[]
    for fatto in fatti:
        if fatto.campo!='esito_deposito' or fatto.verifica not in {'verificata','corretta'}:continue
        for prova in fatto.prove:
            if prova.get('codice')=='correlazione_ricevuta':refs.append(prova)
    aliases={}
    for ref in refs:
        depid=ref.get('deposito_id'); busta=str(ref.get('idbusta') or '')
        if depid in copie and busta:aliases[busta]=depid
    for d in originali:
        if d.id_deposito_esterno in aliases and d.id!=aliases[d.id_deposito_esterno]:
            target=copie[aliases[d.id_deposito_esterno]]
            for field in ('ricevuta_cancelleria','ricevuta_controlli_automatici','esito_controlli','id_deposito_esterno'):
                value=getattr(d,field,'')
                if value:setattr(target,field,value)
            copie.pop(d.id,None)
    states={'accettazione_pec':'ACCETTATO_PEC','consegna_pec':'CONSEGNATO','esito_controlli_deposito':'WARN_CONTROLLI','accettazione_deposito':'ACCETTATO_CANCELLERIA','rifiuto_deposito':'RIFIUTATO_CANCELLERIA'}
    receipt_fields={'accettazione_pec':'ricevuta_accettazione','consegna_pec':'ricevuta_consegna','esito_controlli_deposito':'ricevuta_controlli_automatici','accettazione_deposito':'ricevuta_cancelleria','rifiuto_deposito':'ricevuta_cancelleria'}
    for ref in sorted(refs, key=lambda x: data_ricevuta(x.get('occurred_at'))):
        dep=copie.get(ref.get('deposito_id'))
        if not dep:continue
        stage=ref.get('stage')
        if stage in states:
            stato = states[stage]
            code = ref.get('outcome_code')
            if stage == 'esito_controlli_deposito':
                stato = 'CONTROLLI_SUPERATI' if code == 1 else 'ERRORE_CONTROLLI' if isinstance(code, int) and code < 0 else 'WARN_CONTROLLI'
                dep.esito_controlli = str(code) if code is not None else ''
            # Un esito finale già acquisito non torna indietro per una RAC/RDAC
            # tardivamente importata o per una data assente nella ricevuta.
            if stage in {'accettazione_deposito', 'rifiuto_deposito'} or str(dep.stato) not in {'ACCETTATO_CANCELLERIA', 'RIFIUTATO_CANCELLERIA'}:
                dep.stato = stato
            if stage == 'accettazione_deposito':
                dep.data_accettazione = data_ricevuta(ref.get('occurred_at'))
            field=receipt_fields[stage]
            if not getattr(dep,field,''):
                setattr(dep,field,'\n'.join(['Esito: '+str(ref.get('label') or stage),'Data esito: '+format_datetime_it(ref.get('occurred_at')), 'Fonte PEC: '+str(ref.get('message_id') or ''),'Message-ID deposito: '+str(ref.get('source_message_id') or '')]))
        if ref.get('idbusta'):dep.id_deposito_esterno=str(ref['idbusta'])
    return [copie[d.id] for d in originali if d.id in copie]


def data_ricevuta(value: Any) -> str:
    """Normalizza anche il vecchio campo italiano con ora ripetuta dal parser."""
    from pct.formatting import parse_datetime_rome
    raw = str(value or '').strip()
    match = re.match(r'^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})T', raw)
    parsed = parse_datetime_rome(match.group(1) if match else raw)
    if not parsed:
        return ''
    from datetime import timezone
    return parsed.astimezone(timezone.utc).isoformat()
