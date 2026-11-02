"""L'udienza sostituita da note scritte è un'udienza «cartolare» (art. 127-ter c.p.c.).

Il tipo «cartolare» è quello di ``pct/udienze/tipi.py`` (senza presenza, con la verifica delle
note depositate nel termine). L'udienza in agenda prende la modalità «note scritte» solo quando
l'avvocato conferma la proposta del termine per le note: prima resta com'è, perché la data
viene dal fascicolo e non dal decreto. La preparazione dell'udienza nasce poi già «cartolare».
"""

from __future__ import annotations

import logging
from typing import Any

from pct.udienze.tipi import TIPI

from .proposta import CODICE_NOTE_127_TER, MODALITA_NOTE_SCRITTE

TIPO_CARTOLARE = "cartolare"
if not TIPI.get(TIPO_CARTOLARE, {}).get("senza_presenza"):  # pragma: no cover - catalogo dei tipi incoerente
    raise RuntimeError("Tipo d'udienza «cartolare» assente in pct/udienze/tipi.py")
_LOG = logging.getLogger(__name__)


def e_cartolare(appuntamento: Any) -> bool:
    return str(getattr(appuntamento, "hearing_mode", "") or "").strip() == MODALITA_NOTE_SCRITTE


def tipo_udienza_iniziale(appuntamento: Any) -> str:
    """Il tipo con cui nasce la preparazione: «cartolare» per l'udienza sostituita da note."""
    return TIPO_CARTOLARE if appuntamento is not None and e_cartolare(appuntamento) else ""


def segna_udienza_cartolare(scadenza: Any, *, gestione_agenda: Any) -> bool:
    """Alla conferma del termine per le note, l'udienza collegata diventa cartolare. True se aggiornata."""
    if str(getattr(scadenza, "deadline_profile_code", "") or "").upper() != CODICE_NOTE_127_TER:
        return False
    id_appuntamento = str(getattr(scadenza, "id_appuntamento", "") or "").strip()
    if not id_appuntamento or gestione_agenda is None:
        return False
    appuntamento = gestione_agenda.get(id_appuntamento)
    if appuntamento is None or e_cartolare(appuntamento):
        return False
    riga = (f"Udienza sostituita da note scritte (art. 127-ter c.p.c.): termine per le note confermato "
            f"(scadenza {getattr(scadenza, 'id', '')}).")
    nota = str(getattr(appuntamento, "note", "") or "").rstrip()
    try:
        gestione_agenda.modifica(id_appuntamento, hearing_mode=MODALITA_NOTE_SCRITTE,
                                 note="\n".join(p for p in (nota, riga) if p))
    except Exception as exc:  # la conferma della scadenza resta valida
        _LOG.warning("Udienza %s non segnata come cartolare: %s", id_appuntamento, exc)
        return False
    return True


__all__ = ["TIPO_CARTOLARE", "e_cartolare", "segna_udienza_cartolare", "tipo_udienza_iniziale"]
