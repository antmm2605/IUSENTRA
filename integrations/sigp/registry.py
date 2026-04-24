"""Registry versionato degli schemi XSD SIGP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import SIGP_DEFAULT_SCHEMA_VERSION, SIGP_OFFICIAL_SOURCES, SIGP_SCHEMAS_DIR


@dataclass(frozen=True)
class SigpSchemaVersion:
    version: str
    label: str
    root_dir: Path
    main_xsd: str
    active: bool = True
    data_pubblicazione: str = ""
    fonte: str = ""


SIGP_SCHEMA_REGISTRY = {
    "2024-08-27": SigpSchemaVersion(
        version="2024-08-27",
        label="Schemi XSD SIGP - aggiornamento 27/08/2024",
        root_dir=SIGP_SCHEMAS_DIR / "2024-08-27" / "xsd",
        main_xsd="Professionista.xsd",
        active=True,
        data_pubblicazione="2024-08-27",
        fonte=SIGP_OFFICIAL_SOURCES[0]["url"],
    )
}


def get_active_sigp_schema() -> SigpSchemaVersion:
    schema = SIGP_SCHEMA_REGISTRY.get(SIGP_DEFAULT_SCHEMA_VERSION)
    if not schema:
        raise RuntimeError("Nessuno schema SIGP attivo configurato.")
    return schema


def list_sigp_schemas() -> list[SigpSchemaVersion]:
    return list(SIGP_SCHEMA_REGISTRY.values())
