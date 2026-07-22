from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_feature_flags import _app
from web.services.feature_flags import (
    LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG,
    LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG,
)
from web.services.notification_presidia_runtime import apply_legal_notification_presidia_effective_flags


class _ConfigRepo:
    def __init__(self, enabled: bool, mode: str) -> None:
        self.enabled = enabled
        self.mode = mode

    def get_config(self):
        return {"rollout_enabled": self.enabled, "rollout_mode": self.mode}


def test_presidio_flags_spenti_non_aprono_repository() -> None:
    called = False

    def factory():
        nonlocal called
        called = True
        raise AssertionError("repository non deve essere aperto a flag globale spento")

    flags = apply_legal_notification_presidia_effective_flags(
        {LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG: False, LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG: False},
        repository_factory=factory,
    )

    assert flags[LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG] is False
    assert flags[LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG] is False
    assert called is False


def test_presidio_flags_effettivi_richiedono_tenant_primary() -> None:
    flags = apply_legal_notification_presidia_effective_flags(
        {LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG: True, LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG: True},
        repository_factory=lambda: _ConfigRepo(True, "primary"),
    )
    assert flags[LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG] is True
    assert flags[LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG] is True

    shadow = apply_legal_notification_presidia_effective_flags(
        {LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG: True, LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG: True},
        repository_factory=lambda: _ConfigRepo(True, "shadow"),
    )
    assert shadow[LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG] is True
    assert shadow[LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG] is False


def test_repository_presidi_usa_pec_audit_sqlite_anche_con_core_postgresql(tmp_path: Path) -> None:
    from web.services.notification_presidia_runtime import build_notification_presidio_repository

    app = Flask(__name__)
    app.config.update(TESTING=True, MULTI_TENANT=False)
    pec_audit_db = tmp_path / "tenant-pg" / "email" / "pec_audit.sqlite"
    fake_core_database = SimpleNamespace(
        normalized_mode="POSTGRESQL",
        host="postgres-core.internal",
        db_name="iusentra_core",
        utente="iusentra",
        password="segreto-test",
        porta_effettiva=5432,
        ssl=True,
    )
    with app.test_request_context("/"):
        g.data_paths = {"PEC_AUDIT_DB": str(pec_audit_db)}
        g.api_tenant_slug = "studio-postgresql"
        g.tenant = SimpleNamespace(slug="studio-postgresql", database=fake_core_database)
        repository = build_notification_presidio_repository()

    assert repository.backend_kind == "sqlite"
    assert repository.postgres_dsn == ""
    assert repository.db_path == pec_audit_db


def _seed_presidio(tmp_path: Path) -> str:
    from pct.pec_notification_presidio import NotificationPresidioRepository, NotificationPresidioService

    repo = NotificationPresidioRepository(tmp_path / "email" / "pec_audit.sqlite", tenant_id="default")
    repo.save_config({"rollout_enabled": True, "rollout_mode": "primary"}, actor="pytest")
    result = NotificationPresidioService(repo).create_candidate(
        {
            "fascicolo_id": "FASC-1",
            "source_message_id": "<ordinanza-1@pec.test>",
            "trigger_type": "EXPLICIT_NOTIFICATION_ORDER",
            "notification_case": "notifica_ordinanza",
            "channel": "pec",
            "rulepack_version": "legal-notification-rulepack-v1",
            "legal_basis": [{"id": "art.170.cpc", "label": "Art. 170 c.p.c."}],
            "documents": [
                {
                    "source_message_id": "<ordinanza-1@pec.test>",
                    "fascicolo_document_id": "DOC-1",
                    "document_role": "office_pec_copy",
                    "original_filename": "Ordinanza.pdf",
                    "content_sha256": "a" * 64,
                }
            ],
            "recipients": [
                {
                    "name": "Mario Rossi",
                    "role": "Controparte",
                    "pec_address": "mario.rossi@pec.example.it",
                    "fiscal_id": "RSSMRA80A01H501Z",
                }
            ],
            "source_effective_at": "2026-07-20T09:00:00+02:00",
            "priority": "P1",
            "confidence": 0.99,
            "detection_reason": "Ordine espresso rilevato nella PEC di cancelleria.",
        }
    )
    return str(result["id"])


def test_presidio_api_lista_projection_e_payload_pubblico(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        flags={LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG: True, LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG: True},
    )
    _crea_operatore(app)
    _seed_presidio(tmp_path)

    with app.test_client() as client:
        _login(client)
        response = client.get("/api/v1/ui/notifiche-legali/presidi?status=DETECTED,NEEDS_REVIEW&limit=10")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["items"][0]["practice"]["id"] == "FASC-1"
    assert payload["items"][0]["recipients"][0]["name"] == "Mario Rossi"
    raw = response.get_data(as_text=True)
    assert "tenant_id" not in raw
    assert "studio_id" not in raw
    assert "filesystem_path" not in raw


def test_presidio_api_corregge_conferma_errata_con_motivazione_e_cronologia(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        flags={LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG: True, LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG: True},
    )
    _crea_operatore(app)
    presidio_id = _seed_presidio(tmp_path)

    with app.test_client() as client:
        _login(client)
        confirmed = client.post(
            f"/api/v1/ui/notifiche-legali/presidi/{presidio_id}/confirm",
            json={},
        )
        revised = client.post(
            f"/api/v1/ui/notifiche-legali/presidi/{presidio_id}/revise-decision",
            json={
                "target_status": "NEEDS_REVIEW",
                "reason": "La conferma è stata selezionata per errore e il caso deve essere riesaminato.",
            },
        )
        transitions = client.get(
            f"/api/v1/ui/notifiche-legali/presidi/{presidio_id}/transitions"
        )

    assert confirmed.status_code == 200
    assert confirmed.get_json()["presidio"]["status"] == "NOTIFICATION_CONFIRMED"
    assert revised.status_code == 200
    assert revised.get_json()["presidio"]["status"] == "NEEDS_REVIEW"
    assert transitions.status_code == 200
    [correction] = [
        item for item in transitions.get_json()["items"]
        if item["next_status"] == "NEEDS_REVIEW"
    ]
    assert correction["actor_label"]
    assert correction["occurred_at"]
    assert correction["reason"].startswith("La conferma è stata selezionata")


def test_presidio_api_non_riapre_decisione_se_esiste_prova_di_invio(tmp_path: Path) -> None:
    from pct.pec_notification_presidio import NotificationPresidioRepository

    app = _app(
        tmp_path,
        flags={LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG: True, LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG: True},
    )
    _crea_operatore(app)
    presidio_id = _seed_presidio(tmp_path)
    repo = NotificationPresidioRepository(tmp_path / "email" / "pec_audit.sqlite", tenant_id="default")
    repo.transition(
        presidio_id,
        "NOTIFICATION_CONFIRMED",
        actor="pytest",
        reason="Notifica necessaria confermata dopo la verifica.",
        evidence={"source": "pytest"},
        idempotency_key="pytest-confirm",
    )
    repo.upsert_document(
        presidio_id,
        {
            "document_role": "sent_pec",
            "original_filename": "PEC-inviata.eml",
            "content_sha256": "b" * 64,
        },
    )

    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/api/v1/ui/notifiche-legali/presidi/{presidio_id}/revise-decision",
            json={
                "target_status": "NOT_REQUIRED",
                "reason": "La decisione precedente deve essere corretta dopo un nuovo controllo.",
            },
        )

    assert response.status_code == 400
    assert "prove di invio" in response.get_json()["message"]
    assert repo.get_presidio(presidio_id)["status"] == "NOTIFICATION_CONFIRMED"
