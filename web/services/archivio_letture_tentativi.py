"""Il singolo oggetto che non si lascia leggere: tentativi contati, poi chiuso con il motivo.

Regola del registro delle letture (docs/REGISTRO_LETTURE.md): nessun oggetto
dell'inventario resta «da leggere» per sempre. Un documento la cui lettura
solleva sempre la stessa eccezione bloccava l'intero fascicolo: l'errore
risaliva al giro, il giro falliva e dopo tre giri la coda si fermava, con
i documenti sani mai letti. Qui il guasto resta sul documento: si riprova
al giro successivo fino a ``TENTATIVI_PER_OGGETTO`` volte, poi la lettura si
chiude come «non leggibile» con la causa registrata, e il fascicolo prosegue.

Un guasto del sistema (database bloccato, registro non disponibile) non è
colpa del documento e risale invariato: lo gestisce la coda del fascicolo.

Base normativa: art. 3 D.M. 44/2011 e art. 20 CAD (integrità e impronta del
documento informatico: l'esito si lega all'impronta SHA-256 letta).
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from pct.registro_letture import Oggetto, RegistroLetture, RegistroLettureError

logger = logging.getLogger(__name__)

TENTATIVI_PER_OGGETTO = 3
# Un giro della prenotazione legge al più questi oggetti, poi salva il progresso e proroga la prenotazione.
OGGETTI_PER_GIRO = 10
# Oltre questo tempo il turno del fascicolo si chiude senza errore e il fascicolo torna in coda:
# il posto si libera per gli altri fascicoli e il turno successivo legge solo ciò che manca.
SECONDI_PER_TURNO = 600


def errore_di_sistema(exc: BaseException) -> bool:
    """Guasti del registro o del database: non si attribuiscono al documento."""
    if isinstance(exc, (sqlite3.Error, RegistroLettureError, MemoryError)):
        return True
    return type(exc).__module__.split(".", 1)[0] in {"psycopg", "psycopg2", "sqlalchemy"}


def _tentativi_precedenti(registro: RegistroLetture, tenant: str, fascicolo_id: str, oggetto: Oggetto, lettore: str) -> int:
    for lettura in registro.letture(tenant, fascicolo_id, lettore=lettore):
        if (lettura.tipo, lettura.oggetto_id, lettura.sha256) == (oggetto.tipo, oggetto.oggetto_id, oggetto.impronta):
            # Solo i tentativi ancora aperti: una lettura chiusa e riaperta a mano riparte da zero.
            if lettura.stato == "in_corso":
                return int((lettura.esito or {}).get("tentativi_falliti") or 0)
            return 0
    return 0


def lettura_non_riuscita(registro: RegistroLetture, tenant: str, fascicolo_id: str, oggetto: Oggetto, lettore: str,
                         versione: str, exc: BaseException) -> bool:
    """Registra il tentativo fallito; True se la lettura si chiude ora come non leggibile."""
    tentativi = _tentativi_precedenti(registro, tenant, fascicolo_id, oggetto, lettore) + 1
    causa = f"{type(exc).__name__}: {exc}"[:240]
    logger.warning("Lettura di %s/%s non riuscita (tentativo %d di %d): %s",
                   fascicolo_id, oggetto.oggetto_id, tentativi, TENTATIVI_PER_OGGETTO, causa)
    if tentativi >= TENTATIVI_PER_OGGETTO:
        registro.segna_letto(
            tenant, fascicolo_id, oggetto, lettore, stato="non_leggibile", versione=versione,
            esito={"motivo": f"Lettura non riuscita {tentativi} volte: chiusa come non leggibile ({causa}).",
                   "tentativi_falliti": tentativi, "causa": causa},
        )
        return True
    registro.segna_letto(
        tenant, fascicolo_id, oggetto, lettore, stato="in_corso", versione=versione,
        esito={"motivo": f"lettura non riuscita (tentativo {tentativi} di {TENTATIVI_PER_OGGETTO}): si riprova al prossimo giro",
               "tentativi_falliti": tentativi, "causa": causa},
    )
    return False


def progresso_giro(report: dict[str, Any]) -> int:
    """Quanti oggetti il giro ha portato avanti (letti, chiusi o con un tentativo registrato)."""
    documenti = dict(report.get("documenti") or {})
    pec = dict(report.get("pec") or {})
    progresso = sum(int(documenti.get(campo) or 0) for campo in (
        "letti", "senza_testo", "assenti", "riletture_senza_testo", "chiusi_per_errore", "errori_temporanei"))
    progresso += sum(int(pec.get(campo) or 0) for campo in ("letti", "assenti"))
    progresso += int((report.get("metadati") or {}).get("controllati") or 0)
    return progresso


__all__ = [
    "OGGETTI_PER_GIRO", "SECONDI_PER_TURNO", "TENTATIVI_PER_OGGETTO", "errore_di_sistema",
    "lettura_non_riuscita", "progresso_giro",
]
