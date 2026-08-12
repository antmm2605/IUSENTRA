import argparse
import importlib.util
import sys
from pathlib import Path

from web.services.reginde_cache_search import search_registro_ppaa_cache

_EXPORT_SAMPLE = b"""
<html><body><div class="tabContent">
<?xml version="1.0"?>
<table>
<row>
<column> AVVOCATURA DELLO STATO DI L&#039;AQUILA </column>
<column> 80006940664 </column>
<column> ADS80006940664 </column>
<column> Amministrazione </column>
<column> ADS.AQ@MAILCERT.AVVOCATURASTATO.IT </column>
</row>
<row>
<column> COMUNE DI ISERNIA (IS) </column>
<column> 00034670943 </column>
<column> 00034670943 </column>
<column> Amministrazione </column>
<column> comuneisernia@pec.it </column>
</row>
</table>
</div></body></html>
"""


def _load_module(name: str):
    tools_dir = Path(__file__).resolve().parents[1] / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(name, tools_dir / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_export_rows_normalizes_columns_and_pec():
    module = _load_module("registro_ppaa_harvest_public")

    rows = module.parse_export_rows(_EXPORT_SAMPLE)

    assert rows == [
        {
            "denominazione": "AVVOCATURA DELLO STATO DI L'AQUILA",
            "codice_fiscale": "80006940664",
            "codice_ente": "ADS80006940664",
            "tipo": "Amministrazione",
            "pec": "ads.aq@mailcert.avvocaturastato.it",
        },
        {
            "denominazione": "COMUNE DI ISERNIA (IS)",
            "codice_fiscale": "00034670943",
            "codice_ente": "00034670943",
            "tipo": "Amministrazione",
            "pec": "comuneisernia@pec.it",
        },
    ]


def test_dedup_rows_removes_cross_query_duplicates():
    module = _load_module("registro_ppaa_harvest_public")

    rows = module.parse_export_rows(_EXPORT_SAMPLE) + module.parse_export_rows(_EXPORT_SAMPLE)

    assert len(rows) == 4
    assert len(module.dedup_rows(rows)) == 2


def test_query_plan_covers_digits_and_vowels():
    module = _load_module("registro_ppaa_harvest_public")

    plan = module.build_query_plan()

    assert [query["codFiscale"] for query in plan[:10]] == list("0123456789")
    assert [query["denominazione"] for query in plan[10:]] == list("aeiou")
    assert all(module.export_url(query).startswith(module.PST_FORM_URL) for query in plan)


def test_harvest_skip_fetch_imports_local_pages_into_cache(tmp_path):
    _load_module("reginde_sync_cache")
    _load_module("registro_ppaa_sync_cache")
    module = _load_module("registro_ppaa_harvest_public")

    pages_dir = tmp_path / "registro_ppaa" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "harvest-cf-0.html").write_bytes(_EXPORT_SAMPLE)

    args = argparse.Namespace(
        output_dir=str(tmp_path / "registro_ppaa"),
        jsonl="",
        delay=0.0,
        timeout=10,
        only="cf-0",
        skip_fetch=True,
        import_cache=True,
    )

    summary = module.harvest(args)

    assert summary["rows_distinct"] == 2
    assert summary["rows_with_pec"] == 2
    assert summary["cache_state"]["stats"]["records_distinct"] == 2
    db_path = tmp_path / "registro_ppaa" / "registro_ppaa_cache.sqlite"
    payload = search_registro_ppaa_cache(db_path, "Comune Isernia")
    assert payload["results"][0]["fontePecSuggerita"] == "registro_ppaa"
