"""Collega ricevute di trasporto a un esito ministeriale già collegato.

Solo il job di verifica: confronto di identificativi XML, hash MIME e
indirizzi reciproci. Non modifica deposito, firme o invio.
"""
from __future__ import annotations
import hashlib
import json
import uuid
from email import policy
from email.parser import BytesParser
from web.services.correlazioni_ricevute_archivio import canonical


def _certificato(repository, messaggio):
    from pct.pec_control_tower import _parse_daticert
    raw, row = repository.original_mime(messaggio['id'])
    sha = hashlib.sha256(raw).hexdigest()
    if sha != messaggio.get('mime_sha256') or sha != row['mime_sha256']:
        raise ValueError('Impronta MIME cambiata durante la verifica')
    certs = []
    for part in BytesParser(policy=policy.default).parsebytes(raw).walk():
        if (part.get_filename() or '').lower() != 'daticert.xml':
            continue
        data = part.get_payload(decode=True) or b''
        if not data or len(data) > 500000 or any(x in data.upper() for x in (b'<!ENTITY', b'<!DOCTYPE')):
            continue
        cert = _parse_daticert(data)
        if cert.get('errore') == 'nessuno':
            certs.append((cert, hashlib.sha256(data).hexdigest()))
    return certs[0] if len(certs) == 1 else ({}, '')


def collega_ricevute_da_esito(fascicolo, messaggi, repository):
    from pct.pec_pipeline import canonical_json, iso_now
    rg = f'{fascicolo.numero_rg}/{fascicolo.anno_rg}'
    depositi = {str(d.id_deposito_esterno): d for d in fascicolo.depositi_pct if d.id_deposito_esterno}
    anchors = {}
    for m in messaggi:
        life = m.get('deposit_lifecycle') or {}
        corr = life.get('correlation') or {}
        dep = depositi.get(str(corr.get('idbusta') or ''))
        if not dep or not m.get('collegata') or corr.get('rg') != rg:
            continue
        if (life.get('current_stage') or {}).get('id') not in {'accettazione_deposito', 'rifiuto_deposito', 'intervento_cancelleria'}:
            continue
        source = canonical(corr.get('source_message_id'))
        if not source:
            continue
        cert, xmlsha = _certificato(repository, m)
        office = str(cert.get('mittente') or '').strip().lower()
        recipient = str(cert.get('destinatario') or '').strip().lower()
        if cert.get('tipo') != 'posta-certificata' or not office.endswith('@civile.ptel.giustiziacert.it') or not recipient:
            continue
        anchors.setdefault(source, []).append((dep.id, office, recipient, m['id'], m['mime_sha256'], xmlsha))
    linked = []
    for m in messaggi:
        if m.get('collegata') or m.get('event_type') != 'pct_deposito':
            continue
        stage = ((m.get('deposit_lifecycle') or {}).get('current_stage') or {}).get('id')
        if stage not in {'accettazione_pec', 'consegna_pec'}:
            continue
        cert, xmlsha = _certificato(repository, m)
        provider = canonical(cert.get('identificativo'))
        candidates = anchors.get(provider, [])
        identities = {(a[0], a[1], a[2]) for a in candidates}
        if len(identities) != 1 or cert.get('tipo') not in {'accettazione', 'avvenuta-consegna'} or not canonical(cert.get('msgid')):
            continue
        depid, office, sender = next(iter(identities))
        if str(cert.get('mittente') or '').strip().lower() != sender or str(cert.get('destinatario') or '').strip().lower() != office:
            continue
        anchor = candidates[0]
        ref = {'fascicolo_id': fascicolo.id, 'deposito_id': depid, 'provider_message_id': provider,
               'original_message_id': canonical(cert['msgid']), 'recipient': office,
               'mime_sha256': m['mime_sha256'], 'xml_sha256': xmlsha,
               'anchor_message_id': anchor[3], 'anchor_mime_sha256': anchor[4], 'anchor_xml_sha256': anchor[5],
               'strategy': 'identificativo_xml_esito_ministeriale', 'matched_by': ['certified_provider_id', 'reciprocal_addresses']}
        with repository.connect() as conn:
            current_anchor = conn.execute('SELECT linked_fascicolo_id,mime_sha256 FROM pec_messages WHERE tenant_id=? AND id=?', (repository.tenant_id,anchor[3])).fetchone()
            if not current_anchor or current_anchor['linked_fascicolo_id'] != fascicolo.id or current_anchor['mime_sha256'] != anchor[4]:
                continue
            row = conn.execute('SELECT linked_fascicolo_id,mime_sha256,metadata_json FROM pec_messages WHERE tenant_id=? AND id=?', (repository.tenant_id,m['id'])).fetchone()
            parsed = repository.latest_parsed_row(conn, m['id'])
            if not row or not parsed or row['linked_fascicolo_id'] not in ('', None) or row['mime_sha256'] != m['mime_sha256']:
                continue
            meta = json.loads(row['metadata_json'] or '{}')
            meta['archive_receipt_reference'] = ref
            changed = conn.execute("UPDATE pec_messages SET linked_fascicolo_id=?,linked_fascicolo_score=1,status='linked',metadata_json=? WHERE tenant_id=? AND id=? AND mime_sha256=? AND (linked_fascicolo_id IS NULL OR linked_fascicolo_id='')", (fascicolo.id,canonical_json(meta),repository.tenant_id,m['id'],m['mime_sha256']))
            if changed.rowcount != 1:
                continue
            conn.execute('INSERT INTO pec_fascicolo_links (id,message_id,parsed_version_id,fascicolo_id,score,status,seeds_json,candidates_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)', (uuid.uuid4().hex,m['id'],parsed['id'],fascicolo.id,1.0,'ricevuta_identificativi_verificati',canonical_json(ref),canonical_json([{'id':fascicolo.id,'score':1.0,'reasons':['Identificativo XML coincidente con esito ministeriale e indirizzi reciproci']}]),iso_now()))
            repository.append_audit(conn,action='pec.receipt.linked_from_ministerial_xml',resource_type='pec_message',resource_id=m['id'],payload=ref,actor='lettura-fascicolo')
        m['collegata'] = True
        m['corrispondenza'] = 'collegamento'
        m['archive_receipt_reference'] = ref
        linked.append(m['id'])
    return linked
