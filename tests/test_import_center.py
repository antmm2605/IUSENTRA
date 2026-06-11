"""Test del Migration Center (import multi-gestionale, dry-run sicuro)."""

from __future__ import annotations

import pytest

from pct.importers import (
    ImportError_,
    RecordKind,
    RecordStatus,
    available_adapters,
    build_commit_plan,
    build_staging,
    execute_commit,
    execute_rollback,
    get_adapter,
)
from pct.importers.dedup import natural_key


CSV_CLIENTI = (
    "nome,cognome,codice_fiscale,email\n"
    "Mario,Rossi,RSSMRA80A01H501U,mario@example.it\n"
    "Mario,Rossi,RSSMRA80A01H501U,mario@example.it\n"  # duplicato esatto
    "Anna,Bianchi,BNCNNA85C44F205X,anna@example.it\n"
    ",,,\n"  # riga vuota (scartata)
    "SenzaCF,,XXX,bad@example.it\n"  # CF non valido -> invalid
).encode("utf-8")


def test_registry_espone_generic_csv_e_rifiuta_sconosciuti():
    assert "generic_csv" in available_adapters()
    assert get_adapter("generic_csv").name == "generic_csv"
    with pytest.raises(ImportError_):
        get_adapter("inesistente")


def test_staging_valida_e_deduplica_senza_scrivere():
    staging = build_staging("generic_csv", CSV_CLIENTI, kind=RecordKind.CLIENTE)
    summary = staging.summary()
    # 4 righe non vuote: 1 valida (Mario), 1 duplicata (Mario bis), 1 valida (Anna), 1 invalida (CF errato)
    assert summary["total"] == 4
    assert summary["valid"] == 2
    assert summary["duplicate"] == 1
    assert summary["invalid"] == 1

    invalid = staging.invalid_records()[0]
    assert any(issue.field == "codice_fiscale" for issue in invalid.issues)

    # L'anteprima è sicura: nessun path, solo campi e stato.
    preview = staging.preview(limit=10)
    assert preview["summary"]["valid"] == 2
    assert all("fields" in row and "status" in row for row in preview["records"])


def test_dedup_contro_dati_gia_presenti_nello_studio():
    existing = {natural_key(RecordKind.CLIENTE, {"codice_fiscale": "RSSMRA80A01H501U"})}
    staging = build_staging("generic_csv", CSV_CLIENTI, kind=RecordKind.CLIENTE, existing_keys=existing)
    # Mario è già presente nello studio: entrambe le sue righe diventano duplicate.
    assert staging.summary()["duplicate"] == 2
    assert staging.summary()["valid"] == 1  # resta solo Anna


def test_commit_dry_run_non_scrive_nulla():
    staging = build_staging("generic_csv", CSV_CLIENTI, kind=RecordKind.CLIENTE)
    plan = build_commit_plan(staging)
    assert len(plan.creates) == 2
    assert plan.to_public()["willCreate"] == 2
    assert plan.to_public()["skipReasons"].get("invalid") == 1
    assert plan.to_public()["skipReasons"].get("duplicate") == 1

    # Default dry-run: nessuna scrittura, nessun id creato.
    result = execute_commit(staging)
    assert result.dry_run is True
    assert result.created_ids == []


def test_commit_reale_richiede_sink_e_traccia_rollback():
    staging = build_staging("generic_csv", CSV_CLIENTI, kind=RecordKind.CLIENTE)

    # Sink finto in-memory (i sink reali tenant-aware arrivano in un PR successivo).
    class FakeSink:
        def __init__(self):
            self.store: dict[str, dict] = {}
            self._n = 0

        def create(self, record):
            self._n += 1
            new_id = f"cli-{self._n}"
            self.store[new_id] = dict(record.data)
            return new_id

        def delete(self, kind, record_id):
            return self.store.pop(record_id, None) is not None

    sink = FakeSink()
    result = execute_commit(staging, sink, dry_run=False)
    assert result.dry_run is False
    assert len(result.created_ids) == 2
    assert len(sink.store) == 2
    assert result.ledger is not None and result.ledger.to_public()["rollbackAvailable"] is True

    # Rollback: cancella tutto ciò che era stato creato in questo run.
    outcome = execute_rollback(result.ledger, sink)
    assert outcome["complete"] is True
    assert outcome["deleted"] == 2
    assert sink.store == {}


def test_execute_commit_senza_sink_ma_non_dry_run_resta_sicuro():
    staging = build_staging("generic_csv", CSV_CLIENTI, kind=RecordKind.CLIENTE)
    # dry_run=False ma sink None: non deve scrivere nulla (ritorna piano dry-run).
    result = execute_commit(staging, None, dry_run=False)
    assert result.dry_run is True
    assert result.created_ids == []


def test_csv_senza_intestazioni_errore_controllato():
    with pytest.raises(ImportError_):
        build_staging("generic_csv", b"", kind=RecordKind.CLIENTE)


def test_mapping_colonne_personalizzato():
    csv_raw = "Denominazione;P.IVA\nBeta S.r.l.;01234567890\n".encode("utf-8")
    staging = build_staging(
        "generic_csv",
        csv_raw,
        kind=RecordKind.CLIENTE,
        mapping={"Denominazione": "nome", "P.IVA": "partita_iva"},
    )
    rec = staging.records[0]
    assert rec.data["nome"] == "Beta S.r.l."
    assert rec.data["partita_iva"] == "01234567890"
    assert rec.status == RecordStatus.VALID


def test_fascicolo_dedup_per_numero_ruolo():
    csv_raw = (
        "titolo,numero_ruolo,anno\n"
        "Causa A,1234,2024\n"
        "Causa A bis,1234,2024\n"  # stesso RG/anno -> duplicato
        "Causa B,9999,2024\n"
    ).encode("utf-8")
    staging = build_staging("generic_csv", csv_raw, kind=RecordKind.FASCICOLO)
    assert staging.summary()["valid"] == 2
    assert staging.summary()["duplicate"] == 1
