"""La catena del fascicolo: dalla fonte (documento, PEC, scadenza, incasso, giorno...) fino al quadro e alle bozze.

- ``mappa``: gli anelli, che cosa legge ciascuno, quale meccanismo lo riaccende e quali eventi lo raggiungono;
- ``guardiano``: i controlli di coerenza per fascicolo, puri, con la regola che ripara o l'avviso;
- ``registro``: il registro dei controlli e delle riparazioni (SQLite fuori dalle fonti dei pannelli).
"""

from .mappa import ANELLI, EVENTI, MECCANISMI, anelli_raggiunti, lacune

__all__ = ["ANELLI", "EVENTI", "MECCANISMI", "anelli_raggiunti", "lacune"]
