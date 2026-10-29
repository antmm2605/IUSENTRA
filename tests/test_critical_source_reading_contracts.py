"""Fonti integre e ricevute: il modello di prova non usa rete né inferenza."""
import hashlib
import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from lex.procedura_atti.lettura_fonti import _estrai, prepara_letture
from lex.providers import lettura_normativa_rag as rag
from lex.settings import LexGenerationSettings

TEXT = "La condizione documentata resta invariata fino alla conclusione del procedimento."


def model(system, prompt):
    text = prompt.split("Testo normativo da leggere:\n", 1)[1].split("\nRestituisci JSON valido", 1)[0]
    return json.dumps({"passaggi": [text[:50]], "fine": " ".join(text.split()[-8:])}), "controlled"


@pytest.mark.parametrize("payload", [[], {"passaggi": [], "fine": ""}, {"passaggi": "invalid", "fine": TEXT}, {"passaggi": ["testo inventato"], "fine": TEXT}, {"passaggi": [1], "fine": TEXT}])
def test_invalid_or_invented_passages_are_rejected(payload):
    with pytest.raises(ValueError):
        _estrai(json.dumps(payload), TEXT)


def test_literal_fallback_deduplication_and_size_limits():
    assert _estrai(json.dumps({"passaggi": [], "fine": TEXT}), TEXT) == [TEXT]
    assert _estrai(json.dumps({"passaggi": [TEXT, TEXT], "fine": TEXT}), TEXT) == [TEXT]
    with pytest.raises(ValueError):
        _estrai(json.dumps({"passaggi": [], "fine": TEXT}), TEXT, massimo=10)
    with pytest.raises(ValueError):
        _estrai(json.dumps({"passaggi": [TEXT], "fine": TEXT}), TEXT, massimo=10)


@pytest.mark.parametrize("budget", [False, 999, "6000"])
def test_invalid_reading_budget_never_calls_model(budget):
    with pytest.raises(ValueError, match="Budget"):
        prepara_letture(SimpleNamespace(fonti={1: TEXT}), richiesta="caso", chiama_modello=lambda *a: pytest.fail("no inference"), messaggio_caratteri=100, budget_caratteri=budget)


def test_tokenizer_verifies_whole_prompt_and_original_is_not_changed(monkeypatch):
    monkeypatch.delenv("LEX_STESURA_CONTESTO_CARATTERI", raising=False)
    def call(*args):
        pytest.fail("La fonte integra entra già nel prompt")
    measured = []
    def measure(system, message):
        measured.append((system, message))
        return {"tokens_input": 20, "contesto": 8192}
    call.misura_prompt = measure
    original = SimpleNamespace(fonti={1: TEXT})
    view, receipts = prepara_letture(original, richiesta="caso", chiama_modello=call, messaggio_caratteri=100, messaggio="messaggio", sistema="sistema")
    assert view is original and measured == [("sistema", "messaggio")]
    assert receipts[0]["sha256_testo"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert receipts[0]["modalita"] == "integrale_nel_messaggio"


def test_malformed_answer_is_retried_once_and_never_invents_a_quote():
    calls = []
    def retry(system, prompt):
        calls.append(prompt)
        return ("{}", "controlled") if len(calls) == 1 else model(system, prompt)
    original = SimpleNamespace(fonti={1: TEXT})
    view, receipts = prepara_letture(original, richiesta="caso", chiama_modello=retry, messaggio_caratteri=len(TEXT), budget_caratteri=6000, forza_parti=True)
    assert len(calls) == 2 and TEXT[:50] in view.fonti[1]
    assert original.fonti[1] == TEXT and receipts[0]["parti"][0]["modello"] == "controlled"


def test_case_overhead_is_not_silently_truncated():
    with pytest.raises(ValueError, match="nessun testo"):
        prepara_letture(SimpleNamespace(fonti={1: TEXT}), richiesta="caso", chiama_modello=model, messaggio_caratteri=10000, budget_caratteri=1000, forza_parti=True)


@dataclass
class Norm:
    source_type: str
    normative_full_text: str
    normative_full_text_sha256: str


@pytest.mark.parametrize("as_dataclass", [False, True])
def test_normative_read_view_preserves_source_and_covers_original_parts(as_dataclass):
    text = (TEXT + " ") * 180
    item = Norm("normativa_normattiva", text, hashlib.sha256(text.encode()).hexdigest())
    if not as_dataclass:
        item = dict(vars(item))
    plan = SimpleNamespace(metadata={"evidenze_escluse_budget": [1]})
    result, receipts = rag.completa_lettura_normativa(piano=plan, system_prompt="Istruzioni", question="Leggi le condizioni", evidence={"items": [item]}, workflow="legal_rag", context=None, settings=LexGenerationSettings(), chiama_modello=model)
    assert result is not plan and result.metadata.get("evidenze_escluse_budget") in ([], None)
    assert receipts[0]["sha256_testo"] == hashlib.sha256(text.encode()).hexdigest()
    assert receipts[0]["parti"][-1]["fine"] == len(text)
    assert (item["normative_full_text"] if isinstance(item, dict) else item.normative_full_text) == text


def test_already_fitting_plan_does_not_read_again():
    plan = SimpleNamespace(metadata={})
    result, receipts = rag.completa_lettura_normativa(piano=plan, system_prompt="", question="", evidence={"items": []}, workflow="legal_rag", context=None, settings=LexGenerationSettings(), chiama_modello=lambda *a: pytest.fail("no reread"))
    assert result is plan and receipts == []


def test_final_context_failure_is_not_attested_as_complete(monkeypatch):
    item = {"source_type": "normativa_normattiva", "normative_full_text": TEXT, "normative_full_text_sha256": hashlib.sha256(TEXT.encode()).hexdigest()}
    monkeypatch.setattr(rag, "build_rag_prompt", lambda **kwargs: SimpleNamespace(metadata={"evidenze_escluse_budget": [1]}))
    with pytest.raises(ValueError, match="nessuna risposta parziale"):
        rag.completa_lettura_normativa(piano=SimpleNamespace(metadata={"evidenze_escluse_budget": [1]}), system_prompt="", question="caso", evidence={"items": [item]}, workflow="legal_rag", context=None, settings=LexGenerationSettings(), chiama_modello=model)


def test_component_reader_uses_bound_content_and_rejects_changed_source(tmp_path):
    import sqlite3
    from lex.retrieval.normativa_catalog import leggi_testo_articolo, NormativaIndexUnavailable
    path = tmp_path / "controlled.sqlite"
    digest = hashlib.sha256(TEXT.encode()).hexdigest()
    with sqlite3.connect(path) as conn:
        conn.executescript("CREATE TABLE normative_documents(id INTEGER,xml_sha256 TEXT,text_content TEXT); CREATE TABLE normative_articles(id INTEGER,article_text TEXT); CREATE TABLE normative_chunks(id INTEGER,document_id INTEGER,article_id INTEGER,metadata_json TEXT); CREATE TABLE normative_components(id INTEGER,document_id INTEGER,testo TEXT,sha256_testo TEXT,localizzatore_xml TEXT);")
        conn.execute("INSERT INTO normative_documents VALUES (1,?,?)", (digest, "Atto completo distinto"))
        conn.execute("INSERT INTO normative_chunks VALUES (10,1,NULL,?)", (json.dumps({"component_id": 7}),))
        conn.execute("INSERT INTO normative_components VALUES (7,1,?,?,?)", (TEXT, digest, "/annesso/1"))
    row = {"chunk_rowid": 10, "document_id": 1, "hash_sha256": digest, "articolo_o_chunk": "non deve diventare articolo"}
    before = path.read_bytes()
    result = leggi_testo_articolo(row, path)
    assert result["testo"] == TEXT and result["normative_scope"] == "allegato_non_articolato"
    assert result["articolo_o_chunk"] == "" and result["normative_component_locator"] == "/annesso/1"
    assert path.read_bytes() == before
    with pytest.raises(NormativaIndexUnavailable, match="fonte e cambiata"):
        leggi_testo_articolo(dict(row, document_id=2), path)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE normative_components SET testo='alterato'")
    with pytest.raises(NormativaIndexUnavailable, match="alterato"):
        leggi_testo_articolo(row, path)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE normative_components SET testo='',sha256_testo=?", (hashlib.sha256(b'').hexdigest(),))
    with pytest.raises(NormativaIndexUnavailable, match="senza testo"):
        leggi_testo_articolo(row, path)
    assert leggi_testo_articolo({"document_id": 1}, path) == {"document_id": 1}


def test_prompt_context_filters_credentials_and_preserves_useful_structure():
    from lex.providers.prompt_budget import compact_studio_context, evidence_items, scrub_personal_data
    context = {"facts": [{"token": "PRIVATE_SYNTHETIC", "count": 2, "items": ["preserved", None]}], "deep": {"a": {"b": {"c": {"token": "OTHER_PRIVATE_SYNTHETIC"}}}}}
    result = compact_studio_context(context, max_chars=3000)
    assert "PRIVATE_SYNTHETIC" not in result and "token" not in result
    assert "preserved" in result and '"count":2' in result
    assert compact_studio_context("  testo controllato  ", max_chars=100) == "testo controllato"
    assert compact_studio_context(context, max_chars=0) == ""
    assert compact_studio_context(42, max_chars=100) == ""
    assert compact_studio_context({"structured_context": "invalid"}, max_chars=100)
    assert "narrazione" in compact_studio_context({"lettura_fascicolo": {"narrativa": "narrazione"}}, max_chars=100)
    assert scrub_personal_data("") == ""
    assert evidence_items(SimpleNamespace(items=[{"id": "bound"}])) == [{"id": "bound"}]
    assert evidence_items(SimpleNamespace(items=lambda: [])) == []
