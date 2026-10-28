import hashlib

import pytest

from lex.providers.prompt_budget import format_evidence_item


def test_complete_article_reaches_prompt_after_excerpt_limit():
    text = "Inizio della norma. " * 300 + "CLAUSOLA_FINALE_DA_LEGGERE"
    item = {"source_type":"normativa_normattiva", "title":"Fonte di prova", "excerpt":text[:1600], "metadata":{
        "normative_full_text":text,"normative_full_text_sha256":hashlib.sha256(text.encode()).hexdigest()}}
    block, truncated = format_evidence_item(1,item,max_chars=1600)
    assert text in block and block.endswith("CLAUSOLA_FINALE_DA_LEGGERE")
    assert not truncated


def test_modified_source_is_not_sent_to_model():
    item = {"source_type":"normativa_normattiva", "metadata":{"normative_full_text":"Testo alterato","normative_full_text_sha256":"0"*64}}
    with pytest.raises(ValueError,match="Impronta"):
        format_evidence_item(1,item)


def test_private_document_cannot_promote_its_metadata_to_unlimited_public_text():
    text = "METADATO_NON_AUTORIZZATO " * 200
    item = {"source_type":"documento_fascicolo", "excerpt":"Documento privato di prova", "metadata":{
        "normative_full_text":text,"normative_full_text_sha256":hashlib.sha256(text.encode()).hexdigest()}}
    block, _ = format_evidence_item(1,item,max_chars=1600)
    assert "METADATO_NON_AUTORIZZATO" not in block
    assert "Documento privato di prova" in block
