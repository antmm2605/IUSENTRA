"""Il motore unico del ragionamento processuale di IUSENTRA.

Un solo modello della causa (`modello.Causa`), costruito in modo deterministico dalle fonti certe del
fascicolo (`ingressi.FontiCausa`): atti con natura e autore, rito dal codice oggetto ministeriale, udienze
con modalità, termini con parte onerata e perentorietà, notificazioni legate all'atto notificato, fase,
controlli di coerenza e dubbi dichiarati. Ogni conclusione dice che cosa si è letto, la norma (con URL
Normattiva), che cosa fare, come, perché, se è già fatto e se siamo nei termini. Lettura, prossimi passi,
obblighi di notifica, scadenze, quadro, regia ed economia ne sono viste.
"""

from .ingressi import FontiCausa
from .modello import Causa, Conclusione, Dubbio
from .motore import VERSIONE, ragiona

__all__ = ["VERSIONE", "Causa", "Conclusione", "Dubbio", "FontiCausa", "ragiona"]
