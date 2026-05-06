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


REPORT = ROOT / "artifacts/react-migration/tranche-7a-gate.md"


def _is_react_shell(response) -> bool:
    html = response.get_data(as_text=True)
    return 'id="root"' in html and "iusentra-react-bootstrap" in html and "IUSENTRA - React Shell" in html


def _is_json(response) -> bool:
    return bool(response.is_json and isinstance(response.get_json(silent=True), dict))


def _record(results: list[dict], name: str, ok: bool, detail: str) -> None:
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="iusentra-tranche-7a-", ignore_cleanup_errors=True) as tmp:
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

            for path in ("/preventivi", "/preventivi/nuovo", "/preventivi/conferimento/nuovo"):
                response = client.get(path, headers={"Accept": "text/html"})
                _record(
                    results,
                    f"React shell {path}",
                    response.status_code == 200 and _is_react_shell(response),
                    f"status={response.status_code}",
                )

            for path in (
                "/preventivi?_legacy=1",
                "/preventivi/nuovo?_legacy=1",
                "/preventivi/conferimento/nuovo?_legacy=1",
                "/preventivi/wizard",
                "/preventivi/p/qualunque",
                "/preventivi/conferimento/qualunque",
                "/preventivi/qualunque",
                "/compensi-forensi",
                "/tariffario",
            ):
                response = client.get(path, headers={"Accept": "text/html"}, follow_redirects=False)
                _record(
                    results,
                    f"Ancora legacy {path}",
                    not _is_react_shell(response),
                    f"status={response.status_code}",
                )

            for path in (
                "/api/v1/ui/preventivi",
                "/api/v1/ui/preventivi/nuovo",
                "/api/v1/ui/preventivi/conferimento/nuovo",
            ):
                response = client.get(path, headers={"Accept": "application/json"})
                _record(
                    results,
                    f"JSON {path}",
                    response.status_code == 200 and _is_json(response),
                    f"status={response.status_code}",
                )

            for path in (
                "/preventivi/nuovo",
                "/preventivi/conferimento/nuovo",
                "/preventivi",
                "/compensi-forensi",
                "/tariffario",
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
        "# Tranche 7A gate check",
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
    print("Tranche 7A gate OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
