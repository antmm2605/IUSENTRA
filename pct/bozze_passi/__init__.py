"""Bozze pronte per i passi del fascicolo che richiedono un atto (preparate in sfondo, mai inviate da sole).

Il pacchetto si importa leggero (solo il modello): il catalogo e i testi si importano da ``pct.bozze_passi.catalogo``.
"""

from .modello import (
           AVVISO_BOZZA,
           FONTE_BOZZA_PASSO,
           FONTI_BOZZE_DEL_SOFTWARE,
           Bozza,
           da_completare,
           e_bozza_del_software,
           manca,
)

__all__ = ["AVVISO_BOZZA", "FONTE_BOZZA_PASSO", "FONTI_BOZZE_DEL_SOFTWARE", "Bozza", "da_completare",
           "e_bozza_del_software", "manca"]
