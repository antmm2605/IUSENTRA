from __future__ import annotations

import email
import os
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

from flask import g

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.config_studio import ConfigPEC, ConfigSMTP, ConfigStudio, GestioneConfigStudio
from pct.auth import GestioneUtenti
from pct.email_client import (
    CartellaEmail,
    EmailRicevuta,
    GestioneEmailRicevute,
    StatoEmail,
    _trova_fascicolo_da_email,
    aggiorna_comunicazioni_cancelleria_da_email,
    aggiorna_esiti_da_email,
    cartelle_imap_standard,
)
from pct.fascicoli import GestioneFascicoli, TipoAttivita, TipoFascicolo
from pct.runtime_resilience import clear_runtime_circuit_breakers


def _cfg_web(tmp_path: Path) -> dict:
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "BACKUP_DIR": str(tmp_path / "backup"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "casella.json"),
        "EMAIL_ORDINARIA_DB": str(tmp_path / "ordinaria.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
    }


def _autentica_admin_session(app, client, cfg: dict) -> None:
    utenti = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key=app.secret_key,
    )
    admin = utenti.get_by_username("admin")
    assert admin is not None
    with client.session_transaction() as session_data:
        session_data["user_id"] = admin.id
        session_data["tenant_slug"] = ""
        session_data["auth_scope"] = "platform"
        session_data["auth_tenant_slug"] = ""
        session_data["last_activity"] = datetime.now().isoformat()


def test_email_blueprint_usa_storage_tenant_per_sincronizzazione(tmp_path):
    from web.app import create_app
    import web.blueprints.email_client as email_routes

    cfg = _cfg_web(tmp_path / "root")
    tenant_root = tmp_path / "tenant"
    tenant_email_db = tenant_root / "email" / "casella.json"
    tenant_config = tenant_root / "config" / "studio.json"
    root_email_db = Path(cfg["EMAIL_CASELLA_DB"])
    root_config = Path(cfg["STUDIO_CONFIG"])
    GestioneConfigStudio(str(root_config)).aggiorna(ConfigStudio(pec=ConfigPEC(indirizzo="root@example.it")))
    GestioneConfigStudio(str(tenant_config)).aggiorna(ConfigStudio(pec=ConfigPEC(indirizzo="tenant@example.it")))

    app = create_app(cfg)
    with app.test_request_context("/email/sincronizza", method="POST"):
        g.data_paths = {
            "EMAIL_CASELLA_DB": str(tenant_email_db),
            "STUDIO_CONFIG": str(tenant_config),
        }
        gestore = email_routes._get_gestore()
        pec = email_routes._get_config_pec()

    assert gestore.db_path == tenant_email_db
    assert pec is not None
    assert pec.indirizzo == "tenant@example.it"
    assert gestore.db_path != root_email_db


def test_impostazioni_payload_smtp_locale_usa_password_pec_salvata_del_tenant(tmp_path):
    from web.app import create_app
    import web.blueprints.impostazioni as impostazioni_routes

    cfg = _cfg_web(tmp_path / "root")
    tenant_config = tmp_path / "tenant" / "config" / "studio.json"
    GestioneConfigStudio(str(tenant_config)).aggiorna(
        ConfigStudio(
            pec=ConfigPEC(
                indirizzo="studio@pec.example.it",
                password="segreta",
                smtp_host="smtp.pec.example.it",
                smtp_port=465,
                use_ssl=True,
            )
        )
    )

    app = create_app(cfg)
    with app.test_request_context(
        "/impostazioni/pec/local-smtp-payload",
        method="POST",
        json={"smtp_host": "smtp.override.example.it", "smtp_port": 587, "use_ssl": False},
    ):
        g.utente_corrente = SimpleNamespace(id="u1")
        g.data_paths = {"STUDIO_CONFIG": str(tenant_config)}
        response = impostazioni_routes.pec_local_smtp_payload()

    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["payload"]["indirizzo"] == "studio@pec.example.it"
    assert payload["payload"]["password"] == "segreta"
    assert payload["payload"]["smtp_host"] == "smtp.override.example.it"
    assert payload["payload"]["smtp_port"] == 587
    assert payload["payload"]["use_ssl"] is False


def test_base_template_non_renderizza_vecchio_lex_duplicato():
    template = Path("web/templates/base.html").read_text(encoding="utf-8")
    assert "__legacy_lex_disabled__" not in template
    assert "false and g.utente_corrente" not in template
    assert template.count('include "components/pct_ai_widget.html"') == 1


def test_email_casella_filtri_avanzati_e_flag_letto(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-1",
            cartella="INBOX",
            stato=StatoEmail.LETTA,
            mittente="cancelleria@giustiziapec.it",
            mittente_nome="Cancelleria",
            destinatari="studio@example.pec.it",
            oggetto="ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-08T09:00:00",
            corpo_testo="Ricevuta PEC di accettazione",
            allegati=[{"nome": "ricevuta.eml", "size": 1024, "mime": "message/rfc822"}],
            stato_pct="ACCETTATO_PEC",
            origine="IMAP",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-2",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="operatore@example.com",
            oggetto="Memo interno",
            data="2026-04-08T10:00:00",
            corpo_testo="Promemoria",
            origine="IMAP",
        )
    )

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)

        response = client.get(
            "/email/?_legacy=1&cartella=INBOX&stato=LETTA&pst=1&con_allegati=1&stato_pct=ACCETTATO_PEC&data_da=2026-04-01&data_a=2026-04-30"
        )

        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024" in body
        assert "Memo interno" not in body

        post = client.post("/email/MAIL-1/segna-non-letta", data={"cartella": "INBOX"}, follow_redirects=True)
        assert post.status_code == 200

    ge_reload = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    assert ge_reload.get("MAIL-1").stato == StatoEmail.NON_LETTA


def test_email_route_ufficiale_serve_react_e_api_distingue_inviati_cestino(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-IN",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="Comunicazione in arrivo",
            data="2026-04-08T09:00:00",
            corpo_testo="Arrivo",
            stato_pct="ACCETTATO_PEC",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-SENT",
            cartella=CartellaEmail.INVIATI,
            stato=StatoEmail.LETTA,
            destinatari="cliente@example.it",
            oggetto="PEC inviata",
            data="2026-04-08T10:00:00",
            corpo_testo="Invio",
            origine="INVIATA",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-TRASH",
            cartella=CartellaEmail.CESTINO,
            stato=StatoEmail.CESTINO,
            mittente="archivio@example.it",
            oggetto="PEC cestinata",
            data="2026-04-08T11:00:00",
            corpo_testo="Cestino",
        )
    )

    app = create_app(cfg)
    app.config["API_KEY"] = "react-test-key"
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)

        react = client.get("/email/")
        classic = client.get("/email/?_legacy=1&cartella=INBOX")
        sent_api = client.get("/api/v1/ui/email", query_string={"cartella": "INVIATI"}, headers={"X-API-Key": "react-test-key"})
        trash_api = client.get("/api/v1/ui/email", query_string={"cartella": "CESTINO"}, headers={"X-API-Key": "react-test-key"})

    sent_payload = sent_api.get_json()
    trash_payload = trash_api.get_json()

    assert react.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in react.get_data(as_text=True)
    assert classic.status_code == 200
    assert 'id="root"' not in classic.get_data(as_text=True)
    assert sent_api.status_code == 200
    assert trash_api.status_code == 200
    assert sent_payload["source"] == "repository_reali"
    assert sent_payload["summary"]["sent"] == 1
    assert sent_payload["items"][0]["folder"] == CartellaEmail.INVIATI
    assert trash_payload["summary"]["trash"] == 1
    assert trash_payload["items"][0]["folder"] == CartellaEmail.CESTINO


def test_email_ordinaria_route_react_api_e_repository_separato_da_pec(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    pec = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    ordinaria = GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"])
    pec.aggiungi(
        EmailRicevuta(
            id="PEC-1",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="PEC da non mostrare nella posta ordinaria",
            data="2026-04-08T09:00:00",
            stato_pct="ACCETTATO_PEC",
        )
    )
    ordinaria.aggiungi(
        EmailRicevuta(
            id="MAIL-ORD-1",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="cliente@example.it",
            mittente_nome="Cliente Ordinario",
            oggetto="Email ordinaria da lavorare",
            data="2026-04-08T10:00:00",
            corpo_testo="Richiesta informazioni pratica.",
        )
    )

    app = create_app(cfg)
    app.config["API_KEY"] = "react-test-key"
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        react = client.get("/email-ordinaria/")
        payload_response = client.get(
            "/api/v1/ui/email-ordinaria",
            headers={"X-API-Key": "react-test-key"},
        )
        pec_payload_response = client.get(
            "/api/v1/ui/email",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = payload_response.get_json()
    pec_payload = pec_payload_response.get_json()
    assert react.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in react.get_data(as_text=True)
    assert payload_response.status_code == 200
    assert payload["actions"]["compose"] == "/email-ordinaria/scrivi"
    assert payload["actions"]["sync"] == "/email-ordinaria/sincronizza"
    assert payload["actions"]["bulkAction"] == "/api/v1/ui/email-ordinaria/bulk-action"
    assert payload["actions"]["settings"] == "/impostazioni?tab=smtp"
    assert pec_payload["actions"]["compose"] == "/email/scrivi"
    assert pec_payload["actions"]["sync"] == "/email/sincronizza"
    assert pec_payload["actions"]["bulkAction"] == "/api/v1/ui/email/bulk-action"
    assert payload["actions"]["compose"] != pec_payload["actions"]["compose"]
    assert payload["actions"]["sync"] != pec_payload["actions"]["sync"]
    assert payload["summary"]["pst"] == 0
    assert payload["summary"]["autoLinked"] == 0
    assert payload["items"][0]["id"] == "MAIL-ORD-1"
    assert payload["items"][0]["isPst"] is False
    assert payload["items"][0]["pctStatus"] == ""
    assert pec_payload["items"][0]["id"] == "PEC-1"


def test_email_ordinaria_react_api_non_legge_fallback_globale_senza_tenant(tmp_path):
    from web.app import create_app

    cfg = {
        **_cfg_web(tmp_path),
        "MULTI_TENANT": True,
        "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
    }
    GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"]).aggiungi(
        EmailRicevuta(
            id="MAIL-ROOT-1",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="altro-studio@example.it",
            oggetto="Messaggio che non deve essere esposto",
            data="2026-05-10T10:00:00",
        )
    )

    app = create_app(cfg)
    app.config["API_KEY"] = "react-test-key"
    with app.test_client() as client:
        response = client.get(
            "/api/v1/ui/email-ordinaria",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = response.get_json()
    assert response.status_code == 409
    assert payload["codice"] == "tenant_context_required"
    assert "cross-studio" in payload["errore"]


def test_email_ordinaria_bulk_action_non_cancella_fallback_globale_senza_tenant(tmp_path):
    from web.app import create_app

    cfg = {
        **_cfg_web(tmp_path),
        "MULTI_TENANT": True,
        "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
    }
    root_mail = GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"])
    root_mail.aggiungi(
        EmailRicevuta(
            id="MAIL-ROOT-TRASH",
            cartella=CartellaEmail.CESTINO,
            stato=StatoEmail.CESTINO,
            mittente="altro-studio@example.it",
            oggetto="Non cancellare dal tenant sbagliato",
            data="2026-05-10T10:00:00",
        )
    )

    app = create_app(cfg)
    app.config["API_KEY"] = "react-test-key"
    with app.test_client() as client:
        response = client.post(
            "/api/v1/ui/email-ordinaria/bulk-action",
            headers={"X-API-Key": "react-test-key"},
            json={"ids": ["MAIL-ROOT-TRASH"], "action": "delete"},
        )

    payload = response.get_json()
    assert response.status_code == 409
    assert payload["codice"] == "tenant_context_required"
    assert GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"]).get("MAIL-ROOT-TRASH") is not None


def test_email_pec_react_api_non_legge_fallback_globale_senza_tenant(tmp_path):
    from web.app import create_app

    cfg = {
        **_cfg_web(tmp_path),
        "MULTI_TENANT": True,
        "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
    }
    GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"]).aggiungi(
        EmailRicevuta(
            id="PEC-ROOT-1",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="altro-studio@pec.example.it",
            oggetto="PEC che non deve essere esposta",
            data="2026-05-10T10:00:00",
        )
    )

    app = create_app(cfg)
    app.config["API_KEY"] = "react-test-key"
    with app.test_client() as client:
        response = client.get(
            "/api/v1/ui/email",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = response.get_json()
    assert response.status_code == 409
    assert payload["codice"] == "tenant_context_required"
    assert "cross-studio" in payload["errore"]


def test_email_react_bulk_action_sposta_selezione_nel_cestino(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    pec = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    pec.aggiungi(
        EmailRicevuta(
            id="PEC-A",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="a@example.it",
            oggetto="PEC A",
            data="2026-04-08T09:00:00",
        )
    )
    pec.aggiungi(
        EmailRicevuta(
            id="PEC-B",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.LETTA,
            mittente="b@example.it",
            oggetto="PEC B",
            data="2026-04-08T10:00:00",
        )
    )

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        response = client.post(
            "/api/v1/ui/email/bulk-action",
            json={"ids": ["PEC-A", "PEC-B"], "action": "trash"},
        )

    payload = response.get_json()
    pec_reload = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["updated"] == ["PEC-A", "PEC-B"]
    assert pec_reload.get("PEC-A").cartella == CartellaEmail.CESTINO
    assert pec_reload.get("PEC-B").cartella == CartellaEmail.CESTINO


def test_email_ordinaria_react_bulk_action_elimina_selezione_da_cestino(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ordinaria = GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"])
    ordinaria.aggiungi(
        EmailRicevuta(
            id="ORD-TRASH-1",
            cartella=CartellaEmail.CESTINO,
            stato=StatoEmail.CESTINO,
            mittente="cliente@example.it",
            oggetto="Da eliminare 1",
            data="2026-04-08T09:00:00",
        )
    )
    ordinaria.aggiungi(
        EmailRicevuta(
            id="ORD-TRASH-2",
            cartella=CartellaEmail.CESTINO,
            stato=StatoEmail.CESTINO,
            mittente="cliente2@example.it",
            oggetto="Da eliminare 2",
            data="2026-04-08T10:00:00",
        )
    )

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        response = client.post(
            "/api/v1/ui/email-ordinaria/bulk-action",
            json={"ids": ["ORD-TRASH-1", "ORD-TRASH-2"], "action": "delete"},
        )

    payload = response.get_json()
    ordinaria_reload = GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"])
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["updated"] == ["ORD-TRASH-1", "ORD-TRASH-2"]
    assert ordinaria_reload.get("ORD-TRASH-1") is None
    assert ordinaria_reload.get("ORD-TRASH-2") is None


def test_email_ordinaria_react_bulk_action_sposta_cestino_salva_una_volta(tmp_path, monkeypatch):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ordinaria = GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"])
    ids = [f"ORD-BULK-INBOX-{idx}" for idx in range(40)]
    for email_id in ids:
        ordinaria.aggiungi(
            EmailRicevuta(
                id=email_id,
                cartella=CartellaEmail.INBOX,
                stato=StatoEmail.NON_LETTA,
                mittente="cliente@example.it",
                oggetto=f"Da cestinare {email_id}",
                data="2026-04-08T09:00:00",
            )
        )

    saves: list[str] = []
    original_save = GestioneEmailRicevute._salva

    def _counted_save(self):
        saves.append(str(self.db_path))
        return original_save(self)

    monkeypatch.setattr(GestioneEmailRicevute, "_salva", _counted_save)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        response = client.post(
            "/api/v1/ui/email-ordinaria/bulk-action",
            json={"ids": ids, "action": "trash"},
        )

    payload = response.get_json()
    ordinaria_reload = GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"])
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["updated"] == ids
    assert saves.count(cfg["EMAIL_ORDINARIA_DB"]) == 1
    assert all(ordinaria_reload.get(email_id).cartella == CartellaEmail.CESTINO for email_id in ids)


def test_email_ordinaria_react_bulk_action_elimina_selezione_salva_una_volta(tmp_path, monkeypatch):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ordinaria = GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"])
    ids = [f"ORD-BULK-TRASH-{idx}" for idx in range(40)]
    for email_id in ids:
        ordinaria.aggiungi(
            EmailRicevuta(
                id=email_id,
                cartella=CartellaEmail.CESTINO,
                stato=StatoEmail.CESTINO,
                mittente="cliente@example.it",
                oggetto=f"Da eliminare {email_id}",
                data="2026-04-08T09:00:00",
            )
        )

    saves: list[str] = []
    original_save = GestioneEmailRicevute._salva

    def _counted_save(self):
        saves.append(str(self.db_path))
        return original_save(self)

    monkeypatch.setattr(GestioneEmailRicevute, "_salva", _counted_save)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        response = client.post(
            "/api/v1/ui/email-ordinaria/bulk-action",
            json={"ids": ids, "action": "delete"},
        )

    payload = response.get_json()
    ordinaria_reload = GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"])
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["updated"] == ids
    assert saves.count(cfg["EMAIL_ORDINARIA_DB"]) == 1
    assert all(ordinaria_reload.get(email_id) is None for email_id in ids)


def test_email_ordinaria_scrivi_restera_separata_da_email_pec(tmp_path, monkeypatch):
    from web.app import create_app
    from pct.messaggi import GestioneMessaggi, StatoMessaggio

    cfg = _cfg_web(tmp_path)
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(
            smtp=ConfigSMTP(
                host="smtp.example.it",
                port=587,
                username="studio@example.it",
                password="segreta",
                from_address="studio@example.it",
                from_name="Studio",
                use_tls=True,
            )
        )
    )
    inviati = {}

    def _fake_invia_email(self, **kwargs):
        inviati.update(kwargs)
        return SimpleNamespace(stato=StatoMessaggio.INVIATO, errore="")

    monkeypatch.setattr(GestioneMessaggi, "invia_email", _fake_invia_email)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        form = client.get("/email-ordinaria/scrivi")
        invalid = client.post(
            "/email-ordinaria/scrivi",
            data={"a": "", "oggetto": ""},
            follow_redirects=False,
        )
        sent = client.post(
            "/email-ordinaria/scrivi",
            data={"a": "cliente@example.it", "oggetto": "Prova", "corpo": "Testo"},
            follow_redirects=False,
        )

    body = form.get_data(as_text=True)
    assert form.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in body
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    compose_source = Path("frontend/src/components/EmailPecPage.tsx").read_text(encoding="utf-8")
    email_data_source = Path("frontend/src/emailData.ts").read_text(encoding="utf-8")
    assert "isEmailOrdinariaComposePage?<EmailComposePage mode=\"ordinaria\"/>" in app_source
    assert "const action = isOrdinary ? '/email-ordinaria/scrivi' : '/email/scrivi'" in compose_source
    assert "const backHref = isOrdinary ? '/email-ordinaria/?cartella=INBOX' : '/email/?cartella=INBOX'" in compose_source
    assert "compose: '/email-ordinaria/scrivi'" in email_data_source
    assert "sync: '/email-ordinaria/sincronizza'" in email_data_source
    assert "`${fallbackBasePath}/scrivi?oggetto=" in email_data_source
    assert "/email/scrivi?oggetto=" not in email_data_source
    assert invalid.status_code == 302
    assert "/email-ordinaria/scrivi" in invalid.headers["Location"]
    assert sent.status_code == 302
    assert "/email-ordinaria/?cartella=INVIATI" in sent.headers["Location"]
    assert inviati["destinatario"] == "cliente@example.it"


def test_email_ordinaria_sincronizza_usa_imap_smtp_dalle_impostazioni(tmp_path, monkeypatch):
    from web.app import create_app
    import pct.email_client as email_runtime

    cfg = _cfg_web(tmp_path)
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(
            smtp=ConfigSMTP(
                host="smtp.example.it",
                port=587,
                imap_host="imap.ordinaria.example.it",
                imap_port=993,
                imap_use_ssl=True,
                username="studio@example.it",
                password="segreta",
                from_address="studio@example.it",
                from_name="Studio",
                use_tls=True,
            )
        )
    )
    osservato = {}

    def _fake_sync(self, **kwargs):
        osservato.update(kwargs)
        return {"nuove": 1, "allegati_salvati": 0, "errore": ""}

    monkeypatch.setattr(email_runtime.GestioneEmailRicevute, "sincronizza_imap", _fake_sync)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        response = client.post("/email-ordinaria/sincronizza")

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["messaggio"] == "Sincronizzazione email ordinaria completata."
    assert osservato["imap_host"] == "imap.ordinaria.example.it"
    assert osservato["imap_port"] == 993
    assert osservato["username"] == "studio@example.it"
    assert osservato["password"] == "segreta"
    assert osservato["use_ssl"] is True


def test_impostazioni_smtp_espone_imap_ordinario_e_pec_non_mostra_diagnostica_server(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        smtp = client.get("/impostazioni?tab=smtp&_legacy=1")
        pec = client.get("/impostazioni?tab=pec&_legacy=1")
        ai = client.get("/impostazioni?tab=ai&_legacy=1")

    smtp_html = smtp.get_data(as_text=True)
    pec_html = pec.get_data(as_text=True)
    ai_html = ai.get_data(as_text=True)
    assert "smtp_imap_host" in smtp_html
    assert "smtp_imap_port" in smtp_html
    assert "Testa connessione IMAP" in smtp_html
    assert "Diagnostica server (non invio reale)" not in pec_html
    assert "L'invio PEC reale deve passare dal PC locale tramite Local Signer" not in pec_html
    assert "http://127.0.0.1:11434/api/version" in ai_html


def test_dashboard_ultime_pec_usa_inbox_completa_e_invalida_cache(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    ge.aggiungi(
        EmailRicevuta(
            id="PEC-OLD",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="protocollo@pec.cittametropolitana.rc.it",
            oggetto="Verbale precedente",
            data="2026-04-09T10:00:00",
            corpo_testo="Messaggio PEC gia presente.",
        )
    )

    app = create_app(cfg)
    app.config["API_KEY"] = "react-test-key"
    headers = {"X-API-Key": "react-test-key"}

    with app.test_client() as client:
        first = client.get("/api/v1/ui/dashboard", headers=headers)
        assert first.status_code == 200
        assert first.get_json()["pec"][0]["id"] == "PEC-OLD"

        ge.aggiungi(
            EmailRicevuta(
                id="PEC-GIUSTIZIACERT-NEW",
                cartella=CartellaEmail.INBOX,
                stato=StatoEmail.NON_LETTA,
                mittente="tribunale.palmi@civile.ptel.giustiziacert.it",
                oggetto="Notifica ai sensi del D.L. 179/2012",
                data="2026-04-30T11:42:10+02:00",
                corpo_testo="Messaggio PEC ministeriale piu recente.",
            )
        )
        second = client.get("/api/v1/ui/dashboard", headers=headers)

    payload = second.get_json()
    assert second.status_code == 200
    assert second.headers["Cache-Control"] == "no-store, max-age=0"
    assert second.headers["X-IUSENTRA-Cache"] == "MISS"
    assert payload["pec"][0]["id"] == "PEC-GIUSTIZIACERT-NEW"
    assert payload["stats"]["pecUnread"] == 2
    assert payload["emails"] == []


def test_email_dettaglio_visualizza_e_scarica_allegato_salvato(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    em = EmailRicevuta(
        id="MAIL-ATT-1",
        cartella="INBOX",
        stato=StatoEmail.LETTA,
        mittente="cancelleria@giustiziapec.it",
        oggetto="PEC con allegato RG 1025/2024",
        data="2026-04-09T10:00:00",
        corpo_testo="Contiene una ricevuta allegata.",
        allegati=[{
            "nome": "ricevuta.pdf",
            "mime": "application/octet-stream",
            "size": 18,
            "percorso_rel": "MAIL-ATT-1/ricevuta.pdf",
            "nome_file": "ricevuta.pdf",
        }],
    )
    ge.aggiungi(em)
    allegato_dir = Path(cfg["EMAIL_CASELLA_DB"]).parent / "allegati" / "MAIL-ATT-1"
    allegato_dir.mkdir(parents=True, exist_ok=True)
    contenuto = b"%PDF-1.4 allegato\n"
    (allegato_dir / "ricevuta.pdf").write_bytes(contenuto)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)

        dettaglio = client.get("/email/messaggio/MAIL-ATT-1", follow_redirects=True)
        body = dettaglio.get_data(as_text=True)
        assert '<html lang="it" class="react-shell-document">' in body
        assert 'id="root"' in body

        dettaglio_json = client.get("/api/v1/ui/email/messaggio/MAIL-ATT-1")
        assert dettaglio_json.status_code == 200
        payload = dettaglio_json.get_json()
        assert payload["item"]["subject"] == "PEC con allegato RG 1025/2024"
        assert payload["bodyText"] == "Contiene una ricevuta allegata."
        assert payload["attachments"][0]["viewHref"] == "/email/messaggio/MAIL-ATT-1/allegato/0"
        assert payload["attachments"][0]["previewHref"] == "/email/messaggio/MAIL-ATT-1/allegato/0"
        assert payload["attachments"][0]["downloadHref"] == "/email/messaggio/MAIL-ATT-1/allegato/0?download=1"

        inline = client.get("/email/messaggio/MAIL-ATT-1/allegato/0")
        assert inline.status_code == 200
        assert inline.data == contenuto
        assert inline.headers.get("Content-Type", "").lower().startswith("application/pdf")

        download = client.get("/email/messaggio/MAIL-ATT-1/allegato/0?download=1")
        assert download.status_code == 200
        assert "attachment" in download.headers.get("Content-Disposition", "").lower()


def test_email_dettaglio_non_propone_link_per_allegato_non_recuperato(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    em = EmailRicevuta(
        id="MAIL-ATT-MISSING-0",
        cartella="INBOX",
        stato=StatoEmail.LETTA,
        mittente="cancelleria@giustiziapec.it",
        oggetto="PEC con allegato EML da recuperare",
        data="2026-05-12T12:29:34+02:00",
        corpo_testo="Messaggio PEC con un allegato storico non ancora salvato.",
        allegati=[
            {"nome": "postacert.eml", "mime": "message/rfc822", "size": 0},
            {
                "nome": "EsitoAtto.xml",
                "mime": "application/octet-stream",
                "size": 24,
                "percorso_rel": "MAIL-ATT-MISSING-0/EsitoAtto.xml",
                "nome_file": "EsitoAtto.xml",
            },
        ],
    )
    ge.aggiungi(em)
    allegato_dir = Path(cfg["EMAIL_CASELLA_DB"]).parent / "allegati" / "MAIL-ATT-MISSING-0"
    allegato_dir.mkdir(parents=True, exist_ok=True)
    contenuto = b"<EsitoAtto>ok</EsitoAtto>"
    (allegato_dir / "EsitoAtto.xml").write_bytes(contenuto)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)

        dettaglio_json = client.get("/api/v1/ui/email/messaggio/MAIL-ATT-MISSING-0")
        assert dettaglio_json.status_code == 200
        payload = dettaglio_json.get_json()
        assert payload["attachments"][0]["name"] == "postacert.eml"
        assert payload["attachments"][0]["available"] is False
        assert payload["attachments"][0]["viewHref"] == ""
        assert payload["attachments"][0]["downloadHref"] == ""
        assert "sincronizzazione" in payload["attachments"][0]["statusLabel"].lower()
        assert payload["attachments"][1]["available"] is True
        assert payload["attachments"][1]["viewHref"] == "/email/messaggio/MAIL-ATT-MISSING-0/allegato/1"

        missing = client.get("/email/messaggio/MAIL-ATT-MISSING-0/allegato/0")
        assert missing.status_code == 409
        assert "Sincronizza PEC" in missing.get_data(as_text=True)

        inline = client.get("/email/messaggio/MAIL-ATT-MISSING-0/allegato/1")
        assert inline.status_code == 200
        assert inline.data == contenuto


def test_email_ordinaria_dettaglio_usa_repository_smtp_e_allegati_ordinari(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_ORDINARIA_DB"])
    em = EmailRicevuta(
        id="MAIL-ORD-ATT-1",
        cartella="INBOX",
        stato=StatoEmail.NON_LETTA,
        mittente="cliente@example.it",
        oggetto="Email ordinaria con allegato",
        data="2026-04-10T09:30:00",
        corpo_testo="Messaggio ordinario con documento.",
        allegati=[{
            "nome": "documento.pdf",
            "mime": "application/octet-stream",
            "size": 18,
            "percorso_rel": "MAIL-ORD-ATT-1/documento.pdf",
            "nome_file": "documento.pdf",
        }],
    )
    ge.aggiungi(em)
    allegato_dir = Path(cfg["EMAIL_ORDINARIA_DB"]).parent / "allegati" / "MAIL-ORD-ATT-1"
    allegato_dir.mkdir(parents=True, exist_ok=True)
    contenuto = b"%PDF-1.4 ordinaria\n"
    (allegato_dir / "documento.pdf").write_bytes(contenuto)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)

        dettaglio = client.get("/email-ordinaria/messaggio/MAIL-ORD-ATT-1", follow_redirects=True)
        body = dettaglio.get_data(as_text=True)
        assert dettaglio.status_code == 200
        assert '<html lang="it" class="react-shell-document">' in body
        assert 'id="root"' in body

        dettaglio_json = client.get("/api/v1/ui/email-ordinaria/messaggio/MAIL-ORD-ATT-1")
        assert dettaglio_json.status_code == 200
        payload = dettaglio_json.get_json()
        assert payload["item"]["subject"] == "Email ordinaria con allegato"
        assert payload["bodyText"] == "Messaggio ordinario con documento."
        assert payload["attachments"][0]["viewHref"] == "/email-ordinaria/messaggio/MAIL-ORD-ATT-1/allegato/0"
        assert payload["attachments"][0]["previewHref"] == "/email-ordinaria/messaggio/MAIL-ORD-ATT-1/allegato/0"
        assert payload["attachments"][0]["viewHref"] != "/email/messaggio/MAIL-ORD-ATT-1/allegato/0"

        inline = client.get("/email-ordinaria/messaggio/MAIL-ORD-ATT-1/allegato/0")
        assert inline.status_code == 200
        assert inline.data == contenuto
        assert inline.headers.get("Content-Type", "").lower().startswith("application/pdf")


def test_parse_message_salva_allegato_message_rfc822(tmp_path):
    inner = EmailMessage()
    inner["Subject"] = "Messaggio originale"
    inner["From"] = "tribunale@example.test"
    inner["To"] = "studio@example.pec.it"
    inner.set_content("Corpo del messaggio originale.")

    outer = EmailMessage()
    outer["Subject"] = "POSTA CERTIFICATA: ESITO CONTROLLI"
    outer["From"] = "posta-certificata@example.test"
    outer["To"] = "studio@example.pec.it"
    outer["Date"] = "Tue, 12 May 2026 12:29:34 +0200"
    outer.set_content("Messaggio di posta certificata.")
    outer.make_mixed()

    part = EmailMessage()
    part.set_type("message/rfc822")
    part["Content-Disposition"] = 'attachment; filename="postacert.eml"'
    part.set_payload([inner])
    outer.attach(part)

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    parsed = email.message_from_bytes(outer.as_bytes())
    em = ge._parse_message(parsed, "INBOX:UID:7", "INBOX", email_id="MAIL-RFC822")  # noqa: SLF001

    assert em is not None
    assert em.allegati[0]["nome"] == "postacert.eml"
    assert em.allegati[0]["size"] > 0
    path = ge.percorso_allegato(em, 0)
    assert path is not None
    assert b"Subject: Messaggio originale" in path.read_bytes()


def test_sincronizza_imap_ripara_allegati_storici_senza_file(tmp_path, monkeypatch):
    import pct.email_client as email_runtime

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-STORICA-PEC",
            cartella="INBOX",
            stato=StatoEmail.LETTA,
            mittente="posta-certificata@pec.aruba.it",
            mittente_nome="Per conto di: protocollo@pec.cittametropolitana.rc.it",
            destinatari="studio@example.pec.it",
            oggetto="POSTA CERTIFICATA: [0030458-2026] Verbale di contestazione",
            data="2026-04-09T17:51:00+02:00",
            corpo_testo="PEC importata prima del salvataggio fisico allegati.",
            uid_imap="INBOX:42",
            allegati=[
                {"nome": "30458.pdf", "mime": "application/octet-stream", "size": 356352},
                {"nome": "Segnatura.xml", "mime": "application/octet-stream", "size": 3072},
                {"nome": "smime.p7s", "mime": "application/pkcs7-signature", "size": 7168},
            ],
        )
    )
    for seq in ("100", "101"):
        ge.aggiungi(
            EmailRicevuta(
                id=f"MAIL-RECENTE-{seq}",
                cartella="INBOX",
                stato=StatoEmail.LETTA,
                mittente="ufficio@example.test",
                oggetto=f"Email gia salvata {seq}",
                data="2026-04-24T09:00:00",
                corpo_testo="Messaggio recente gia completo.",
                uid_imap=f"INBOX:{seq}",
            )
        )

    msg = EmailMessage()
    msg["Subject"] = "POSTA CERTIFICATA: [0030458-2026] Verbale di contestazione"
    msg["From"] = "Per conto di: protocollo@pec.cittametropolitana.rc.it <posta-certificata@pec.aruba.it>"
    msg["To"] = "studio@example.pec.it"
    msg["Date"] = "Thu, 09 Apr 2026 17:51:00 +0200"
    msg["Message-ID"] = "<pec-30458@example.test>"
    msg.set_content("Comunicazione PEC con tre allegati.")
    msg.add_attachment(b"%PDF-1.4\nverbale\n", maintype="application", subtype="octet-stream", filename="30458.pdf")
    msg.add_attachment(b"<Segnatura>ok</Segnatura>", maintype="application", subtype="octet-stream", filename="Segnatura.xml")
    msg.add_attachment(b"firma", maintype="application", subtype="pkcs7-signature", filename="smime.p7s")
    raw_message = msg.as_bytes()

    class _FakeIMAP:
        def login(self, username, password):
            return "OK", []

        def select(self, mailbox, readonly=True):
            assert mailbox == "INBOX"
            return "OK", [b"1"]

        def search(self, charset, criteria):
            return "OK", [b"1 2 42 100 101"]

        def fetch(self, uid, query):
            assert uid == "42"
            return "OK", [(b"42 (RFC822)", raw_message)]

        def logout(self):
            return "OK", []

    monkeypatch.setattr(email_runtime.imaplib, "IMAP4_SSL", lambda *a, **k: _FakeIMAP())

    report = ge.sincronizza_imap(
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        username="studio@example.pec.it",
        password="segreta",
        use_ssl=True,
        cartelle_imap=["INBOX"],
        limite=2,
    )

    assert report["nuove"] == 0
    assert report["allegati_salvati"] == 3

    ge_reload = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    em = ge_reload.get("MAIL-STORICA-PEC")
    assert em is not None
    assert [a["nome"] for a in em.allegati] == ["30458.pdf", "Segnatura.xml", "smime.p7s"]
    for idx in range(3):
        assert ge_reload.percorso_allegato(em, idx) is not None
    assert ge_reload.percorso_allegato(em, 0).read_bytes().startswith(b"%PDF")


def test_sincronizza_imap_mappa_inviati_e_cestino_da_cartelle_reali(tmp_path, monkeypatch):
    import pct.email_client as email_runtime

    def _raw_message(subject: str, sender: str, recipient: str) -> bytes:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient
        msg["Date"] = "Thu, 09 Apr 2026 17:51:00 +0200"
        msg["Message-ID"] = f"<{subject.replace(' ', '-').lower()}@example.test>"
        msg.set_content(subject)
        return msg.as_bytes()

    messages = {
        "INBOX": _raw_message("PEC in arrivo", "ufficio@example.it", "studio@example.pec.it"),
        "Sent": _raw_message("PEC inviata reale", "studio@example.pec.it", "cliente@example.it"),
        "Trash": _raw_message("PEC cestinata reale", "ufficio@example.it", "studio@example.pec.it"),
    }

    class _FakeIMAP:
        selected = "INBOX"

        def login(self, username, password):
            return "OK", []

        def select(self, mailbox, readonly=True):
            self.selected = mailbox
            if mailbox in messages:
                return "OK", [b"1"]
            return "NO", []

        def search(self, charset, criteria):
            return "OK", [b"1"]

        def fetch(self, uid, query):
            return "OK", [(b"1 (RFC822)", messages[self.selected])]

        def logout(self):
            return "OK", []

    monkeypatch.setattr(email_runtime.imaplib, "IMAP4_SSL", lambda *a, **k: _FakeIMAP())

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    report = ge.sincronizza_imap(
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        username="studio@example.pec.it",
        password="segreta",
        use_ssl=True,
        cartelle_imap=["INBOX", "Sent", "Trash"],
        limite=10,
    )
    rows = {email.oggetto: email for email in GestioneEmailRicevute(str(tmp_path / "casella.json"))._carica().values()}

    assert report["nuove"] == 3
    assert rows["PEC in arrivo"].cartella == CartellaEmail.INBOX
    assert rows["PEC in arrivo"].stato == StatoEmail.NON_LETTA
    assert rows["PEC inviata reale"].cartella == CartellaEmail.INVIATI
    assert rows["PEC inviata reale"].stato == StatoEmail.LETTA
    assert rows["PEC cestinata reale"].cartella == CartellaEmail.CESTINO
    assert rows["PEC cestinata reale"].stato == StatoEmail.CESTINO
    assert {
        "INBOX",
        "Sent",
        "Sent Items",
        "Posta inviata",
        "INBOX/Spedite",
        "Trash",
        "Deleted Items",
        "Posta eliminata",
        "INBOX/Trash",
        "INBOX/Draft",
        "INBOX/Posta Indesiderata",
    }.issubset(set(cartelle_imap_standard()))


def test_sincronizza_imap_scopre_cartelle_legalmail_e_corregge_spedite(tmp_path, monkeypatch):
    import pct.email_client as email_runtime

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-SPEDITE-35",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="studio@example.pec.it",
            destinatari="cliente@example.it",
            oggetto="PEC inviata gia importata male",
            data="2026-04-15T10:00:00+02:00",
            uid_imap="INBOX/Spedite:UID:35",
            message_id="<sent-35@example.test>",
        )
    )

    def _raw_message(subject: str, sender: str, recipient: str, message_id: str) -> bytes:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient
        msg["Date"] = "Thu, 30 Apr 2026 10:12:00 +0200"
        msg["Message-ID"] = message_id
        msg.set_content(subject)
        return msg.as_bytes()

    messages = {
        "INBOX": {
            "1": _raw_message("PEC in arrivo", "ufficio@example.it", "studio@example.pec.it", "<inbox-1@example.test>"),
        },
        "INBOX/Spedite": {
            "35": _raw_message("PEC inviata gia importata male", "studio@example.pec.it", "cliente@example.it", "<sent-35@example.test>"),
        },
        "160925 SPEDITE": {
            "10": _raw_message("PEC inviata archivio Legalmail", "studio@example.pec.it", "cliente@example.it", "<sent-10@example.test>"),
        },
        "INBOX/Trash": {
            "3": _raw_message("PEC cestinata Legalmail", "ufficio@example.it", "studio@example.pec.it", "<trash-3@example.test>"),
        },
    }

    class _FakeIMAP:
        selected = "INBOX"
        selected_raw = []

        def login(self, username, password):
            return "OK", []

        def list(self):
            return "OK", [
                b'(\\HasNoChildren) "/" "INBOX"',
                b'(\\HasNoChildren) "/" "INBOX/Spedite"',
                b'(\\HasNoChildren) "/" "160925 SPEDITE"',
                b'(\\HasNoChildren) "/" "INBOX/Trash"',
            ]

        def select(self, mailbox, readonly=True):
            self.selected_raw.append(mailbox)
            normalized = str(mailbox or "").strip().strip('"').replace(r"\"", '"').replace(r"\\", "\\")
            self.selected = normalized
            if normalized in messages:
                return "OK", [str(len(messages[normalized])).encode()]
            return "NO", []

        def uid(self, command, *args):
            if command == "SEARCH":
                return "OK", [" ".join(messages[self.selected]).encode()]
            if command == "FETCH":
                uid = str(args[0])
                return "OK", [(f"{uid} (RFC822)".encode(), messages[self.selected][uid])]
            return "NO", []

        def logout(self):
            return "OK", []

    monkeypatch.setattr(email_runtime.imaplib, "IMAP4_SSL", lambda *a, **k: _FakeIMAP())

    report = ge.sincronizza_imap(
        imap_host="mbox.cert.legalmail.it",
        imap_port=993,
        username="studio@example.pec.it",
        password="segreta",
        use_ssl=True,
        cartelle_imap=["INBOX"],
        limite=10,
    )

    rows = GestioneEmailRicevute(str(tmp_path / "casella.json"))._carica()
    by_subject = {email.oggetto: email for email in rows.values()}

    assert report["nuove"] == 3
    assert report["cartelle_corrette"] == 1
    assert '"160925 SPEDITE"' in _FakeIMAP.selected_raw
    assert by_subject["PEC in arrivo"].cartella == CartellaEmail.INBOX
    assert by_subject["PEC inviata gia importata male"].cartella == CartellaEmail.INVIATI
    assert by_subject["PEC inviata gia importata male"].stato == StatoEmail.LETTA
    assert by_subject["PEC inviata archivio Legalmail"].cartella == CartellaEmail.INVIATI
    assert by_subject["PEC cestinata Legalmail"].cartella == CartellaEmail.CESTINO


def test_sincronizza_imap_usa_uid_stabili_e_non_salta_pec_recenti(tmp_path, monkeypatch):
    import pct.email_client as email_runtime

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-LEGACY-200",
            cartella="INBOX",
            stato=StatoEmail.LETTA,
            mittente="vecchia@example.test",
            oggetto="Vecchia PEC con sequenza non stabile",
            data="2026-04-10T09:00:00",
            corpo_testo="Gia salvata con numero di sequenza IMAP legacy.",
            uid_imap="INBOX:200",
            message_id="<legacy-200@example.test>",
        )
    )

    def _raw_message(uid: str, subject: str, message_id: str) -> bytes:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = "posta-certificata@pec.aruba.it"
        msg["To"] = "studio@example.pec.it"
        msg["Date"] = f"Thu, 30 Apr 2026 1{uid[-1]}:15:00 +0200"
        msg["Message-ID"] = message_id
        msg.set_content(f"PEC recente UID {uid}")
        return msg.as_bytes()

    messages = {
        "150": _raw_message("150", "PEC ricevuta oggi UID 150", "<today-150@example.test>"),
        "200": _raw_message("200", "PEC ricevuta oggi UID 200", "<today-200@example.test>"),
        "8": _raw_message("8", "PEC vecchia UID 8", "<old-8@example.test>"),
    }

    class _FakeIMAP:
        def login(self, username, password):
            return "OK", []

        def select(self, mailbox, readonly=True):
            return "OK", [b"3"]

        def uid(self, command, *args):
            if command == "SEARCH":
                return "OK", [b"8 200 150"]
            if command == "FETCH":
                uid = str(args[0])
                return "OK", [(f"{uid} (RFC822)".encode(), messages[uid])]
            return "NO", []

        def search(self, charset, criteria):
            raise AssertionError("Il sync deve usare UID SEARCH quando disponibile")

        def fetch(self, uid, query):
            raise AssertionError("Il sync deve usare UID FETCH quando disponibile")

        def logout(self):
            return "OK", []

    monkeypatch.setattr(email_runtime.imaplib, "IMAP4_SSL", lambda *a, **k: _FakeIMAP())

    report = ge.sincronizza_imap(
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        username="studio@example.pec.it",
        password="segreta",
        use_ssl=True,
        cartelle_imap=["INBOX"],
        limite=2,
    )

    rows = {email.oggetto: email for email in GestioneEmailRicevute(str(tmp_path / "casella.json"))._carica().values()}
    assert report["nuove"] == 3
    assert "PEC ricevuta oggi UID 150" in rows
    assert "PEC ricevuta oggi UID 200" in rows
    assert "PEC vecchia UID 8" in rows
    assert rows["PEC ricevuta oggi UID 200"].uid_imap == "INBOX:UID:200"
    assert rows["Vecchia PEC con sequenza non stabile"].uid_imap == "INBOX:200"


def test_sincronizza_imap_migra_riferimenti_legacy_tramite_message_id(tmp_path, monkeypatch):
    import pct.email_client as email_runtime

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-LEGACY-42",
            cartella="INBOX",
            stato=StatoEmail.LETTA,
            mittente="posta-certificata@pec.aruba.it",
            oggetto="PEC gia presente",
            data="2026-04-09T17:51:00+02:00",
            corpo_testo="Messaggio gia importato.",
            uid_imap="INBOX:42",
            message_id="<same-message@example.test>",
        )
    )

    msg = EmailMessage()
    msg["Subject"] = "PEC gia presente"
    msg["From"] = "posta-certificata@pec.aruba.it"
    msg["To"] = "studio@example.pec.it"
    msg["Date"] = "Thu, 09 Apr 2026 17:51:00 +0200"
    msg["Message-ID"] = "<same-message@example.test>"
    msg.set_content("Messaggio gia importato.")
    raw_message = msg.as_bytes()

    class _FakeIMAP:
        def login(self, username, password):
            return "OK", []

        def select(self, mailbox, readonly=True):
            return "OK", [b"1"]

        def uid(self, command, *args):
            if command == "SEARCH":
                return "OK", [b"142"]
            if command == "FETCH":
                return "OK", [(b"142 (RFC822)", raw_message)]
            return "NO", []

        def logout(self):
            return "OK", []

    monkeypatch.setattr(email_runtime.imaplib, "IMAP4_SSL", lambda *a, **k: _FakeIMAP())

    report = ge.sincronizza_imap(
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        username="studio@example.pec.it",
        password="segreta",
        use_ssl=True,
        cartelle_imap=["INBOX"],
        limite=1,
    )

    rows = GestioneEmailRicevute(str(tmp_path / "casella.json"))._carica()
    assert report["nuove"] == 0
    assert len(rows) == 1
    assert rows["MAIL-LEGACY-42"].uid_imap == "INBOX:UID:142"


def test_sincronizza_imap_non_fonde_uid_stabili_con_stesso_message_id(tmp_path, monkeypatch):
    import pct.email_client as email_runtime

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-UID-10",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="posta-certificata@pec.legalmail.it",
            oggetto="CONSEGNA: primo duplicato Legalmail",
            data="2026-04-29T10:00:00+02:00",
            corpo_testo="Primo messaggio gia importato.",
            uid_imap="INBOX:UID:10",
            message_id="<legalmail-same-id@example.test>",
        )
    )

    def _raw_message(uid: str, subject: str) -> bytes:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = "posta-certificata@pec.legalmail.it"
        msg["To"] = "studio@example.pec.it"
        msg["Date"] = f"Thu, 30 Apr 2026 10:{int(uid):02d}:00 +0200"
        msg["Message-ID"] = "<legalmail-same-id@example.test>"
        msg.set_content(f"Messaggio Legalmail con UID stabile {uid}.")
        return msg.as_bytes()

    messages = {
        "10": _raw_message("10", "CONSEGNA: primo duplicato Legalmail"),
        "11": _raw_message("11", "CONSEGNA: secondo duplicato Legalmail"),
    }

    class _FakeIMAP:
        def login(self, username, password):
            return "OK", []

        def select(self, mailbox, readonly=True):
            return "OK", [b"2"]

        def uid(self, command, *args):
            if command == "SEARCH":
                return "OK", [b"10 11"]
            if command == "FETCH":
                uid = str(args[0])
                return "OK", [(f"{uid} (RFC822)".encode(), messages[uid])]
            return "NO", []

        def search(self, charset, criteria):
            raise AssertionError("Il sync deve usare UID SEARCH quando disponibile")

        def fetch(self, uid, query):
            raise AssertionError("Il sync deve usare UID FETCH quando disponibile")

        def logout(self):
            return "OK", []

    monkeypatch.setattr(email_runtime.imaplib, "IMAP4_SSL", lambda *a, **k: _FakeIMAP())

    report = ge.sincronizza_imap(
        imap_host="mbox.cert.legalmail.it",
        imap_port=993,
        username="studio@example.pec.it",
        password="segreta",
        use_ssl=True,
        cartelle_imap=["INBOX"],
        limite=10,
    )

    rows = GestioneEmailRicevute(str(tmp_path / "casella.json"))._carica()
    uids = {email.uid_imap for email in rows.values()}
    subjects = {email.oggetto for email in rows.values()}

    assert report["nuove"] == 1
    assert len(rows) == 2
    assert {"INBOX:UID:10", "INBOX:UID:11"} == uids
    assert "CONSEGNA: secondo duplicato Legalmail" in subjects


def test_sincronizza_inviati_rimuove_doppione_quando_esiste_gia_copia_imap_inviata(tmp_path):
    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-IMAP-SENT-1",
            cartella=CartellaEmail.INVIATI,
            stato=StatoEmail.LETTA,
            mittente="studio@example.it",
            destinatari="cliente@example.it",
            oggetto="Parere inviato al cliente",
            data="2026-05-10T09:30:00",
            corpo_testo="Testo invio ordinario.",
            uid_imap="Sent Items:UID:44",
            message_id="<sent-sync-44@example.test>",
            origine="IMAP",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="INVIATA:MSG-44",
            cartella=CartellaEmail.INVIATI,
            stato=StatoEmail.LETTA,
            destinatari="cliente@example.it",
            oggetto="Parere inviato al cliente",
            data="2026-05-10T09:30:00",
            corpo_testo="Testo invio ordinario.",
            message_id="<sent-sync-44@example.test>",
            origine="INVIATA",
        )
    )

    msg = SimpleNamespace(
        id="MSG-44",
        email_destinatario="cliente@example.it",
        oggetto="Parere inviato al cliente",
        corpo="Testo invio ordinario.",
        corpo_html="",
        inviato_il="2026-05-10T09:30:00",
        creato_il="2026-05-10T09:29:59",
        sid_esterno="<sent-sync-44@example.test>",
    )

    aggiunti = ge.sincronizza_inviati([msg])
    rows = GestioneEmailRicevute(str(tmp_path / "casella.json"))._carica()

    assert aggiunti == 0
    assert len(rows) == 1
    assert "MAIL-IMAP-SENT-1" in rows
    assert "INVIATA:MSG-44" not in rows
    assert rows["MAIL-IMAP-SENT-1"].uid_imap == "Sent Items:UID:44"


def test_email_dettaglio_visualizza_anche_xml_ed_eml(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    em = EmailRicevuta(
        id="MAIL-ATT-XML",
        cartella="INBOX",
        stato=StatoEmail.LETTA,
        mittente="cancelleria@giustiziapec.it",
        oggetto="PEC con allegati tecnici",
        data="2026-04-09T10:10:00",
        corpo_testo="Contiene daticert.xml e ricevuta.eml.",
        allegati=[
            {
                "nome": "daticert.xml",
                "mime": "application/xml",
                "size": 24,
                "percorso_rel": "MAIL-ATT-XML/daticert.xml",
                "nome_file": "daticert.xml",
            },
            {
                "nome": "ricevuta.eml",
                "mime": "message/rfc822",
                "size": 32,
                "percorso_rel": "MAIL-ATT-XML/ricevuta.eml",
                "nome_file": "ricevuta.eml",
            },
        ],
    )
    ge.aggiungi(em)
    allegato_dir = Path(cfg["EMAIL_CASELLA_DB"]).parent / "allegati" / "MAIL-ATT-XML"
    allegato_dir.mkdir(parents=True, exist_ok=True)
    (allegato_dir / "daticert.xml").write_text("<root>ok</root>\n", encoding="utf-8")
    (allegato_dir / "ricevuta.eml").write_text("Subject: Test\n\nCorpo PEC\n", encoding="utf-8")

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)

        dettaglio = client.get("/email/messaggio/MAIL-ATT-XML?_legacy=1", follow_redirects=True)
        body = dettaglio.get_data(as_text=True)
        assert body.count("Visualizza") >= 2

        xml_inline = client.get("/email/messaggio/MAIL-ATT-XML/allegato/0")
        assert xml_inline.status_code == 200
        assert "xml" in (xml_inline.headers.get("Content-Type", "").lower())

        eml_inline = client.get("/email/messaggio/MAIL-ATT-XML/allegato/1")
        assert eml_inline.status_code == 200
        assert eml_inline.headers.get("Content-Type", "").lower().startswith("text/plain")


def test_aggiorna_comunicazioni_cancelleria_da_email_associa_per_rg_senza_duplicare(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="PEC-COMM-1",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="posta-certificata@legalmail.it",
            mittente_nome="Legalmail PEC",
            oggetto="ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-09T10:15:00",
            corpo_testo="Ricevuta di accettazione del deposito telematico.",
            uid_imap="INBOX:100",
            message_id="<msg-100@example>",
            allegati=[{"nome": "ricevuta.eml"}],
            stato_pct="ACCETTATO_PEC",
        )
    )

    report = aggiorna_comunicazioni_cancelleria_da_email(ge, gf)
    assert report["associati"] == 1
    assert report["duplicati"] == 0

    fasc_reload = gf.get(fasc.id)
    comunicazioni = [
        att for att in fasc_reload.attivita
        if att.tipo == TipoAttivita.COMUNICAZIONE_CANCELLERIA
    ]
    assert len(comunicazioni) == 1
    assert comunicazioni[0].email_uid_imap == "INBOX:100"
    assert "ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024" in comunicazioni[0].email_oggetto
    assert "ricevuta.eml" in (comunicazioni[0].note or "")

    report_dup = aggiorna_comunicazioni_cancelleria_da_email(ge, gf)
    assert report_dup["duplicati"] == 1


def test_aggiorna_comunicazioni_cancelleria_da_email_riconosce_notifiche_giustiziacert(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="RG 1025/2024 Giovannella Maria Elena",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        nome_cliente="Giovannella Maria Elena",
        oggetto="Vendita immobili",
    )

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="PEC-GIUSTIZIA-1",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="tribunale.palmi@civile.ptel.giustiziacert.it",
            mittente_nome="Tribunale di Palmi",
            oggetto="POSTA CERTIFICATA: Tribunale di Palmi Notificazione ai sensi del D.L. 179/2012",
            data="2026-04-10T11:42:10",
            corpo_testo="Procedimento RG 1025/2024 relativo a Giovannella Maria Elena.",
            uid_imap="INBOX:200",
        )
    )

    report = aggiorna_comunicazioni_cancelleria_da_email(ge, gf)

    assert report["associati"] == 1
    fasc_reload = gf.get(fasc.id)
    comunicazioni = [
        att for att in fasc_reload.attivita
        if att.tipo == TipoAttivita.COMUNICAZIONE_CANCELLERIA
    ]
    assert len(comunicazioni) == 1
    assert "Notificazione ai sensi del D.L. 179/2012" in comunicazioni[0].titolo


def test_trova_fascicolo_da_email_pesa_rg_e_nome_cliente(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc_match = gf.nuovo(
        titolo="RG 1025/2024 Giovannella Maria Elena",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        nome_cliente="Giovannella Maria Elena",
        oggetto="Vendita immobili",
    )
    gf.nuovo(
        titolo="RG 1025/2024 altro fascicolo",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        nome_cliente="Mario Rossi",
        oggetto="Opposizione",
    )

    em = EmailRicevuta(
        id="PEC-MATCH-1",
        cartella="INBOX",
        stato=StatoEmail.NON_LETTA,
        mittente="cancelleria@giustiziapec.it",
        oggetto="Esito deposito RG 1025/2024 - Giovannella Maria Elena",
        data="2026-04-20T09:15:00",
        corpo_testo="Tribunale di Palmi - procedimento RG 1025/2024 relativo a Giovannella Maria Elena.",
    )

    trovato = _trova_fascicolo_da_email(gf.tutti(), em)

    assert trovato is not None
    assert trovato.id == fasc_match.id


def test_aggiorna_esiti_da_email_popola_fasi_deposito_tramite_rg(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )
    dep = gf.aggiungi_esito_deposito(
        fasc.id,
        tipo_atto="CITAZIONE",
        pec_destinatario="tribunale.palmi@giustiziapec.it",
        stato="INVIATO",
        nome_atto_principale="citazione.pdf.p7m",
    )

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="E1",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-08T09:00:00",
            corpo_testo="Accettazione PEC",
            stato_pct="ACCETTATO_PEC",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="E2",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="CONSEGNA DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-08T09:05:00",
            corpo_testo="Consegna PEC",
            stato_pct="CONSEGNATO",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="E3",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="WARN CONTROLLI DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-08T09:10:00",
            corpo_testo="Anomalia controlli automatici",
            stato_pct="WARN_CONTROLLI",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="E4",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="AVVISO CANCELLERIA RG 1025/2024",
            data="2026-04-08T09:20:00",
            corpo_testo="Deposito accettato dalla cancelleria",
            stato_pct="ACCETTATO_CANCELLERIA",
        )
    )

    log = aggiorna_esiti_da_email(ge, gf)
    assert log

    gf_reload = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc_reload = gf_reload.get(fasc.id)
    dep_reload = next(d for d in fasc_reload.depositi_pct if d.id == dep.id)
    assert dep_reload.stato == "ACCETTATO_CANCELLERIA"
    assert dep_reload.ricevuta_accettazione
    assert dep_reload.ricevuta_consegna
    assert dep_reload.ricevuta_controlli_automatici
    assert dep_reload.esito_controlli == "WARN"
    assert dep_reload.ricevuta_cancelleria


def test_aggiorna_esiti_da_email_non_marca_come_processata_email_non_abbinata(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="E-NO-MATCH",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-08T09:00:00",
            corpo_testo="Accettazione PEC",
            stato_pct="ACCETTATO_PEC",
        )
    )

    log = aggiorna_esiti_da_email(ge, gf)
    assert any("Nessun deposito abbinato" in row for row in log)
    assert ge.get("E-NO-MATCH").auto_registrata is False

    fasc = gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )
    dep = gf.aggiungi_esito_deposito(
        fasc.id,
        tipo_atto="CITAZIONE",
        pec_destinatario="tribunale.palmi@giustiziapec.it",
        stato="INVIATO",
        nome_atto_principale="citazione.pdf.p7m",
    )

    log_retry = aggiorna_esiti_da_email(ge, gf)
    assert any(dep.id in row for row in log_retry)
    assert ge.get("E-NO-MATCH").auto_registrata is True


def test_api_pec_poll_cancelleria_usa_workflow_condiviso(tmp_path, monkeypatch):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = Path(cfg["STUDIO_CONFIG"])
    studio_cfg.parent.mkdir(parents=True, exist_ok=True)

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
    )

    gs = GestioneConfigStudio(str(studio_cfg))
    config = gs.config
    config.pec = ConfigPEC(
        indirizzo="studio@example.pec.it",
        password="segreta",
        smtp_host="smtp.pec.aruba.it",
        smtp_port=465,
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        use_ssl=True,
    )
    gs.aggiorna(config)

    osservato = {}

    def _fake_sync_workflow(gestione_email, gestione_fascicoli, config_pec, **kwargs):
        osservato["indirizzo"] = config_pec.indirizzo
        osservato["state_path"] = kwargs.get("state_path", "")
        osservato["fascicolo_id"] = kwargs.get("fascicolo_id", "")
        return {
            "sync": {"nuove": 2, "pst_trovate": 2, "errore": ""},
            "auto_esiti": ["ok-1", "ok-2"],
            "poll": {"trovati": 2, "associati": 1, "duplicati": 0, "errori": 0},
        }

    monkeypatch.setattr("pct.email_client.sincronizza_pec_e_fascicoli", _fake_sync_workflow)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)

        response = client.post("/api/pec/poll-cancelleria", json={"id_fascicolo": gf.tutti()[0].id}, follow_redirects=True)

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["nuove"] == 2
    assert data["esiti_aggiornati"] == 2
    assert data["report"]["associati"] == 1
    assert osservato["indirizzo"] == "studio@example.pec.it"
    assert osservato["state_path"].endswith("pec_cancelleria_state.json")
    assert osservato["fascicolo_id"] == gf.tutti()[0].id


def test_api_pec_poll_cancelleria_espone_duplicati_e_warning_sync(tmp_path, monkeypatch):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = Path(cfg["STUDIO_CONFIG"])
    studio_cfg.parent.mkdir(parents=True, exist_ok=True)

    gs = GestioneConfigStudio(str(studio_cfg))
    config = gs.config
    config.pec = ConfigPEC(
        indirizzo="studio@example.pec.it",
        password="segreta",
        smtp_host="smtp.pec.aruba.it",
        smtp_port=465,
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        use_ssl=True,
    )
    gs.aggiorna(config)

    def _fake_sync_workflow(gestione_email, gestione_fascicoli, config_pec, **kwargs):
        return {
            "sync": {"nuove": 0, "pst_trovate": 0, "errore": "Credenziali IMAP non valide"},
            "auto_esiti": [],
            "poll": {
                "trovati": 1,
                "associati": 0,
                "duplicati": 1,
                "errori": 0,
                "da_email": {"trovati": 1, "associati": 0, "duplicati": 1, "errori": 0},
                "poll_imap": {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0},
            },
        }

    monkeypatch.setattr("pct.email_client.sincronizza_pec_e_fascicoli", _fake_sync_workflow)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)

        response = client.post("/api/pec/poll-cancelleria", json={}, follow_redirects=True)

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["warning"] is True
    assert data["sync_errore"] == "Credenziali IMAP non valide"
    assert data["report"]["duplicati"] == 1
    assert "già present" in data["messaggio"]
    assert "Sincronizzazione IMAP non completata" in data["messaggio"]


def test_email_stats_route_restituisce_statistiche_json(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-STATS-1",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="Comunicazione di prova",
            data="2026-04-20T09:30:00",
            corpo_testo="Test statistica.",
            stato_pct="ACCETTATO_PEC",
        )
    )

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        response = client.get("/email/api/stats")

    data = response.get_json()
    assert response.status_code == 200
    assert data["totale"] == 1
    assert data["non_lette"] == 1
    assert data["pst"] == 1


def test_email_sync_route_espone_warning_e_sync_errore(tmp_path, monkeypatch):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    pec_cfg = ConfigPEC(
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        indirizzo="studio@example.pec.it",
        password="segreta",
        use_ssl=True,
    )
    osservato = {}
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(ConfigStudio(pec=pec_cfg))

    def _fake_sync_workflow(gestione_email, gestione_fascicoli, config_pec, **kwargs):
        osservato["db_path"] = str(gestione_fascicoli.db_path)
        osservato["documents_dir"] = str(gestione_fascicoli.documents_dir)
        osservato["archive_dir"] = str(gestione_fascicoli.archive_dir)
        return {
            "sync": {
                "nuove": 0,
                "pst_trovate": 0,
                "errore": "Connessione IMAP non completata entro 15 secondi. Verifica server PEC o rete e riprova.",
            },
            "auto_esiti": [],
            "poll": {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0},
        }

    monkeypatch.setattr("pct.email_client.sincronizza_pec_e_fascicoli", _fake_sync_workflow)

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        response = client.post("/email/sincronizza", follow_redirects=True)

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["warning"] is True
    assert "Sincronizzazione IMAP non completata" in data["messaggio"]
    assert "Connessione IMAP non completata entro 15 secondi" in data["sync_errore"]
    assert osservato["db_path"] == cfg["FASCICOLI_DB"]
    assert osservato["documents_dir"] == cfg["FASCICOLI_DOCS"]
    assert osservato["archive_dir"] == cfg["FASCICOLI_ARCH"]


def test_email_auto_esiti_route_usa_runtime_fascicoli_e_non_genera_warning_spurio(tmp_path, monkeypatch):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    osservato = {}

    def _fake_aggiorna_esiti(gestione_email, gestione_fascicoli):
        osservato["db_path"] = str(gestione_fascicoli.db_path)
        osservato["documents_dir"] = str(gestione_fascicoli.documents_dir)
        osservato["archive_dir"] = str(gestione_fascicoli.archive_dir)
        return []

    def _fake_aggiorna_comunicazioni(gestione_email, gestione_fascicoli):
        osservato["comm_documents_dir"] = str(gestione_fascicoli.documents_dir)
        osservato["comm_archive_dir"] = str(gestione_fascicoli.archive_dir)
        return {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0}

    monkeypatch.setattr("pct.email_client.aggiorna_esiti_da_email", _fake_aggiorna_esiti)
    monkeypatch.setattr(
        "pct.email_client.aggiorna_comunicazioni_cancelleria_da_email",
        _fake_aggiorna_comunicazioni,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        response = client.post("/email/auto-esiti", follow_redirects=True)

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["warning"] is False
    assert "Alcune comunicazioni non sono state elaborate completamente." not in data["messaggio"]
    assert osservato["db_path"] == cfg["FASCICOLI_DB"]
    assert osservato["documents_dir"] == cfg["FASCICOLI_DOCS"]
    assert osservato["archive_dir"] == cfg["FASCICOLI_ARCH"]
    assert osservato["comm_documents_dir"] == cfg["FASCICOLI_DOCS"]
    assert osservato["comm_archive_dir"] == cfg["FASCICOLI_ARCH"]


def test_sincronizza_imap_usa_timeout_e_restituisce_errore_chiaro(tmp_path, monkeypatch):
    import pct.email_client as email_runtime

    osservato = {}

    def _fake_imap_ssl(host, port, timeout=None):
        osservato["host"] = host
        osservato["port"] = port
        osservato["timeout"] = timeout
        raise TimeoutError("timed out")

    monkeypatch.setattr(email_runtime.imaplib, "IMAP4_SSL", _fake_imap_ssl)

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    report = ge.sincronizza_imap(
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        username="studio@example.pec.it",
        password="segreta",
        use_ssl=True,
        cartelle_imap=["INBOX"],
        limite=10,
    )

    assert osservato["timeout"] == 15
    assert report["nuove"] == 0
    assert "Connessione IMAP non completata entro 15 secondi" in report["errore"]


def test_sincronizza_imap_apre_circuit_breaker_dopo_errori_ripetuti(tmp_path, monkeypatch):
    import pct.email_client as email_runtime

    clear_runtime_circuit_breakers("pec_imap")
    monkeypatch.setenv("PCT_IMAP_CIRCUIT_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("PCT_IMAP_CIRCUIT_TIMEOUT", "120")

    osservato = {"chiamate": 0}

    def _fake_imap_ssl(host, port, timeout=None):
        osservato["chiamate"] += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr(email_runtime.imaplib, "IMAP4_SSL", _fake_imap_ssl)

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    for _ in range(2):
        report = ge.sincronizza_imap(
            imap_host="imaps.pec.aruba.it",
            imap_port=993,
            username="studio@example.pec.it",
            password="segreta",
            use_ssl=True,
            cartelle_imap=["INBOX"],
            limite=10,
        )
        assert "Connessione IMAP non completata entro 15 secondi" in report["errore"]

    third = ge.sincronizza_imap(
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        username="studio@example.pec.it",
        password="segreta",
        use_ssl=True,
        cartelle_imap=["INBOX"],
        limite=10,
    )

    assert osservato["chiamate"] == 2
    assert "temporaneamente sospesa" in third["errore"]


def test_poll_cancelleria_pec_usa_timeout_imap(tmp_path, monkeypatch):
    import pct.polling_depositi as polling_runtime

    clear_runtime_circuit_breakers("pec_imap")
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita immobili",
    )

    osservato = {}

    def _fake_imap_ssl(host, port, timeout=None):
        osservato["timeout"] = timeout
        raise TimeoutError("timed out")

    monkeypatch.setattr(polling_runtime.imaplib, "IMAP4_SSL", _fake_imap_ssl)

    report = polling_runtime.poll_cancelleria_pec(
        gf=gf,
        config_pec=SimpleNamespace(
            imap_host="imaps.pec.aruba.it",
            imap_port=993,
            indirizzo="studio@example.pec.it",
            password="segreta",
        ),
        state_path=str(tmp_path / "pec_cancelleria_state.json"),
    )

    assert osservato["timeout"] == 15
    assert report == {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0}
