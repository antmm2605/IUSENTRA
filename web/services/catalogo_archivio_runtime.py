"""Aggiorna il catalogo del singolo fascicolo dai testi SQL correnti."""
from __future__ import annotations
from typing import Any
from pct.document_intelligence.catalog_context import fascicolo_catalog_context
from pct.document_intelligence.catalog_pipeline import FascicoloDocumentCatalogPipeline
from pct.document_intelligence.catalog_resolver import RESOLVER_VERSION, resolve_profile
from pct.document_intelligence.sources import DocumentAISource


def _text(value: Any) -> str:
    return str(getattr(value, 'value', value) or '').strip()


def _human(assignment: Any) -> bool:
    return assignment is not None and (assignment.source_state == 'manual_override' or assignment.status == 'confirmed')


def prepara_catalogo(fascicolo: Any, oggetti: list[Any], repository: Any, tenant: str) -> tuple[list, dict, dict]:
    """Solo documenti presenti: l'ID del fascicolo resta distinto dall'ID DocumentAI."""
    fid = str(fascicolo.id)
    hashes = {o.oggetto_id: o.sha256 for o in oggetti if o.tipo == 'documento' and o.presente and o.sha256}
    ready = {}
    for record in sorted(repository.list_documents(tenant, fid), key=lambda r: _text(r.updated_at), reverse=True):
        if _text(record.status) == 'ready' and record.sha256 in hashes.values():
            ready.setdefault(record.sha256, record)
    assignments = {}
    for assignment in sorted(repository.list_catalog_assignments(tenant, fid), key=lambda a: _text(a.updated_at), reverse=True):
        assignments.setdefault((assignment.document_id, assignment.document_sha256), assignment)
    context = fascicolo_catalog_context(fascicolo)
    profile, _ = resolve_profile(context)
    report = {'fascicolo_id': fid, 'source_of_truth': repository.backend_kind, 'read_mode': 'sql_text_only', 'file_reads': 0,
              'resolver_version': RESOLVER_VERSION, 'current_documents': len(fascicolo.documenti),
              'stale_assignments': 0, 'missing_assignments': 0, 'manual_or_confirmed_preserved': 0,
              'waiting_for_text': 0, 'eligible_documents': 0, 'status': 'unchanged'}
    sources, texts = [], {}
    for doc in fascicolo.documenti:
        doc_id = str(doc.id)
        sha = hashes.get(doc_id, '')
        record = ready.get(sha)
        if record is None:
            report['waiting_for_text'] += 1
            continue
        assignment = assignments.get((doc_id, sha))
        if _human(assignment):
            report['manual_or_confirmed_preserved'] += 1
            continue
        stale = assignment is None or assignment.resolver_version != RESOLVER_VERSION or (assignment.document_version_id or '') != record.current_version_id
        if assignment is not None and profile:
            stale = stale or any((getattr(assignment, attr, '') or '') != value for attr, value in (
                ('profile_id', profile), ('legal_area', context.get('area') or ''),
                ('legal_branch', context.get('branca') or ''), ('legal_subfamily', context.get('sottobranca') or '')))
        if not stale:
            continue
        report['missing_assignments' if assignment is None else 'stale_assignments'] += 1
        extracted = repository.get_extracted_text(tenant, fid, record.id, record.current_version_id)
        text = _text(getattr(extracted, 'text', ''))
        if not text or text.lstrip().startswith('PCTENC') or 'binary-best-effort' in _text(getattr(extracted, 'extraction_engine', '')) or _text(getattr(extracted, 'extraction_engine', '')) == 'email.message':
            report['waiting_for_text'] += 1
            continue
        filename = _text(getattr(doc, 'nome', '')) or record.original_filename
        source = DocumentAISource(
            tenant_id=tenant, fascicolo_id=fid, source_id=doc_id,
            source_type='portale_telematico' if _text(getattr(doc, 'fonte_documento', '')) == 'PORTALE_TELEMATICO' else 'documenti_fascicolo',
            filename=filename, safe_filename=record.safe_filename, file_type=record.file_type,
            mime_type=record.mime_type, size_bytes=record.size_bytes, sha256=sha, updated_at=record.updated_at,
            supported=True, metadata={
                'documento_id': doc_id, 'document_ai_id': record.id, 'document_version_id': record.current_version_id,
                'fonte_documento': _text(getattr(doc, 'fonte_documento', '')), 'tipo_documento': _text(getattr(doc, 'tipo', '')),
                'id_deposito_pct': _text(getattr(doc, 'id_deposito_pct', '')), 'nome_portale': _text(getattr(doc, 'nome_portale', '')),
                'classificazione_portale': _text(getattr(doc, 'classificazione_portale', '')), 'archive_reading': True})
        sources.append(source)
        texts[doc_id] = text
    report['eligible_documents'] = len(sources)
    return sources, texts, report


def aggiorna_catalogo_da_archivio(fascicolo: Any, registro: Any = None, *, applica: bool = True) -> dict[str, Any]:
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id, _registra_catalogo
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    registro = registro or registro_corrente()
    tenant = document_ai_tenant_id()
    repository = build_document_ai_service().repository
    if repository.backend_kind not in {'sqlite', 'postgresql'}:
        raise ValueError('Catalogo archivio richiede una fonte SQL')
    sources, texts, report = prepara_catalogo(fascicolo, registro.oggetti(tenant_corrente(), fascicolo.id), repository, tenant)
    report['dry_run'] = not applica
    if not sources or not applica:
        return report
    pipeline = FascicoloDocumentCatalogPipeline(repository, text_provider=lambda doc_id: texts.get(doc_id, ''),
        client_name=_text(getattr(fascicolo, 'nome_cliente', '')), client_id=_text(getattr(fascicolo, 'id_cliente', '')))
    run = pipeline.run(tenant_id=tenant, fascicolo=fascicolo, sources=sources, actor='archivio-letture.catalogo', process=True)
    report['run'] = run.to_dict()
    report['status'] = 'error' if run.errors else ('updated' if run.processed else 'unchanged')
    assignments = repository.list_catalog_assignments(tenant, fascicolo.id)
    _registra_catalogo(fascicolo.id, sources, {(a.document_id, a.document_sha256): a for a in assignments})
    return report
