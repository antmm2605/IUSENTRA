"""Preservazione del testo delle fonti pubbliche nei percorsi condivisi."""

from lex.sources.extractors import extract_html, extract_text, extract_text_from_bytes


def test_html_respects_declared_windows1252_without_losing_italian_letters():
    text = "La nullità è distinta dall’impugnazione: perché il termine è diverso."
    source = f"<html><body><p>{text}</p></body></html>".encode("cp1252")

    assert extract_text_from_bytes(source, "text/html; charset=Windows-1252") == text


def test_html_meta_charset_is_used_when_http_does_not_declare_one():
    text = "L’avvocato può verificare la nullità."
    source = (
        '<html><head><meta charset="windows-1252"></head>'
        f"<body><p>{text}</p></body></html>"
    ).encode("cp1252")

    assert extract_text_from_bytes(source, "text/html") == text


def test_html_file_and_memory_use_the_same_charset_path(tmp_path):
    text = "La responsabilità è già accertata."
    source = f"<html><body>{text}</body></html>".encode("cp1252")
    path = tmp_path / "fonte.html"
    path.write_bytes(source)

    assert extract_text(path, "text/html; charset=windows-1252") == text


def test_utf8_html_and_entities_preserve_text_and_exclude_scripts():
    source = '<p>È un atto &amp; una fonte.</p><script>testo estraneo</script>'

    assert extract_text_from_bytes(source.encode(), "text/html; charset=UTF-8") == "È un atto & una fonte."
    assert extract_html(source) == "È un atto & una fonte."


def test_unknown_declared_charset_does_not_discard_valid_utf8():
    source = "<p>La capacità è verificabile.</p>".encode()

    assert extract_text_from_bytes(source, "text/html; charset=codifica-inesistente") == "La capacità è verificabile."
