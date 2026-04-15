"""Facciata compatibile per il prompt builder di Lex.

Il modulo reale vive in ``lex.prompts.prompt_builder``.
"""

from lex.prompts.prompt_builder import build_assistente_prompt, latest_user_message

__all__ = ["build_assistente_prompt", "latest_user_message"]
