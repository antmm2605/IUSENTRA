"""Inventario della fonte: contenuti, note, codifica e collegamenti."""

from lex.sources.html_structure import read_html_structure


def read(html):
    return read_html_structure(html.encode(), "text/html; charset=utf-8", url="https://example.org/atti/pagina")


def test_multiple_articles_and_hidden_notes_are_preserved_without_navigation():
    result = read('<nav>Menu estraneo</nav><article><h1>Atto primo</h1><p>Testo primo.</p>'
                  '<aside hidden>Nota pertinente.</aside></article>'
                  '<article><h2>Atto secondo</h2><p>Testo secondo.</p></article>')
    assert "Testo primo." in result["text"]
    assert "Testo secondo." in result["text"]
    assert "Nota pertinente." in result["text"]
    assert "Menu estraneo" not in result["text"]
    assert "Menu estraneo" in result["full_text"]


def test_nested_list_does_not_duplicate_child_in_parent_block():
    result = read('<main><ul><li>Presupposto<ul><li>Eccezione specifica</li></ul></li></ul></main>')
    assert [b["text"] for b in result["blocks"]] == ["Presupposto", "Eccezione specifica"]
    assert result["markdown"].count("Eccezione specifica") == 1


def test_table_preserves_cells_and_section_without_duplicate_cell_blocks():
    result = read('<main><h1>Termini</h1><table><tr><th>Rito</th><th>Termine</th></tr>'
                  '<tr><td><p>Civile</p></td><td>Sei mesi</td></tr></table></main>')
    assert result["tables"][0]["rows"] == [["Rito", "Termine"], ["Civile", "Sei mesi"]]
    assert result["tables"][0]["section"] == ["Termini"]
    assert [b["kind"] for b in result["blocks"]] == ["heading", "table"]


def test_links_are_resolved_without_credentials_or_script_actions():
    result = read('<main><p><a href="../norma#articolo">Norma</a>'
                  '<a href="https://user:secret@example.org/private">Riservato</a>'
                  '<a href="javascript:alert(1)">Azione</a></p></main>')
    assert result["links"] == [{"url": "https://example.org/norma#articolo", "label": "Norma"}]


def test_long_page_inventory_keeps_last_paragraph_and_heading_levels():
    result = read('<main><h1>Norma</h1><h3>Eccezioni</h3>' +
                  ''.join(f'<p>Passaggio {i}.</p>' for i in range(250)) + '</main>')
    assert result["block_count"] == 252
    assert result["blocks"][-1]["text"] == "Passaggio 249."
    assert "### Eccezioni" in result["markdown"]


def test_declared_charset_and_script_exclusion_match_full_and_main_text():
    result = read_html_structure('<main><p>La nullità è dichiarata.</p><script>falso</script></main>'.encode('cp1252'),
                                 'text/html; charset=windows-1252', url='https://example.org/')
    assert result["text"] == result["full_text"] == "La nullità è dichiarata."


def test_div_based_article_and_notes_are_blocks_without_navigation_duplicates():
    result = read('<div id="g_navbar"><a href="/uno">Menu primo</a><a href="/due">Menu secondo</a></div>'
                  '<h1>Norma</h1><h2>Dispositivo</h2><div class="text">'
                  '<div class="corpoDelTesto">La disposizione <a href="/rinvio">richiamata</a> si applica.</div>'
                  '<h3>Note</h3><div class="nota">Eccezione pertinente.</div></div>')
    texts = [b['text'] for b in result['blocks']]
    assert 'La disposizione richiamata si applica.' in texts
    assert 'Eccezione pertinente.' in texts
    assert 'Menu primo' not in result['text']
    assert 'Menu primo' in result['full_text']
