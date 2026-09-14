"""Le verifiche automatiche dei presìdi: registro, necessità, collegamento PEC per ruolo, orchestrazione."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from pct.pec_pipeline import PecAuditRepository
from tests.test_fascicolo_pec_presidio import _inserisci, _repository
from tests.test_react_shell import _app
from web.services import fascicolo_lettura_verifiche as servizio

ROME = ZoneInfo("Europe/Rome")
HEADERS = {"X-API-Key": "react-test-key"}


def test_registro_per_fascicolo_e_necessita_delle_verifiche(tmp_path: Path):
    paths = {"FASCICOLI_DB": str(tmp_path / "dati" / "fascicoli" / "fascicoli.json")}
    assert servizio.leggi_registro("F1", paths=paths) == {"in_corso": False}
    assert servizio.verifiche_necessarie(servizio.leggi_registro("F1", paths=paths)) is True
    adesso = datetime.now(ROME)
    servizio.scrivi_registro("F1", {"eseguita_il": adesso.isoformat(timespec="seconds"), "esiti": {"pec": {"esaminate": 2}}, "in_corso": True}, paths=paths)
    record = servizio.leggi_registro("F1", paths=paths)
    assert record["esiti"]["pec"]["esaminate"] == 2 and record["in_corso"] is False
    assert record["eseguita_il_it"].startswith(adesso.strftime("%d/%m/%Y"))
    assert servizio.verifiche_necessarie(record) is False
    assert servizio.verifiche_necessarie(record, forza=True) is True
    vecchio = (adesso - timedelta(minutes=servizio.INTERVALLO_MINUTI + 1)).isoformat(timespec="seconds")
    servizio.scrivi_registro("F1", {"eseguita_il": vecchio, "esiti": {}}, paths=paths)
    assert servizio.verifiche_necessarie(servizio.leggi_registro("F1", paths=paths)) is True
    assert (tmp_path / "dati" / "intelligence" / "lettura_verifiche.json").exists()
    assert json.loads((tmp_path / "dati" / "intelligence" / "lettura_verifiche.json").read_text(encoding="utf-8"))["F1"]["eseguita_il"] == vecchio


def test_verifica_pec_collega_il_ruolo_citato_da_un_ufficio_e_lascia_da_confermare_il_resto(tmp_path: Path):
    repository: PecAuditRepository = _repository(tmp_path)
    _inserisci(repository, "M1", "Comunicazione di cancelleria n. 777/2026 - udienza", received="2026-09-01T09:00:00")
    _inserisci(repository, "M2", "Documenti per Anna Bianchi", received="2026-09-02T09:00:00")
    _inserisci(repository, "M3", "Già collegata", linked="F1", received="2026-09-03T09:00:00")
    with repository.connect() as conn:
        conn.execute("INSERT INTO pec_parsed_versions (id, message_id, version, parser_version, parsed_json, parsed_sha256, created_at) VALUES ('v1','M1',1,'1','{}','p1','2026-09-01T09:05:00')")
        conn.commit()
    fascicolo = SimpleNamespace(id="F1", numero_rg="777", anno_rg=2026, nome_cliente="Anna Bianchi")

    esito = servizio.verifica_pec(fascicolo, repository=repository)

    assert esito["esaminate"] == 3 and esito["collegate"] == 1
    assert [voce["id"] for voce in esito["da_confermare"]] == ["M2"]
    with repository.connect() as conn:
        riga = conn.execute("SELECT linked_fascicolo_id, status FROM pec_messages WHERE id='M1'").fetchone()
        assert riga["linked_fascicolo_id"] == "F1" and riga["status"] == "linked"
        link = conn.execute("SELECT fascicolo_id, status, score FROM pec_fascicolo_links WHERE message_id='M1'").fetchone()
        assert link["fascicolo_id"] == "F1" and link["status"] == "ruolo_certificato_ufficio" and link["score"] == 1.0
        # Il presidio riparte sul messaggio (validate → link) e il linker automatico non sovrascrive il collegamento certificato.
        job_types = {str(row["job_type"]) for row in conn.execute("SELECT job_type FROM pec_jobs WHERE message_id='M1'").fetchall()}
        assert job_types <= {"validate", "link"}
        assert conn.execute("SELECT linked_fascicolo_id FROM pec_messages WHERE id='M2'").fetchone()["linked_fascicolo_id"] == ""


def test_verifica_pec_non_collega_il_ruolo_se_il_mittente_non_e_un_ufficio(tmp_path: Path):
    repository = _repository(tmp_path)
    with repository.connect() as conn:
        conn.execute(
            "INSERT INTO pec_messages (id, tenant_id, account_email, folder, mime_sha256, mime_size, original_mime, received_at, ingested_at, status, quality_status, signature_status, linked_fascicolo_id, metadata_json) "
            "VALUES ('M9','default','studio@pec.it','INBOX','sha9',10,X'00','2026-09-01T09:00:00','2026-09-01T09:00:00','parsed','verde','valida','',?)",
            (json.dumps({"headers": {"subject": "Vi scrivo per il ruolo 777/2026", "from": "controparte@pec.privato.it"}}),),
        )
        conn.commit()
    esito = servizio.verifica_pec(SimpleNamespace(id="F1", numero_rg="777", anno_rg=2026, nome_cliente="Anna Bianchi"), repository=repository)
    assert esito["collegate"] == 0 and [voce["corrispondenza"] for voce in esito["da_confermare"]] == ["rg"]


def test_esegui_verifiche_registra_gli_esiti_e_le_lacune(tmp_path: Path, monkeypatch):
    from pct.fascicoli import TipoFascicolo

    app = _app(tmp_path)
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo("Rossi / Verdi", TipoFascicolo.ALTRO, nome_cliente="Mario Rossi", tipo_procedimento="Arbitrato rituale", numero_rg="1", anno_rg=2026)
    monkeypatch.setattr(servizio, "verifica_pec", lambda fascicolo, repository=None: {"esaminate": 1, "collegate": 1, "job_eseguiti": 1, "da_confermare": []})
    monkeypatch.setattr(servizio, "verifica_notifiche", lambda fascicolo_id: {"esaminati": 0, "riallineati": 0})
    monkeypatch.setattr(servizio, "verifica_documenti", lambda fascicolo_id, tenant_slug="": (_ for _ in ()).throw(RuntimeError("OCR non disponibile")))
    monkeypatch.setattr(servizio, "verifica_depositi", lambda app_, fascicolo, paths: {"pendenti": 0, "esito": "nessun_deposito_in_corso"})

    record = servizio.esegui_verifiche(app, fascicolo.id, paths={"FASCICOLI_DB": app.config["FASCICOLI_DB"]})

    assert record["esiti"]["pec"]["collegate"] == 1
    assert record["esiti"]["depositi"]["esito"] == "nessun_deposito_in_corso"
    assert record["errori"]["documenti"] == "OCR non disponibile"
    assert [voce["tipo"] for voce in record["lacune_conoscenza"]] == ["rito"]
    letto = servizio.leggi_registro(fascicolo.id, paths={"FASCICOLI_DB": app.config["FASCICOLI_DB"]})
    assert letto["esiti"]["pec"]["collegate"] == 1 and letto["completata_il"]

    # La lettura del fascicolo espone gli esiti e li racconta.
    with app.app_context():
        from lex.context.fascicolo_lettura_context import load_fascicolo_lettura_context

        lettura = load_fascicolo_lettura_context(fascicolo_id=fascicolo.id)
    assert lettura["verifiche"]["esiti"]["pec"]["collegate"] == 1
    assert "1 messaggi esaminati, 1 collegati automaticamente" in lettura["narrativa"]
    assert "Verifica documenti non completata: OCR non disponibile" in lettura["narrativa"]


def test_endpoint_lettura_avvia_le_verifiche_in_sfondo(tmp_path: Path, monkeypatch):
    from pct.fascicoli import TipoFascicolo
    from web.blueprints import api_v1_react

    avvii: list[tuple] = []
    monkeypatch.setattr(servizio, "avvia_verifiche_in_background", lambda app, fascicolo_id, **kwargs: avvii.append((fascicolo_id, kwargs.get("forza"))) or True)
    api_v1_react._LETTURA_CACHE.clear()
    app = _app(tmp_path)
    with app.app_context():
        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().nuovo("Neri / Blu", TipoFascicolo.CIVILE, nome_cliente="Anna Neri")
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/lettura?aggiorna=1", headers=HEADERS)
    assert risposta.status_code == 200
    assert risposta.get_json()["lettura"]["verifiche"]["in_corso"] is True
    assert avvii == [(fascicolo.id, True)]
    api_v1_react._LETTURA_CACHE.clear()
