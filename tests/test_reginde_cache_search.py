import json
import sqlite3

from web.services.reginde_cache_search import (
    default_reginde_cache_db_path,
    default_registro_ppaa_cache_db_path,
    search_reginde_cache,
    search_registro_ppaa_cache,
)


def _create_cache(path):
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE records (
            record_key TEXT PRIMARY KEY,
            denominazione TEXT,
            nome_completo TEXT,
            codici_fiscali_json TEXT NOT NULL,
            partite_iva_json TEXT NOT NULL,
            pec_json TEXT NOT NULL,
            ruolo TEXT,
            stato TEXT,
            visibile INTEGER NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            first_page_start INTEGER NOT NULL,
            last_page_start INTEGER NOT NULL,
            response_sha256 TEXT NOT NULL,
            record_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO records (
            record_key, denominazione, nome_completo, codici_fiscali_json,
            partite_iva_json, pec_json, ruolo, stato, visibile,
            first_seen_at, last_seen_at, first_page_start, last_page_start,
            response_sha256, record_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "record-avvocatura-milano",
            "AVVOCATURA DELLO STATO DI MILANO",
            "",
            json.dumps(["97021490152"]),
            json.dumps([]),
            json.dumps(["ads.mi@mailcert.avvocaturastato.it"]),
            "ente",
            "attivo",
            1,
            "2026-07-25T22:29:27+02:00",
            "2026-07-25T22:29:27+02:00",
            1,
            1,
            "hash",
            json.dumps({"source": "reginde"}, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def test_default_reginde_cache_path_uses_pct_data_root(monkeypatch, tmp_path):
    monkeypatch.setenv("PCT_DATA_ROOT", str(tmp_path))

    assert default_reginde_cache_db_path() == tmp_path / "local" / "reginde" / "reginde_cache.sqlite"
    assert default_registro_ppaa_cache_db_path() == tmp_path / "local" / "registro_ppaa" / "registro_ppaa_cache.sqlite"


def test_reginde_cache_missing_returns_empty_payload(tmp_path):
    payload = search_reginde_cache(tmp_path / "missing.sqlite", "milano")

    assert payload["available"] is False
    assert payload["results"] == []
    assert "non ancora sincronizzato" in payload["message"]


def test_reginde_cache_short_query_does_not_search(tmp_path):
    db_path = tmp_path / "reginde_cache.sqlite"
    _create_cache(db_path)

    payload = search_reginde_cache(db_path, "mi")

    assert payload["available"] is True
    assert payload["results"] == []
    assert "almeno 3 caratteri" in payload["message"]


def test_reginde_cache_search_returns_notification_recipient(tmp_path):
    db_path = tmp_path / "reginde_cache.sqlite"
    _create_cache(db_path)

    payload = search_reginde_cache(db_path, "Avvocatura Milano")

    assert payload["available"] is True
    assert payload["records"] == 1
    assert payload["message"] == ""
    assert payload["results"][0]["nome"] == "AVVOCATURA DELLO STATO DI MILANO"
    assert payload["results"][0]["codiceFiscalePiva"] == "97021490152"
    assert payload["results"][0]["pec"] == "ads.mi@mailcert.avvocaturastato.it"
    assert payload["results"][0]["fontePecSuggerita"] == "reginde"
    assert payload["results"][0]["ruolo"] == "pa"


def test_registro_ppaa_cache_search_returns_public_administration_recipient(tmp_path):
    db_path = tmp_path / "registro_ppaa_cache.sqlite"
    _create_cache(db_path)

    payload = search_registro_ppaa_cache(db_path, "Avvocatura Milano")

    assert payload["available"] is True
    assert payload["records"] == 1
    assert payload["message"] == ""
    assert payload["results"][0]["nome"] == "AVVOCATURA DELLO STATO DI MILANO"
    assert payload["results"][0]["codiceFiscalePiva"] == "97021490152"
    assert payload["results"][0]["pec"] == "ads.mi@mailcert.avvocaturastato.it"
    assert payload["results"][0]["fontePecSuggerita"] == "registro_ppaa"
    assert payload["results"][0]["ruoloPratica"] == "Registro PP.AA."
    assert payload["results"][0]["ruolo"] == "pa"
    assert payload["results"][0]["cacheSource"] == "registro_ppaa_cache_locale"
