"""Dove la console cerca gli archivi di backup.

La stessa pagina diceva "Backup esterni 0 B, nessun archivio trovato" e poco
sotto "Archivi backup esterni 64,3 GiB". Due misure della stessa cartella: una
guardava il percorso dell'host cosi' com'e' scritto, l'altra lo raggiungeva
sotto la radice dell'host montata nel container. Finche' la prima non trovava
niente, la retention non aveva archivi da governare e non cancellava mai nulla.
"""

from __future__ import annotations

from pathlib import Path

from web.services import server_maintenance_surface as sms


def test_usa_il_percorso_diretto_quando_esiste(tmp_path: Path, monkeypatch):
    diretto = tmp_path / "backups"
    diretto.mkdir()
    monkeypatch.setenv("IUSENTRA_BACKUP_DIR", str(diretto))

    assert sms.resolve_external_backup_dir({}) == diretto


def test_ripiega_sotto_la_radice_host_quando_il_percorso_diretto_non_esiste(tmp_path: Path, monkeypatch):
    """E' il caso di produzione: nel container /opt/iusentra/backups non c'e'."""

    host = tmp_path / "host" / "opt" / "iusentra"
    (host / "backups").mkdir(parents=True)
    monkeypatch.setenv("IUSENTRA_BACKUP_DIR", str(tmp_path / "non-esiste" / "backups"))
    monkeypatch.setattr(sms, "resolve_host_iusentra_dir", lambda cfg=None: host)

    risolto = sms.resolve_external_backup_dir({})

    assert risolto == host / "backups"
    assert risolto.exists(), "la retention deve poter leggere gli archivi veri"


def test_senza_radice_host_resta_il_percorso_indicato(tmp_path: Path, monkeypatch):
    indicato = tmp_path / "non-esiste" / "backups"
    monkeypatch.setenv("IUSENTRA_BACKUP_DIR", str(indicato))
    monkeypatch.setattr(sms, "resolve_host_iusentra_dir", lambda cfg=None: None)

    assert sms.resolve_external_backup_dir({}) == indicato
