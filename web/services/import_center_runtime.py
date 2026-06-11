"""Wiring del Migration Center verso i repository reali (sink clienti).

Primo sink tenant-aware: traduce i record di staging di tipo CLIENTE in clienti
reali tramite ``GestioneClienti``. Il ``GestioneClienti`` viene iniettato dal
chiamante già nel contesto tenant corretto (percorso dati dello studio), quindi
il sink non conosce né sceglie il tenant. Resta valido il principio del Migration
Center: si scrive solo con commit esplicito (``dry_run=False``); l'anteprima non
tocca i dati.
"""

from __future__ import annotations

from typing import Any

from pct.clienti import GestioneClienti, TipoCliente
from pct.importers import (
    CommitResult,
    RecordKind,
    StagedRecord,
    StagingArea,
    execute_commit,
)
from pct.importers.dedup import natural_key


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _cf(data: dict[str, Any]) -> str:
    return _text(data.get("codice_fiscale") or data.get("cf")).upper()


class ClientiRecordSink:
    """Sink reale: crea/elimina clienti tramite GestioneClienti (tenant-aware)."""

    def __init__(self, gestione: GestioneClienti) -> None:
        self.gestione = gestione

    def create(self, record: StagedRecord) -> str:
        if record.kind != RecordKind.CLIENTE:
            raise ValueError(f"ClientiRecordSink non gestisce il tipo {record.kind.value}.")
        data = record.data or {}
        ragione = _text(data.get("ragione_sociale") or data.get("denominazione"))
        if ragione:
            cliente = self.gestione.nuovo(
                TipoCliente.PERSONA_GIURIDICA,
                ragione_sociale=ragione,
                codice_fiscale=_cf(data),
                partita_iva=_text(data.get("partita_iva") or data.get("piva")),
            )
        else:
            cliente = self.gestione.nuovo(
                TipoCliente.PERSONA_FISICA,
                nome=_text(data.get("nome")),
                cognome=_text(data.get("cognome")),
                codice_fiscale=_cf(data),
            )
        email = _text(data.get("email"))
        cellulare = _text(data.get("cellulare") or data.get("telefono"))
        recapiti: dict[str, str] = {}
        if email:
            recapiti["email"] = email
        if cellulare:
            recapiti["cellulare"] = cellulare
        if recapiti:
            self.gestione.aggiorna_recapiti(cliente.id, **recapiti)
        return cliente.id

    def delete(self, kind: str, record_id: str) -> bool:
        try:
            if self.gestione.get(record_id) is None:
                return False
            self.gestione.elimina(record_id)
            return True
        except Exception:
            return False


def existing_client_keys(gestione: GestioneClienti) -> set[str]:
    """Chiavi naturali dei clienti già presenti (per la deduplica dell'import)."""

    keys: set[str] = set()
    for cliente in gestione.tutti():
        data = {
            "codice_fiscale": getattr(cliente, "codice_fiscale", ""),
            "partita_iva": getattr(cliente, "partita_iva", ""),
            "nome": getattr(cliente, "nome", ""),
            "cognome": getattr(cliente, "cognome", ""),
        }
        key = natural_key(RecordKind.CLIENTE, data)
        if key:
            keys.add(key)
    return keys


def import_clienti_from_staging(gestione: GestioneClienti, staging: StagingArea, *, dry_run: bool = True) -> CommitResult:
    """Esegue (o simula) l'import dei clienti dallo staging verso lo studio.

    Default dry-run: nessuna scrittura. Con ``dry_run=False`` scrive i clienti
    validi non duplicati e restituisce il ledger per l'eventuale rollback.
    """

    sink = ClientiRecordSink(gestione)
    return execute_commit(staging, sink, dry_run=dry_run)


__all__ = ["ClientiRecordSink", "existing_client_keys", "import_clienti_from_staging"]
