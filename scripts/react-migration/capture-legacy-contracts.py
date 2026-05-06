from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.app import create_app

OUT = Path("artifacts/react-migration/legacy-contracts")
OUT.mkdir(parents=True, exist_ok=True)

FORM_RE = re.compile(r"<form\b[^>]*>", re.I)
ACTION_RE = re.compile(r"""action=["']([^"']+)["']""", re.I)
METHOD_RE = re.compile(r"""method=["']([^"']+)["']""", re.I)
LINK_RE = re.compile(r"""href=["']([^"']+)["']""", re.I)

DEFAULT_ROUTES = [
    "/fatturazione",
    "/incassi-pagamenti",
    "/preventivi",
    "/compensi-forensi",
    "/tariffario",
    "/template-atti",
    "/redazione-atti",
    "/giurisprudenza",
    "/legal-intelligence",
    "/utenti",
    "/profili",
    "/audit",
    "/registro-attivita",
    "/studio",
    "/impostazioni",
    "/backup",
    "/statistiche",
    "/sito-studio",
    "/deposito/checklist",
    "/polisWeb",
    "/pdp",
    "/pat",
    "/sigit",
    "/sigp",
    "/portali",
]


def legacy_url(route: str) -> str:
    clean = route if route.startswith("/") else f"/{route}"
    parts = urlsplit(clean)
    query = parts.query
    query = f"{query}&_legacy=1" if query else "_legacy=1"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def safe_name(route: str) -> str:
    clean = route.strip("/") or "root"
    clean = clean.split("?", 1)[0].replace("*", "wildcard")
    return clean.replace("/", "__")


def contract_from_html(route: str, status: int, html: str, redirect_location: str) -> dict[str, object]:
    forms = []
    for raw in FORM_RE.findall(html):
        action = ACTION_RE.search(raw)
        method = METHOD_RE.search(raw)
        forms.append(
            {
                "action": action.group(1) if action else "",
                "method": (method.group(1) if method else "GET").upper(),
                "raw": raw[:300],
            }
        )

    links = sorted(set(LINK_RE.findall(html)))
    downloads = [
        href
        for href in links
        if any(href.lower().endswith(ext) for ext in [".pdf", ".xml", ".csv", ".zip", ".docx"])
        or "/download" in href.lower()
        or "/scarica" in href.lower()
        or "/export" in href.lower()
        or "/esporta" in href.lower()
    ]

    return {
        "route": route,
        "legacyUrl": legacy_url(route),
        "status": status,
        "redirectLocation": redirect_location,
        "forms": forms,
        "links": links,
        "linksCount": len(links),
        "downloads": downloads,
        "hasBootstrapClass": "class=\"btn " in html or "class='btn " in html,
        "hasReactRoot": 'id="root"' in html or 'id="iusentra-react-root"' in html,
    }


def main() -> None:
    routes = sys.argv[1:] or DEFAULT_ROUTES
    app = create_app({"TESTING": True})
    client = app.test_client()

    for route in routes:
        if "*" in route:
            print(f"[contract] salto route wildcard non richiedibile direttamente: {route}")
            continue
        response = client.get(
            legacy_url(route),
            headers={"Accept": "text/html"},
            follow_redirects=False,
        )
        html = response.get_data(as_text=True)
        contract = contract_from_html(
            route=route,
            status=response.status_code,
            html=html,
            redirect_location=response.headers.get("Location", ""),
        )
        target = OUT / f"{safe_name(route)}.json"
        target.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[contract] {route} -> {target}")


if __name__ == "__main__":
    main()
