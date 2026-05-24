"""Regex legali versionate per OCR e fascicoli."""

from .rules import LEGAL_REGEX_PACK_VERSION, validate_codice_fiscale_persona_fisica, validate_regex_pack

__all__ = ["LEGAL_REGEX_PACK_VERSION", "validate_codice_fiscale_persona_fisica", "validate_regex_pack"]
