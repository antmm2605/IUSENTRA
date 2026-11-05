from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.structured_logging import JsonLogFormatter, SensitiveDataFilter, mask_sensitive_log_text


def test_mask_sensitive_log_text_redige_cf_email_iban_e_telefono():
    raw = (
        "CF RSSMRA85M01H501Z email mario.rossi@example.it "
        "IBAN IT60X0542811101000000123456 telefono +39 333 1234567"
    )

    masked = mask_sensitive_log_text(raw)

    assert "RSSMRA85M01H501Z" not in masked
    assert "mario.rossi@example.it" not in masked
    assert "IT60X0542811101000000123456" not in masked
    assert "+39 333 1234567" not in masked
    assert masked.count("[REDACTED]") >= 4


def test_sensitive_data_filter_maschera_il_log_record():
    record = logging.LogRecord(
        name="test.logging",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Invio PEC a mario.rossi@example.it per RSSMRA85M01H501Z",
        args=(),
        exc_info=None,
    )

    assert SensitiveDataFilter().filter(record) is True
    assert "mario.rossi@example.it" not in record.msg
    assert "RSSMRA85M01H501Z" not in record.msg
    assert "[REDACTED]" in record.msg


def test_json_log_formatter_usa_orario_italiano():
    record = logging.LogRecord(
        name="test.logging",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Job Lex completato",
        args=(),
        exc_info=None,
    )
    record.created = datetime(2026, 6, 26, 7, 47, tzinfo=timezone.utc).timestamp()

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["timezone"] == "Europe/Rome"
    assert payload["timestamp"].startswith("2026-06-26T09:47:00")
    assert payload["timestamp"].endswith("+02:00")


def test_create_app_configura_logging_json_in_produzione(monkeypatch, tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    monkeypatch.setenv("PCT_ENV", "production")
    cfg = _cfg_web(tmp_path)
    cfg["TESTING"] = False

    create_app(cfg)

    assert any(isinstance(handler.formatter, JsonLogFormatter) for handler in logging.getLogger().handlers)


def test_le_librerie_pdf_non_scrivono_sotto_warning_anche_in_debug():
    # 05/11/2026: l'app isolata della prova di resilienza (TESTING) portava a DEBUG il processo dello scheduler.
    from flask import Flask

    from web.services.structured_logging import configure_structured_logging

    app = Flask(__name__)
    app.config["TESTING"] = True
    configure_structured_logging(app, {})
    for nome in ("pdfminer", "pdfplumber", "PIL", "fontTools"):
        assert logging.getLogger(nome).getEffectiveLevel() >= logging.WARNING


def test_l_app_isolata_della_prova_di_resilienza_non_porta_i_log_a_debug():
    from pct.operational_resilience import _build_isolated_app_config

    cfg = _build_isolated_app_config({}, Path("/tmp/prova-resilienza"))
    assert cfg["TESTING"] is True and cfg["PCT_LOG_LEVEL"] in {"INFO", "WARNING", "ERROR"}
