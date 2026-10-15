"""La domanda pubblica conserva il quesito giuridico, non i dati della causa."""

from lex.guards.hallucination_guard import extract_legal_references
from lex.research.privacy_safe_query_rewriter import rewrite_query_for_legal_research


def test_exact_criminal_procedure_reference_is_not_lost_or_changed_into_penal_code():
    query = rewrite_query_for_legal_research('cerca sul web libero art. 606 c.p.p.')
    assert query.public_research_query == 'art. 606 c.p.p.'
    references = extract_legal_references(query.public_research_query)
    assert references[0].key.endswith(':c.p.p.')
    assert extract_legal_references('art. 606 c.p.')[0].key.endswith(':c.p.')


def test_long_term_and_all_requested_matters_are_preserved():
    query = rewrite_query_for_legal_research('termine lungo impugnazione civile amministrativa tributaria')
    assert query.public_research_query == 'termine lungo impugnazione civile amministrativa tributaria'


def test_private_case_identifiers_do_not_enter_public_projection():
    query = rewrite_query_for_legal_research('Cliente Mario Rossi RG 9926/2026: termine lungo impugnazione civile')
    public = query.public_research_query
    assert '9926' not in public
    assert 'Mario' not in public and 'Rossi' not in public
    assert 'termine lungo' in public


def test_year_explicitly_attached_to_public_reform_is_preserved():
    query = rewrite_query_for_legal_research('cerca sul web libero riforma mediazione 2026')
    assert query.public_research_query == 'riforma mediazione 2026'
    private = rewrite_query_for_legal_research('riforma mediazione per Mario Rossi RG 9926/2026')
    assert '2026' not in private.public_research_query
