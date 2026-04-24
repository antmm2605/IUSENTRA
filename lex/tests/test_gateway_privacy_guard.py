from lex.gateway.privacy_guard import PrivacyGuard


def test_public_text_is_public():
    guard = PrivacyGuard()
    result = guard.classify_text("Spiegami in generale cosa è un decreto ingiuntivo.")
    assert result.sensitivity in {"public", "sensitive"}


def test_codice_fiscale_is_highly_sensitive():
    guard = PrivacyGuard()
    result = guard.classify_text("Cliente RSSMRA80A01H501U chiede verifica pratica.")
    assert result.sensitivity == "highly_sensitive"
    assert "codice_fiscale" in result.reasons
    assert "[CODICE_FISCALE_OSCURATO]" in result.redacted_text


def test_rg_is_highly_sensitive():
    guard = PrivacyGuard()
    result = guard.classify_text("Fascicolo RG 1234/2024 davanti al Tribunale.")
    assert result.sensitivity == "highly_sensitive"
    assert "numero_rg" in result.reasons
