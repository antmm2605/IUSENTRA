"""Le sezioni dei documenti del fascicolo: una sola tassonomia per tutto il sistema.

Il catalogo documentale le assegna, la correzione manuale le ammette, la
lettura del fascicolo le racconta e l'elenco dei documenti le usa come filtri
(frontend: components/fascicoloDocumenti/sezioniDocumento.ts, stesso ordine).
"""

from __future__ import annotations

SEZIONI_DOCUMENTO: tuple[str, ...] = (
    "atti", "provvedimenti", "procure", "notifiche", "comunicazioni",
    "contratti", "pagamenti", "identita", "allegati", "da-verificare",
)

__all__ = ["SEZIONI_DOCUMENTO"]
