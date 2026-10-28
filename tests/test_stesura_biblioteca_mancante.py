from types import SimpleNamespace
import pytest
from web.services import redazione_lex_runtime as runtime


def test_mount_assente_non_crea_archivio_vuoto(tmp_path,monkeypatch):
    db=tmp_path/"mount_assente"/"codici_leggi.sqlite"
    def vietato(*args,**kwargs):
        raise AssertionError("Non leggere schede o invocare modelli senza biblioteca")
    monkeypatch.setattr(runtime,"fonti_per_scheda",vietato)
    with pytest.raises(ValueError,match="nessun database vuoto"):
        runtime.stesura(model_code="CIV_CIT_001",risolta={"scheda":"CIV_CIT_001"},
                        fascicolo=SimpleNamespace(),cliente=SimpleNamespace(),oggetto="Prova",
                        ruolo_assistito="attore",biblioteca=db,chiama_modello=vietato,campi_modello=[])
    assert not db.exists()
    assert not db.parent.exists()
