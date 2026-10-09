"""Associa le identità già lette nel SQL, senza copie né nuove scansioni OCR.

Procedura straordinaria esplicita: il catalogo SQL è anche il checkpoint.
Le fonti senza lettura corrente o con titolare discordante restano nel report.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def associate_case(case, client, repository, objects, tenant, *, apply=False):
    from pct.document_intelligence.catalog_identita_personale import documento_identita_personale, documento_identita_dal_nome
    from pct.document_intelligence.catalog_pipeline import FascicoloDocumentCatalogPipeline
    from pct.document_intelligence.sources import DocumentAISource
    from web.services.client_document_reader import parse_client_document_text

    report = {'fascicolo_id': case.id, 'cliente_id': case.id_cliente,
              'candidates': [], 'already_linked': [], 'unresolved': [], 'errors': []}
    if client is None or str(client.id) != str(case.id_cliente):
        report['errors'].append('Cliente SQL non disponibile.')
        return report
    hashes = {o.oggetto_id: {h for h in (o.sha256, getattr(o, 'sha256_archivio', '')) if h}
              for o in objects if o.tipo == 'documento' and o.presente}
    records = repository.list_documents(tenant, case.id)
    assignments = {}
    for assignment in repository.list_catalog_assignments(tenant, case.id):
        assignments.setdefault(assignment.document_id, assignment)
    sources, texts = [], {}
    for doc in case.documenti:
        current_hashes = hashes.get(doc.id, set())
        record = next((r for r in records if r.status == 'ready' and r.sha256 in current_hashes), None)
        if record is None:
            if documento_identita_dal_nome(doc.nome_originale or doc.nome):
                report['unresolved'].append({'documento_id': doc.id, 'reason': 'Lettura corrente mancante: recupero puntuale necessario.'})
            continue
        extracted = repository.get_extracted_text(tenant, case.id, record.id, record.current_version_id)
        text = str(getattr(extracted, 'text', '') or '')
        identity = documento_identita_personale(text, cliente=client.nome_completo)
        if not identity:
            if documento_identita_dal_nome(doc.nome_originale or doc.nome):
                report['unresolved'].append({'documento_id': doc.id, 'reason': 'Documento candidato non riconosciuto nella lettura corrente: recupero puntuale necessario.'})
            continue
        patch = parse_client_document_text(text)['patch']
        actual_cf = str(patch.get('codice_fiscale') or '').upper()
        expected_cf = str(client.codice_fiscale or '').upper()
        from pct.document_intelligence.catalog_identita_personale import normalizza
        parsed_name = normalizza(str(patch.get('nome') or '') + ' ' + str(patch.get('cognome') or ''))
        expected_name = normalizza(str(client.nome or '') + ' ' + str(client.cognome or ''))
        # Il CF valido estratto e concordante riscontra il titolare anche
        # quando l'OCR ha mescolato le etichette Nome/Cognome. Le parole del
        # nome devono comunque comparire nella carta riconosciuta dal motore.
        cf_matches = bool(actual_cf and expected_cf and actual_cf == expected_cf)
        if (not identity.get('titolare') or (not cf_matches and sorted(parsed_name.split()) != sorted(expected_name.split()))
                or (actual_cf and expected_cf and actual_cf != expected_cf)):
            missing_name = not patch.get('nome') or not patch.get('cognome')
            reason = ('Nome e cognome non estratti in modo affidabile: recupero puntuale necessario.' if missing_name
                      else 'Titolare o codice fiscale discordante: collegamento impedito.')
            report['unresolved'].append({'documento_id': doc.id, 'reason': reason})
            continue
        assignment = assignments.get(doc.id)
        if assignment and assignment.document_sha256 == record.sha256:
            if assignment.metadata.get('identity_client_id') == client.id and assignment.metadata.get('identity_holder'):
                report['already_linked'].append(doc.id)
                continue
            if assignment.status == 'confirmed' or assignment.source_state == 'manual_override':
                report['unresolved'].append({'documento_id': doc.id, 'reason': 'Decisione manuale conservata.'})
                continue
        report['candidates'].append(doc.id)
        sources.append(DocumentAISource(tenant_id=tenant, fascicolo_id=case.id, source_id=doc.id,
            source_type='documenti_fascicolo', filename=doc.nome_originale or doc.nome,
            safe_filename=record.safe_filename, file_type=record.file_type, mime_type=record.mime_type,
            size_bytes=record.size_bytes, sha256=record.sha256, updated_at=record.updated_at,
            metadata={'documento_id': doc.id, 'archive_reading': True, 'identity_binding_verified': True}))
        texts[doc.id] = text
    if apply and sources:
        outcome = FascicoloDocumentCatalogPipeline(repository, text_provider=lambda did: texts.get(did, ''),
            client_name=client.nome_completo, client_id=client.id).run(tenant_id=tenant,
            fascicolo=case, sources=sources, actor='associazione-identita-clienti', process=True, retry=True)
        report['run'] = outcome.to_dict()
        report['errors'].extend(outcome.errors)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--case-id', action='append', default=[], help='Ripresa puntuale: elabora solo questi fascicoli del tenant.')
    parser.add_argument('--backup-dir', default='')
    parser.add_argument('--backup-report', default='', help='Report precedente con impronta della copia coerente da riconvalidare per la ripresa.')
    args = parser.parse_args()
    if args.apply and not args.backup_dir:
        parser.error('Occorre --backup-dir per una copia coerente prima delle scritture.')
    from web.app import create_app
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    from web.helpers import get_clienti, get_fascicoli
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    app = create_app()
    manager, targets = _targets(app, args.tenant)
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('a', encoding='utf-8') as log:
        for slug, studio in targets.items():
            with _tenant_context(app, manager, studio, slug):
                cases, clients = get_fascicoli(), get_clienti()
                repository = build_document_ai_service().repository
                if repository.backend_kind not in {'sqlite', 'postgresql'}:
                    raise RuntimeError('Occorre il repository SQL del tenant.')
                if args.apply:
                    if repository.backend_kind != 'sqlite':
                        raise RuntimeError('Preparare prima il backup PostgreSQL nativo; non applicare un backup SQLite.')
                    from deploy.hetzner.backup_structured import _backup_sqlite
                    import shutil
                    destination = Path(args.backup_dir)
                    destination.mkdir(parents=True, exist_ok=True)
                    source_db = Path(cases._studio_db.db_path)
                    if shutil.disk_usage(destination).free < source_db.stat().st_size + 1024**3:
                        raise RuntimeError('Spazio insufficiente per il backup: nessuna associazione applicata.')
                    backup = destination / 'studio-identita-clienti.db'
                    if backup.exists():
                        if not args.backup_report:
                            raise RuntimeError('Backup già presente: occorre il report firmato dall’impronta per riprendere.')
                        from deploy.hetzner.backup_structured import _sha256
                        prior = json.loads(Path(args.backup_report).read_text(encoding='utf-8').splitlines()[0])
                        info = prior.get('backup') or {}
                        if (prior.get('tenant') != slug or info.get('source') != str(source_db)
                                or info.get('sha256') != _sha256(backup) or info.get('quick_check') != 'ok'):
                            raise RuntimeError('Copia coerente non verificata per il tenant: nessuna scrittura.')
                    else:
                        info = _backup_sqlite(source_db, backup)
                    log.write(json.dumps({'backup': info, 'tenant': slug}, ensure_ascii=False) + '\n')
                    log.flush()
                registry = registro_corrente()
                totals = {'fascicoli': 0, 'candidates': 0, 'already_linked': 0, 'unresolved': 0, 'errors': 0}
                selected_cases = cases.tutti(archiviati=True)
                requested = set(args.case_id)
                if requested:
                    available = {str(case.id) for case in selected_cases}
                    if not requested.issubset(available):
                        raise RuntimeError('Fascicolo non disponibile nel tenant richiesto: nessuna associazione puntuale.')
                    selected_cases = [case for case in selected_cases if str(case.id) in requested]
                for case in selected_cases:
                    result = associate_case(case, clients.get(case.id_cliente), repository,
                        registry.oggetti(tenant_corrente(), case.id), document_ai_tenant_id(), apply=args.apply)
                    totals['fascicoli'] += 1
                    for key in ('candidates', 'already_linked', 'unresolved', 'errors'):
                        totals[key] += len(result[key])
                    log.write(json.dumps(result, ensure_ascii=False) + '\n')
                    log.flush()
                print(json.dumps({'tenant': slug, 'apply': args.apply, **totals}), flush=True)


if __name__ == '__main__':
    main()
