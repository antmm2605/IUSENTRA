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
