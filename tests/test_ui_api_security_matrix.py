from __future__ import annotations

import json
import re
from pathlib import Path

from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.tenant import GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg_web(tmp_path), "MULTI_TENANT": True})
    app.config["API_KEY"] = "global-test-key"
    return app


def _tenant(app, *, nome: str, slug: str, api_key: str) -> tuple[object, dict[str, str]]:
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = manager.crea(nome, slug)
    manager.aggiorna(studio.slug, api_key=api_key)
    studio = manager.get(studio.slug)
    assert studio is not None
    return studio, manager.percorsi_dati(studio.slug, reconcile_aliases=False)


def _tenant_headers(api_key: str, slug: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "X-Tenant-Slug": slug}


def _seed_fascicolo(paths: dict[str, str], title: str):
    repo = GestioneFascicoli(
        db_path=paths["FASCICOLI_DB"],
        documents_dir=paths["FASCICOLI_DOCS"],
        archive_dir=paths["FASCICOLI_ARCH"],
        studio_db=None,
    )
    return repo.nuovo(title, TipoFascicolo.CIVILE, nome_cliente="Cliente matrice")


def _audit_text(audit_path: str) -> str:
    path = Path(audit_path)
    if not path.exists():
        return ""
    payload = json.loads(path.read_text(encoding="utf-8") or "[]")
    return json.dumps(payload, ensure_ascii=False)


def _sample_value(name: str, converter: str = "") -> str:
    if converter == "int":
        return "1"
    samples = {
        "account_id": "account-matrice",
        "asset_id": "1",
        "calendar_id": "calendar-matrice",
        "conflict_id": "conflict-matrice",
        "conferimento_id": "conferimento-matrice",
        "deposito_id": "deposito-matrice",
        "id_cliente": "cliente-matrice",
        "id_conferimento": "conferimento-matrice",
        "id_doc": "documento-matrice",
        "id_documento": "documento-matrice",
        "id_email": "email-matrice",
        "id_evento": "evento-matrice",
        "id_fasc": "fascicolo-matrice",
        "id_pagamento": "pagamento-matrice",
        "id_preventivo": "preventivo-matrice",
        "id_prenotazione": "prenotazione-matrice",
        "id_sessione": "sessione-matrice",
        "id_soggetto": "soggetto-matrice",
        "id_utente": "utente-matrice",
        "id_voce": "voce-matrice",
        "model_code": "CIV_CIT_001",
        "module_id": "strumenti-forensi",
        "page_id": "1",
        "preventivo_id": "preventivo-matrice",
        "profile_id": "profilo-matrice",
        "qa_id": "qa-matrice",
        "revision_id": "1",
        "run_id": "run-matrice",
        "section": "studio",
        "slot_key": "procura",
        "surface": "checklist",
        "test_id": "smtp",
        "tool_id": "calcolo-interessi",
    }
    return samples.get(name, f"{name}-matrice")


def _sample_path(rule: str) -> str:
    def replace(match: re.Match[str]) -> str:
        converter = match.group("converter") or ""
        name = match.group("name")
        return _sample_value(name, converter)

    return re.sub(r"<(?:(?P<converter>[^:<>]+):)?(?P<name>[^<>]+)>", replace, rule)


def _ui_api_cases(app) -> list[tuple[str, str]]:
    cases: list[tuple[str, str]] = []
    for rule in app.url_map.iter_rules():
        if not str(rule.rule).startswith("/api/v1/ui/"):
            continue
        for method in sorted((rule.methods or set()) - {"HEAD", "OPTIONS"}):
            cases.append((method, _sample_path(str(rule.rule))))
    return sorted(set(cases))


def _is_public_client_portal_path(path: str) -> bool:
    return path.startswith("/api/v1/ui/client-portal/public/")


def test_all_ui_api_endpoints_enforce_auth_tenant_denials_and_forbidden_context_keys(tmp_path: Path):
    app = _app(tmp_path)
    _studio_a, paths_a = _tenant(app, nome="Studio A", slug="studio-a", api_key="studio-a-key")
    _tenant(app, nome="Studio B", slug="studio-b", api_key="studio-b-key")
    cases = _ui_api_cases(app)

    assert len(cases) >= 200

    forbidden_query = {
        "tenant_id": "studio-b",
        "tenant_slug": "studio-b",
        "studio_id": "studio-b",
        "studio_slug": "studio-b",
        "user_id": "utente-b",
        "api_key": "query-api-key-segreta",
        "token": "token-segreto",
        "access_token": "access-token-segreto",
        "refresh_token": "refresh-token-segreto",
        "redirect": "https://evil.example/ritorno",
        "redirect_url": "https://evil.example/ritorno-url",
        "return_url": "https://evil.example/return",
        "next": "https://evil.example/next",
        "path": "C:/studio-b/segreto.pdf",
        "root_path": "../studio-b/segreto.pdf",
        "file_path": "C:/studio-b/segreto.pdf",
    }
    sensitive_fragments = {
        "studio-b-key",
        "studio-a-key",
        "query-api-key-segreta",
        "token-segreto",
        "access-token-segreto",
        "refresh-token-segreto",
        "https://evil.example",
        "../studio-b/segreto.pdf",
        "C:/studio-b/segreto.pdf",
        str(tmp_path),
    }

    with app.test_client() as client:
        for method, path in cases:
            anonymous = client.open(path, method=method)
            if _is_public_client_portal_path(path):
                assert anonymous.status_code >= 400, (
                    method,
                    path,
                    anonymous.status_code,
                    anonymous.get_data(as_text=True),
                )
            else:
                assert anonymous.status_code == 401, (
                    method,
                    path,
                    anonymous.status_code,
                    anonymous.get_data(as_text=True),
                )
            assert not any(fragment in anonymous.get_data(as_text=True) for fragment in sensitive_fragments)

            mismatch = client.open(path, method=method, headers=_tenant_headers("studio-a-key", "studio-b"))
            if _is_public_client_portal_path(path):
                assert mismatch.status_code == anonymous.status_code, (
                    method,
                    path,
                    mismatch.status_code,
                    mismatch.get_data(as_text=True),
                )
            else:
                assert mismatch.status_code == 403, (
                    method,
                    path,
                    mismatch.status_code,
                    mismatch.get_data(as_text=True),
                )
            assert not any(fragment in mismatch.get_data(as_text=True) for fragment in sensitive_fragments)

            forced = client.open(
                path,
                method=method,
                headers=_tenant_headers("studio-a-key", "studio-a"),
                query_string=forbidden_query,
            )
            raw_forced = forced.get_data(as_text=True)
            assert forced.status_code == 400, (method, path, forced.status_code, raw_forced)
            assert forced.get_json()["code"] == "backend_security_control_param"
            assert set(forbidden_query).issubset({item["key"] for item in forced.get_json()["violations"]})
            assert not any(fragment in raw_forced for fragment in sensitive_fragments)

    global_audit = _audit_text(app.config["AUDIT_DB"])
    tenant_a_audit = _audit_text(paths_a["AUDIT_DB"])
    assert "policy_denied.tenant_isolation" in global_audit
    assert "policy_denied.backend_security" in tenant_a_audit
    for audit_raw in (global_audit, tenant_a_audit):
        assert not any(fragment in audit_raw for fragment in sensitive_fragments)


def test_ui_api_security_matrix_copre_auth_tenant_cross_tenant_success_e_audit_denial(tmp_path: Path):
    app = _app(tmp_path)
    _studio_a, paths_a = _tenant(app, nome="Studio A", slug="studio-a", api_key="studio-a-key")
    _studio_b, paths_b = _tenant(app, nome="Studio B", slug="studio-b", api_key="studio-b-key")
    fascicolo_b = _seed_fascicolo(paths_b, "Fascicolo riservato Studio B")

    with app.test_client() as client:
        anonymous = client.get("/api/v1/ui/fascicoli")
        mismatch = client.get("/api/v1/ui/fascicoli", headers=_tenant_headers("studio-a-key", "studio-b"))
        forced_tenant = client.get(
            "/api/v1/ui/fascicoli?tenant_id=studio-b",
            headers=_tenant_headers("studio-a-key", "studio-a"),
        )
        forced_path = client.post(
            "/api/v1/ui/sito-studio/builder/assets/upload",
            data={"root_path": "../studio-b/allegato.pdf"},
            headers=_tenant_headers("studio-a-key", "studio-a"),
        )
        cross_tenant = client.get(
            f"/api/v1/ui/fascicoli/{fascicolo_b.id}",
            headers=_tenant_headers("studio-a-key", "studio-a"),
        )
        success_list = client.get("/api/v1/ui/fascicoli", headers=_tenant_headers("studio-b-key", "studio-b"))
        success_detail = client.get(
            f"/api/v1/ui/fascicoli/{fascicolo_b.id}",
            headers=_tenant_headers("studio-b-key", "studio-b"),
        )

    assert anonymous.status_code == 401
    assert mismatch.status_code == 403
    assert forced_tenant.status_code == 400
    assert forced_tenant.get_json()["code"] == "backend_security_control_param"
    assert "studio-b" not in forced_tenant.get_data(as_text=True)
    assert forced_path.status_code == 400
    assert forced_path.get_json()["code"] == "backend_security_control_param"
    assert "../studio-b/allegato.pdf" not in forced_path.get_data(as_text=True)

    cross_payload = cross_tenant.get_json()
    assert cross_tenant.status_code == 404
    assert cross_payload["notFound"] is True
    assert "Fascicolo riservato Studio B" not in cross_tenant.get_data(as_text=True)

    assert success_list.status_code == 200
    assert success_detail.status_code == 200
    assert success_detail.get_json().get("notFound") is not True

    audit_raw = _audit_text(paths_a["AUDIT_DB"])
    assert "policy_denied.backend_security" in audit_raw
    assert "tenant_id" in audit_raw
    assert "studio-b" not in audit_raw
