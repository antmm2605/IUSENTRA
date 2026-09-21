"""Incident regression: a partial read must never replace the whole archive."""
import pytest

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.storage import StudioDB


@pytest.mark.parametrize("mode", ["empty", "one", "without_documents"])
def test_partial_full_save_is_rejected_without_changing_sql(tmp_path, mode):
    db = StudioDB(str(tmp_path / "studio.db"))
    path = str(tmp_path / "fascicoli.json")
    full = GestioneFascicoli(path, studio_db=db)
    first = full.nuovo("Pratica uno", TipoFascicolo.CIVILE)
    full.nuovo("Pratica due", TipoFascicolo.CIVILE)
    full.aggiungi_documento(first.id, "originale.txt", TipoDocumento.ALLEGATO, b"originale")
    before = [tuple(row) for row in db.conn.execute("SELECT * FROM fascicoli ORDER BY id")]
    mirror = (tmp_path / "fascicoli.json").read_bytes()
    partial = GestioneFascicoli(path, studio_db=db,
                               carica_tutto=mode == "without_documents",
                               senza_documenti=mode == "without_documents")
    if mode == "one":
        partial.get(first.id)
    with pytest.raises(RuntimeError, match="Salvataggio integrale bloccato"):
        partial.nuovo("Collaudo", TipoFascicolo.CIVILE)
    assert [tuple(row) for row in db.conn.execute("SELECT * FROM fascicoli ORDER BY id")] == before
    assert (tmp_path / "fascicoli.json").read_bytes() == mirror


def test_sql_bootstrap_does_not_replace_concurrently_inserted_case(tmp_path, monkeypatch):
    path = str(tmp_path / "fascicoli.json")
    legacy = GestioneFascicoli(path)
    expected = legacy.nuovo("Da importare", TipoFascicolo.CIVILE)
    db = StudioDB(str(tmp_path / "studio.db"))
    other_repo = GestioneFascicoli(str(tmp_path / "other.json"), studio_db=db)
    monkeypatch.setattr(other_repo, "_prossimo_numero", lambda: "2026/99999")
    read = GestioneFascicoli._payloads_da_json_bootstrap
    inserted = []

    def concurrent_insert(self):
        payloads = read(self)
        inserted.append(other_repo.nuovo("Inserita durante bootstrap", TipoFascicolo.CIVILE).id)
        return payloads

    monkeypatch.setattr(GestioneFascicoli, "_payloads_da_json_bootstrap", concurrent_insert)
    loaded = GestioneFascicoli(path, studio_db=db)
    assert loaded.get(expected.id) is not None
    assert {row[0] for row in db.conn.execute("SELECT id FROM fascicoli")} == {expected.id, inserted[0]}


@pytest.mark.parametrize("without_documents", [False, True])
def test_legacy_sql_migration_preserves_documents_and_other_rows(tmp_path, without_documents):
    db = StudioDB(str(tmp_path / "studio.db"))
    path = str(tmp_path / "fascicoli.json")
    repo = GestioneFascicoli(path, studio_db=db)
    first = repo.nuovo("Archivio storico", TipoFascicolo.CIVILE)
    second = repo.nuovo("Altro fascicolo", TipoFascicolo.CIVILE)
    repo.aggiungi_documento(first.id, "originale.txt", TipoDocumento.ALLEGATO, b"originale")
    db.conn.execute("UPDATE fascicoli SET dati_json=NULL WHERE id=?", (first.id,))
    db.conn.commit()
    documents = db.conn.execute("SELECT documenti_json FROM fascicoli WHERE id=?", (first.id,)).fetchone()[0]
    other = tuple(db.conn.execute("SELECT * FROM fascicoli WHERE id=?", (second.id,)).fetchone())
    GestioneFascicoli(path, studio_db=db, senza_documenti=without_documents)
    assert db.conn.execute("SELECT documenti_json FROM fascicoli WHERE id=?", (first.id,)).fetchone()[0] == documents
    assert tuple(db.conn.execute("SELECT * FROM fascicoli WHERE id=?", (second.id,)).fetchone()) == other
