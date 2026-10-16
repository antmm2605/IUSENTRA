from datetime import date
from types import SimpleNamespace

from lex.operational_knowledge.models import OperationalQueryContext
from lex.operational_knowledge.query_selection import resolve_query_selection
from lex.operational_knowledge.tools import OperationalKnowledgeTools


def test_notifiche_rbac_prima_di_aprire_repository(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError('Repository aperto senza permessi')
    monkeypatch.setattr('web.services.notification_presidia_runtime.build_notification_presidio_repository', forbidden)
    context = OperationalQueryContext(tenant_id='study-a', user_id='controlled')
    selection = resolve_query_selection('notifiche accettate oggi', today=date(2026, 10, 16))
    result = OperationalKnowledgeTools().query_legal_notifications_page(context, selection=selection)
    assert not result.ok


def test_notifiche_zero_risultati_e_tenant_discordante(monkeypatch):
    calls = []
    def query(**kwargs):
        calls.append(kwargs)
        return dict(rows=[], has_more=False, cursor=None, unknown_date_count=2)
    repo = SimpleNamespace(tenant_id='study-a', list_operational_page=query, close=lambda: calls.append('closed'))
    monkeypatch.setattr('web.services.notification_presidia_runtime.build_notification_presidio_repository', lambda **kw: repo)
    context = OperationalQueryContext(tenant_id='study-a', user_id='controlled', user=SimpleNamespace(id='controlled'),
                                      permissions={'ai.usa', 'messaggi.leggi', 'fascicoli.leggi'})
    selection = resolve_query_selection('notifiche accettate oggi', today=date(2026, 10, 16))
    tools = OperationalKnowledgeTools()
    result = tools.query_legal_notifications_page(context, selection=selection)
    assert result.ok and result.query_metadata['executed']
    assert result.query_metadata['unknown_date_count'] == 2
    assert calls[0]['mode'] == 'accepted'
    assert calls[-1] == 'closed'
    calls.clear()
    repo.tenant_id = 'other-study'
    assert not tools.query_legal_notifications_page(context, selection=selection).ok
    assert calls == ['closed']
