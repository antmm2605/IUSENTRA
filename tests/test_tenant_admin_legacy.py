import json

from pct.auth import GestioneUtenti, RuoloUtente
from pct.tenant import DbMode, GestioneTenant, StudioLegale
from web.app import create_app
from web.services.storage_runtime import get_request_studio_db


def test_studio_legale_legacy_db_config_string_non_rompe_database():
    studio = StudioLegale.from_dict(
        {
            "slug": "antonella-mammola",
            "nome": "Studio Antonella Mammola",
            "db_config": "LOCAL",
            "branding": "legacy-string",
            "moduli_override": "fascicoli,clienti",
        }
    )

    assert studio.database.mode == DbMode.LOCAL
    assert studio.branding == {}
    assert studio.moduli_override == ["fascicoli", "clienti"]


def test_admin_dettaglio_studio_renderizza_anche_con_db_legacy(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    app = create_app(
        {
            "TESTING": True,
            "TENANTS_REGISTRY": str(registry_path),
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
            "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        }
    )

    gu = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=get_request_studio_db(app.config["CLIENTI_DB"]),
    )
    superadmin = gu.crea(
        username="legacy-superadmin",
        password="superpass123",
        ruolo=RuoloUtente.SUPERADMIN,
        tenant_slug="",
        must_change_password=False,
    )

    client = app.test_client()
    client.post(
        "/login",
        data={"username": superadmin.username, "password": "superpass123"},
        follow_redirects=False,
    )
    resp = client.get("/admin/studi/antonella-mammola")

    assert resp.status_code == 200
    assert b"Antonella Mammola" in resp.data


def test_gestione_tenant_get_supporta_registry_con_chiave_diversa_dallo_slug(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tm = GestioneTenant(str(registry_path))
    studio = tm.get("antonella-mammola")

    assert studio is not None
    assert studio.slug == "antonella-mammola"


def test_percorsi_dati_usano_storage_key_legacy_quando_presente(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "storage_key": "tenant-8bf98719c459",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": {
                        "mode": "LOCAL",
                        "directory_dati": str(tmp_path / "tenants" / "tenant-8bf98719c459"),
                    },
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tm = GestioneTenant(str(registry_path))
    paths = tm.percorsi_dati("antonella-mammola")

    assert "tenant-8bf98719c459" in paths["CLIENTI_DB"]
    assert "tenant-8bf98719c459" in paths["AUTH_DB"]
