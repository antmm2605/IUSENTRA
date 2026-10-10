from pct import editor_grammar


def test_invalid_document_does_not_start_runtime(monkeypatch):
    monkeypatch.setattr(editor_grammar, "_avvia", lambda: (_ for _ in ()).throw(AssertionError()))
    import pytest
    with pytest.raises(ValueError):
        editor_grammar.controlla_documento("x" * 200001)


def test_chunks_cover_all_text_and_preserve_utf16_offsets(monkeypatch):
    monkeypatch.setattr(editor_grammar, "_avvia", lambda: None)
    sent = []
    def check(path, data):
        sent.append(data["text"])
        return {"matches": [{"offset": 0, "length": 1, "message": "Prova", "replacements": [{"value": "à"}], "rule": {"id": "TEST"}}]}
    monkeypatch.setattr(editor_grammar, "_richiesta", check)
    text = "😀" + "a" * 10000 + "\n\n" + "b" * 16000
    findings = editor_grammar.controlla_documento(text)
    assert "".join(sent) == text
    assert findings[1]["offset"] == len(sent[0].encode("utf-16-le")) // 2
    assert findings[0]["suggerimenti"] == ["à"]
