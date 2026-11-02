"""I provvedimenti del giudice letti per l'avvocato: che cosa ordinano e che cosa ne segue.

Decreti, ordinanze, verbali con provvedimenti e sentenze, arrivati con la PEC di
cancelleria o letti dal fascicolo, in tutte le materie: il software riconosce il tipo
di provvedimento e il rito, legge i capi del dispositivo (chi, che cosa, entro quando),
calcola le date con il motore dei termini e propone all'avvocato i passi successivi:

* udienze e modalità (cartolare, da remoto, in presenza, camera di consiglio);
* termini perentori e ordinatori, scritti dal giudice o fissati dalla legge quando il
  provvedimento tace (tabella versionata ``pct/data/provvedimenti_regole_v2026_11.json``
  con norme del registro ``pct/procedura_fasi/fonti.py``);
* adempimenti (notifiche, depositi, pagamenti, consulenza, testimoni) e requisiti formali;
* che cosa aspettarsi dopo (decisione, comunicazione dello scioglimento della riserva);
* domande all'avvocato quando una data o un riferimento è ambiguo: mai indovinare.

Il contratto d'uscita è ``modello.Voce`` (regola stabile, norme, prova, dati,
confidenza, stato); le bozze nello scadenziario passano da ``scadenziario`` e dal
meccanismo di conferma esistente. Il decreto di trattazione scritta senza data
(art. 127-ter c.p.c.) è un caso di questo strato, letto da ``pct/note_127_ter``.
"""

from .esame import esamina_provvedimento
from .modello import EsitoProvvedimento, Voce
from .scadenziario import TermineProposto, proposte_scadenziario, scadenza_equivalente

__all__ = [
    "EsitoProvvedimento", "TermineProposto", "Voce", "esamina_provvedimento", "proposte_scadenziario", "scadenza_equivalente",
]
