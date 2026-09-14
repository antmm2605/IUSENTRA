"""Errori del motore di lettura, con un messaggio gia' pronto per l'avvocato."""

from __future__ import annotations


class ErroreLettura(RuntimeError):
    """La pagina non si puo' leggere: il messaggio dice perche', in italiano."""


class MotoreNonDisponibile(ErroreLettura):
    """Tesseract o il dizionario italiano non sono installati su questa macchina."""


__all__ = ["ErroreLettura", "MotoreNonDisponibile"]
