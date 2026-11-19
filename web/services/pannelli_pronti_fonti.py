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

# Le PEC collegate e i loro riscontri aggiornano il solo fascicolo interessato.
# La ricerca usa anche RG e nominativo per le PEC ancora da collegare.
# Aperture, download ed eventi di audit non sono fonti dei pannelli.
TABELLE_PEC = (
    "pec_messages", "pec_parsed_versions", "pec_attachments", "pec_validation_reports",
    "pec_fascicolo_links", "pec_legal_events", "pec_legal_deadlines", "pec_legal_hearings",
    "pec_legal_payments", "pec_fascicolo_documenti", "pec_fascicolo_documenti_messaggi",
)


def percorso_pec(data_paths: dict) -> str:
    esplicito = data_paths.get("PEC_AUDIT_DB")
    if esplicito:
        return str(esplicito)
    casella = data_paths.get("EMAIL_CASELLA_DB")
    return str(Path(casella).with_name("pec_audit.sqlite")) if casella else ""


def file_dello_studio(data_paths: dict) -> tuple[str, ...]:
    return tuple(sorted({str(data_paths[key]) for key in CHIAVI_FILE if data_paths.get(key)}))
