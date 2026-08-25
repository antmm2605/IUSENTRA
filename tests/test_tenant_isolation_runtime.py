from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import g

from pct.tenant import GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.blueprints.api_v1_react import _api_key_valida
from web.services.tenant_isolation_runtime import (
    TenantIsolationError,
    assert_tenant_data_path,
    ensure_private_tenant_context,
)
from web.services.storage_runtime import _derive_studio_db_path


def _app(tmp_path: Path, *, multi_tenant: bool = False):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg_web(tmp_path), "MULTI_TENANT": multi_tenant})
    app.config["API_KEY"] = "global-test-key"
    return app


def _tenant(app, nome: str, slug: str, api_key: str):
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = manager.crea(nome, slug)
    manager.aggiorna(studio.slug, api_key=api_key)
    studio = manager.get(studio.slug)
    assert studio is not None
    return studio, manager.percorsi_dati(studio.slug, reconcile_aliases=False)


def _tenant_headers(api_key: str, slug: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "X-Tenant-Slug": slug}


def test_single_tenant_global_api_key_restays_compatible(tmp_path: Path):
    app = _app(tmp_path, multi_tenant=False)

    with app.test_client() as client:
        response = client.get("/api/v1/clienti", headers={"X-API-Key": "global-test-key"})

    assert response.status_code == 200


def test_multi_tenant_global_api_key_does_not_authorize_clienti(tmp_path: Path):
    app = _app(tmp_path, multi_tenant=True)
    _tenant(app, "Studio A", "studio-a", "studio-a-key")

    with app.test_client() as client:
        response = client.get(
            "/api/v1/clienti",
            headers={"X-API-Key": "global-test-key", "X-Tenant-Slug": "studio-a"},
        )

    assert response.status_code in {401, 403}
    raw = response.get_data(as_text=True)
    assert "global-test-key" not in raw
    assert str(tmp_path) not in raw


def test_multi_tenant_studio_api_key_authorizes_matching_tenant(tmp_path: Path):
    app = _app(tmp_path, multi_tenant=True)
    _tenant(app, "Studio A", "studio-a", "studio-a-key")

    with app.test_client() as client:
        response = client.get("/api/v1/clienti", headers=_tenant_headers("studio-a-key", "studio-a"))

    assert response.status_code == 200


def test_multi_tenant_studio_api_key_is_blocked_for_other_tenant(tmp_path: Path):
    app = _app(tmp_path, multi_tenant=True)
    _tenant(app, "Studio A", "studio-a", "studio-a-key")
    _tenant(app, "Studio B", "studio-b", "studio-b-key")

    with app.test_client() as client:
        response = client.get("/api/v1/clienti", headers=_tenant_headers("studio-a-key", "studio-b"))

    assert response.status_code in {401, 403}
    raw = response.get_data(as_text=True)
    assert "studio-a-key" not in raw
    assert str(tmp_path) not in raw


def test_missing_tenant_context_for_non_superadmin_is_blocked(tmp_path: Path):
    app = _app(tmp_path, multi_tenant=True)

    with app.test_request_context("/fascicoli"):
        g.multi_tenant_enabled = True
        g.utente_corrente = SimpleNamespace(is_superadmin=False, tenant_slug="")
        g.tenant = None
        g.data_paths = {}

        with pytest.raises(TenantIsolationError) as excinfo:
            ensure_private_tenant_context()

    assert excinfo.value.status_code == 409
    assert str(tmp_path) not in str(excinfo.value)


def test_session_tenant_mismatch_for_non_superadmin_is_blocked(tmp_path: Path):
    app = _app(tmp_path, multi_tenant=True)
    _tenant(app, "Studio A", "studio-a", "studio-a-key")
    studio_b, paths_b = _tenant(app, "Studio B", "studio-b", "studio-b-key")

    with app.test_request_context("/clienti"):
        g.multi_tenant_enabled = True
        g.utente_corrente = SimpleNamespace(is_superadmin=False, tenant_slug="studio-a")
        g.utente_auth_tenant_slug = "studio-a"
        g.tenant = studio_b
        g.tenant_context_slug = "studio-b"
        g.data_paths = paths_b

        with pytest.raises(TenantIsolationError) as excinfo:
            ensure_private_tenant_context()

    assert excinfo.value.status_code == 403


def test_assert_tenant_data_path_blocks_path_outside_tenant_root(tmp_path: Path):
    app = _app(tmp_path, multi_tenant=True)
    studio, paths = _tenant(app, "Studio A", "studio-a", "studio-a-key")
    outside = tmp_path / "clienti" / "anagrafica.json"

    with app.test_request_context("/api/v1/clienti"):
        g.multi_tenant_enabled = True
        g.tenant = studio
        g.tenant_context_slug = "studio-a"
        g.data_paths = paths

        with pytest.raises(TenantIsolationError) as excinfo:
            assert_tenant_data_path(outside, key="CLIENTI_DB")

    message = str(excinfo.value)
    assert excinfo.value.status_code == 403
    assert str(outside) not in message
    assert str(tmp_path) not in message


def test_crm_usa_percorso_tenant_e_rientra_nel_perimetro_isolato(tmp_path: Path):
    """Il CRM non deve mai tornare al filesystem dell'immagine applicativa."""

    app = _app(tmp_path, multi_tenant=True)
    studio, paths = _tenant(app, "Studio CRM", "studio-crm", "studio-crm-key")

    crm_path = Path(paths["CRM_DB"])
    assert crm_path == tmp_path / "tenants" / "studio-crm" / "crm" / "leads.json"
    aml_path = Path(paths["ANTIRICICLAGGIO_DB"])
    assert aml_path == tmp_path / "tenants" / "studio-crm" / "antiriciclaggio" / "verifiche.json"

    with app.test_request_context("/crm"):
        g.multi_tenant_enabled = True
        g.tenant = studio
        g.tenant_context_slug = "studio-crm"
        g.data_paths = paths

        assert_tenant_data_path(crm_path, key="CRM_DB") == str(crm_path)
        assert_tenant_data_path(aml_path, key="ANTIRICICLAGGIO_DB") == str(aml_path)

    assert _derive_studio_db_path(str(crm_path)) == str(
        tmp_path / "tenants" / "studio-crm" / "studio.db"
    )
    assert _derive_studio_db_path(str(aml_path)) == str(
        tmp_path / "tenants" / "studio-crm" / "studio.db"
    )


def test_api_react_key_validation_is_tenant_aware(tmp_path: Path):
    app = _app(tmp_path, multi_tenant=True)
    _tenant(app, "Studio A", "studio-a", "studio-a-key")

    with app.test_client() as client:
        valid = client.get("/api/v1/ui/bootstrap", headers=_tenant_headers("studio-a-key", "studio-a"))
        global_key = client.get(
            "/api/v1/ui/bootstrap",
            headers={"X-API-Key": "global-test-key", "X-Studio-Slug": "studio-a"},
        )

    assert valid.status_code == 200
    assert global_key.status_code in {401, 403}


def test_api_react_api_key_helper_accepts_only_matching_tenant_key(tmp_path: Path):
    app = _app(tmp_path, multi_tenant=True)
    _tenant(app, "Studio A", "studio-a", "studio-a-key")
    _tenant(app, "Studio B", "studio-b", "studio-b-key")

    with app.test_request_context(
        "/api/v1/ui/bootstrap",
        headers=_tenant_headers("studio-a-key", "studio-a"),
    ):
        g.multi_tenant_enabled = True
        assert _api_key_valida() is True

    with app.test_request_context(
        "/api/v1/ui/bootstrap",
        headers=_tenant_headers("studio-a-key", "studio-b"),
    ):
        g.multi_tenant_enabled = True
        assert _api_key_valida() is False


def test_expected_tenant_root_memoizzato_per_richiesta(tmp_path: Path, monkeypatch):
    """La radice studio si risolve una volta sola: il registry non va riletto per ogni chiave."""

    app = _app(tmp_path, multi_tenant=True)
    studio, paths = _tenant(app, "Studio A", "studio-a", "studio-a-key")

    import web.services.tenant_isolation_runtime as isolation

    chiamate: list[str] = []
    originale = isolation._resolve_expected_tenant_root

    def _conta(slug, request_paths):
        chiamate.append(slug)
        return originale(slug, request_paths)

    monkeypatch.setattr(isolation, "_resolve_expected_tenant_root", _conta)

    with app.test_request_context("/api/v1/clienti"):
        g.multi_tenant_enabled = True
        g.tenant = studio
        g.tenant_context_slug = "studio-a"
        g.data_paths = paths

        for _ in range(5):
            assert_tenant_data_path(paths["CLIENTI_DB"], key="CLIENTI_DB")

    assert chiamate == ["studio-a"]


def test_cache_radice_studio_non_perde_isolamento_tra_studi(tmp_path: Path):
    """Cambiare studio nella stessa richiesta ricalcola la radice e blocca il percorso altrui."""

    app = _app(tmp_path, multi_tenant=True)
    studio_a, paths_a = _tenant(app, "Studio A", "studio-a", "studio-a-key")
    studio_b, paths_b = _tenant(app, "Studio B", "studio-b", "studio-b-key")

    with app.test_request_context("/api/v1/clienti"):
        g.multi_tenant_enabled = True
        g.tenant = studio_a
        g.tenant_context_slug = "studio-a"
        g.data_paths = paths_a
        assert_tenant_data_path(paths_a["CLIENTI_DB"], key="CLIENTI_DB")

        g.tenant = studio_b
        g.tenant_context_slug = "studio-b"
        g.data_paths = paths_b
        assert_tenant_data_path(paths_b["CLIENTI_DB"], key="CLIENTI_DB")

        with pytest.raises(TenantIsolationError) as excinfo:
            assert_tenant_data_path(paths_a["CLIENTI_DB"], key="CLIENTI_DB")

    assert excinfo.value.status_code == 403


def test_confronto_contenimento_percorsi_non_confonde_prefissi_omonimi(tmp_path: Path):
    """`/dati/studio-a-bis` non deve risultare interno a `/dati/studio-a`."""

    from web.services.tenant_isolation_runtime import _path_is_relative_to

    radice = tmp_path / "studio-a"
    assert _path_is_relative_to(radice, radice) is True
    assert _path_is_relative_to(radice / "clienti" / "anagrafica.json", radice) is True
    assert _path_is_relative_to(tmp_path / "studio-a-bis" / "clienti.json", radice) is False
    assert _path_is_relative_to(tmp_path / "studio-b", radice) is False
