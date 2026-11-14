from __future__ import annotations

from pathlib import Path

from pct.sync_uffici import carica_ultimo_report, esegui_sync_completo


def test_sync_uffici_scrive_report_leggibile_e_valida_resolver_pst(tmp_path, monkeypatch):
    monkeypatch.setattr("pct.sync_uffici.sync_da_pst", lambda: [])
    monkeypatch.setattr("pct.sync_uffici.sync_da_giustizia_amm", lambda: [])
    monkeypatch.setattr("pct.sync_uffici.sync_da_giustizia_tributaria", lambda: [])
    monkeypatch.setattr("pct.sync_uffici.arricchisci_pec_da_ipa", lambda uffici: (uffici, 0, {"ok": True}))

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


def test_catalogo_pst_aggiorna_solo_un_codice_gia_identificato():
    from pct.sync_uffici import _merge_uffici, _parse_pst_public_catalog

    def office(code, address):
        return f"""<tr><td><a href="/?actionPath=viewUfficio.action&amp;codiceUfficio={code}">Tribunale di Palmi</a>
            </td><td>Reggio Calabria</td><td>Palmi</td><td>{address}</td></tr>"""

    page = """<table id="ufficio"><thead><tr><th>Descrizione</th><th>Distretto</th><th>Città/Comune</th>
        <th>PEC</th><th>Certificato</th></tr></thead><tbody>"""
    page += office("0800570096", "ufficio@civile.ptel.giustiziacert.it") + office("0800570999", "altro@giustiziacert.it")
    rows = _parse_pst_public_catalog(page + "</tbody></table>")
    merged, changes, new = _merge_uffici([{"codice": "0800570096", "nome": "Tribunale di Palmi", "pec": ""}], rows)
    assert len(merged) == 1 and changes == 1 and new == 0
    assert merged[0]["pec"] == "ufficio@civile.ptel.giustiziacert.it"

def test_ipa_non_dichiara_successo_con_endpoint_irraggiungibile(monkeypatch):
    from pct import sync_uffici

    def unavailable(*args, **kwargs):
        raise ConnectionError("HTTP 404")

    monkeypatch.setattr(sync_uffici, "_get", unavailable)
    uffici, updated, report = sync_uffici.arricchisci_pec_da_ipa([])
    assert uffici == [] and updated == 0
    assert report["ok"] is False
    assert report["categorie_non_disponibili"] == ["GIUSTIZIA", "AM_GIUSTIZIA"]
