from __future__ import annotations

import logging
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


def test_create_app_configura_logging_json_in_produzione(monkeypatch, tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    monkeypatch.setenv("PCT_ENV", "production")
    cfg = _cfg_web(tmp_path)
    cfg["TESTING"] = False

    create_app(cfg)

    assert any(isinstance(handler.formatter, JsonLogFormatter) for handler in logging.getLogger().handlers)
