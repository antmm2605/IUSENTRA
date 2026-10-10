from types import SimpleNamespace

import pytest

from pct.archivio_letture.date_campi_modello import estrai_date_modello
from pct.editor_linked_fields import date_modello_da_fatti, linked_fields_catalog


SOURCE = """TRIBUNALE DI VELLETRI
SENTENZA
Causa n. 123/2025 R.G.
PROMOSSA DA ROSSI MARIA
Con ricorso depositato in data 05 aprile 2025 la parte chiedeva quanto segue.
Il decreto di fissazione udienza del 12.04.2025 disponeva l'udienza del 12.03.2026.
"""


def matter():
    return SimpleNamespace(id="f", id_cliente="", nome_cliente="Rossi Maria", numero_rg="123",
                           anno_rg="2025", tribunale="TRIBUNALE DI VELLETRI")


def test_semantic_dates_are_distinct_from_hearing_and_upload():
    facts = estrai_date_modello(SOURCE, fascicolo=matter())
    assert [(f.campo, f.valore) for f in facts] == [
        ("data_deposito_ricorso", "2025-04-05"), ("data_emissione_decreto", "2025-04-12")]
    for f in facts:
        f.fascicolo_id, f.tipo, f.oggetto_id, f.sha256 = "f", "documento", "doc", "hash"
    obj = SimpleNamespace(tipo="documento", oggetto_id="doc", impronta="hash", presente=True)
    dates = date_modello_da_fatti(facts, fascicolo_id="f", oggetti=[obj])
    fields = {f["id"]: f for f in linked_fields_catalog(fascicolo=matter(), date_processuali=dates)}
    assert fields["fascicolo.data_deposito_ricorso"]["value"] == "05/04/2025"
    assert fields["fascicolo.data_emissione_decreto"]["value"] == "12/04/2025"
    assert not fields["fascicolo.data_pronuncia_sentenza"]["available"]
    assert not date_modello_da_fatti(facts, fascicolo_id="altro", oggetti=[obj])
    obj.impronta = "cambiata"
    assert not date_modello_da_fatti(facts, fascicolo_id="f", oggetti=[obj])


@pytest.mark.parametrize("source,origin", [
    (SOURCE.replace("123/2025", "124/2025"), "nativo"),
    (SOURCE.replace("ROSSI MARIA", "VERDI ANNA"), "nativo"),
    (SOURCE.replace("SENTENZA", "NOTE SCRITTE"), "nativo"),
])
def test_unproved_source_is_not_a_model_date(source, origin):
    assert not estrai_date_modello(source, fascicolo=matter(), origine=origin)


def test_optical_dates_remain_candidates_until_independently_verified():
    facts = estrai_date_modello(SOURCE, fascicolo=matter(), origine='ocr')
    assert len(facts) == 2 and all(f.verifica == 'plausibile' for f in facts)
    for f in facts:
        f.fascicolo_id, f.tipo, f.oggetto_id, f.sha256 = 'f', 'documento', 'doc', 'hash'
    assert not date_modello_da_fatti(facts, fascicolo_id='f', oggetti=[
        SimpleNamespace(tipo='documento', oggetto_id='doc', impronta='hash', presente=True)])


def test_conflicting_dates_are_preserved_without_autofill():
    facts = estrai_date_modello(SOURCE, fascicolo=matter())[:1]
    facts += estrai_date_modello(SOURCE.replace("05 aprile", "06 aprile"), fascicolo=matter())[:1]
    for f in facts:
        f.fascicolo_id, f.tipo, f.oggetto_id, f.sha256 = "f", "documento", "doc", "hash"
    dates = date_modello_da_fatti(facts, fascicolo_id="f", oggetti=[
        SimpleNamespace(tipo="documento", oggetto_id="doc", impronta="hash", presente=True)])
    field = dates["fascicolo.data_deposito_ricorso"]
    assert field["conflict"] and field["value"] == ""
    assert len(field["alternatives"]) == 2


def test_actual_telemetric_deposit_clause():
    source = SOURCE.replace('depositato in data 05 aprile 2025', 'depositato telematicamente il 5/4/2025')
    assert estrai_date_modello(source, fascicolo=matter())[0].valore == '2025-04-05'


def test_new_document_reading_includes_model_dates_in_shared_motor():
    from pct.archivio_letture.collaudo import Contesto
    from pct.archivio_letture.motore_documenti import leggi_testo

    facts = leggi_testo(SOURCE, nome='sentenza.pdf', origine='nativo',
                       contesto=Contesto(numero_rg='123', anno_rg='2025',
                                        ufficio_giudiziario='TRIBUNALE DI VELLETRI', cliente='Rossi Maria'),
                       metadata={'fascicolo': matter()})
    assert {(f.campo, f.valore) for f in facts if f.categoria == 'metadato_fascicolo'} >= {
        ('data_deposito_ricorso', '2025-04-05'), ('data_emissione_decreto', '2025-04-12')}


def test_model_date_rules_invalidate_previous_reading_version():
    from pct.archivio_letture.date_campi_modello import VERSIONE_DATE_CAMPI_MODELLI
    from pct.archivio_letture.motore_documenti import VERSIONE_MOTORE_DOCUMENTI, VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI

    suffix = '+date-modello:' + VERSIONE_DATE_CAMPI_MODELLI
    assert VERSIONE_MOTORE_DOCUMENTI.endswith(suffix)
    assert VERSIONE_MOTORE_DOCUMENTI.removesuffix(suffix) not in VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI


ATTESTATION = '''ATTESTAZIONE DI CONFORMITÀ
Il sottoscritto avvocato attesta che le copie informatiche:
- Ricorso per Rossi Maria depositato in data 05/04/2025;
- Decreto fissazione udienza, emesso dal Tribunale di Velletri Sez. Lavoro
in data 12/04/2025,
sono conformi alle copie informatiche presenti nel fascicolo informatico del
relativo procedimento R.G. n. 123/2025 dal quale sono estratte.'''


def test_actual_attestation_dates_keep_joint_identity_and_named_proof():
    facts = estrai_date_modello(ATTESTATION, fascicolo=matter())
    assert [(f.campo, f.valore) for f in facts] == [('data_emissione_decreto', '2025-04-12')]
    assert any(proof['codice'] == 'attestazione_copie_fascicolo_informatico' for proof in facts[0].prove)


@pytest.mark.parametrize('source', [
    ATTESTATION.replace('Rossi Maria', 'Verdi Anna'),
    ATTESTATION.replace('123/2025', '124/2025'),
    ATTESTATION.replace('ATTESTAZIONE DI CONFORMITÀ', 'MODELLO ATTESTAZIONE'),
    ATTESTATION.replace('sono conformi alle copie informatiche presenti nel fascicolo informatico', 'sono documenti di esempio'),
])
def test_unverified_attestation_does_not_autofill(source):
    assert not estrai_date_modello(source, fascicolo=matter())
