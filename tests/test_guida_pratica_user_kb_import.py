from scripts.import_guida_pratica_user_kb_modules import _convert_item


def test_import_user_kb_converte_143105_subfornitura_senza_sovrascrivere_noleggio():
    row, conversion, official = _convert_item(
        {
            "codice": "143105",
            "denominazione": "Contratto di subfornitura: abuso di dipendenza economica",
        }
    )

    assert official is None
    assert conversion is not None
    assert row["codice"] == "GUIDA_CONTRATTO_SUBFORNITURA_ABUSO_DIPENDENZA_ECONOMICA_143105"
    assert row["codice_originale_ricevuto"] == "143105"
    assert row["guida_interna_non_depositabile"] is True
    assert row["depositabile"] is False
    assert "noleggio" in row["nota_integrazione_iusentra"].lower()
