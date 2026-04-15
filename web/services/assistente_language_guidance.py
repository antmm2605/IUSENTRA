"""Facciata compatibile per la regia linguistica di Lex.

Il modulo reale vive in ``lex.prompts.language_guidance``.
"""

from lex.prompts.language_guidance import LanguageGuidance, build_language_guidance

__all__ = ["LanguageGuidance", "build_language_guidance"]
