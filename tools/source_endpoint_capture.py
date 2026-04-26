from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Cattura endpoint/download di una fonte ufficiale usando Chromium, come fatto per Normattiva.")
    parser.add_argument("--url", required=True, help="URL iniziale della fonte ufficiale")
    parser.add_argument("--label", default="source", help="Nome breve della fonte: es. gazzetta_ufficiale")
    parser.add_argument("--out", default="data/fonti_ufficiali/captures")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("Playwright non installato. Esegui: pip install playwright && python -m playwright install chromium")
        return 2

    out_dir = Path(args.out) / f"{args.label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    captured = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "target_url": args.url,
        "label": args.label,
        "downloads": [],
        "xhr_candidates": [],
        "notes": "Verificare condizioni d'uso della fonte. Non condividere cookie/sessioni private.",
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        def on_response(response):
            try:
                req = response.request
                if req.resource_type in {"xhr", "fetch", "document"}:
                    headers = dict(response.headers)
                    captured["xhr_candidates"].append({
                        "url": response.url,
                        "status": response.status,
                        "method": req.method,
                        "resource_type": req.resource_type,
                        "request_headers_public": {k: v for k, v in req.headers.items() if k.lower() not in {"cookie", "authorization"}},
                        "response_headers_public": {k: v for k, v in headers.items() if k.lower() not in {"set-cookie"}},
                        "post_data": req.post_data,
                    })
            except Exception:
                pass

        page.on("response", on_response)

        def on_download(download):
            suggested = download.suggested_filename
            target = out_dir / suggested
            download.save_as(str(target))
            captured["downloads"].append({
                "suggested_filename": suggested,
                "saved_as": str(target),
                "url": download.url,
            })

        page.on("download", on_download)
        page.goto(args.url, wait_until="domcontentloaded", timeout=120000)
        print("Browser aperto. Interagisci con il sito e avvia download/API. Quando hai finito, torna qui e premi INVIO.")
        input()
        context.close()
        browser.close()

    capture_path = out_dir / "endpoint_capture.json"
    capture_path.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Capture salvato: {capture_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
