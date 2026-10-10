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


def test_empty_document_reports_missing_text_without_starting_runtime(monkeypatch):
    import pytest

    monkeypatch.setattr(editor_grammar, "_avvia", lambda: (_ for _ in ()).throw(AssertionError()))
    with pytest.raises(ValueError, match="Inserisci del testo"):
        editor_grammar.controlla_documento(" \n ")


def test_context_names_and_legal_abbreviations_keep_real_typos(monkeypatch):
    monkeypatch.setattr(editor_grammar, '_avvia', lambda: None)
    text = '😀 Avv. Montagnese, Dott.ssa Vaccaro, art. 127-ter, PEC: roberto@studio.it; esammina Taliana.'
    words = ['Avv', 'Montagnese', 'ssa', 'Vaccaro', 'ter', 'roberto', 'esammina', 'Taliana']
    def check(path, data):
        return {'matches': [{'offset': len(text[:text.index(word)].encode('utf-16-le')) // 2,
            'length': len(word), 'message': 'Refuso', 'replacements': [],
            'rule': {'id': 'MORFOLOGIK_RULE_IT_IT'}} for word in words]}
    monkeypatch.setattr(editor_grammar, '_richiesta', check)
    findings = editor_grammar.controlla_documento(text, termini_contesto=['Montagnese', 'Vaccaro'])
    assert len(findings) == 2
    assert [text.encode('utf-16-le')[v['offset']*2:(v['offset']+v['length'])*2].decode('utf-16-le')
            for v in findings] == ['esammina', 'Taliana']


def test_typographic_continuation_does_not_hide_real_sentence_error(monkeypatch):
    monkeypatch.setattr(editor_grammar, '_avvia', lambda: None)
    text = 'contenenti le sole\n\nistanze. errore.'
    def check(path, data):
        return {'matches': [{'offset': text.index(word), 'length': len(word), 'message': 'Maiuscola',
            'replacements': [], 'rule': {'id': 'UPPERCASE_SENTENCE_START'}} for word in ['istanze', 'errore']]}
    monkeypatch.setattr(editor_grammar, '_richiesta', check)
    findings = editor_grammar.controlla_documento(text)
    assert len(findings) == 1
    assert findings[0]['offset'] == text.index('errore')


def test_euphonic_d_is_not_reported_as_a_typo(monkeypatch):
    monkeypatch.setattr(editor_grammar, '_avvia', lambda: None)
    monkeypatch.setattr(editor_grammar, '_richiesta', lambda *args: {'matches': [
        {'offset': 0, 'length': 12, 'message': 'Stile', 'replacements': [], 'rule': {'id': 'ST_03_001'}}]})
    assert editor_grammar.controlla_documento('ad usufruire') == []


def test_phone_label_is_technical_only_when_followed_by_phone(monkeypatch):
    monkeypatch.setattr(editor_grammar, '_avvia', lambda: None)
    text = 'Tel +393384626697; Tel esammina.'
    offsets = [text.index('Tel'), text.rindex('Tel'), text.index('esammina')]
    monkeypatch.setattr(editor_grammar, '_richiesta', lambda *args: {'matches': [
        {'offset': offset, 'length': 3 if offset in offsets[:2] else 8,
         'message': 'Refuso', 'replacements': [], 'rule': {'id': 'MORFOLOGIK_RULE_IT_IT'}}
        for offset in offsets]})
    assert [finding['offset'] for finding in editor_grammar.controlla_documento(text)] == offsets[1:]
