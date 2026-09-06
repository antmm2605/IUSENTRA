"""Guardrail brevi per dettagli ed identità, senza automatismi contabili."""
import pytest

from pct.document_intelligence.catalog_fields import FATTURAPA_NS, document_fields
from pct.document_intelligence.catalog_identity import structural_identity
from pct.document_intelligence.catalog_resolver import _content_identity


def invoice_xml(*bodies):
    return (f'<p:FatturaElettronica xmlns:p="{FATTURAPA_NS}">'
            '<FatturaElettronicaHeader/>' + ''.join(bodies) + '</p:FatturaElettronica>')


def invoice_body(number='0005/A', currency='EUR', day='2026-09-06', kind='TD01'):
    return ('<FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento>'
            f'<TipoDocumento>{kind}</TipoDocumento><Numero>{number}</Numero>'
            f'<Data>{day}</Data><Divisa>{currency}</Divisa>'
            '<ImportoTotaleDocumento>1234.56</ImportoTotaleDocumento>'
            '</DatiGeneraliDocumento></DatiGenerali></FatturaElettronicaBody>')


def test_every_invoice_in_xml_lot_keeps_its_own_fields_and_original_number():
    text = invoice_xml(invoice_body(), invoice_body(number='0006/B'))
    fields = document_fields(text, 'fattura_xml')
    assert len(fields) == 8
    for index, number in [(1, '0005/A'), (2, '0006/B')]:
        own = [(where, value) for where, value in fields if f'Body[{index}]' in where]
        assert [value for _, value in own] == [number, '06/09/2026', 'EUR', '€ 1.234,56']
    identity = structural_identity(text)
    assert identity['label'] == 'Lotto di documenti fiscali in XML FatturaPA'
    assert 'non prova emissione SdI o pagamento' in identity['evidence']


def test_credit_note_is_not_labelled_as_an_invoice():
    assert structural_identity(invoice_xml(invoice_body(kind='TD04')))['label'] == 'Nota di credito in XML FatturaPA'


def test_invalid_date_and_foreign_currency_are_not_invented_or_converted():
    fields = document_fields(invoice_xml(invoice_body(currency='USD', day='2026-02-31')), 'fattura_xml')
    assert [value for _, value in fields] == ['0005/A', 'USD']


@pytest.mark.parametrize('text', [
    '<!DOCTYPE a [<!ENTITY x SYSTEM "file:///private">]><a>&x;</a>',
    '<!DOCTYPE a SYSTEM "https://example.test/evil.dtd"><a/>',
    '<root>Fattura n. 05</root>',
    invoice_xml(invoice_body()).replace(FATTURAPA_NS, 'https://untrusted.test/fatture'),
    invoice_xml(invoice_body().replace('<Numero>', '<Numero xmlns="https://untrusted.test">')).replace('<Data>', '<Data xmlns="https://untrusted.test">'),
])
def test_untrusted_xml_does_not_supply_a_number(text):
    assert not any('Numero documento' in where for where, _ in document_fields(text, 'fattura_xml'))


@pytest.mark.parametrize('title', ['Fattura proforma', 'Fattura pro-forma', 'Avviso di parcella', 'Notula'])
def test_proforma_with_totals_is_not_an_issued_invoice(title):
    identity = structural_identity(f'{title}\nCliente: prova\nTotale fattura € 1.234,56')
    assert identity['role'] == 'proforma'
    assert 'non prova emissione' in identity['evidence']


def test_textual_invoice_number_keeps_leading_zero_and_line_not_guessed_page():
    assert document_fields('Studio\nFATTURA n. 05\nTotale fattura € 1.234,56', 'fattura') == [
        ('Numero fattura letto · riga 2 del testo indicizzato', '05')]
    assert document_fields('FATTURA\nNumero\n05\nTotale € 1.234,56', 'fattura') == []


def test_multiple_cited_case_numbers_are_evidence_not_case_identity():
    fields = document_fields('Si confrontano R.G. 1025/2024 e R.G. 1025/2026.', 'provvedimento')
    assert len(fields) == 2
    assert all(where.startswith('RG citato') for where, _ in fields)
    assert any('2024' in value for _, value in fields)
    assert any('2026' in value for _, value in fields)


@pytest.mark.parametrize('outcome', ['mancata adesione', 'mancata partecipazione', 'esito negativo'])
def test_mediation_outcomes_remain_distinct(outcome):
    identity = structural_identity(f'Verbale di mediazione\nOrganismo di mediazione\n{outcome}')
    assert identity['label'] == f'Verbale di mediazione — {outcome}'


def test_mediation_agreement_is_not_a_minute_or_proof_of_signature():
    from pct.document_intelligence.catalog_sources import document_source_ids
    identity = structural_identity('Accordo di conciliazione\nOrganismo di mediazione\nLe parti convengono quanto segue.')
    assert identity['role'] == 'accordo_mediazione'
    assert 'firme ed efficacia non verificate' in identity['evidence']
    assert 'normattiva_d_lgs_28_2010_mediazione' in document_source_ids(identity['role'], identity['section'], 'CIV-PCT')
    minute = structural_identity('Verbale di mediazione\nOrganismo di mediazione\nLe parti convengono di allegare un accordo di conciliazione.')
    assert minute['role'] == 'verbale_mediazione'


@pytest.mark.parametrize(('title', 'label'), [
    ('Ricevuta di accettazione', 'Ricevuta PEC di accettazione'),
    ('Ricevuta di avvenuta consegna', 'Ricevuta PEC di avvenuta consegna'),
    ('Avviso di mancata consegna', 'Avviso PEC di mancata consegna'),
    ('Avviso di non accettazione', 'Avviso PEC di non accettazione'),
    ('Ricevuta di presa in carico', 'Ricevuta PEC di presa in carico'),
])
def test_pec_receipt_title_precedes_quoted_receipts_and_acts(title, label):
    text = (f'{title}\nPosta certificata - identificativo messaggio: prova\n'
            'Messaggio originale:\nRicevuta di avvenuta consegna\n'
            'TRIBUNALE DI ROMA\nIN NOME DEL POPOLO ITALIANO\nSENTENZA\n')
    identity = _content_identity(text)
    assert identity.classification.label == label
    assert identity.classification.deposit_candidate is False


def test_procura_mention_does_not_replace_the_document_identity():
    identity = _content_identity('Lettera del difensore. Si allega la procura speciale.\n'
                                 'Il cliente conferisce delega con atto separato.')
    assert identity is None or identity.classification.role != 'procura'
    assert _content_identity('PROCURA SPECIALE\nIl sottoscritto delega il difensore.').classification.role == 'procura'


def test_unsigned_mediation_power_template_without_heading_is_not_a_conferred_power():
    text = ('Il sottoscritto __________ conferisce procura speciale sostanziale a __________ '
            'per intervenire presso l’organismo di mediazione __________.')
    identity = _content_identity(text).classification
    assert identity.role == 'modulo_procura_mediazione'
    assert identity.label == 'Modulo di procura speciale per la mediazione'
    assert not identity.deposit_candidate
    assert 'non prova una procura conferita' in identity.evidence
    assert structural_identity('Lettera di accompagnamento. ' + text) is None
