from __future__ import annotations

from pathlib import Path

import pytest

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo


def _gestione(tmp_path: Path) -> GestioneFascicoli:
    return GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )


def test_rimuovi_documento_non_elimina_file_se_salvataggio_fallisce(tmp_path: Path, monkeypatch):
    fascicoli = _gestione(tmp_path)
    fascicolo = fascicoli.nuovo("Fascicolo prova", TipoFascicolo.CIVILE)
    documento = fascicoli.aggiungi_documento(
        fascicolo.id,
        "pec_prova.eml",
        TipoDocumento.COMUNICAZIONE,
        b"From: cancelleria@example.test\r\nSubject: Prova\r\n\r\nCorpo",
    )
    percorso = fascicoli.percorso_documento(fascicolo.id, documento.id)

    def _fail_salva():
        raise RuntimeError("database is locked")

    monkeypatch.setattr(fascicoli, "_salva", _fail_salva)

    with pytest.raises(RuntimeError, match="database is locked"):
        fascicoli.rimuovi_documento(fascicolo.id, documento.id)

    assert percorso.exists()
    assert any(doc.id == documento.id for doc in fascicolo.documenti)


def test_percorso_documento_lettura_recupera_duplicato_storico(tmp_path: Path):
    fascicoli = _gestione(tmp_path)
    fascicolo = fascicoli.nuovo("Fascicolo prova", TipoFascicolo.CIVILE)
    documento = fascicoli.aggiungi_documento(
        fascicolo.id,
        "pec_a977d2adfae8a994cccdb334.eml",
        TipoDocumento.COMUNICAZIONE,
        b"From: cancelleria@example.test\r\nSubject: Prova\r\n\r\nCorpo",
    )
    percorso = fascicoli.percorso_documento(fascicolo.id, documento.id)
    duplicato = percorso.with_name("pec_a977d2adfae8a994cccdb334_8bbc.eml")
    duplicato.write_bytes(percorso.read_bytes())
    percorso.unlink()

    assert not percorso.exists()
    assert fascicoli.percorso_documento_lettura(fascicolo.id, documento.id) == duplicato
