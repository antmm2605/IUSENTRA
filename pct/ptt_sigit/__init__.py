"""Processo Tributario Telematico (PTT) sul SIGIT: dominio per la preparazione del deposito.

Base normativa: artt. 16-bis, 18, 22 D.Lgs. 546/1992; D.M. 23/12/2013 n. 163;
decreto direttoriale 4/8/2015 e modifiche del 28/11/2017 e 21/4/2023; art. 13
c. 6-quater d.P.R. 115/2002. Il SIGIT non ha servizi per i gestionali:
IUSENTRA prepara dati e file, controlla, calcola CUT e termini e registra lo
stato che l'avvocato riporta dall'area riservata.
"""

from . import catalogo, cut, parti, regole, scheda, termini
from .archivio import ArchivioPtt

__all__ = ["ArchivioPtt", "catalogo", "cut", "parti", "regole", "scheda", "termini"]
