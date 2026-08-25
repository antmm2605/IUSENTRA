from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from pct.aml_screening import EU_FINANCIAL_SANCTIONS_URL, screen_eu_financial_sanctions


def _snapshot(cache_dir, xml: str):
    cache_dir.mkdir(parents=True)
    path = cache_dir / "eu-financial-sanctions.xml"
    path.write_text(xml, encoding="utf-8")
    payload = xml.encode("utf-8")
    (cache_dir / "eu-financial-sanctions.json").write_text(
        json.dumps({
            "source_url": EU_FINANCIAL_SANCTIONS_URL,
            "source_version": "qa",
            "snapshot_hash": hashlib.sha256(payload).hexdigest(),
            "acquired_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }),
        encoding="utf-8",
    )


def test_screening_usa_snapshot_locale_e_segnala_match_da_verificare(tmp_path):
    cache_dir = tmp_path / "screening"
    _snapshot(
        cache_dir,
        "<root><sanctionEntity logicalId='EU-1'><nameAlias wholeName='Mario Rossi'/></sanctionEntity></root>",
    )

    result = screen_eu_financial_sanctions("Rossi Mario", cache_dir=cache_dir)

    assert result["outcome"] == "POTENZIALE_RISCONTRO"
    assert result["matches"][0]["manual_review_required"] is True
    assert result["snapshot_hash"]


def test_screening_senza_match_registra_esito_con_snapshot_verificabile(tmp_path):
    cache_dir = tmp_path / "screening"
    _snapshot(cache_dir, "<root><sanctionEntity logicalId='EU-1'><nameAlias wholeName='Mario Rossi'/></sanctionEntity></root>")

    result = screen_eu_financial_sanctions("Verdi Anna", cache_dir=cache_dir)

    assert result["outcome"] == "NESSUN_RISCONTRO"
    assert result["matches"] == []
