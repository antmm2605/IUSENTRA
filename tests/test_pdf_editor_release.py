import pytest

from tools.build_pdf_editor_release import build


@pytest.fixture
def root(tmp_path):
    source = tmp_path / 'web/static/vendor/pdfcraft-direct/editor'
    source.mkdir(parents=True)
    (source / 'index.html').write_bytes(b'<html>Editor\r\nPDF</html>')
    (source / 'editcore.wasm').write_bytes(b'\0asm\r\n\xff')
    return tmp_path


def test_changed_source_uses_new_address_and_preserves_previous_release(root):
    first = build(root)
    assert build(root, check=True) == first
    previous = root / 'web' / first.lstrip('/') / 'index.html'
    (root / 'web/static/vendor/pdfcraft-direct/editor/index.html').write_text('Seconda versione')
    with pytest.raises(ValueError):
        build(root, check=True)
    second = build(root)
    assert first != second
    assert previous.read_bytes() == b'<html>Editor\nPDF</html>'
    assert (root / 'web' / second.lstrip('/') / 'editcore.wasm').read_bytes() == b'\0asm\r\n\xff'


def test_tampered_release_is_rejected_without_overwriting_it(root):
    base = build(root)
    target = root / 'web' / base.lstrip('/') / 'index.html'
    target.write_text('Contenuto discordante')
    for check in (True, False):
        with pytest.raises(ValueError):
            build(root, check=check)
    assert target.read_text() == 'Contenuto discordante'


def test_extra_file_in_immutable_release_is_rejected(root):
    base = build(root)
    (root / 'web' / base.lstrip('/') / 'extra.js').write_text('extra')
    with pytest.raises(ValueError):
        build(root, check=True)


def test_published_bytes_must_match_even_when_only_line_endings_change(root):
    base = build(root)
    (root / 'web' / base.lstrip('/') / 'index.html').write_bytes(b'<html>Editor\r\nPDF</html>')
    with pytest.raises(ValueError):
        build(root, check=True)
