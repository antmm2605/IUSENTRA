from datetime import date, timedelta

from pct.fascicoli import GestioneFascicoli, TipoAttivita, TipoFascicolo
from pct.legal_intelligence import (
    GestioneLegalIntelligence,
    costruisci_tracker_fascicolo,
)


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
