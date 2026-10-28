import hashlib
import json

import pytest

from lex.normativa.lettori_attestati import politica_lettori


def test_senza_politica_non_si_accetta_automaticamente_un_lettore_vecchio(monkeypatch):
    monkeypatch.delenv("PCT_NORMATTIVA_LETTORI_MANIFEST", raising=False)
    monkeypatch.delenv("PCT_NORMATTIVA_LETTORI_MANIFEST_SHA256", raising=False)
    assert politica_lettori("a" * 64).lettori == frozenset(("a" * 64,))


def test_politica_con_percorso_ma_senza_impronta_non_vale_come_approvazione(monkeypatch, tmp_path):
    monkeypatch.setenv("PCT_NORMATTIVA_LETTORI_MANIFEST", str(tmp_path / "policy.json"))
    monkeypatch.delenv("PCT_NORMATTIVA_LETTORI_MANIFEST_SHA256", raising=False)
    with pytest.raises(ValueError, match="SHA atteso"):
        politica_lettori("a" * 64)


def test_flag_verificato_e_lista_vuota_non_attestano_compatibilita(monkeypatch, tmp_path):
    raw=json.dumps({"schema": 1,"lettore_runtime": "a" * 64,"lettori": [],"verificata": True}).encode()
    p=tmp_path / "policy.json";p.write_bytes(raw)
    monkeypatch.setenv("PCT_NORMATTIVA_LETTORI_MANIFEST", str(p))
    monkeypatch.setenv("PCT_NORMATTIVA_LETTORI_MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match="Elenco"):
        politica_lettori("a" * 64)


def test_manifest_modificato_non_resta_fidato_con_lo_stesso_sha(monkeypatch, tmp_path):
    p=tmp_path / "policy.json";raw=b"{}";p.write_bytes(raw + b" ")
    monkeypatch.setenv("PCT_NORMATTIVA_LETTORI_MANIFEST", str(p))
    monkeypatch.setenv("PCT_NORMATTIVA_LETTORI_MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match="alterata"):
        politica_lettori("a" * 64)
