"""Configurazione storica SIGP usata solo dai componenti non esposti."""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SIGP_DEFAULT_SCHEMA_VERSION = "2024-08-27"
SIGP_SCHEMAS_DIR = BASE_DIR / "schemas"

SIGP_MODULE_NAME = "Percorso PST unico"
SIGP_MODULE_SUBTITLE = (
    "Redazione, validazione XSD, predeposito e gestione dei depositi "
    "telematici presso gli Uffici del Giudice di Pace."
)

SIGP_AMBIENTI = {
    "test": {
        "label": "Model Office SIGP",
        "enabled": True,
        "codice_gestore_locale": "GLMV",
    },
    "produzione": {
        "label": "Produzione",
        "enabled": True,
        "codice_gestore_locale": "",
    },
}

SIGP_OFFICIAL_SOURCES = [
    {
        "label": "PST - Nota modifiche XSD SIGP - 27/08/2024",
        "url": "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3460",
    },
    {
        "label": "PST - PDF modifiche XSD SIGP - 27/08/2024",
        "url": "https://pst.giustizia.it/PST/resources/cms/documents/modifiche_XSD_SIGP_20240827.pdf",
    },
]
