"""AI locale con un modello alla volta e modello di riserva.

Decisione dell'avvocato del 03/11/2026: Ollama tiene in memoria un solo modello (OLLAMA_MAX_LOADED_MODELS=1) e lo
scarica subito dopo l'uso. Se il modello principale non risponde (errore, tempo scaduto o memoria esaurita) si
scarica e si avvia il modello di riserva; l'esito si scrive nel registro (``RegistroNotte.scrivi_esito_ai``).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def scarica_modello(client: Any, modello: str) -> bool:
    """keep_alive=0: Ollama libera subito la memoria del modello. Mai bloccante."""
    try:
        client.generate_completion(modello, "", keep_alive="0", timeout=30)
        return True
    except Exception as exc:
        logger.info("[ai] Modello %s non scaricato: %s", modello, type(exc).__name__)
        return False


def genera_con_riserva(
    client: Any,
    principale: str,
    riserva: str,
    chiama: Callable[[str], Any],
    *,
    registra: Callable[[dict[str, Any]], None] | None = None,
) -> Any:
    """Esegue ``chiama(modello)`` col principale; se fallisce scarica il principale e prova la riserva."""
    try:
        return chiama(principale)
    except Exception as exc:
        motivo = f"{type(exc).__name__}: {str(exc)[:200]}"
        if not riserva or riserva == principale:
            raise
    scarica_modello(client, principale)
    esito = {"principale": principale, "riserva": riserva, "motivo": motivo}
    try:
        risultato = chiama(riserva)
        esito["esito"] = "riserva_riuscita"
        return risultato
    except Exception as exc:
        esito["esito"] = "riserva_fallita"
        esito["motivo_riserva"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        scarica_modello(client, riserva)
        raise
    finally:
        logger.warning("[ai] Modello %s non riuscito (%s): %s con %s.", principale, motivo, esito.get("esito"), riserva)
        if registra is not None:
            try:
                registra(esito)
            except Exception:
                logger.warning("[ai] Esito della riserva non registrato.")
