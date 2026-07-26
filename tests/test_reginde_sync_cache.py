import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "reginde_sync_cache.py"
    spec = importlib.util.spec_from_file_location("reginde_sync_cache", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_page_extracts_subject_fields():
    module = _load_module()
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
      <env:Body>
        <ns2:elencoPaginatoSoggettiResponse xmlns:ns2="http://www.giustizia.it/serviziTelematici/reginde/interrogazioniExt">
          <return>
            <soggetto>
              <codFisc>RSSMRA80A01H501U</codFisc>
              <nome>Mario</nome>
              <cognome>Rossi</cognome>
              <pec>studio@example.pec.it</pec>
              <stato>ATTIVO</stato>
              <visibile>true</visibile>
            </soggetto>
          </return>
        </ns2:elencoPaginatoSoggettiResponse>
      </env:Body>
    </env:Envelope>"""

    records, response_hash = module.parse_page(xml, page_start=1)

    assert len(records) == 1
    record = records[0]
    assert len(response_hash) == 64
    assert record["codici_fiscali"] == ["RSSMRA80A01H501U"]
    assert record["pec"] == ["studio@example.pec.it"]
    assert record["nome_completo"] == "Mario Rossi"
    assert record["stato"] == "ATTIVO"
    assert record["visibile"] is True
    assert len(record["record_key"]) == 64


def test_parse_page_prefers_professional_cf_and_explicit_pec_over_nested_order_data():
    module = _load_module()
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
      <env:Body>
        <ns2:elencoPaginatoSoggettiResponse xmlns:ns2="http://www.giustizia.it/serviziTelematici/reginde/interrogazioniExt">
          <return>
            <soggetto>
              <codiceFiscale>80010790055</codiceFiscale>
              <descrizione>ODA ASTI</descrizione>
              <email>consiglio@ordineavvocatiasti.eu</email>
              <persona>
                <codFisc>BRSMRT71T50A479N</codFisc>
                <nome>Marta</nome>
                <cognome>Barsotti</cognome>
                <pec>barsotti.marta@ordineavvocatiasti.eu</pec>
                <email>barsotti.avv.marta@gmail.com</email>
                <ruolo>avvocato</ruolo>
              </persona>
              <stato>attivo</stato>
              <visibile>true</visibile>
            </soggetto>
          </return>
        </ns2:elencoPaginatoSoggettiResponse>
      </env:Body>
    </env:Envelope>"""

    records, _response_hash = module.parse_page(xml, page_start=1)

    assert len(records) == 1
    record = records[0]
    assert record["codici_fiscali"] == ["BRSMRT71T50A479N"]
    assert record["pec"] == ["barsotti.marta@ordineavvocatiasti.eu"]
    assert record["nome_completo"] == "Marta Barsotti"
    assert record["denominazione"] == "ODA ASTI"


def test_cache_writer_deduplicates_records(tmp_path):
    module = _load_module()
    cache = module.CacheWriter(tmp_path)
    try:
        record = {
            "record_key": "a" * 64,
            "denominazione": "Studio test",
            "nome_completo": "",
            "codici_fiscali": ["RSSMRA80A01H501U"],
            "partite_iva": [],
            "pec": ["studio@example.pec.it"],
            "ruolo": "AVVOCATO",
            "stato": "ATTIVO",
            "visibile": True,
            "response_sha256": "b" * 64,
        }

        cache.upsert_records([record], page_start=1, seen_at="2026-07-25T22:00:00+02:00")
        cache.upsert_records([record], page_start=51, seen_at="2026-07-25T22:05:00+02:00")

        stats = cache.stats()
        assert stats["records_distinct"] == 1
        row = cache.conn.execute("SELECT last_page_start, record_json FROM records").fetchone()
        assert row[0] == 51
        assert json.loads(row[1])["pec"] == ["studio@example.pec.it"]
        if cache.fts_available:
            fts_row = cache.conn.execute("SELECT COUNT(*) FROM records_fts WHERE records_fts MATCH ?", ("studio*",)).fetchone()
            assert fts_row[0] == 1
    finally:
        cache.close()


def test_soap_body_uses_one_based_page_parameters():
    module = _load_module()

    body = module.soap_body_for_page(101, 50)

    assert "elencoPaginatoSoggetti" in body
    assert "<da>101</da>" in body
    assert "<count>50</count>" in body
