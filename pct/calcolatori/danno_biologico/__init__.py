"""Liquidazione del danno biologico sulle tabelle oggi vigenti.

Tre tabelle, ciascuna con il proprio ambito imposto dalla legge:

- ``art139``: lesioni di lieve entita' da 1 a 9 punti, art. 139 D.Lgs. 209/2005,
  con gli importi del decreto ministeriale annuale (art. 139 comma 5);
- ``tun``: macrolesioni da 10 a 100 punti, tabella unica nazionale del
  D.P.R. 13 gennaio 2025 n. 12 in attuazione dell'art. 138 D.Lgs. 209/2005,
  per i sinistri dal 5 marzo 2025;
- ``milano``: tabelle milanesi edizione 2024, parametro nazionale della
  liquidazione equitativa ex art. 1226 c.c. (Cass. 12408/2011) per tutto cio'
  che resta fuori dagli artt. 138 e 139.

``regime`` sceglie quale si applica, ``calcolo`` orchestra, ``tabelle`` carica i
dati da ``pct/data/tabelle_danno`` e ``fonti`` porta con se' la provenienza.
"""
from pct.calcolatori.danno_biologico import art139, calcolo, fonti, milano, regime, tabelle, tun  # noqa: F401
from pct.calcolatori.danno_biologico.calcolo import calcola  # noqa: F401

__all__ = ["art139", "calcola", "calcolo", "fonti", "milano", "regime", "tabelle", "tun"]
