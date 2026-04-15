"""Facciata compatibile per il riepilogo operativo giornaliero di Lex.

Il modulo reale vive in ``lex.context.today_summary``.
"""

from lex.context.today_summary import build_today_operational_summary

__all__ = ["build_today_operational_summary"]
