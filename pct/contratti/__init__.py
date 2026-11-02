"""Catalogo della contrattualistica dello studio.

Base normativa: art. 1322 c.c. (autonomia contrattuale, contratti atipici) e
artt. 1321-1469 c.c. (disciplina generale); per ogni famiglia le norme speciali
dichiarate nei file di ``pct/contratti/dati/``. Ricognizione riferita al
2 novembre 2026: ogni riferimento resta da verificare sulla fonte ufficiale
prima dell'uso in un testo (``stato_verifica``).

Il catalogo distingue la redazione e negoziazione del testo (attività dello
studio) dalla stipulazione nelle forme di legge (notaio, pubblico ufficiale,
autorizzazioni, trascrizione, registrazione), che il sistema segnala senza
sostituirla.
"""

from pct.contratti.catalogo import carica_catalogo, famiglia, regole_comuni
from pct.contratti.selezione import valuta

__all__ = ["carica_catalogo", "famiglia", "regole_comuni", "valuta"]
