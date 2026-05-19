from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from pct.cli import cli
from pct.legal_update_diagnostics import (
    run_legal_updates_backfill_diagnostics,
    run_legal_updates_canary,
)
from pct.legal_update_pipeline import build_legal_update_pipeline
from pct.legal_reference_extractor import extract_references, reference_labels


FIXTURES = Path(__file__).parent / "fixtures" / "legal_updates"


class DummyResponse:
    def __init__(self, body: str | bytes, *, url: str, content_type: str = "text/html; charset=utf-8") -> None:
        self.url = url
        self.status_code = 200
        self.headers = {"content-type": content_type, "content-length": str(len(body))}
        if isinstance(body, bytes):
            self.content = body
            self.text = body.decode("utf-8", errors="ignore")
        else:
            self.text = body
            self.content = body.encode("utf-8")

    def iter_content(self, chunk_size: int = 65536):
        yield self.content


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_fixture_legali_offline_minime_presenti():
    expected = {
        "cassazione_index.html",
        "cassazione_civile.html",
        "cassazione_penale.html",
        "cassazione_detail_qsp50194.html",
        "cassazione_qsp50194.pdf",
        "agcom_consultazione_fuori.html",
        "agcom_provvedimento_sanzione.html",
        "inps_feed.xml",
        "curia_feed.xml",
        "openga_ckan.json",
        "anac_documento_utile.html",
        "garante_provvedimento_utile.html",
        "pst_download_tecnico.html",
        "pdf_testuale.pdf",
        "pdf_scansionato_mock.pdf",
    }

    present = {path.name for path in FIXTURES.iterdir()}

    assert expected.issubset(present)
    assert (FIXTURES / "pdf_testuale.pdf").read_bytes().startswith(b"%PDF")
    assert (FIXTURES / "pdf_scansionato_mock.pdf").read_bytes().startswith(b"%PDF")


def test_canary_sicuro_limita_fonte_salva_diagnostica_e_non_pubblica(tmp_path, monkeypatch):
    intelligence_db = tmp_path / "intelligence" / "motori.json"

    def fake_get(url, **_kwargs):
        target = str(url)
        if target.endswith("/it/ultime_sent_ord_e_questioni.page"):
            return DummyResponse(_fixture("cassazione_index.html"), url=target)
        if target.endswith("/it/giurisprudenza_penale.page"):
            return DummyResponse(_fixture("cassazione_penale.html"), url=target)
        if target.endswith("/it/giurisprudenza_civile.page"):
            return DummyResponse(_fixture("cassazione_civile.html"), url=target)
        if "qsp_dettaglio.page?contentId=QSP50194" in target:
            return DummyResponse(_fixture("cassazione_detail_qsp50194.html"), url=target)
        if "_dettaglio.page?contentId=" in target:
            return DummyResponse("<main>Dettaglio con art. 606 c.p.p.</main>", url=target)
        if target.endswith(".pdf"):
            return DummyResponse((FIXTURES / "cassazione_qsp50194.pdf").read_bytes(), url=target, content_type="application/pdf")
        return DummyResponse("<main>pagina non documentale</main>", url=target)

    def fake_analyze(normalized, source_row, **_kwargs):
        return {
            "classification_type": "GIURISPRUDENZA",
            "confidence_score": 0.93,
            "impact_level": "alto",
            "court_name": "Corte di Cassazione",
            "decision_year": "2026",
            "summary_short": "Questione penale pendente.",
            "summary_long": "Questione penale pendente su ricorso e art. 606 c.p.p.",
            "what_changes": "Da usare come monitoraggio giurisprudenziale.",
            "matter_slug": "penale",
        }

    def fake_verify(review, source, *, direct_only=True, **_kwargs):
        assert direct_only is True
        return {
            "ok": True,
            "status": "verified",
            "reason": "Fixture ufficiale letta.",
            "confirmation_count": 1,
            "official_confirmations": 1,
            "confirmations": [
                {
                    "origin": "fonte_ufficiale",
                    "title": review["title"],
                    "source_url": review["source_url"],
                    "attachment_url": "https://www.cortedicassazione.it/documenti/qsp50194.pdf",
                    "attachment_type": "pdf",
                    "sha256": "fixture-sha",
                    "official": True,
                    "context_chars": 140,
                    "excerpt": "PDF ufficiale con art. 606 c.p.p. e R.G. 9966/2026.",
                    "content": "PDF ufficiale collegato alla scheda. Art. 606 c.p.p. e R.G. 9966/2026.",
                    "matched_terms": ["art. 606 c.p.p."],
                }
            ],
            "searched": {"query": review["title"], "queries": [review["title"]]},
        }

    monkeypatch.setattr("pct.legal_update_pipeline.analyze_document", fake_analyze)
    monkeypatch.setattr("pct.legal_update_pipeline.verify_legal_update_against_public_sources", fake_verify)

    report = run_legal_updates_canary(
        intelligence_db=str(intelligence_db),
        source_code="cassazione_ultime_sent_ord_questioni",
        limit=1,
        max_seconds=20,
        no_publish=True,
        direct_only=True,
        save_diagnostics=True,
        request_get=fake_get,
    )

    pipeline = build_legal_update_pipeline(str(intelligence_db))
    latest = pipeline.repository.latest_source_agent_runs()["cassazione_ultime_sent_ord_questioni"]

    assert report["ok"] is True
    assert report["limit"] == 1
    assert report["processed"] == 1
    assert report["autopublished"]["count"] == 0
    assert report["items"][0]["attachment_count"] == 1
    assert report["items"][0]["reference_count"] >= 1
    assert report["items"][0]["question_count"] >= 1
    assert report["items"][0]["quality"]["pdf_found"] is True
    assert latest["trigger_label"] == "canary"
    assert latest["documents_found"] >= 1
    assert latest["autopublished_count"] == 0


def test_canary_invariato_rinfresca_allegato_pdf_normalizzato(tmp_path, monkeypatch):
    intelligence_db = tmp_path / "intelligence" / "motori.json"
    listing = """
    <html><body>
      <a href="/do/gazzetta/downloadPdf?dataPubblicazioneGazzetta=20260518&numeroGazzetta=113&tipoSerie=SG&tipoSupplemento=GU&numeroSupplemento=0&progressivo=0&estensione=pdf&edizione=0">Download PDF</a>
    </body></html>
    """
    verify_calls = {"count": 0}

    def fake_get(url, **_kwargs):
        return DummyResponse(listing, url=str(url))

    def fake_analyze(normalized, source_row, **_kwargs):
        return {
            "classification_type": "COMMENTO",
            "confidence_score": 0.86,
            "impact_level": "medio",
            "summary_short": "Fascicolo ufficiale della Gazzetta Ufficiale.",
            "summary_long": "Fascicolo ufficiale della Gazzetta Ufficiale.",
            "what_changes": "Da leggere come aggiornamento normativo.",
            "matter_slug": "normativa",
        }

    def fake_verify(review, source, **_kwargs):
        verify_calls["count"] += 1
        if verify_calls["count"] == 1:
            return {
                "ok": True,
                "reason": "Pagina ufficiale letta.",
                "confirmation_count": 1,
                "official_confirmations": 1,
                "confirmations": [
                    {
                        "origin": "fonte_acquisita",
                        "source_name": source["name"],
                        "title": review["title"],
                        "url": review["source_url"],
                        "official": True,
                        "excerpt": "Pagina ufficiale.",
                        "content": "Pagina ufficiale.",
                        "context_chars": 17,
                        "matched_terms": [],
                    }
                ],
                "searched": {"web_results": 0, "direct_only": True},
            }
        return {
            "ok": True,
            "reason": "Pagina e PDF ufficiale letti.",
            "confirmation_count": 2,
            "official_confirmations": 2,
            "confirmations": [
                {
                    "origin": "fonte_acquisita",
                    "source_name": source["name"],
                    "title": review["title"],
                    "url": review["source_url"],
                    "official": True,
                    "excerpt": "Pagina ufficiale.",
                    "content": "Pagina ufficiale.",
                    "context_chars": 17,
                    "matched_terms": [],
                },
                {
                    "origin": "allegato_fonte_ufficiale",
                    "source_name": source["name"],
                    "title": "Download PDF",
                    "source_url": review["source_url"],
                    "attachment_url": review["attachments_json"][0]["url"],
                    "attachment_type": "pdf",
                    "sha256": "hash-gazzetta",
                    "official": True,
                    "excerpt": "PDF ufficiale della Gazzetta Ufficiale letto.",
                    "content": "PDF ufficiale della Gazzetta Ufficiale letto.",
                    "context_chars": 48,
                    "matched_terms": [],
                },
            ],
            "searched": {"web_results": 0, "direct_only": True},
        }

    monkeypatch.setattr("pct.legal_update_pipeline.analyze_document", fake_analyze)
    monkeypatch.setattr("pct.legal_update_pipeline.verify_legal_update_against_public_sources", fake_verify)

    first = run_legal_updates_canary(
        intelligence_db=str(intelligence_db),
        source_code="gazzetta_ufficiale",
        limit=1,
        max_seconds=20,
        no_publish=True,
        direct_only=True,
        save_diagnostics=False,
        request_get=fake_get,
    )
    second = run_legal_updates_canary(
        intelligence_db=str(intelligence_db),
        source_code="gazzetta_ufficiale",
        limit=1,
        max_seconds=20,
        no_publish=True,
        direct_only=True,
        save_diagnostics=False,
        request_get=fake_get,
    )

    assert first["processed"] == 1
    assert second["skipped_unchanged"] == 1
    assert second["web_verification_attempts"] == 1
    assert second["verification_attachments_saved"] == 1
    assert second["items"][0]["quality"]["pdf_found"] is True
    assert second["items"][0]["quality"]["text_read"] is True


def test_backfill_diagnostics_arricchisce_riferimenti_e_domande_senza_pubblicare(tmp_path):
    intelligence_db = tmp_path / "intelligence" / "motori.json"
    pipeline = build_legal_update_pipeline(str(intelligence_db))
    pipeline.repository.upsert_sources(
        [
            {
                "name": "Cassazione",
                "code": "cassazione_ultime_sent_ord_questioni",
                "category": "giurisprudenza",
                "base_url": "https://www.cortedicassazione.it/",
                "source_type": "web",
                "trust_class": "A",
                "is_official": True,
                "enabled": True,
                "polling_minutes": 720,
                "parser_type": "html",
            }
        ]
    )
    with pipeline.repository._connect() as conn:
        conn.execute(
            """
            INSERT INTO web_verification_evidence (
                evidence_key, source_code, source_name, query, origin, title,
                source_url, attachment_url, attachment_type, sha256, is_official,
                context_chars, excerpt, content_text, matched_terms_json,
                verification_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "fixture-evidence",
                "cassazione_ultime_sent_ord_questioni",
                "Cassazione",
                "R.G. 9926/2026",
                "fonte_ufficiale",
                "Questione Penale Pendente R.G. 9926/2026",
                "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                "https://www.cortedicassazione.it/documenti/qsp50194.pdf",
                "pdf",
                "fixture-sha",
                1,
                140,
                "PDF ufficiale con R.G. 9966/2026.",
                "Il PDF richiama art. 606 c.p.p., D.Lgs. 150/2022 e ricorso R.G. 9966/2026.",
                "[]",
                "verified",
            ),
        )
        conn.commit()

    refs = run_legal_updates_backfill_diagnostics(
        intelligence_db=str(intelligence_db),
        source_code="cassazione_ultime_sent_ord_questioni",
        missing="references",
        limit=5,
        max_seconds=10,
        no_publish=True,
    )
    questions = run_legal_updates_backfill_diagnostics(
        intelligence_db=str(intelligence_db),
        source_code="cassazione_ultime_sent_ord_questioni",
        missing="questions",
        limit=5,
        max_seconds=10,
        no_publish=True,
    )

    with sqlite3.connect(pipeline.repository.db_path) as conn:
        matched_terms = json.loads(conn.execute("SELECT matched_terms_json FROM web_verification_evidence").fetchone()[0])

    assert refs["updated"] == 1
    assert questions["checked"] == 1
    assert refs["autopublished"]["count"] == 0
    assert any("art. 606 c.p.p." in term for term in matched_terms)
    assert any("?" in term for term in matched_terms)


def test_backfill_diagnostics_supporta_missing_multipli_senza_pubblicare(tmp_path):
    intelligence_db = tmp_path / "intelligence" / "motori.json"
    pipeline = build_legal_update_pipeline(str(intelligence_db))
    pipeline.repository.upsert_sources(
        [
            {
                "name": "Cassazione",
                "code": "cassazione_ultime_sent_ord_questioni",
                "category": "giurisprudenza",
                "base_url": "https://www.cortedicassazione.it/",
                "source_type": "web",
                "trust_class": "A",
                "is_official": True,
                "enabled": True,
                "polling_minutes": 720,
                "parser_type": "html",
            }
        ]
    )
    with pipeline.repository._connect() as conn:
        conn.execute(
            """
            INSERT INTO web_verification_evidence (
                evidence_key, source_code, source_name, query, origin, title,
                source_url, attachment_url, attachment_type, sha256, is_official,
                context_chars, excerpt, content_text, matched_terms_json,
                verification_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "fixture-evidence-multiple",
                "cassazione_ultime_sent_ord_questioni",
                "Cassazione",
                "R.G. 9926/2026",
                "fonte_ufficiale",
                "Questione Penale Pendente R.G. 9926/2026",
                "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                "https://www.cortedicassazione.it/documenti/qsp50194.pdf",
                "pdf",
                "fixture-sha",
                1,
                180,
                "PDF ufficiale con R.G. 9966/2026.",
                "Il PDF richiama art. 606 c.p.p., D.Lgs. 150/2022 e ricorso R.G. 9966/2026.",
                "[]",
                "verified",
            ),
        )
        conn.commit()

    report = run_legal_updates_backfill_diagnostics(
        intelligence_db=str(intelligence_db),
        source_code="cassazione_ultime_sent_ord_questioni",
        missing="references,questions",
        limit=5,
        max_seconds=10,
        no_publish=True,
    )

    assert report["ok"] is True
    assert report["missing_kinds"] == ["references", "questions"]
    assert len(report["reports"]) == 2
    assert report["summary"]["references_added"] > 0
    assert report["summary"]["questions_added"] > 0
    assert report["autopublished"]["count"] == 0


def test_cli_canary_e_backfill_supportano_json_e_limiti(monkeypatch):
    import pct.legal_update_diagnostics as diagnostics
    backfill_calls: list[str] = []

    def fake_canary(**kwargs):
        assert kwargs["source_code"] == "normattiva"
        assert kwargs["limit"] == 1
        assert kwargs["no_publish"] is True
        assert kwargs["publish_mode"] == "off"
        return {"ok": True, "source_code": "normattiva", "processed": 0, "documents_found": 0, "no_publish": True, "errors": []}

    def fake_backfill(**kwargs):
        assert kwargs["missing"] in {"references", "references,questions"}
        assert kwargs["limit"] == 2
        assert kwargs["no_publish"] is True
        backfill_calls.append(kwargs["missing"])
        return {"ok": True, "checked": 0, "updated": 0, "missing": kwargs["missing"]}

    monkeypatch.setattr(diagnostics, "run_legal_updates_canary", fake_canary)
    monkeypatch.setattr(diagnostics, "run_legal_updates_backfill_diagnostics", fake_backfill)
    runner = CliRunner()

    canary = runner.invoke(
        cli,
        ["legal-updates-canary", "--source", "normattiva", "--limit", "1", "--no-publish", "--publish-mode", "off", "--json"],
    )
    backfill = runner.invoke(
        cli,
        [
            "legal-updates-backfill-diagnostics",
            "--source",
            "normattiva",
            "--missing",
            "references",
            "--limit",
            "2",
            "--no-publish",
            "--json",
        ],
    )
    backfill_multiple = runner.invoke(
        cli,
        [
            "legal-updates-backfill-diagnostics",
            "--source",
            "normattiva",
            "--missing",
            "references,questions",
            "--limit",
            "2",
            "--no-publish",
            "--json",
        ],
    )

    assert canary.exit_code == 0, canary.output
    assert json.loads(canary.output)["source_code"] == "normattiva"
    assert backfill.exit_code == 0, backfill.output
    assert json.loads(backfill.output)["missing"] == "references"
    assert backfill_multiple.exit_code == 0, backfill_multiple.output
    assert json.loads(backfill_multiple.output)["missing"] == "references,questions"
    assert backfill_calls == ["references", "references,questions"]


def test_reference_extractor_riconosce_cause_cgue():
    refs = extract_references("Sentenza della Corte nella causa C-155/25 e causa T-24/25.")
    labels = reference_labels(refs, allowed_types=("eu_case",))

    assert "causa C-155/25" in labels
    assert "causa T-24/25" in labels
