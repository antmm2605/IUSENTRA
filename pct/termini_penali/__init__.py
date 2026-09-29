"""Termini del processo penale calcolati in modo deterministico e spiegato.

Moduli: ``calendario`` (art. 172 c.p.p., L. 742/1969), ``impugnazioni`` (artt. 585, 461, 309-311, 324,
408, 415-bis), ``indagini`` (artt. 405-407-bis), ``custodia`` (art. 303), ``prescrizione`` (artt. 157-161-bis
c.p. e regimi transitori), ``improcedibilita`` (art. 344-bis). Fonti consultate il 29/09/2026:
docs/specs/ministero/fonti_ufficiali/2026-09-29/penale/README.md.
"""

from pct.termini_penali import custodia, impugnazioni, improcedibilita, indagini, prescrizione

__all__ = ["custodia", "impugnazioni", "improcedibilita", "indagini", "prescrizione"]
