"""Sequenza notturna dei lavori pesanti: uno alla volta, dalle 21:30 alle 07:30 (Europe/Rome).

Verifica del 03/11/2026: con le corsie (``pct/scheduler_corsie.py``) un solo lavoro lungo girava alla volta nel
processo delle pianificazioni, ma i lavori notturni erano fissati a orari sparsi (23:00, 23:15, 00:17, 00:40,
01:20, 01:45, 02:40, 02:55, 03:25, ogni 15 minuti dall'1 alle 4...) e quelli frequenti (letture dell'archivio
ogni 10 minuti, presidio economico ogni 15, seconda lettura del catalogo con l'AI locale ogni 2) si
intercalavano a quelli notturni, mentre il worker OCR e Ollama lavoravano negli stessi minuti. Ogni lavoro
pesante lasciava il processo più grande (Python non restituisce la memoria al sistema) e l'AI locale restava
caricata: il kernel ha chiuso prima Ollama e poi lo scheduler per memoria esaurita.

Ora i lavori pesanti stanno in una catena ordinata per dipendenza (``sequenza.py``): il successivo parte quando il
precedente è finito, l'avanzamento è scritto su SQLite (``registro.py``) e riprende la notte dopo se non è
finito entro le 07:30. Base: art. 3 D.M. 44/2011 e art. 20 CAD per l'integrità delle letture, che non devono
essere interrotte da chiusure per memoria esaurita.
"""

from pct.scheduler_notturno.catena import esegui_passo
from pct.scheduler_notturno.integrazione import installa_sequenza_notturna
from pct.scheduler_notturno.sequenza import FASI, lavori_della_sequenza

__all__ = ["FASI", "esegui_passo", "installa_sequenza_notturna", "lavori_della_sequenza"]
