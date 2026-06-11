"""Test del sink reale clienti del Migration Center (tenant-aware, dry-run sicuro)."""

from __future__ import annotations

from pathlib import Path

from pct.clienti import GestioneClienti
from pct.importers import RecordKind, build_staging
from web.services.import_center_runtime import (
    existing_client_keys,
    import_clienti_from_staging,
)

CSV = (
    "nome,cognome,codice_fiscale,email\n"
    "Mario,Rossi,RSSMRA80A01H501U,mario@example.it\n"
    "Anna,Bianchi,BNCNNA85C44F205X,anna@example.it\n"
    "SenzaCF,,XXX,bad@example.it\n"  # CF invalido -> invalid, non importato
).encode("utf-8")


def _gestione(tmp_path: Path) -> GestioneClienti:
    return GestioneClienti(db_path=str(tmp_path / "clienti" / "anagrafica.json"))


def test_dry_run_non_crea_clienti(tmp_path):
    gestione = _gestione(tmp_path)
    staging = build_staging("generic_csv", CSV, kind=RecordKind.CLIENTE)
    result = import_clienti_from_staging(gestione, staging, dry_run=True)
    assert result.dry_run is True
    assert result.created_ids == []
    assert gestione.tutti() == []  # nessuna scrittura


def test_commit_reale_crea_clienti_validi_e_salta_invalidi(tmp_path):
    gestione = _gestione(tmp_path)
    staging = build_staging("generic_csv", CSV, kind=RecordKind.CLIENTE)
    result = import_clienti_from_staging(gestione, staging, dry_run=False)

    assert result.dry_run is False
    assert len(result.created_ids) == 2  # Mario + Anna; "SenzaCF" (CF invalido) saltato
    clienti = gestione.tutti()
    assert len(clienti) == 2
    cf_set = {c.codice_fiscale for c in clienti}
    assert "RSSMRA80A01H501U" in cf_set and "BNCNNA85C44F205X" in cf_set
    # recapiti importati
    mario = next(c for c in clienti if c.codice_fiscale == "RSSMRA80A01H501U")
    assert mario.recapiti.email == "mario@example.it"


def test_dedup_contro_clienti_gia_presenti(tmp_path):
    gestione = _gestione(tmp_path)
    # Mario è già nello studio.
    from pct.clienti import TipoCliente

    gestione.nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi", codice_fiscale="RSSMRA80A01H501U")
    keys = existing_client_keys(gestione)

    staging = build_staging("generic_csv", CSV, kind=RecordKind.CLIENTE, existing_keys=keys)
    result = import_clienti_from_staging(gestione, staging, dry_run=False)

    # Solo Anna viene importata: Mario è duplicato, SenzaCF invalido.
    assert len(result.created_ids) == 1
    assert len(gestione.tutti()) == 2  # Mario preesistente + Anna


def test_rollback_elimina_i_clienti_creati_nel_run(tmp_path):
    gestione = _gestione(tmp_path)
    staging = build_staging("generic_csv", CSV, kind=RecordKind.CLIENTE)
    result = import_clienti_from_staging(gestione, staging, dry_run=False)
    assert len(gestione.tutti()) == 2
    assert result.ledger is not None

    from pct.importers import execute_rollback
    from web.services.import_center_runtime import ClientiRecordSink

    outcome = execute_rollback(result.ledger, ClientiRecordSink(gestione))
    assert outcome["complete"] is True
    assert outcome["deleted"] == 2
    assert gestione.tutti() == []  # tutto annullato


def test_persona_giuridica_da_ragione_sociale(tmp_path):
    gestione = _gestione(tmp_path)
    csv = "ragione_sociale,partita_iva\nBeta S.r.l.,01234567890\n".encode("utf-8")
    staging = build_staging("generic_csv", csv, kind=RecordKind.CLIENTE)
    result = import_clienti_from_staging(gestione, staging, dry_run=False)
    assert len(result.created_ids) == 1
    cliente = gestione.tutti()[0]
    assert cliente.ragione_sociale == "Beta S.r.l."
    assert cliente.partita_iva == "01234567890"
