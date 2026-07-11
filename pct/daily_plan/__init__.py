"""Bounded context "Piano del giorno" (Lex Oggi).

Aggrega in modo deterministico e tenant-aware i segnali operativi dello
studio (PEC, presidi fascicolo, agenda, scadenziario, economico) e produce
per ogni giornata e per ogni avvocato un piano ordinato di attività con
motivo, fonte, fascicolo, scadenza e azioni approvabili.

Base normativa: il piano non calcola termini processuali autonomamente;
riusa esclusivamente scadenze, eventi e presidi già governati dai moduli
di dominio (D.M. 44/2011 per il telematico, c.p.c. per i termini gestiti
da ``pct.scadenziario`` e ``pct.termini_processuali``).
"""

from __future__ import annotations

DAILY_PLAN_SCHEMA = "iusentra.daily_plan.v1"

__all__ = ["DAILY_PLAN_SCHEMA"]
