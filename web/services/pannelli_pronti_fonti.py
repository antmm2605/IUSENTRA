"""Fonti condivise lette dai pannelli del fascicolo."""

from __future__ import annotations

from pathlib import Path

CHIAVI_FILE = (
    "CONFIG_STUDIO_DB",
    "FATTURAZIONE_DB",
    "PREVENTIVI_DB",
    "SENTENZA_ECONOMIC_DB",
    "TIMESHEET_DB",
)

# Anche la regia ha contatori SQL per fascicolo. Il suo mirror JSON è un export.
# Le tabelle con la colonna del fascicolo hanno già i propri contatori.
# Agenda conserva il collegamento nel JSON sullo schema storico dello studio.
TABELLE_STUDIO = (
    "appuntamenti",
    "clienti",
    "email_mailbox_records",
    "fatturazione_sdi_receipts",
    "parcella_incassi_proofs",
    "parcella_incassi_state",
    "payment_config",
    "preventivi",
    "settings_config",
    "soggetti",
    "utenti",
)
TABELLE_REGISTRO: tuple[str, ...] = ()


def file_dello_studio(data_paths: dict) -> tuple[str, ...]:
    file = {str(data_paths[key]) for key in CHIAVI_FILE if data_paths.get(key)}
    casella = data_paths.get("EMAIL_CASELLA_DB")
    if casella:
        file.add(str(Path(casella).with_name("pec_audit.sqlite")))
    return tuple(sorted(file))
