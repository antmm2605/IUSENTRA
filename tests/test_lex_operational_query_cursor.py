from dataclasses import replace
from datetime import date

import pytest
from flask import Flask

from lex.operational_knowledge.models import OperationalQueryContext
from lex.operational_knowledge.query_cursor import decode_query_cursor, encode_query_cursor
from lex.operational_knowledge.query_selection import resolve_query_selection


def test_cursor_conserva_filtri_e_non_passi_indietro_sul_periodo():
    app = Flask(__name__)
    app.secret_key = 'controlled-test-secret-only'
    context = OperationalQueryContext('study-a', 'user-a')
    selection = resolve_query_selection('PEC inviate nel cestino ieri', today=date(2026, 10, 16))
    cursor = ('2026-10-15T12:00:00.000000+00:00', 'one')
    with app.app_context():
        token = encode_query_cursor(context, selection, cursor)
        decoded, position = decode_query_cursor(token, context)
        assert decoded == selection
        assert position == cursor
        for changed in (replace(context, tenant_id='study-b'), replace(context, user_id='user-b')):
            with pytest.raises(ValueError, match='sessione'):
                decode_query_cursor(token, changed)
        with pytest.raises(ValueError, match='scaduta'):
            decode_query_cursor(token, context, max_age=-1)
        with pytest.raises(ValueError):
            decode_query_cursor(token[:-10] + '0000000000', context)


def test_sessione_senza_segreto_non_crea_token_non_firmato():
    app = Flask(__name__)
    with app.app_context(), pytest.raises(ValueError, match='Sessione'):
        encode_query_cursor(OperationalQueryContext('a', 'u'), resolve_query_selection('PEC oggi', today=date.today()), ('data', 'id'))


@pytest.mark.parametrize('question', ['notifiche accettate ieri', 'notifiche da fare oggi', 'udienze ieri', 'scadenze aperte oggi', 'agenda domani'])
def test_cursor_notificazioni_preserva_evento_e_stato(question):
    app = Flask(__name__)
    app.secret_key = 'controlled-query-secret'
    context = OperationalQueryContext('studio-controllato', 'utente-controllato')
    selection = resolve_query_selection(question, today=date(2026, 10, 16))
    with app.app_context():
        token = encode_query_cursor(context, selection, ('2026-10-15T12:00:00.000000', 'controlled-id'))
        decoded, cursor = decode_query_cursor(token, context)
    assert decoded == selection
    assert cursor[1] == 'controlled-id'
