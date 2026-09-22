"""Il conto dello spazio, fatto dove il tempo c'e'.

«Analizza manutenzione» misurava backup, cartelle escluse, snapshot, normativa
globale, log di sistema e cache dei servizi dentro la richiesta HTTP. Su un
disco da 262 GiB sono minuti, e il server chiude a 120 secondi: il bottone non
tornava, quindi quel numero nessuno lo vedeva.

Qui il conto si fa di notte, una volta, e si scrive. Il pannello legge il
risultato gia' pronto e lo mostra subito, con la data della scansione. Per
rifarlo prima del giro notturno si usa «Esegui adesso» sulla pianificazione:
la richiesta viene accodata e il lavoro avviene nello scheduler, dove il tempo
non e' contato in secondi di richiesta.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

NOME_FILE = "censimento_spazio.json"

#: Oltre questa eta' la scansione e' vecchia e va dichiarata tale.
ORE_PRIMA_DI_DICHIARARLO_VECCHIO = 30


def percorso_censimento(config: dict[str, Any] | None = None) -> Path:
    from web.services.server_maintenance_surface import resolve_data_root

    radice = Path(resolve_data_root(config))
    return radice / "intelligence" / NOME_FILE


def ultimo_censimento(config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """L'ultima scansione scritta, o niente se non ne e' mai stata fatta una."""
    percorso = percorso_censimento(config)
    try:
        if not percorso.is_file():
            return None
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(dati, dict) or not dati.get("risultato"):
        return None
    return dati


def eta_ore(censimento: dict[str, Any] | None) -> float | None:
    """Da quante ore e' fermo quel numero."""
    if not censimento:
        return None
    try:
        quando = datetime.fromisoformat(str(censimento.get("eseguito_il") or ""))
    except ValueError:
        return None
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=UTC)
    return (datetime.now(UTC) - quando).total_seconds() / 3600.0


def esegui_censimento(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Misura e scrive. Non cancella niente: e' l'analisi, non l'azione."""
    from web.services.server_maintenance_surface import run_professional_server_maintenance

    risultato = run_professional_server_maintenance(apply=False, config=config)
    voce = {"eseguito_il": datetime.now(UTC).isoformat(), "risultato": risultato}
    percorso = percorso_censimento(config)
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps(voce, ensure_ascii=False, indent=2), encoding="utf-8")
        voce["percorso"] = str(percorso)
    except Exception as exc:
        # Il numero resta comunque utile a chi ha chiamato: si dichiara solo
        # che non e' stato conservato per il pannello.
        voce["errore_scrittura"] = str(exc)
    return voce


__all__ = [
    "NOME_FILE",
    "ORE_PRIMA_DI_DICHIARARLO_VECCHIO",
    "esegui_censimento",
    "eta_ore",
    "percorso_censimento",
    "ultimo_censimento",
]
