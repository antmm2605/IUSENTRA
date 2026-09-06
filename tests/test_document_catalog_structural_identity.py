import pytest

from pct.document_intelligence.catalog_context import enrich_official_context
from pct.document_intelligence.catalog_identity import structural_identity


@pytest.mark.parametrize(('text', 'label'), [
    ('REPUBBLICA ITALIANA\nIN NOME DEL POPOLO ITALIANO\nTRIBUNALE DI ROMA\nS E N T E N Z A\nRisoluzione del contratto preliminare di vendita', 'Sentenza'),
    ('ATTESTAZIONE DI CONFORMITÀ\nIl difensore ATTESTA che sono conformi i seguenti documenti: verbale udienza, sentenza.', 'Attestazione di conformità'),
    ('ISTANZA DI MEDIAZIONE\nOrganismo di mediazione\nIstante _________ Parte _________ Avvocato _________', 'Modulo di istanza di mediazione'),
    ('TRIBUNALE DI ROMA\nIl Presidente di sezione ASSEGNA il procedimento al giudice.', 'Provvedimento dell’ufficio giudiziario'),
    ('TRIBUNALE DI ROMA\nIl Giudice RITENUTO opportuno DELEGA il GOP.', 'Provvedimento dell’ufficio giudiziario'),
    ('TRIBUNALE DI ROMA\nORDINANZA\nIl Giudice\nDISPONE\nla prosecuzione del giudizio.', 'Ordinanza dell’ufficio giudiziario'),
    ('FATTURA n. 05\nCliente Esempio\nPartita IVA 00000000000\nTotale fattura € 1.234,56', 'Fattura'),
    ('<Sentenza xmlns="http://schemi.processotelematico.giustizia.it/sicid/atti"><dati>sentenza</dati></Sentenza>', 'Dati strutturati PST — Sentenza'),
])
def test_document_identity_precedes_quoted_acts(text, label):
    identity = structural_identity(text)
    assert identity and identity['label'] == label
    assert identity['evidence']


@pytest.mark.parametrize('text', [
    'La sentenza cita un contratto preliminare.',
    'TRIBUNALE DI ROMA\nDifensore: il giudice ha dichiarato che la sentenza DISPONE la consegna.',
    '<!DOCTYPE a [<!ENTITY x SYSTEM "file:///private">]><a>&x;</a>',
    '<!DOCTYPE a SYSTEM "https://example.test/evil.dtd"><a/>',
    '<root>Sentenza</root>',
])
def test_mentions_or_untrusted_xml_do_not_establish_identity(text):
    assert structural_identity(text) is None


def test_unique_ministerial_object_supplies_traceable_profile_without_mutation():
    context = {'oggetto': 'Vendita di cose immobili', 'canale': 'PST'}
    enriched = enrich_official_context(context)
    assert enriched['_official_object_code'] == '140011'
    assert enriched['sottobranca'] == 'Vendita di cose immobili'
    assert enriched['_official_profile_id'] == 'CIV-PCT'
    assert len(enriched['_official_catalog_sha256']) == 64
    assert 'area' not in context


@pytest.mark.parametrize('extra', [
    {'area': 'Civile'}, {'branca': 'Scelta esplicita'}, {'sottobranca': 'Scelta esplicita'},
    {'canale': 'PDP'}, {'tipo_fascicolo': 'penale'}, {'codice_oggetto_pst': 'codice-sconosciuto'},
])
def test_manual_partial_profiles_and_other_channels_are_not_overwritten(extra):
    context = {'oggetto': 'Vendita di cose immobili', **extra}
    assert enrich_official_context(context) == context
