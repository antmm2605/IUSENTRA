from __future__ import annotations

import json

from lex.learning.models import (
    LearningSignal,
    LegalCitation,
    LegalLanguageProfile,
    LegalSourceSample,
    LegalTermObservation,
    SourceReadingResult,
    stable_id_from,
)


def test_stable_id_deterministico_e_indipendente_dall_ordine_chiavi():
    a = stable_id_from({"x": 1, "y": "due"})
    b = stable_id_from({"y": "due", "x": 1})
    assert a == b
    assert len(a) == 16
    assert a != stable_id_from({"x": 2, "y": "due"})


def test_round_trip_di_tutti_i_modelli():
    citation = LegalCitation(
        raw_text="art. 6 GDPR",
        normalized_text="art. 6 Regolamento (UE) 2016/679",
        reference_type="article",
        confidence=0.9,
        start=2,
        end=13,
        snippet="...",
    )
    term = LegalTermObservation(normalized="legittimo interesse", label="legittimo interesse", kind="concetto", area="privacy", occurrences=2, confidence=0.8)
    sample = LegalSourceSample(sample_id="s1", title="Titolo", text="testo", area="civile")
    reading = SourceReadingResult(url="https://www.normattiva.it/x", status="ok", citations_normalized=["art. 2043 c.c."])
    signal = LearningSignal(name="nuovi_citations", value=3, cycle_index=0)
    profile = LegalLanguageProfile(
        sample_id="s1",
        area="privacy",
        characters=100,
        tokens=20,
        sentence_count=2,
        average_sentence_length=10.0,
        legal_density=0.1,
        complexity_index=0.3,
        citations=[citation],
        terms=[term],
    )
    for model in (citation, term, sample, reading, signal, profile):
        payload = json.loads(json.dumps(model.to_dict()))
        rebuilt = type(model).from_dict(payload)
        assert rebuilt.to_dict() == model.to_dict()
        assert model.stable_id() == model.stable_id()


def test_stable_id_citazione_dipende_solo_da_tipo_e_testo_normalizzato():
    a = LegalCitation(raw_text="art. 6 GDPR", normalized_text="art. 6 Regolamento (UE) 2016/679", reference_type="article", start=0, end=10)
    b = LegalCitation(raw_text="ART. 6 gdpr", normalized_text="ART. 6 REGOLAMENTO (UE) 2016/679", reference_type="article", start=99, end=120)
    assert a.stable_id() == b.stable_id()
