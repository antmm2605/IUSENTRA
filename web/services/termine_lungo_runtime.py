"""Giro periodico del termine lungo (art. 327 c.p.c.): comunicazioni di deposito sentenza → bozza in scadenziario.

Legge in sola lettura le comunicazioni di deposito sentenza collegate a un fascicolo
(PEC_AUDIT_DB, scritto dal worker PEC) e i fatti già letti dall'archivio delle letture:
nessun documento viene riletto qui. La regola è in `pct.termine_lungo_sentenza`.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pct.pec_provvedimento_terms import is_labour_matter
from pct.termine_lungo_sentenza import completa_termini_lunghi

logger = logging.getLogger(__name__)

# Sei mesi più agosto e qualche giorno di proroga: oltre, il termine lungo è comunque scaduto.
FINESTRA_GIORNI = 230


def _json(valore: Any) -> dict[str, Any]:
    try:
        dati = json.loads(str(valore or "{}"))
    except ValueError:
        return {}
    return dati if isinstance(dati, dict) else {}


def comunicazioni_deposito_sentenza(db_path: Path, *, oggi: date) -> list[dict[str, Any]]:
    """Comunicazioni di deposito sentenza collegate a un fascicolo e ancora utili per il termine lungo."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        righe = conn.execute(
            """
            SELECT m.id, m.linked_fascicolo_id, m.metadata_json,
                   (SELECT p.parsed_json FROM pec_parsed_versions p WHERE p.message_id = m.id
                    ORDER BY p.version DESC LIMIT 1) AS parsed_json
            FROM pec_messages m
            WHERE TRIM(COALESCE(m.linked_fascicolo_id, '')) <> '' AND m.received_at >= ?
              AND EXISTS (SELECT 1 FROM pec_legal_events e WHERE e.message_id = m.id AND e.tenant_id = m.tenant_id
                          AND e.primary_event = 'deposito_sentenza')
            """,
            ((oggi - timedelta(days=FINESTRA_GIORNI)).isoformat(),),
        ).fetchall()
    finally:
        conn.close()
    comunicazioni = []
    for riga in righe:
        parsed = _json(riga["parsed_json"])
        intestazioni = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
        intestazioni = intestazioni or (_json(riga["metadata_json"]).get("headers") or {})
        corpo = parsed.get("body") if isinstance(parsed.get("body"), dict) else {}
        oggetto = str((intestazioni or {}).get("subject") or "")
        testo = f"{oggetto}\n{corpo.get('text') or ''}"
        comunicazioni.append({
            "id": str(riga["id"]), "fascicolo_id": str(riga["linked_fascicolo_id"]), "testo": testo,
            "lavoro": is_labour_matter(oggetto, testo),
        })
    return comunicazioni


def _fatti_del_fascicolo(fascicolo_id: str) -> list[Any]:
    from web.services.archivio_letture_runtime import fatti_fascicolo

    try:
        return fatti_fascicolo(SimpleNamespace(id=fascicolo_id), categoria="data")
    except Exception as exc:  # archivio non disponibile: resta il promemoria senza data
        logger.warning("Fatti del fascicolo %s non disponibili per il termine lungo: %s", fascicolo_id, exc)
        return []


def completa_termini_lunghi_runtime(db_path: Path | None, scadenziario: Any, *, oggi: date) -> dict[str, Any]:
    """Un errore qui non ferma le notifiche dello studio: si registra e si prosegue."""
    if db_path is None or not Path(db_path).exists():
        return {"proposte": 0, "senza_data": 0}
    try:
        comunicazioni = comunicazioni_deposito_sentenza(Path(db_path), oggi=oggi)
        return completa_termini_lunghi(comunicazioni, scadenziario, _fatti_del_fascicolo, oggi=oggi)
    except Exception as exc:
        logger.warning("Termini lunghi delle sentenze non completati: %s", exc)
        return {"errore": f"{type(exc).__name__}: {exc}"[:200]}


__all__ = ["comunicazioni_deposito_sentenza", "completa_termini_lunghi_runtime"]
