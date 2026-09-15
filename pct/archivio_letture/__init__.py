"""Archivio di alimentazione: due motori leggono, i presìdi consultano.

Il motore documenti legge i documenti del fascicolo (testo nativo, OCR,
indice documentale); il motore PEC legge i messaggi del presidio PEC e i loro
allegati. Entrambi producono *fatti* — date con il loro campo (udienza,
termine, notifica, deposito, accettazione, consegna, comunicazione), numeri
di ruolo, prove di notifica, eventi — e ogni fatto passa dal collaudo
automatico prima di entrare nell'archivio (`letture_fatti` del registro delle
letture): calendario, forma del token, ancoraggio al contesto, orizzonte del
fascicolo, doppia lettura, concordanza con agenda, scadenziario, PEC e
portale. Il verdetto è del software: `verificata`, `plausibile`, `respinta`.
I presìdi (documentale, notifiche, economico, lettura del fascicolo) leggono
dall'archivio e non rileggono i documenti; le letture si mantengono solo
quando un documento cambia o arriva una PEC (registro delle letture).

Base normativa: art. 3 D.M. 44/2011 e art. 20 CAD (integrità e impronta dei
documenti informatici); D.M. 44/2011 e specifiche DGSIA per le date in forma
giorno/mese/anno; L. 53/1994 art. 3-bis e art. 147 c.p.c. per le prove di
notifica a mezzo PEC; art. 136 c.p.c. per le comunicazioni di cancelleria.
"""

from __future__ import annotations

from .collaudo import Contesto, collauda
from .motore_documenti import VERSIONE_MOTORE_DOCUMENTI, leggi_testo
from .motore_pec import VERSIONE_MOTORE_PEC, fatti_da_allegato, fatti_da_messaggio
from .presidi import CAMPI_DA_CONFERMARE, da_confermare_ora, prove_notifica_per_oggetto, riassunto_archivio, ruoli_letti, udienze_e_termini

VERSIONE_ARCHIVIO = "2026.09.16.archivio-letture.v1"

__all__ = [
    "VERSIONE_ARCHIVIO",
    "VERSIONE_MOTORE_DOCUMENTI",
    "VERSIONE_MOTORE_PEC",
    "Contesto",
    "collauda",
    "fatti_da_allegato",
    "fatti_da_messaggio",
    "leggi_testo",
    "prove_notifica_per_oggetto",
    "CAMPI_DA_CONFERMARE",
    "da_confermare_ora",
    "riassunto_archivio",
    "ruoli_letti",
    "udienze_e_termini",
]
