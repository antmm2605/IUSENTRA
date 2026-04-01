from datetime import date, timedelta

from pct.fascicoli import GestioneFascicoli, TipoAttivita, TipoFascicolo
from pct.legal_intelligence import (
    GestioneLegalIntelligence,
    costruisci_tracker_fascicolo,
    fonti_per_query,
)
from pct.normative_tables import FONTI_OPERATIVE, FonteOperativa


class DummyResponse:
    def __init__(self, content: bytes, status_code: int = 200, url: str = "https://example.test"):
        self.content = content
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}


def test_monitor_source_generates_alert_on_change(tmp_path):
    db_path = tmp_path / "intelligence.json"
    gestore = GestioneLegalIntelligence(str(db_path))

    first = gestore.monitor_source(
        "normattiva",
        request_get=lambda *args, **kwargs: DummyResponse(b"versione-1"),
    )
    second = gestore.monitor_source(
        "normattiva",
        request_get=lambda *args, **kwargs: DummyResponse(b"versione-2"),
    )

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["run"]["changed"] is True
    assert any(alert["alert_type"] == "norma_o_testo_modificato" for alert in second["alerts"])


def test_registra_trace_usa_snapshot_ultima_fonte(tmp_path):
    db_path = tmp_path / "intelligence.json"
    gestore = GestioneLegalIntelligence(str(db_path))
    gestore.monitor_source(
        "pst_giustizia",
        request_get=lambda *args, **kwargs: DummyResponse(b"nota-tecnica"),
    )

    trace = gestore.registra_trace_risposta(
        query="Come cambia il deposito PCT con il nuovo XSD?",
        user="admin",
        ai_model="mistral",
    )

    assert trace["query"].startswith("Come cambia")
    assert trace["source_ids"]
    assert trace["source_snapshots"]
    assert trace["source_snapshots"][0]["content_hash"]


def test_monitor_cycle_integra_sync_tabelle_normative(tmp_path):
    db_path = tmp_path / "intelligence.json"
    normative_path = tmp_path / "tabelle_normative.json"
    gestore = GestioneLegalIntelligence(str(db_path), normative_db_path=str(normative_path))

    report = gestore.run_monitor_cycle(
        source_ids=["gazzetta_ufficiale"],
        request_get=lambda *args, **kwargs: DummyResponse(b"gazzetta-v1"),
    )

    assert report["normative_sync"]["processed_tables"] >= 1
    assert "alerts" in report["normative_sync"]
    assert gestore.recent_audit_traces(limit=4)


def test_fonte_in_errore_non_risulta_mai_controllata(tmp_path):
    db_path = tmp_path / "intelligence.json"
    gestore = GestioneLegalIntelligence(str(db_path))

    gestore.monitor_source(
        "cassazione",
        request_get=lambda *args, **kwargs: DummyResponse(b"errore", status_code=500),
    )

    snapshot = gestore.build_dashboard_snapshot(
        fascicoli=[],
        clienti=[],
        appuntamenti=[],
        scadenze=[],
        portali=[],
    )
    row = next(item for item in snapshot["source_rows"] if item["id"] == "cassazione")

    assert row["status"] == "errore"
    assert row["freshness"] == "errore"


def test_recent_alerts_escludono_fonti_risolte(tmp_path):
    db_path = tmp_path / "intelligence.json"
    gestore = GestioneLegalIntelligence(str(db_path))

    gestore.monitor_source(
        "normattiva",
        request_get=lambda *args, **kwargs: DummyResponse(b"errore", status_code=503),
    )
    gestore.monitor_source(
        "normattiva",
        request_get=lambda *args, **kwargs: DummyResponse(b"ok", status_code=200),
    )

    alerts = gestore.recent_alerts(limit=8)

    assert not any(
        alert["source_id"] == "normattiva" and alert["alert_type"] == "fonte_non_raggiungibile"
        for alert in alerts
    )


def test_sync_normativo_usa_fallback_per_fonte_operativa(tmp_path):
    originale = FONTI_OPERATIVE["cu_viterbo"]
    FONTI_OPERATIVE["cu_viterbo"] = FonteOperativa(
        code=originale.code,
        title=originale.title,
        url="https://primary.example.test/cu",
        note=originale.note,
        monitor_urls=["https://backup.example.test/cu"],
        change_detection="availability_only",
    )
    try:
        db_path = tmp_path / "intelligence.json"
        normative_path = tmp_path / "tabelle_normative.json"
        gestore = GestioneLegalIntelligence(str(db_path), normative_db_path=str(normative_path))

        def fake_get(url, **kwargs):
            if "primary.example.test" in url:
                return DummyResponse(b"ko", status_code=503, url=url)
            return DummyResponse(b"ok", status_code=200, url=url)

        report = gestore.sync_normative_tables(
            source_ids=["normattiva", "gazzetta_ufficiale"],
            request_get=fake_get,
        )
        checks = gestore.normative_tables.source_checks()

        assert report["processed_tables"] >= 1
        assert checks["cu_viterbo"]["status"] == "ok"
        assert checks["cu_viterbo"]["final_url"] == "https://backup.example.test/cu"
        assert checks["cu_viterbo"]["comparison_mode"] == "availability_only"
    finally:
        FONTI_OPERATIVE["cu_viterbo"] = originale


def test_dashboard_snapshot_espone_contatore_riferimenti_normativi(tmp_path):
    db_path = tmp_path / "intelligence.json"
    normative_path = tmp_path / "tabelle_normative.json"
    gestore = GestioneLegalIntelligence(str(db_path), normative_db_path=str(normative_path))

    snapshot = gestore.build_dashboard_snapshot(
        fascicoli=[],
        clienti=[],
        appuntamenti=[],
        scadenze=[],
        portali=[],
    )

    assert snapshot["headline"]["riferimenti_normativi"] >= 8
    assert snapshot["normative_tables"]["riferimenti_normativi"]


def test_dashboard_snapshot_include_registro_mediazione(tmp_path):
    db_path = tmp_path / "intelligence.json"
    gestore = GestioneLegalIntelligence(str(db_path))

    snapshot = gestore.build_dashboard_snapshot(
        fascicoli=[],
        clienti=[],
        appuntamenti=[],
        scadenze=[],
        portali=[],
    )

    row = next(item for item in snapshot["source_rows"] if item["id"] == "registro_mediazione")

    assert row["official_url"].endswith("mg_3_4_15.page")
    assert "mediazione" in row["nome"].lower()


def test_sync_registro_mediazione_elenco_popola_cache(tmp_path):
    db_path = tmp_path / "intelligence.json"
    normative_path = tmp_path / "tabelle_normative.json"
    gestore = GestioneLegalIntelligence(str(db_path), normative_db_path=str(normative_path))

    html = b"""
    <html><body>
      <table>
        <tr>
          <th>N. iscrizione</th>
          <th>Organismo</th>
          <th>Tipo</th>
          <th>Sede</th>
          <th>PEC</th>
        </tr>
        <tr>
          <td>101</td>
          <td>Camera Arbitrale Demo</td>
          <td>Pubblico</td>
          <td>Roma</td>
          <td>demo1@pec.example.test</td>
        </tr>
        <tr>
          <td>202</td>
          <td>Organismo Privato Demo</td>
          <td>Privato</td>
          <td>Milano</td>
          <td>demo2@pec.example.test</td>
        </tr>
      </table>
    </body></html>
    """

    result = gestore.sync_registro_mediazione_elenco(
        request_get=lambda *args, **kwargs: DummyResponse(html, url="https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX"),
    )
    snapshot = gestore.mediazione_registry_snapshot(city="Milano")

    assert result["ok"] is True
    assert result["rows"] == 2
    assert snapshot["total_rows"] == 2
    assert snapshot["filtered_rows"] == 1
    assert snapshot["rows"][0]["name"] == "Organismo Privato Demo"
    assert snapshot["data_origin"] == "live_registry"


def test_sync_normative_tables_include_registro_mediazione_snapshot(tmp_path):
    db_path = tmp_path / "intelligence.json"
    normative_path = tmp_path / "tabelle_normative.json"
    gestore = GestioneLegalIntelligence(str(db_path), normative_db_path=str(normative_path))

    html = b"""
    <html><body>
      <table>
        <tr><th>N. iscrizione</th><th>Organismo</th><th>Tipo</th><th>Sede</th></tr>
        <tr><td>301</td><td>Organismo Test</td><td>Pubblico</td><td>Napoli</td></tr>
      </table>
    </body></html>
    """

    report = gestore.sync_normative_tables(
        source_ids=["registro_mediazione"],
        request_get=lambda url, **kwargs: DummyResponse(
            html if "ALBOORGANISMIMEDIAZIONE" in url else b"pagina-info",
            url=url,
        ),
    )

    assert "mediazione_registry" in report
    assert report["mediazione_registry"]["ok"] is True
    assert report["mediazione_registry"]["rows"] == 1


def test_import_registro_mediazione_snapshot_popola_cache(tmp_path):
    db_path = tmp_path / "intelligence.json"
    normative_path = tmp_path / "tabelle_normative.json"
    gestore = GestioneLegalIntelligence(str(db_path), normative_db_path=str(normative_path))

    html = """
    <html><body>
      <table>
        <tr><th>N. iscrizione</th><th>Organismo</th><th>Tipo</th><th>Sede</th><th>PEC</th></tr>
        <tr><td>401</td><td>Organismo Importato</td><td>Privato</td><td>Bologna</td><td>import@pec.example.test</td></tr>
      </table>
    </body></html>
    """

    report = gestore.import_registro_mediazione_snapshot(html, filename="registro.html")
    snapshot = gestore.mediazione_registry_snapshot()

    assert report["ok"] is True
    assert report["imported"] is True
    assert snapshot["total_rows"] == 1
    assert snapshot["data_origin"] == "manual_snapshot"
    assert snapshot["data_origin_label"] == "Snapshot HTML ufficiale importato"
    assert snapshot["import_filename"] == "registro.html"


def test_sync_registro_mediazione_elenco_preserva_cache_se_portale_non_raggiungibile(tmp_path):
    db_path = tmp_path / "intelligence.json"
    normative_path = tmp_path / "tabelle_normative.json"
    gestore = GestioneLegalIntelligence(str(db_path), normative_db_path=str(normative_path))

    gestore.import_registro_mediazione_snapshot(
        """
        <html><body>
          <table>
            <tr><th>N. iscrizione</th><th>Organismo</th><th>Tipo</th><th>Sede</th></tr>
            <tr><td>501</td><td>Organismo Cache</td><td>Pubblico</td><td>Roma</td></tr>
          </table>
        </body></html>
        """,
        filename="cache.html",
    )

    info_html = b"""
    <html><body>
      <p>Per motivi tecnici, al momento non e possibile accedere</p>
      <p>Registro degli organismi di mediazione</p>
    </body></html>
    """

    def fake_get(url, **kwargs):
        if "mg_3_4_15.page" in url:
            return DummyResponse(info_html, url=url)
        return DummyResponse(b"ko", status_code=503, url=url)

    report = gestore.sync_registro_mediazione_elenco(request_get=fake_get)
    snapshot = gestore.mediazione_registry_snapshot()

    assert report["ok"] is True
    assert report["used_cached_rows"] is True
    assert snapshot["total_rows"] == 1
    assert snapshot["rows"][0]["name"] == "Organismo Cache"
    assert "motivi tecnici" in snapshot["technical_notice"].lower()


def test_fonti_per_query_mediazione_risolvono_la_fonte_ufficiale():
    assert "registro_mediazione" in fonti_per_query("verifica organismo di mediazione iscritto")


def test_tracker_fascicolo_mostra_avanzamento_e_chiusura(tmp_path):
    gestore = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )
    fascicolo = gestore.nuovo(
        titolo="Rossi c/ Bianchi",
        tipo=TipoFascicolo.CIVILE,
        id_cliente="CLI-1",
        nome_cliente="Mario Rossi",
    )
    gestore.aggiungi_attivita(
        fascicolo.id,
        TipoAttivita.UDIENZA,
        (date.today() + timedelta(days=10)).isoformat(),
        "Prima udienza",
    )
    fascicolo = gestore.get(fascicolo.id)
    tracker = costruisci_tracker_fascicolo(fascicolo)

    assert tracker["percent"] >= 75
    assert tracker["next_event"]

    gestore.definisci(fascicolo.id, esito_finale="FAVOREVOLE", motivo="Sentenza")
    fascicolo_def = gestore.get(fascicolo.id)
    tracker_def = costruisci_tracker_fascicolo(fascicolo_def)

    assert tracker_def["percent"] == 100
    assert tracker_def["current_label"] == "Pratica definita"
