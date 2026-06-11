"""KPI direzionali dello studio (cabina di controllo gestione)."""

from .engine import ROME_TZ, compute_kpis

__all__ = ["compute_kpis", "ROME_TZ"]
