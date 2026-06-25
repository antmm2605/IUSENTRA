from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legal_ocr.models import PageArtifact  # noqa: E402
from legal_ocr.unlimited.client import UnlimitedOcrClient  # noqa: E402
from legal_ocr.unlimited.config import UnlimitedOcrSettings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica endpoint self-hosted Unlimited-OCR OpenAI-compatible.")
    parser.add_argument("--endpoint", default=os.getenv("IUSENTRA_UNLIMITED_OCR_ENDPOINT") or "http://127.0.0.1:10000")
    parser.add_argument("--model", default=os.getenv("IUSENTRA_UNLIMITED_OCR_MODEL") or "Unlimited-OCR")
    parser.add_argument("--timeout", type=int, default=int(os.getenv("IUSENTRA_UNLIMITED_OCR_TIMEOUT_SECONDS") or "300"))
    parser.add_argument("--smoke", action="store_true", help="Esegue anche una richiesta OCR minima con immagine generata.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    os.environ["IUSENTRA_UNLIMITED_OCR_ENABLED"] = "1"
    os.environ["IUSENTRA_UNLIMITED_OCR_ENDPOINT"] = args.endpoint
    os.environ["IUSENTRA_UNLIMITED_OCR_MODEL"] = args.model
    os.environ["IUSENTRA_UNLIMITED_OCR_TIMEOUT_SECONDS"] = str(args.timeout)

    started = time.perf_counter()
    settings = UnlimitedOcrSettings.from_env()
    readiness = settings.readiness()
    report: dict[str, object] = {
        "ok": False,
        "endpoint": settings.endpoint,
        "model": settings.model,
        "readiness": readiness,
        "models_api": {},
        "smoke": {},
        "elapsed_ms": 0,
    }
    if not readiness.get("ok"):
        return _finish(report, args.json, 2, started)

    models = _get_json(f"{settings.endpoint}/v1/models", timeout=10)
    report["models_api"] = models
    if not models.get("ok"):
        return _finish(report, args.json, 2, started)

    if args.smoke:
        smoke = _smoke_ocr(settings)
        report["smoke"] = smoke
        if not smoke.get("ok"):
            return _finish(report, args.json, 2, started)

    report["ok"] = True
    return _finish(report, args.json, 0, started)


def _get_json(url: str, *, timeout: int) -> dict[str, object]:
    try:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - endpoint validato local-first.
            raw = response.read().decode("utf-8", errors="replace")
        try:
            body: object = json.loads(raw)
        except json.JSONDecodeError:
            body = raw[:500]
        return {"ok": True, "status": getattr(response, "status", 200), "body": body}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def _smoke_ocr(settings: UnlimitedOcrSettings) -> dict[str, object]:
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        return {"ok": False, "error": f"Pillow non disponibile: {exc}"}

    with tempfile.TemporaryDirectory(prefix="iusentra-unlimited-ocr-smoke-") as tmpdir:
        image_path = Path(tmpdir) / "smoke.png"
        image = Image.new("RGB", (900, 260), "white")
        draw = ImageDraw.Draw(image)
        draw.text((40, 90), "TRIBUNALE DI TEST - R.G. 123/2026", fill="black")
        image.save(image_path)
        page = PageArtifact(1, str(image_path), "smoke", image.width, image.height)
        result = UnlimitedOcrClient(settings).generate_for_pages([page])
    text = str(result.get("text") or "")
    return {
        "ok": bool(text.strip()),
        "chars": len(text),
        "attempts": result.get("attempts"),
        "elapsed_ms": result.get("elapsed_ms"),
        "preview": text[:300],
        "error": result.get("error") or "",
    }


def _finish(report: dict[str, object], as_json: bool, code: int, started: float) -> int:
    report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Unlimited-OCR endpoint: {'OK' if report.get('ok') else 'NON PRONTO'}")
        print(f"Endpoint: {report.get('endpoint')}")
        if not report.get("ok"):
            print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
