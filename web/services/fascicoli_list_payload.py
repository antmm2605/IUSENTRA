"""Payload React dell'elenco ottenuto da paginazione e aggregazioni SQL."""
from web.services.react_fascicoli_bridge import (
    _summary, _facets, _contracts, _list_actions, _now, _positive_int, _normalise_payment_kind,
)


def _summary_values(metrics, archived):
    result = _summary([])
    for key, value in metrics.items():
        if key in result:
            result[key] = round(value, 2) if key in {'registeredAmount', 'advancesToRecover'} else int(value)
    result['total'] += archived
    result['archived'] += archived
    return result


def build_sql_list_payload(repository, *, page=1, page_size=5, query='', client_filter='', rg_filter='',
                           type_filter='', status_filter='', court='', sort='rg', secondary_sort='', group_by='',
                           view='', alerts_only=False, communications_only=False, payments_only=False,
                           missing_rg_only=False, duplicates_only=False, payment_filters=None, field_filters=None,
                           enrich_economic=None):
    normalized_payments = {(_normalise_payment_kind(key) or key): value for key, value in (payment_filters or {}).items()}
    selection = dict(query=query, client=client_filter, rg=rg_filter, type_filter=type_filter, status=status_filter,
        court=court, alerts_only=alerts_only, communications_only=communications_only, payments_only=payments_only,
        missing_rg_only=missing_rg_only, duplicates_only=duplicates_only, payment_filters=normalized_payments,
        field_filters=field_filters)
    result = repository.list_page(page=_positive_int(page, 1, maximum=100000),
        page_size=_positive_int(page_size, 5, maximum=100), sort=sort, secondary_sort=secondary_sort, group_by=group_by,
        **selection)
    archived = repository.archived_count()
    summary = _summary_values(repository.aggregates(**selection), archived)
    card_selection = dict(query=query, client=client_filter, rg=rg_filter, type_filter=type_filter,
                          court=court, field_filters=field_filters)
    card_summary = _summary_values(repository.aggregates(**card_selection), archived)
    overview = repository.deadline_overview()
    summary.update({key: overview[key] for key in ('deadlines7', 'deadlines30', 'overdueDeadlines', 'urgentDeadlines')})
    facets = _facets([])
    counts = repository.facets()
    for group, column in (('types', 'type'), ('statuses', 'status')):
        for entry in facets[group]:
            value = entry['value']
            values = {'definito', 'da_archiviare'} if group == 'statuses' and value == 'definito' else {value}
            entry['count'] = sum(row['count'] for row in counts if value == 'tutti' or row[column] in values)
    items = result['items']
    if str(view).strip().lower() == 'economica' and items:
        if enrich_economic is None:
            raise RuntimeError('Proiezione della vista economica non disponibile.')
        items = enrich_economic(items)
    repository._ready()
    return dict(source='repository_reali', generatedAt=_now(), contracts=_contracts(), summary=summary,
                cardSummary=card_summary, items=items, pagination=result['pagination'], facets=facets,
                deadlines=overview['deadlines'], actions=_list_actions())
