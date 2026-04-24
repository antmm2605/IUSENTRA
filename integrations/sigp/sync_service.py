"""Servizi applicativi per sincronizzare fascicoli SIGP autorizzati."""

from __future__ import annotations

from pathlib import Path

from .sync_mapper import normalize_sigp_sync_payload
from .sync_policy import get_sigp_sync_policy
from .sync_repository import SigpSyncRepository


def resolve_sigp_sync_db_path(config: dict | None = None) -> Path:
    config = config or {}
    configured = config.get("SIGP_SYNC_DB_PATH") or config.get("DATABASE_PATH")
    if configured:
        return Path(str(configured))
    data_root = Path(str(config.get("DATA_ROOT") or "data"))
    return data_root / "sigp" / "sigp_sync.db"


def get_sigp_sync_status() -> dict:
    return {
        "ok": True,
        "policy": get_sigp_sync_policy(),
        "adapter": "payload_autorizzato",
        "messaggio": (
            "Il server importa solo dati gia' ottenuti tramite Local Connector, "
            "PST/PdA autorizzato o Model Office SIGP. Nessun file esempio viene "
            "usato come sorgente dati."
        ),
    }


def import_authorized_sigp_payload(
    raw_payload: dict,
    db_path: str | Path,
    fascicolo_locale_id: str | None = None,
) -> dict:
    normalized = normalize_sigp_sync_payload(raw_payload)
    repo = SigpSyncRepository(db_path)
    result = repo.import_snapshot(normalized, fascicolo_locale_id=fascicolo_locale_id)
    result["hash_snapshot"] = normalized["hash_snapshot"]
    result["fascicolo"] = normalized["fascicolo"]
    return result
