"""Prova reale PostgreSQL del catalogo in uno schema temporaneo isolato.

Usa un DSN già configurato, mai stampato. Non modifica tabelle esistenti.
Esempio: --dsn-env AUDIT_DATABASE_URL (ambiente locale di collaudo).
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn

from pct.document_intelligence.catalog_pipeline import FascicoloDocumentCatalogPipeline
from pct.document_intelligence.models import (
    DocumentAIPageText, DocumentAIRecord, DocumentAIText, DocumentAIVersion, utc_now,
)
from pct.document_intelligence.repository import DocumentAIRepository
from pct.document_intelligence.sources import DocumentAISource


def verify(dsn: str) -> dict:
    schema = 'catalog_verify_' + uuid4().hex
    admin = psycopg2.connect(dsn, connect_timeout=10)
    admin.autocommit = True
    repo = None
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        with tempfile.TemporaryDirectory(prefix='iusentra-catalog-postgres-') as folder:
            repo = DocumentAIRepository.from_postgres_dsn(
                make_dsn(dsn, options=f'-c search_path={schema}', connect_timeout=10),
                storage_root=Path(folder),
            )
            now = utc_now()
            text = 'FATTURA n. 0005\nCliente collaudo\nTotale fattura € 1.234,56'
            repo.create_document(DocumentAIRecord(
                id='DA1', tenant_id='catalog-test', fascicolo_id='F1', original_filename='collaudo.txt',
                safe_filename='collaudo.txt', file_type='txt', mime_type='text/plain', size_bytes=len(text),
                sha256='a' * 64, status='ready', current_version_id='V1', page_count=1,
                created_by='test', created_at=now, updated_at=now,
            ))
            repo.create_version(DocumentAIVersion(
                id='V1', tenant_id='catalog-test', fascicolo_id='F1', document_id='DA1',
                version_number=1, source='upload', storage_path='collaudo.txt', extracted_text_path=None,
                pdf_preview_path=None, sha256='a' * 64, created_by='test', created_at=now,
            ))
            repo.save_extracted_text(DocumentAIText(
                document_id='DA1', version_id='V1', tenant_id='catalog-test', fascicolo_id='F1',
                text=text, pages=[DocumentAIPageText(page_number=1, text=text)],
                extraction_engine='controlled', created_at=now,
            ))
            source = DocumentAISource(
                tenant_id='catalog-test', fascicolo_id='F1', source_id='D1', source_type='documenti_fascicolo',
                filename='collaudo.txt', safe_filename='collaudo.txt', file_type='txt', mime_type='text/plain',
                size_bytes=len(text), sha256='a' * 64, updated_at=now,
                metadata={'documento_id': 'D1'}, content_bytes=text.encode(),
            )
            run = FascicoloDocumentCatalogPipeline(repo).run(
                tenant_id='catalog-test', fascicolo=SimpleNamespace(id='F1', oggetto='Vendita di cose immobili'),
                sources=[source], actor='test', process=True,
            )
            assert not run.errors, 'La pipeline PostgreSQL ha restituito errori'
            before = repo.get_catalog_assignment('catalog-test', 'F1', 'D1')
            assert before and before.document_nature == 'fattura'
            evidence = repo.list_catalog_evidence(before.id)
            assert any(item.locator.startswith('campo:') and item.excerpt == '0005' for item in evidence)
            broken = replace(evidence[0], id='invalid-evidence', evidence_type='invalid_type')
            try:
                repo.save_catalog_assignment(replace(before, document_label='Non salvare'), evidence=[broken])
            except psycopg2.IntegrityError:
                pass
            else:
                raise AssertionError('Il vincolo PostgreSQL non ha respinto il dato invalido')
            assert repo.get_catalog_assignment('catalog-test', 'F1', 'D1').document_label == before.document_label
            assert {item.id: item for item in repo.list_catalog_evidence(before.id)} == {item.id: item for item in evidence}
            assert repo.get_catalog_assignment('different-tenant', 'F1', 'D1') is None
            repo.save_catalog_assignment(before, evidence=evidence)
            # Le prove con peso/data uguali non hanno un ordine SQL garantito.
            assert {item.id: item for item in repo.list_catalog_evidence(before.id)} == {item.id: item for item in evidence}
        return {'source_of_truth': 'postgresql', 'pipeline': 'passed', 'field_evidence': 'passed',
                'atomic_rollback': 'passed', 'tenant_isolation': 'passed', 'connection_after_error': 'passed'}
    finally:
        if repo is not None:
            repo.structured_db.close()
        # Solo lo schema casuale creato da questa esecuzione; mai public o dati studio.
        if not schema.startswith('catalog_verify_') or len(schema) != len('catalog_verify_') + 32:
            raise RuntimeError('Nome dello schema temporaneo non valido')
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
        admin.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsn-env', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(os.environ[args.dsn_env]), ensure_ascii=False))
