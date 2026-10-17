"""Metadati delle ricevute già analizzate dal motore PEC, senza rilettura MIME."""
import json
from datetime import UTC, datetime

from pct.formatting import DISPLAY_TIMEZONE


def projected_receipt(row):
    """Non attribuisce fascicoli e non modifica lo stato di alcun deposito."""
    from pct.pec_pipeline import LINK_STATI_CERTIFICATI, sha256_json

    row = dict(row)
    stored_report = row['report_json']
    report = stored_report if isinstance(stored_report, dict) else json.loads(stored_report)
    if not isinstance(report, dict):
        raise ValueError('Analisi della ricevuta non strutturata.')
    if sha256_json(report) != row['report_sha256']:
        raise ValueError('Impronta del report PEC discordante.')
    life = report.get('deposit_lifecycle')
    if not isinstance(life, dict):
        raise ValueError('Analisi della ricevuta di deposito assente.')
    history, stage, correlation = (life.get(key) or {} for key in ('history_event', 'current_stage', 'correlation'))
    if not all(isinstance(value, dict) for value in (history, stage, correlation)):
        raise ValueError('Analisi della ricevuta di deposito non ricostruibile.')
    analyzed_hash = str(correlation.get('mime_sha256') or '')
    if analyzed_hash and analyzed_hash != str(row.get('mime_sha256') or ''):
        raise ValueError('Impronta MIME della fonte analizzata discordante.')
    stage_id = str(stage.get('id') or '')
    if history.get('stage') != stage_id:
        raise ValueError('Fase e cronologia della ricevuta discordanti.')
    state = ''
    if stage_id == 'accettazione_pec':
        state = 'ACCETTATO_PEC'
    elif stage_id in {'accettazione_deposito', 'intervento_cancelleria'} and life.get('final_state') in {'accepted', 'accepted_manually'}:
        state = 'ACCETTATO_CANCELLERIA'
    elif stage_id == 'rifiuto_deposito':
        state = 'RIFIUTATO_CANCELLERIA'
    event_at = ''
    try:
        parsed = datetime.fromisoformat(str(history.get('occurred_at') or '').replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=DISPLAY_TIMEZONE)
        event_at = parsed.astimezone(UTC).isoformat(timespec='microseconds')
    except ValueError:
        pass
    key = str(correlation.get('key') or '')
    issue = 'correlation_not_confirmed' if not key or correlation.get('manual_review') else ''
    if not event_at:
        issue = issue or 'event_date_not_available'
    case_id = str(row.get('linked_fascicolo_id') or '')
    confirmed = bool(case_id and row.get('case_link_status') in LINK_STATI_CERTIFICATI)
    return dict(state=state, event_at=event_at, correlation_key=key,
                title=str(correlation.get('document_name') or correlation.get('atto') or 'Ricevuta di deposito'),
                case_id=case_id if confirmed else '', candidate_case_id=case_id,
                case_link_confirmed=confirmed,
                message_id=str(row['message_id']), report_id=str(row['id']),
                source_revision=str(row['report_sha256']), source_mime_sha256=str(row.get('mime_sha256') or ''),
                issue=issue)
