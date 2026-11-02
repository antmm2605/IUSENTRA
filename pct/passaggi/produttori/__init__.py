"""Produttori di passaggi: adattatori dalle azioni automatiche del software al modello comune."""

from .note_127_ter import passaggi_da_esame, passaggi_da_scadenza
from .termini_pec import passaggi_termini_pec

__all__ = ["passaggi_da_esame", "passaggi_da_scadenza", "passaggi_termini_pec"]
