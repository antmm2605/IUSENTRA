from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, Recapiti, TipoCliente
from pct.email_client import EmailRicevuta, GestioneEmailRicevute
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.soggetti import GestioneSoggetti, RuoloSoggetto, TipoSoggetto
from pct.storage import StudioDB
from pct.tenant import GestioneTenant
from web.app import create_app
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data


DEFAULT_ROOT = REPO_ROOT / ".tmp" / "notifiche-legali-ui"
INFO_FILE = DEFAULT_ROOT / "server-info.json"


def _inside_tmp(path: Path) -> bool:
    tmp_root = (REPO_ROOT / ".tmp").resolve()
    try:
        path.resolve().relative_to(tmp_root)
    except ValueError:
        return False
    return True


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Verifica Notifiche",
                    "avvocato": "Avv. Verifica",
                    "codice_fiscale_avvocato": "VRFVCF80A01H501U",
                    "ordine_avvocati": "Roma",
                    "indirizzo": "Via Roma 20",
                    "city": "Roma",
                    "province": "RM",
                    "telefono": "06 123456",
                    "email": "studio.verifica@example.it",
                },
                "pec": {
                    "indirizzo": "studio.verifica@pec.example.it",
                    "password": "",
                    "smtp_host": "smtp.pec.example.it",
                    "smtp_port": 465,
                    "imap_host": "imap.pec.example.it",
                    "imap_port": 993,
                    "use_ssl": True,
                },
                "ai": {
                    "enabled": True,
                    "base_url": "http://127.0.0.1:11434/api/version",
                    "auto_index_documents": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _safe_demo_redirect_target(raw_target: str | None) -> str:
    target = str(raw_target or "/fascicoli").strip()
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return "/fascicoli"
    return target


def _config(root: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "notifiche-ui-demo",
        "AUTH_DB": str(root / "auth" / "utenti.json"),
        "AUDIT_DB": str(root / "auth" / "audit.json"),
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH": str(root / "auth" / "bootstrap_admin.json"),
        "CLIENTI_DB": str(root / "clienti" / "anagrafica.json"),
        "CONDIVISIONI_DB": str(root / "clienti" / "condivisioni.json"),
        "FASCICOLI_DB": str(root / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(root / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(root / "fascicoli" / "archivio"),
        "PRACTICE_ENGINE_DB": str(root / "fascicoli" / "practice_engine.json"),
        "AGENDA_DB": str(root / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(root / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(root / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(root / "email" / "casella.json"),
        "EMAIL_ORDINARIA_DB": str(root / "email" / "ordinaria.json"),
        "SEARCH_INDEX": str(root / "search" / "index.db"),
        "SOGGETTI_DB": str(root / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(root / "soggetti" / "parti.json"),
        "PST_IMPORT_DIR": str(root / "import_pst"),
        "VALIDATION_RUNS_DB": str(root / "intelligence" / "validation_runs.json"),
        "LEGAL_INTELLIGENCE_DB": str(root / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(root / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(root / "intelligence" / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(root / "intelligence" / "workspace_intelligence.json"),
        "TEMPLATE_ATTI_DB": str(root / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(root / "template_atti" / "editor_layout.json"),
        "PREVENTIVI_DB": str(root / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(root / "fatturazione" / "parcelle.json"),
        "PAGAMENTI_DIR": str(root / "pagamenti"),
        "TIMESHEET_DB": str(root / "timesheet" / "entries.json"),
        "LOCAL_AI_DB": str(root / "intelligence" / "local_ai.db"),
        "LOCAL_AI_POLICY": str(REPO_ROOT / "config" / "ai-policy.json"),
        "LOCAL_AI_MODELS_DIR": str(root / "intelligence" / "models"),
        "STUDIO_CONFIG": str(root / "config" / "studio.json"),
        "PDP_PENALE_DB": str(root / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(root / "telematico" / "workflow.db"),
        "PORTALE_DB": str(root / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(root / "portale" / "uploads"),
        "TENANTS_REGISTRY": str(root / "tenants.json"),
    }


def _seed_tenant(app, *, username: str, password: str) -> tuple[str, str]:
    tenants = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tenants.get("studio-verifica") or tenants.crea(
        "Studio Verifica Notifiche",
        "studio-verifica",
        db_config={"mode": "SQLITE"},
    )
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio.slug)
    paths = tenants.percorsi_dati(studio.slug)
    utenti = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=StudioDB.get(paths["STUDIO_DB"]),
    )
    utente = utenti.get_by_username(username)
    if utente is None:
        utente = utenti.crea(
            username=username,
            password=password,
            ruolo=RuoloUtente.AMMINISTRATORE,
            tenant_slug=studio.slug,
            must_change_password=False,
        )
    utenti_json = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=None,
    )
    if utenti_json.get_by_username(username) is None:
        utenti_json.importa_utente_esistente(utente, tenant_slug=studio.slug, preserve_id=True)
    return studio.slug, utente.id


def _seed_fascicoli_and_pec(app, tenant_slug: str) -> str:
    tenants = GestioneTenant(app.config["TENANTS_REGISTRY"])
    paths = tenants.percorsi_dati(tenant_slug)
    fascicoli = GestioneFascicoli(
        db_path=paths["FASCICOLI_DB"],
        documents_dir=paths["FASCICOLI_DOCS"],
        archive_dir=paths["FASCICOLI_ARCH"],
    )
    clienti = GestioneClienti(paths["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_GIURIDICA,
        ragione_sociale="Cliente S.r.l.",
        partita_iva="01234567890",
        recapiti=Recapiti(email="amministrazione@cliente.example.it", pec="cliente@pec.example.it"),
    )
    target = fascicoli.nuovo(
        "Cliente S.r.l. / Controparte S.p.A. - provvedimento da notificare",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente="Cliente S.r.l.",
        controparte="Controparte S.p.A.",
        tribunale="Tribunale di Roma",
        numero_rg="1234",
        anno_rg=2026,
        giudice="Dott. Verdi",
        sezione="III",
        oggetto="Opposizione a decreto ingiuntivo",
    )
    soggetti = GestioneSoggetti(paths["SOGGETTI_DB"], paths["SOGGETTI_PARTI_DB"])
    controparte = soggetti.crea(
        TipoSoggetto.PERSONA_GIURIDICA,
        ragione_sociale="Controparte S.p.A.",
        partita_iva="01234567890",
        recapiti=Recapiti(email="ufficio.legale@controparte.example.it", pec="controparte@pec.example.it"),
    )
    soggetti.aggiungi_parte(
        target.id,
        controparte.id,
        RuoloSoggetto.CONTROPARTE,
        note="Destinatario demo con PEC da pubblico elenco INI-PEC.",
    )
    fascicoli.aggiungi_documento(
        target.id,
        "atto_gia_presente.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-1.4\natto gia presente nel fascicolo",
        caricato_da="demo-ui",
        fonte_documento="CARICAMENTO_STUDIO",
    )
    fascicoli.sincronizza_deposito_portale(
        target.id,
        fonte="PST",
        id_deposito_esterno="PST-DEMO-1234",
        tipo_atto="Documenti del fascicolo",
        data_deposito="2026-05-23",
        mittente="Tribunale di Roma",
        servizio_portale="ConsultazioneFascicolo",
        documenti_portale=[
            {
                "id_documento": "pst-doc-ordinanza",
                "nome": "ordinanza_da_notificare.pdf",
                "tipo": "Ordinanza da notificare",
                "data_deposito": "2026-05-23",
                "mittente": "Tribunale di Roma",
                "dimensione_bytes": 42120,
            }
        ],
        registrato_da="demo-ui",
        note="Metadati portale disponibili: non generano notifica senza PEC dell'ufficio.",
    )
    for index in range(1, 32):
        fascicoli.nuovo(
            f"Fascicolo demo paginazione {index:02d}",
            TipoFascicolo.CIVILE,
            nome_cliente=f"Cliente Demo {index:02d}",
            controparte=f"Controparte Demo {index:02d}",
            tribunale="Tribunale di Roma",
            numero_rg=str(2000 + index),
            anno_rg=2026,
        )
    email = GestioneEmailRicevute(paths["EMAIL_CASELLA_DB"])
    eml_bytes = (
        "From: Cancelleria Tribunale di Roma <cancelleria.tribunale.roma@giustiziacert.it>\r\n"
        "To: studio.verifica@pec.example.it\r\n"
        "Subject: Tribunale di Roma R.G. 1234/2026 - provvedimento da notificare\r\n"
        "Date: Sat, 23 May 2026 10:15:00 +0200\r\n"
        "Message-ID: <pec-cancelleria-1234@giustizia>\r\n"
        "\r\n"
        "Si comunica il rilascio del provvedimento ordinanza_da_notificare.pdf da notificare nel procedimento R.G. 1234/2026.\r\n"
    ).encode("utf-8")
    eml_dir = Path(paths["EMAIL_CASELLA_DB"]).parent / "eml"
    eml_dir.mkdir(parents=True, exist_ok=True)
    eml_path = eml_dir / "pec-cancelleria-1234.eml"
    eml_path.write_bytes(eml_bytes)
    eml_sha256 = hashlib.sha256(eml_bytes).hexdigest()
    email.aggiungi(
        EmailRicevuta(
            id="pec-cancelleria-1234",
            mittente="cancelleria.tribunale.roma@giustiziacert.it",
            mittente_nome="Cancelleria Tribunale di Roma",
            destinatari="studio.verifica@pec.example.it",
            oggetto="Tribunale di Roma R.G. 1234/2026 - provvedimento da notificare",
            data="2026-05-23T10:15:00",
            corpo_testo=(
                "Si comunica il rilascio del provvedimento ordinanza_da_notificare.pdf "
                "da notificare nel procedimento R.G. 1234/2026."
            ),
            allegati=[
                {
                    "nome": "ordinanza_da_notificare.pdf",
                    "mime": "application/pdf",
                    "size": 42120,
                    "sha256": "c" * 64,
                }
            ],
            message_id="<pec-cancelleria-1234@giustizia>",
            eml_file="eml/pec-cancelleria-1234.eml",
            eml_sha256=eml_sha256,
            origine="IMAP",
        )
    )
    return target.id


def create_demo_app(root: Path, *, username: str, password: str) -> tuple[object, dict]:
    if root.exists():
        if not _inside_tmp(root):
            raise RuntimeError(f"Percorso demo non sicuro: {root}")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    _write_studio_config(root / "config" / "studio.json")
    app = create_app(_config(root))
    tenant_slug, user_id = _seed_tenant(app, username=username, password=password)
    fascicolo_id = _seed_fascicoli_and_pec(app, tenant_slug)

    def _open_demo_session():
        from flask import redirect, request, session

        next_url = _safe_demo_redirect_target(request.args.get("next"))
        session.clear()
        session["user_id"] = user_id
        session["tenant_slug"] = tenant_slug
        session["auth_scope"] = "tenant"
        session["auth_tenant_slug"] = tenant_slug
        session["last_activity"] = datetime.now().isoformat()
        session["must_change_password"] = False
        session.permanent = True
        return redirect(next_url)

    def _demo_login_before_request():
        from flask import request

        if request.path == "/__demo_login":
            return _open_demo_session()
        return None

    app.before_request_funcs.setdefault(None, []).insert(0, _demo_login_before_request)

    @app.get("/__demo_login")
    def __demo_login():
        return _open_demo_session()

    return app, {
        "tenantSlug": tenant_slug,
        "userId": user_id,
        "username": username,
        "fascicoloId": fascicolo_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Server demo UI per verifica Relata notifica.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5067)
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--username", default="verifica-notifiche")
    parser.add_argument("--password", default="PasswordSicura!123")
    args = parser.parse_args()

    root = Path(args.root)
    app, info = create_demo_app(root, username=args.username, password=args.password)
    info.update(
        {
            "baseUrl": f"http://{args.host}:{args.port}",
            "notificheUrl": f"http://{args.host}:{args.port}/notifiche-legali?id_fascicolo={info['fascicoloId']}&fase=notifica",
            "fascicoliUrl": f"http://{args.host}:{args.port}/fascicoli",
        }
    )
    info_path = root / "server-info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False), flush=True)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
