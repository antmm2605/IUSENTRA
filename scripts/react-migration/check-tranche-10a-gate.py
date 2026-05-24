from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_web_bootstrap import _cfg_web, _seed_tenant_admin, _write_studio_config  # noqa: E402
from web.app import create_app  # noqa: E402


REPORT = ROOT / "artifacts/react-migration/tranche-10a-gate.md"


def _is_react_shell(response) -> bool:
    html = response.get_data(as_text=True)
    return 'id="root"' in html and "iusentra-react-bootstrap" in html and "IUSENTRA - React Shell" in html


def _is_json(response) -> bool:
    return bool(response.is_json and isinstance(response.get_json(silent=True), dict))


def _record(results: list[dict], name: str, ok: bool, detail: str) -> None:
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="iusentra-tranche-10a-", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        _write_studio_config(tmp_path / "config" / "studio.json")
        app = create_app(_cfg_web(tmp_path))
        studio, tenant_admin = _seed_tenant_admin(app)

        with app.test_client() as client:
            login = client.post(
                "/login",
                data={
                    "username": tenant_admin.username,
                    "password": "PasswordSicura!123",
                    "studio_slug": studio.slug,
                },
                follow_redirects=False,
            )
            _record(results, "login tenant", login.status_code == 302, f"status={login.status_code}")

            for path in (
                "/giurisprudenza",
                "/giurisprudenza/nuova",
                "/legal-intelligence",
                "/legal-intelligence/news",
                "/legal-intelligence/mediazione",
                "/ricerca-legale",
            ):
                response = client.get(path, headers={"Accept": "text/html"}, follow_redirects=False)
                _record(
                    results,
                    f"React shell {path}",
                    response.status_code == 200 and _is_react_shell(response),
                    f"status={response.status_code}",
                )

            for path in (
                "/giurisprudenza?_legacy=1",
                "/giurisprudenza/nuova?_legacy=1",
                "/giurisprudenza/qualunque",
                "/legal-intelligence?_legacy=1",
                "/legal-intelligence/news?_legacy=1",
                "/legal-intelligence/mediazione?_legacy=1",
                "/legal-intelligence/qualunque",
                "/ricerca-legale?_legacy=1",
                "/ricerca-legale/qualunque",
                "/checklist",
                "/deposito/checklist",
            ):
                response = client.get(path, headers={"Accept": "text/html"}, follow_redirects=False)
                _record(
                    results,
                    f"Ancora legacy {path}",
                    not _is_react_shell(response),
                    f"status={response.status_code}",
                )

            for path in (
                "/api/v1/ui/giurisprudenza",
                "/api/v1/ui/giurisprudenza/nuova",
                "/api/v1/ui/legal-intelligence",
                "/api/v1/ui/legal-intelligence/news",
                "/api/v1/ui/legal-intelligence/mediazione",
                "/api/v1/ui/ricerca-legale",
            ):
                response = client.get(path, headers={"Accept": "application/json"})
                _record(
                    results,
                    f"JSON {path}",
                    response.status_code == 200 and _is_json(response),
                    f"status={response.status_code}",
                )

            response = client.post(
                "/api/v1/ui/giurisprudenza/nuova",
                json={
                    "titolo": "Cassazione su consenso informato",
                    "source_system": "manuale_interno",
                    "area": "Civile",
                    "massima": "La prova del consenso informato deve essere specifica.",
                },
                headers={"Accept": "application/json"},
            )
            payload = response.get_json(silent=True) or {}
            _record(
                results,
                "JSON POST /api/v1/ui/giurisprudenza/nuova",
                response.status_code == 201 and payload.get("ok") is True and bool(payload.get("record", {}).get("id")),
                f"status={response.status_code}",
            )

            for path in (
                "/giurisprudenza",
                "/giurisprudenza/nuova",
                "/legal-intelligence",
                "/legal-intelligence/news",
                "/deposito/checklist",
            ):
                response = client.post(path, data={}, headers={"Accept": "text/html"}, follow_redirects=False)
                _record(
                    results,
                    f"POST non intercettato {path}",
                    not _is_react_shell(response),
                    f"status={response.status_code}",
                )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Tranche 10A gate check",
        "",
        *[
            f"- [{'OK' if item['ok'] else 'KO'}] {item['name']} ({item['detail']})"
            for item in results
        ],
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    failures = [item for item in results if not item["ok"]]
    if failures:
        print(json.dumps({"ok": False, "failures": failures}, ensure_ascii=False, indent=2))
        return 1
    print("Tranche 10A gate OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
