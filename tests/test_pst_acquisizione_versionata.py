"""Guardrail di persistenza: non sostituiscono la prova reale con CNS."""
import hashlib
from types import SimpleNamespace

import pytest
from flask import Flask, g

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.storage import StudioDB
from web.services.fascicoli_runtime import build_fascicoli_runtime


@pytest.fixture
def storage(tmp_path):
    db = StudioDB.get(str(tmp_path / "studio.db"))
    manager = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"), studio_db=db,
    )
    case = manager.nuovo(titolo="Acquisizione controllata", tipo=TipoFascicolo.CIVILE)
    return manager, case


def add(manager, case, payload, **kwargs):
    return manager.aggiungi_documento(
        case.id, "Documento.pdf", TipoDocumento.ALTRO, payload,
        id_documento_portale="33584995", fonte_documento="PORTALE_TELEMATICO",
        **kwargs,
    )


def test_refresh_preserves_id_bytes_and_signed_history_in_sql(storage):
    manager, case = storage
    old = add(manager, case, b"old-signed-version", firmato=True, note="Nota dell'avvocato")
    old_path = manager.percorso_documento(case.id, old.id)
    new = add(manager, case, b"new-official-copy", aggiorna_contenuto_portale=True)
    assert old.id == new.id
    assert len(case.documenti) == 1
    assert old_path.read_bytes() == b"old-signed-version"
    assert manager.percorso_documento(case.id, new.id).read_bytes() == b"new-official-copy"
    assert not new.firmato_digitalmente
    assert new.signature_metadata == {}
    assert new.note == "Nota dell'avvocato"
    assert new.versioni[-1].metadati["firmato_digitalmente"] is True
    manager._carica()
    reloaded = manager.get(case.id).documenti[0]
    assert reloaded.hash_sha256 == hashlib.sha256(b"new-official-copy").hexdigest()
    assert reloaded.versioni[-1].metadati["firmato_digitalmente"] is True


def test_refresh_sql_failure_restores_metadata_and_keeps_old_file(storage, monkeypatch):
    manager, case = storage
    old = add(manager, case, b"previous")
    previous = old.to_dict()
    files_before = set(manager.documents_dir.rglob("*"))
    def fail():
        raise RuntimeError("SQL unavailable")
    monkeypatch.setattr(manager, "_salva", fail)
    with pytest.raises(RuntimeError, match="SQL unavailable"):
        add(manager, case, b"new", aggiorna_contenuto_portale=True)
    assert old.to_dict() == previous
    assert set(manager.documents_dir.rglob("*")) == files_before
    assert manager.percorso_documento(case.id, old.id).read_bytes() == b"previous"


def test_refresh_never_updates_another_case(storage):
    manager, case = storage
    old = add(manager, case, b"first-case")
    other = manager.nuovo(titolo="Altro fascicolo", tipo=TipoFascicolo.CIVILE)
    new = add(manager, other, b"other-case", aggiorna_contenuto_portale=True)
    assert old.id != new.id
    assert manager.percorso_documento(case.id, old.id).read_bytes() == b"first-case"


@pytest.mark.parametrize("historical_state", ["different", "missing", "tampered"])
def test_runtime_checks_physical_file_and_repeat_is_idempotent(storage, historical_state):
    manager, case = storage
    old = add(manager, case, b"historical")
    old_path = manager.percorso_documento(case.id, old.id)
    if historical_state == "missing":
        old_path.unlink()
    elif historical_state == "tampered":
        old_path.write_bytes(b"tampered")
    app = Flask(__name__)
    app.config["SEARCH_INDEX"] = "unused"
    noop = lambda *args, **kwargs: None
    runtime = build_fascicoli_runtime(
        app, get_deposito_guidato=noop, get_config_studio=noop,
        get_clienti=noop, get_soggetti=noop, get_utenti=noop,
        audit=noop, sync_pubblica=noop, accoda_ocr=noop,
        encrypt_doc=lambda value: b"ENC" + value,
        decrypt_doc=lambda value: value[3:] if value.startswith(b"ENC") else value,
    )
    payload = b"%PDF-1.4\nnew official bytes\n%%EOF"
    item = {"nome": "Documento.pdf", "contenuto": payload, "id_documento": "33584995"}
    with app.test_request_context():
        g.utente_corrente = SimpleNamespace(username="test")
        result = runtime["importa_documenti_portale_items"](gf=manager, fasc=case, items=[item])
        assert result["integrita_verificata"] is True
        assert result["documenti_aggiornati"] == 1
        assert result["documenti_nuovi"] == 0
        assert result["documenti_riusati"] == 0
        again = runtime["importa_documenti_portale_items"](gf=manager, fasc=case, items=[item])
    assert again["documenti_riusati"] == 1
    assert again["documenti_aggiornati"] == 0
    assert len(case.documenti) == 1
    assert len(old.versioni) == 1
    assert manager.percorso_documento(case.id, old.id).read_bytes() == b"ENC" + payload
