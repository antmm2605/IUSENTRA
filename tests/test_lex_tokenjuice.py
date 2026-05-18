from lex.tokenjuice import compress_lex_context


def test_tokenjuice_ripulisce_html_e_conserva_norme_e_rg():
    html = """
    <html>
      <head><style>.x{display:none}</style><script>alert(1)</script></head>
      <body>
        <nav>menu decorativo</nav>
        <article>
          <h1>Questione penale pendente</h1>
          <p>Il punto riguarda l'art. 599-bis c.p.p. e il ricorso R.G. 9926/2026.</p>
          <p>Si richiama anche art. 606 c.p.p. per i motivi di ricorso.</p>
        </article>
      </body>
    </html>
    """

    result = compress_lex_context(html, source_type="text/html", max_chars=360)

    assert result.schema == "iusentra.lex_tokenjuice.v1"
    assert result.rule_id.startswith("html:")
    assert "alert" not in result.text
    assert "art. 599-bis c.p.p" in result.text
    assert "R.G. 9926/2026" in result.anchors
    assert result.metadata["llm_used"] is False


def test_tokenjuice_compatta_testo_ocr_lungo_senza_perdere_ancoraggi_legali():
    noisy = ("CORTE SUPREMA | d testo OCR sporco senza valore " * 120) + (
        " Questione: concordato in appello ex art. 599-bis c.p.p.; "
        "ricorso per cassazione ex art. 606 c.p.p.; R.G. 9966/2026; udienza 09 luglio 2026. "
        "Motivi: determinazione della pena e controllo sull'accordo."
    )

    result = compress_lex_context(noisy, source_type="application/pdf; ocr", max_chars=520)

    assert result.rule_id.startswith("legal_ocr:")
    assert result.compressed_chars <= 520
    assert result.compressed_chars < result.original_chars
    assert any("599" in anchor for anchor in result.anchors)
    assert "R.G. 9966/2026" in result.anchors
    assert "R.G. 9966/2026" in result.text
    assert "testo OCR potenzialmente sporco" in " ".join(result.warnings)


def test_tokenjuice_compatta_json_in_forma_deterministica():
    result = compress_lex_context(
        '{"b": "R.G. 9926/2026", "a": {"norma": "art. 606 c.p.p."}}',
        source_type="application/json",
        max_chars=300,
    )

    assert result.rule_id.startswith("json:")
    assert result.text.startswith('{"a":')
    assert "R.G. 9926/2026" in result.anchors
