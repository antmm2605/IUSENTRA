"""Test per il sistema di backup professionale."""

import json
import zipfile
from pathlib import Path

import pytest

# Verifica disponibilità crittografia
import subprocess, sys
_res = subprocess.run(
    [sys.executable, "-c",
     "from cryptography.hazmat.primitives.ciphers.aead import AESGCM"],
    capture_output=True
)
_CRYPTO_OK = _res.returncode == 0

skip_crypto = pytest.mark.skipif(
    not _CRYPTO_OK,
    reason="cryptography/cffi non disponibile in questo ambiente"
)

from pct.backup import (
    GestioneBackup,
    TipoBackup,
    StatoBackup,
    FrequenzaBackup,
    ConfigBackup,
    RecordBackup,
    _sha256_file,
)


@pytest.fixture
def dati(tmp_path):
    """Crea file di dati di test."""
    agenda = tmp_path / "agenda.json"
    agenda.write_text('{"appuntamenti": []}', encoding="utf-8")
    clienti = tmp_path / "clienti.json"
    clienti.write_text('{"clienti": []}', encoding="utf-8")
    docs = tmp_path / "documenti"
    docs.mkdir()
    (docs / "doc1.pdf").write_bytes(b"%PDF-1.4 test")
    (docs / "doc2.pdf").write_bytes(b"%PDF-1.4 altro")
    return {
        "agenda": str(agenda),
        "clienti": str(clienti),
        "documenti": str(docs),
    }


@pytest.fixture
def gb(tmp_path, dati):
    return GestioneBackup(
        directory_backup=str(tmp_path / "backup"),
        percorsi_dati=dati,
    )


# ------------------------------------------------------------------ Backup

def test_backup_completo(gb):
    record = gb.esegui_backup(tipo=TipoBackup.COMPLETO, nota="test")
    assert record.stato == StatoBackup.OK
    assert record.num_file > 0
    assert Path(record.percorso_file).exists()
    assert record.hash_file != ""
    assert record.nota == "test"
    assert record.tipo == TipoBackup.COMPLETO


def test_backup_crea_zip_valido(gb):
    record = gb.esegui_backup()
    with zipfile.ZipFile(record.percorso_file, "r") as zf:
        nomi = zf.namelist()
    assert "_manifest.json" in nomi
    assert "_meta.json" in nomi


def test_backup_contiene_tutti_file(gb):
    record = gb.esegui_backup()
    with zipfile.ZipFile(record.percorso_file, "r") as zf:
        nomi = zf.namelist()
    # almeno i JSON dei dati
    assert any("agenda" in n for n in nomi)
    assert any("clienti" in n for n in nomi)


def test_backup_incrementale(gb):
    gb.esegui_backup(tipo=TipoBackup.COMPLETO)
    record = gb.esegui_backup(tipo=TipoBackup.INCREMENTALE)
    assert record.tipo == TipoBackup.INCREMENTALE
    assert record.backup_base_id != ""


def test_backup_componenti_selettivi(gb):
    record = gb.esegui_backup(componenti=["agenda"])
    assert "agenda" in record.componenti
    # solo componenti selezionati
    assert len(record.componenti) == 1


def test_backup_salvato_nel_registro(gb):
    gb.esegui_backup()
    assert len(gb.tutti()) == 1


# ------------------------------------------------------------------ Rotazione

def test_rotazione(tmp_path, dati):
    gb = GestioneBackup(
        directory_backup=str(tmp_path / "backup"),
        percorsi_dati=dati,
    )
    gb._config.max_backup = 3
    for _ in range(5):
        gb.esegui_backup()
    ok_records = [r for r in gb.tutti() if r.stato == StatoBackup.OK]
    assert len(ok_records) <= 3


# ------------------------------------------------------------------ Verifica integrità

def test_verifica_integrita_ok(gb):
    record = gb.esegui_backup()
    ris = gb.verifica_integrita(record.id)
    assert ris["ok"] is True


def test_verifica_integrita_corrotto(gb):
    record = gb.esegui_backup()
    # Corrompi il file
    p = Path(record.percorso_file)
    p.write_bytes(p.read_bytes() + b"CORROTTO")
    ris = gb.verifica_integrita(record.id)
    assert ris["ok"] is False


# ------------------------------------------------------------------ Ripristino

def test_ripristina_completo(gb, tmp_path):
    record = gb.esegui_backup()
    dest = str(tmp_path / "restore")
    ris = gb.ripristina(record.id, dest)
    assert ris["file_ripristinati"] > 0
    assert len(ris["errori"]) == 0


def test_ripristina_file_esistono(gb, tmp_path):
    record = gb.esegui_backup()
    dest = str(tmp_path / "restore2")
    gb.ripristina(record.id, dest)
    # Verifica che almeno un file sia stato estratto
    dest_path = Path(dest)
    extracted = list(dest_path.rglob("*"))
    assert any(f.is_file() for f in extracted)


def test_ripristina_componente_selettivo(gb, tmp_path):
    record = gb.esegui_backup(componenti=["agenda", "clienti"])
    dest = str(tmp_path / "restore_sel")
    ris = gb.ripristina(record.id, dest, componenti=["agenda"])
    assert ris["file_ripristinati"] >= 1


def test_ripristina_senza_sovrascrittura(gb, tmp_path):
    record = gb.esegui_backup()
    dest = str(tmp_path / "restore_noow")
    # Prima volta: ok
    ris1 = gb.ripristina(record.id, dest)
    # Seconda volta senza sovrascrivi: file saltati
    ris2 = gb.ripristina(record.id, dest, sovrascrivi=False)
    assert ris2["file_saltati"] > 0


def test_ripristina_con_sovrascrittura(gb, tmp_path):
    record = gb.esegui_backup()
    dest = str(tmp_path / "restore_ow")
    gb.ripristina(record.id, dest)
    ris2 = gb.ripristina(record.id, dest, sovrascrivi=True)
    assert ris2["file_ripristinati"] > 0


def test_ripristina_backup_inesistente(gb, tmp_path):
    with pytest.raises(ValueError):
        gb.ripristina("nonexistent-id", str(tmp_path / "dest"))


# ------------------------------------------------------------------ Cifratura

@skip_crypto
def test_backup_cifrato(gb, tmp_path):
    record = gb.esegui_backup(password="segreta123")
    assert record.cifrato is True
    p = Path(record.percorso_file)
    assert p.suffix == ".enc"
    assert p.exists()


@skip_crypto
def test_ripristina_cifrato(gb, tmp_path):
    record = gb.esegui_backup(password="segreta123")
    dest = str(tmp_path / "restore_enc")
    ris = gb.ripristina(record.id, dest, password="segreta123")
    assert ris["file_ripristinati"] > 0


@skip_crypto
def test_ripristina_cifrato_senza_password_errore(gb, tmp_path):
    record = gb.esegui_backup(password="segreta123")
    dest = str(tmp_path / "restore_nopass")
    with pytest.raises(ValueError, match="password"):
        gb.ripristina(record.id, dest)


@skip_crypto
def test_ripristina_cifrato_password_sbagliata(gb, tmp_path):
    record = gb.esegui_backup(password="corretta")
    dest = str(tmp_path / "restore_wrongpass")
    with pytest.raises(Exception):
        gb.ripristina(record.id, dest, password="sbagliata")


# ------------------------------------------------------------------ Eliminazione

def test_elimina_backup(gb):
    record = gb.esegui_backup()
    p = Path(record.percorso_file)
    gb.elimina(record.id)
    assert gb.get(record.id) is None
    assert not p.exists()


def test_elimina_inesistente(gb):
    with pytest.raises(ValueError):
        gb.elimina("nonexistent")


# ------------------------------------------------------------------ Query

def test_tutti_ordine_decrescente(gb):
    gb.esegui_backup(nota="primo")
    gb.esegui_backup(nota="secondo")
    records = gb.tutti()
    assert records[0].nota == "secondo"


def test_ultimo_backup(gb):
    assert gb.ultimo() is None
    gb.esegui_backup()
    assert gb.ultimo() is not None


def test_get_backup(gb):
    record = gb.esegui_backup()
    trovato = gb.get(record.id)
    assert trovato is not None
    assert trovato.id == record.id


# ------------------------------------------------------------------ Persistenza

def test_registro_persistito(tmp_path, dati):
    bk_dir = str(tmp_path / "backup")
    gb1 = GestioneBackup(directory_backup=bk_dir, percorsi_dati=dati)
    gb1.esegui_backup()
    gb2 = GestioneBackup(directory_backup=bk_dir, percorsi_dati=dati)
    assert len(gb2.tutti()) == 1


# ------------------------------------------------------------------ Statistiche

def test_statistiche(gb):
    gb.esegui_backup()
    stats = gb.statistiche()
    assert stats["totale"] == 1
    assert stats["ok"] == 1
    assert stats["falliti"] == 0
    assert stats["dimensione_totale_bytes"] > 0
    assert stats["ultimo"] is not None
