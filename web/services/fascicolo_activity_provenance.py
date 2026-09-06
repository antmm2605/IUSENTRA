"""Proiezione delle acquisizioni già registrate nel fascicolo SQL.

Non consulta portali, non modifica lo stato della pratica e non certifica
download. La provenienza è quella conservata dal repository del tenant.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from pct.formatting import format_datetime_it, parse_datetime_rome


def recorded_portal_acquisition(fascicolo: Any) -> Any | None:
    """Rende visibile l'ultimo snapshot acquisito, non una sincronizzazione presunta."""

    snapshot = getattr(fascicolo, "source_snapshot", None)
    if not isinstance(snapshot, dict):
        return None
    log_id = str(snapshot.get("import_log_id") or "").strip()
    raw_date = str(snapshot.get("acquisito_il") or "").strip()
    source = str(snapshot.get("portale") or "").strip()
    # Solo sorgenti governate e un'acquisizione realmente identificabile.
    sources = {
        "polisweb / pst": "PolisWeb / PST",
        "polisweb": "PolisWeb",
        "pst": "PST",
        "pdp": "PDP",
        "pat": "PAT",
        "ptt": "PTT",
    }
    label = sources.get(source.casefold())
    if not log_id or not raw_date or not label:
        return None
    try:
        parsed = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
    except ValueError:
        return None
    recorded = parse_datetime_rome(parsed)
    if recorded is None:
        return None
    return SimpleNamespace(
        id=f"acquisizione:{log_id}",
        tipo="ACQUISIZIONE",
        data=recorded.date().isoformat(),
        titolo=f"Acquisizione dati da {label}",
        descrizione=(
            f"Dati della pratica acquisiti il {format_datetime_it(recorded)}. "
            "La registrazione riguarda i dati del fascicolo: non attesta da sola "
            "il download di tutti i documenti o un deposito telematico."
        ),
        esito="REGISTRATO",
        creato_il=recorded.isoformat(),
    )
