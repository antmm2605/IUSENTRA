"""Che cosa comporta una notifica che nasce da una comunicazione ricevuta: atti, destinatari, modalità, dopo.

Il motore dei provvedimenti (``pct/provvedimenti``) propone il termine di notifica con il suo codice; questo
pacchetto dice all'avvocato, sempre con la norma, che cosa notificare, a chi, presso quale indirizzo e che cosa
depositare dopo. Non indovina: se la controparte non è nota lo dice e rimanda alla scelta dell'avvocato.
"""

from .catalogo import OBBLIGHI, Obbligo, obbligo_per_codice
from .destinatari import come_notificare
from .scheda import scheda_notifica

__all__ = ["OBBLIGHI", "Obbligo", "come_notificare", "obbligo_per_codice", "scheda_notifica"]
