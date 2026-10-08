from types import SimpleNamespace

import pytest

from pct.pec_case_identity import case_identity_evidence, document_case_identity_evidence


@pytest.mark.parametrize('number,year', [('1548', 2023), ('00001548/2023', 2023), ('1548/2023', '')])
def test_rg_complete_or_split_preserves_joint_identity(number, year):
    case = SimpleNamespace(numero_rg=number, anno_rg=year, nome_cliente='Spagnolo Sara', tribunale='Tribunale di Palmi')
    source = dict(numero_ruolo_certificato='1548/2023', cliente='Sara Spagnolo', ufficio='Tribunale ordinario di Palmi')
    proof = case_identity_evidence(source, case)
    assert proof['rg_match'] and proof['client_name_match'] and proof['office_match']
    assert not proof['conflicts']
    for key, value in [('cliente', 'Altro Cliente'), ('ufficio', 'Tribunale di Roma'), ('numero_ruolo_certificato', '1548/2024')]:
        other = case_identity_evidence({**source, key: value}, case)
        assert not all(other[k] for k in ('rg_match', 'client_name_match', 'office_match'))


def test_year_conflict_inside_case_is_never_verified():
    case = SimpleNamespace(numero_rg='1548/2023', anno_rg=2024, nome_cliente='Spagnolo Sara', tribunale='Tribunale di Palmi')
    proof = case_identity_evidence(dict(numero_ruolo_certificato='1548/2023', cliente='Spagnolo Sara', ufficio='Tribunale di Palmi'), case)
    assert not proof['rg_match']


@pytest.mark.parametrize('office', ['Tribunale di Vicenza', 'TRIBUNALE ORDINARIO di VICENZA'])
def test_document_header_keeps_office_line_boundary(office):
    case = SimpleNamespace(numero_rg='1548', anno_rg=2023, nome_cliente='Spagnolo Sara', tribunale='Tribunale di Vicenza')
    text = f'{office}\nSentenza n. 230/2024 pubblicata il 07/05/2024\nRG n. 1548/2023\nSpagnolo Sara contro MIM\nP.Q.M.\n'
    proof = document_case_identity_evidence(text, case)
    assert proof['source_office'] == 'Tribunale di Vicenza'
    assert proof['complete_match']
    wrong = document_case_identity_evidence(text.replace('VICENZA', 'ROMA').replace('Vicenza', 'Roma'), case)
    assert not wrong['complete_match']
