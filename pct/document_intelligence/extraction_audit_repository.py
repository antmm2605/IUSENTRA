"""Dettagli degli errori di lettura, dal registro SQL del tenant corrente."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .security import DocumentAIValidationError


class DocumentAIExtractionAuditRepository:
    def __init__(self, repository: Any):
        self.repository = repository

    def error_messages(self, tenant_id: str, fascicolo_id: str, document_hashes: Mapping[str, str]) -> dict[str, str]:
        if not document_hashes:
            return {}
        if len(document_hashes) > 12:
            raise DocumentAIValidationError('Il dettaglio degli errori richiede una selezione di massimo 12 documenti.')
        if not getattr(self.repository, '_backend', None):
            raise DocumentAIValidationError('Il dettaglio dell’indicizzazione richiede il registro SQL dello studio.')
        placeholders = ','.join('?' for _ in document_hashes)
        rows = self.repository._conn().execute(
            f'''SELECT document_id, payload_json FROM (
                SELECT document_id, payload_json,
                    ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY created_at DESC, id DESC) AS position
                FROM fascicolo_documenti_ai_audit
                WHERE tenant_id = ? AND fascicolo_id = ?
                    AND event_type = 'document_ai.extraction.failed'
                    AND document_id IN ({placeholders})
            ) latest WHERE position = 1''',
            (tenant_id, fascicolo_id, *document_hashes),
        ).fetchall()
        messages: dict[str, str] = {}
        for row in rows:
            try:
                payload = json.loads(row['payload_json'])
            except (TypeError, ValueError) as exc:
                raise DocumentAIValidationError('Il registro dell’indicizzazione contiene un dettaglio non leggibile.') from exc
            if not isinstance(payload, dict):
                raise DocumentAIValidationError('Il registro dell’indicizzazione contiene un dettaglio non valido.')
            document_id = str(row['document_id'])
            if payload.get('sha256') != document_hashes.get(document_id):
                continue
            message = payload.get('error_message')
            if isinstance(message, str) and message.strip():
                messages[document_id] = message.strip()
        return messages
