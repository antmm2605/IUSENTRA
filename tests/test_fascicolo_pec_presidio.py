"""Le PEC del presidio per un fascicolo: collegate, per numero di ruolo, per nome del cliente."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

from pct.pec_pipeline import PecAuditRepository
from web.services.fascicolo_pec_presidio import chiavi_cliente, chiavi_ruolo, messaggi_pec_per_fascicolo
from web.services.pec_pipeline_runtime import repository_for_current_request


def _repository(tmp_path: Path) -> PecAuditRepository:
    repository = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    repository.ensure_schema()
    return repository


def _inserisci(repository: PecAuditRepository, id_messaggio: str, subject: str, *, linked: str = "", received: str = "2026-09-10T10:00:00", quality: str = "verde") -> None:
    metadata = {"headers": {"subject": subject, "from": "tribunale.torino@civile.ptel.giustiziacert.it", "to": "studio@pec.it"}}
    with repository.connect() as conn:
        conn.execute(
            "INSERT INTO pec_messages (id, tenant_id, account_email, folder, mime_sha256, mime_size, original_mime, received_at, ingested_at, status, quality_status, signature_status, linked_fascicolo_id, metadata_json) "
            "VALUES (?, 'default', 'studio@pec.it', 'INBOX', ?, 10, X'00', ?, ?, 'parsed', ?, 'valida', ?, ?)",
            (id_messaggio, f"sha-{id_messaggio}", received, received, quality, linked, json.dumps(metadata)),
        )
        conn.commit()


def test_chiavi_di_ricerca_per_ruolo_e_cliente():
    assert chiavi_ruolo("1234", "2026") == ["1234/2026", "1234/26", "1234-2026", "RG 1234", "R.G. 1234", "n. 1234"]
    assert chiavi_ruolo("", "2026") == []
    assert chiavi_cliente("Anna Bianchi") == ["Anna Bianchi", "Bianchi Anna"]
    assert chiavi_cliente("Anna") == []  # un nome solo pescherebbe omonimi


def test_messaggi_per_fascicolo_con_le_tre_corrispondenze(tmp_path: Path):
    repository = _repository(tmp_path)
    _inserisci(repository, "M1", "Comunicazione di cancelleria: udienza", linked="F1", received="2026-09-01T09:00:00")
    _inserisci(repository, "M2", "Avviso relativo al procedimento n. 777/2026", received="2026-09-02T09:00:00", quality="giallo")
    _inserisci(repository, "M3", "Documenti per Anna Bianchi", received="2026-09-03T09:00:00")
    _inserisci(repository, "M4", "Altra pratica 999/2026", received="2026-09-04T09:00:00")
    with repository.connect() as conn:
        conn.execute("INSERT INTO pec_parsed_versions (id, message_id, version, parser_version, parsed_json, parsed_sha256, created_at) VALUES ('v1','M2',1,'1','{}','p1','2026-09-02T09:05:00')")
        conn.execute("INSERT INTO pec_legal_events (id, tenant_id, message_id, parsed_version_id, rulepack_version, family, primary_event, priority, confidence, human_review_required, event_json, event_sha256, created_at) VALUES ('E1','default','M2','v1','1','cancelleria','fissazione_udienza','alta',0.9,0,'{}','h1','2026-09-02T09:05:00')")
        conn.execute("INSERT INTO pec_legal_deadlines (id, tenant_id, legal_event_id, deadline_type, norm_ref, dies_a_quo_type, dies_a_quo_date, duration_value, duration_unit, direction, peremptory, deterministic_status, scadenziario_id, human_review_required, evidence_json, created_at) VALUES ('D1','default','E1','memoria_171_ter','art. 171-ter c.p.c.','comunicazione','2026-09-02',40,'days','backward',1,'computed','',0,'[]','2026-09-02T09:05:00')")
        conn.execute("INSERT INTO pec_legal_hearings (id, tenant_id, legal_event_id, hearing_date, hearing_time, mode, human_review_required, evidence_json, created_at) VALUES ('H1','default','E1','2026-11-05','09:30','presenza',0,'[]','2026-09-02T09:05:00')")
        conn.commit()
    fascicolo = SimpleNamespace(id="F1", numero_rg="777", anno_rg=2026, nome_cliente="Anna Bianchi")

    messaggi = messaggi_pec_per_fascicolo(fascicolo, repository=repository)

    assert [voce["id"] for voce in messaggi] == ["M3", "M2", "M1"]
    per_id = {voce["id"]: voce for voce in messaggi}
    assert per_id["M1"]["corrispondenza"] == "collegamento" and per_id["M1"]["collegata"] is True
    assert per_id["M2"]["corrispondenza"] == "rg" and per_id["M2"]["quality_status"] == "giallo"
    assert per_id["M3"]["corrispondenza"] == "cliente"
    assert per_id["M2"]["eventi"][0]["primary_event"] == "fissazione_udienza"
    assert per_id["M2"]["termini"][0]["norm_ref"] == "art. 171-ter c.p.c." and per_id["M2"]["termini"][0]["scadenziario_id"] == ""
    assert per_id["M2"]["udienze"][0]["hearing_date"] == "2026-11-05"
    assert per_id["M1"]["subject"].startswith("Comunicazione di cancelleria")
    assert "original_mime" not in per_id["M1"] and "metadata_json" not in per_id["M1"]


def test_registro_assente_non_rompe_la_lettura(tmp_path: Path):
    class Rotto:
        tenant_id = "default"

        def connect(self):
            raise RuntimeError("nessun registro")

    assert messaggi_pec_per_fascicolo(SimpleNamespace(id="F1", numero_rg="1", anno_rg=2026, nome_cliente="A B"), repository=Rotto()) == []
    assert messaggi_pec_per_fascicolo(SimpleNamespace(id="", numero_rg="1", anno_rg=2026, nome_cliente="A B"), repository=Rotto()) == []


def test_repository_corrente_usa_lo_slug_tenant_della_richiesta(tmp_path: Path):
    app = Flask(__name__)
    email_db = tmp_path / "tenant-a" / "email" / "casella.json"
    email_db.parent.mkdir(parents=True)

    with app.app_context():
        g.data_paths = {"EMAIL_CASELLA_DB": str(email_db)}
        g.tenant_context_slug = "studio-a"

        repository = repository_for_current_request()

    assert repository.tenant_id == "studio-a"
    assert repository.db_path == email_db.parent / "pec_audit.sqlite"
