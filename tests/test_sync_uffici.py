from __future__ import annotations

from pathlib import Path

from pct.sync_uffici import carica_ultimo_report, esegui_sync_completo


def test_sync_uffici_scrive_report_leggibile_e_valida_resolver_pst(tmp_path, monkeypatch):
    monkeypatch.setattr("pct.sync_uffici.sync_da_pst", lambda: [])
    monkeypatch.setattr("pct.sync_uffici.sync_da_giustizia_amm", lambda: [])
    monkeypatch.setattr("pct.sync_uffici.sync_da_giustizia_tributaria", lambda: [])
    monkeypatch.setattr("pct.sync_uffici.arricchisci_pec_da_ipa", lambda uffici: (uffici, 0))

    cache_path = tmp_path / "uffici" / "uffici_giudiziari.json"
    report = esegui_sync_completo(str(cache_path))
    markdown_path = Path(report["report_markdown_path"])

    assert report["ok"] is True
    assert report["resolver_pst"]["ok"] is True
    assert report["fonti_memorizzate"]
    assert markdown_path.exists()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Report aggiornamento uffici giudiziari" in markdown
    assert "Resolver PST / JPW" in markdown
    assert "PST Ministero della Giustizia" in markdown

    loaded = carica_ultimo_report(str(cache_path))
    assert loaded is not None
    assert loaded["report_markdown_path"] == str(markdown_path)
    assert "Resolver PST / JPW" in loaded["report_markdown"]
