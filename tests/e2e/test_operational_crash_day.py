from __future__ import annotations

from pathlib import Path

import pytest

from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.legal_coverage_pipeline import approve_draft, publish_single_draft
from web.services.legal_coverage_surface import build_generator, build_repository, run_action
from web.services.system_health_surface import build_system_health_api_payload
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def test_operational_crash_dirty_data_blocca_duplicati_cf_errati_e_fascicolo_incompleto(tmp_path: Path):
    clienti = GestioneClienti(db_path=str(tmp_path / "clienti" / "anagrafica.json"))
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )

    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Anna",
        cognome="Verdi",
        codice_fiscale="VRDNNA80A41H501Z",
        email="anna.verdi@example.it",
    )

    with pytest.raises(ValueError, match="già presente|gia' presente"):
        clienti.nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Anna",
            cognome="Duplicata",
            codice_fiscale="VRDNNA80A41H501Z",
        )

    with pytest.raises(ValueError, match="Codice fiscale non valido"):
        clienti.nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Mario",
            cognome="Rossi",
            codice_fiscale="ROSSIMARIO",
        )

    with pytest.raises(ValueError, match="titolo del fascicolo"):
        fascicoli.nuovo(
            titolo="   ",
            tipo=TipoFascicolo.CIVILE,
            id_cliente=cliente.id,
            nome_cliente=cliente.nome_completo,
        )

    assert len(clienti.tutti()) == 1
    assert clienti.get(cliente.id) is not None
    assert fascicoli.tutti(stato=None) == []


def test_operational_crash_publish_failure_non_corrompe_db_o_stato_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(
        {
            **_cfg_web(tmp_path),
            "STUDIO_DB": str(tmp_path / "studio.db"),
        }
    )

    with app.app_context():
        repository = build_repository(app)
        assert repository.ping() is True
        run_action("audit")
        run_action("gaps")
        run_action("drafts", limit=5)

        drafts = repository.list_drafts()
        assert drafts
        draft_id = int(drafts[0]["id"])
        approve_draft(
            repository,
            draft_id,
            reviewer="review-operativo",
            review_reason="Bozza approvata per test di failure controllata.",
            review_signature="Avv. Operativo",
        )

        def _broken_apply_generated_sql(sql_payload):
            raise RuntimeError("Database coverage non raggiungibile durante il publish di prova.")

        monkeypatch.setattr(repository, "apply_generated_sql", _broken_apply_generated_sql)

        with pytest.raises(RuntimeError, match="Database coverage non raggiungibile"):
            publish_single_draft(repository, draft_id, apply_to_db=True)

        draft = repository.get_draft(draft_id)
        history = repository.list_published_history(limit=10)
        review_history = repository.list_review_history(draft_id)

    assert draft is not None
    assert draft["status"] == "approved"
    assert history == []
    assert any(str(row.get("review_action") or "") == "approved" for row in review_history)


def test_operational_crash_observability_resta_azionabile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    def _fake_observability_payload(_app):
        return {
            "alerts": [
                {
                    "code": "OCR_QUEUE_OVERFLOW",
                    "normalized_code": "OCR_QUEUE_OVERFLOW",
                    "title": "OCR rallentato",
                    "operator_message": "La coda OCR e' oltre soglia e l'operatore deve intervenire.",
                    "remediation": "Verifica worker OCR o risorse CPU prima di continuare.",
                    "severity": "warning",
                    "family": "OCR",
                    "component": "worker",
                },
                {
                    "code": "TENANT_DB_ERROR",
                    "normalized_code": "TENANT_DB_ERROR",
                    "title": "Database tenant non raggiungibile",
                    "operator_message": "Il backend strutturato dello studio non risponde.",
                    "remediation": "Blocca il publish e controlla la connessione SQL o PostgreSQL.",
                    "severity": "danger",
                    "family": "STORAGE",
                    "component": "database",
                },
            ],
            "storage": {"default_mode": "SQLITE"},
            "scheduler_worker_mode": True,
            "ocr": {"in_coda": 512, "throughput_ultima_ora": 2},
            "providers": {"local_ai": {"runtime": {"status": "ok"}}},
            "error_taxonomy": {
                "OCR": ["OCR_QUEUE_OVERFLOW"],
                "STORAGE": ["TENANT_DB_ERROR"],
            },
        }

    monkeypatch.setattr("web.services.system_health_surface.build_observability_payload", _fake_observability_payload)

    with app.app_context():
        payload = build_system_health_api_payload()

    assert payload["status"] == "error"
    assert payload["ocr"] == "degraded"
    assert payload["db"] == "error"
    assert payload["actions_required"]
    assert payload["actions_required"][0]["message"]
    assert payload["actions_required"][0]["action"]
    assert "OCR" in payload["error_taxonomy"]
