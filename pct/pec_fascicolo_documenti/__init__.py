"""PEC → documenti del fascicolo: il contenuto utile di ogni PEC collegata con certezza entra nel fascicolo.

Richiesta dell'avvocato del 02/11/2026: quando una PEC è collegata al fascicolo, i provvedimenti e gli atti
allegati (decreto, sentenza, ordinanza, verbale…) e, per le notifiche in proprio, l'.eml della notifica e delle
sue ricevute devono stare tra i documenti del fascicolo senza che nessuno li carichi a mano.

Regole (una per modulo):

* ``classificazione``: che genere di PEC è (comunicazione, notifica, ricevuta di notifica, ricevuta di deposito)
  e quali allegati servono; ciò che non serve resta fuori con il motivo (``daticert.xml``, involucro
  ``postacert.eml``, firme ``.p7s``, XML tecnici, doppioni). Nulla si cancella.
* ``registro``: il registro SQL del flusso nel database del presidio PEC (stessa base dei collegamenti):
  esito per allegato con impronta SHA-256, stato per messaggio, giri con i conteggi.
* ``flusso``: un messaggio alla volta, solo se il collegamento è certo (stato certificato o conferma
  dell'avvocato); salvataggio idempotente per Message-ID e impronta, provenienza nel documento e nell'audit
  del presidio, eventi del registro delle letture.
* ``recupero``: le PEC già collegate, a lotti limitati e riprendibili, e lo stato verificabile del flusso.

Base normativa: art. 136 c.p.c. e art. 16, comma 4, D.L. 179/2012 (comunicazioni di cancelleria);
L. 53/1994 art. 3-bis e art. 19-bis Provv. DGSIA 16/04/2014 (notifica in proprio e ricevuta completa di
avvenuta consegna in formato .eml come prova); art. 20 CAD e art. 3 D.M. 44/2011 (impronta e integrità
dei documenti informatici). L'allegato della PEC di cancelleria è copia informativa: la copia da notificare
resta quella scaricata dall'avvocato dal Portale dei Servizi Telematici (nessun download autonomo).
"""

from __future__ import annotations

from pct.pec_fascicolo_documenti.flusso import STATI_COLLEGAMENTO_CERTI, conferma_collegamento, processa_messaggio
from pct.pec_fascicolo_documenti.recupero import recupera_storico, stato_flusso

__all__ = [
    "STATI_COLLEGAMENTO_CERTI",
    "conferma_collegamento",
    "processa_messaggio",
    "recupera_storico",
    "stato_flusso",
]
