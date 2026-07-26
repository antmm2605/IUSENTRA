import argparse
import importlib.util
import json
import sys
from pathlib import Path

from web.services.reginde_cache_search import search_registro_ppaa_cache


def _load_module():
    tools_dir = Path(__file__).resolve().parents[1] / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    reginde_path = tools_dir / "reginde_sync_cache.py"
    reginde_spec = importlib.util.spec_from_file_location("reginde_sync_cache", reginde_path)
    reginde_module = importlib.util.module_from_spec(reginde_spec)
    assert reginde_spec.loader is not None
    sys.modules[reginde_spec.name] = reginde_module
    reginde_spec.loader.exec_module(reginde_module)

    module_path = tools_dir / "registro_ppaa_sync_cache.py"
    spec = importlib.util.spec_from_file_location("registro_ppaa_sync_cache", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_record_from_mapping_normalizes_public_administration_fields():
    module = _load_module()

    record = module.record_from_mapping({
        "denominazione": " Avvocatura Distrettuale dello Stato di Milano ",
        "codice_fiscale": " 97021490152 ",
        "pec": " ADS.MI@MAILCERT.AVVOCATURASTATO.IT ",
    }, index=1, response_sha256="a" * 64)

    assert record["source"] == "registro_ppaa"
    assert record["denominazione"] == "Avvocatura Distrettuale dello Stato di Milano"
    assert record["codici_fiscali"] == ["97021490152"]
    assert record["pec"] == ["ads.mi@mailcert.avvocaturastato.it"]
    assert record["ruolo"] == "PPAA"
    assert record["visibile"] is True
    assert len(record["record_key"]) == 64


def test_import_file_populates_sql_cache_without_pst_call(tmp_path):
    module = _load_module()
    import_file = tmp_path / "ppaa.json"
    import_file.write_bytes(("\ufeff" + json.dumps({
        "records": [{
            "denominazione": "AVVOCATURA DELLO STATO DI MILANO",
            "codice_fiscale": "97021490152",
            "pec": "ads.mi@mailcert.avvocaturastato.it",
        }]
    }, ensure_ascii=False)).encode("utf-8"))

    args = argparse.Namespace(
        output_dir=str(tmp_path / "registro_ppaa"),
        query=[],
        import_file=[str(import_file)],
        reset=False,
        status=False,
        request_timeout=90,
        cert_thumbprint="",
        prefer_cf="",
        pin_env="",
        pin_stdin=False,
    )

    result = module.run(args)

    db_path = tmp_path / "registro_ppaa" / "registro_ppaa_cache.sqlite"
    assert db_path.exists()
    assert result["source"] == "registro_ppaa"
    assert result["imports"] == 1
    assert result["stats"]["records_distinct"] == 1
    payload = search_registro_ppaa_cache(db_path, "Avvocatura Milano")
    assert payload["results"][0]["fontePecSuggerita"] == "registro_ppaa"
    assert payload["results"][0]["ruolo"] == "pa"
