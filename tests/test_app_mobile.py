"""App installabile e pubblicabile negli store: manifest, icone, service worker con pagina offline,
Digital Asset Links (Android) e Apple App Site Association (iOS) configurati da ambiente."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

STATIC = Path(__file__).resolve().parents[1] / "web" / "static"


def test_manifest_completo_per_installazione_e_store():
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["id"] == "/app-v2" and manifest["start_url"] == "/app-v2" and manifest["display"] == "standalone"
    assert manifest["theme_color"] == manifest["background_color"] == "#0B1B3A"
    mascherabili = [i for i in manifest["icons"] if i["purpose"] == "maskable"]
    assert mascherabili and all((STATIC / i["src"].removeprefix("/static/")).is_file() for i in manifest["icons"])
    assert Image.open(STATIC / "icons" / "icon-maskable-512.png").size == (512, 512)
    assert [s["url"] for s in manifest["shortcuts"]] == ["/oggi", "/scadenziario", "/agenda", "/fascicoli"]
    assert json.loads((STATIC / "manifest.json").read_text(encoding="utf-8")) == manifest


def test_service_worker_solo_pagina_offline_senza_dati():
    sw = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert "request.mode !== 'navigate'" in sw and "OFFLINE_URL = '/offline'" in sw
    assert "SHELL_ASSETS = [OFFLINE_URL" in sw and "caches.delete" in sw
    assert "/api/" not in sw.split("SHELL_ASSETS", 1)[1].split(";", 1)[0]


def test_collegamenti_app_da_ambiente(tmp_path, monkeypatch):
    from tests.test_revisione_2410_sicurezza import _app

    app = _app(tmp_path)
    with app.test_client() as client:
        vuoto = client.get("/.well-known/assetlinks.json")
        assert vuoto.status_code == 200 and vuoto.get_json() == []
        assert client.get("/.well-known/apple-app-site-association").get_json() == {"applinks": {"details": []}}
        impronta = ":".join(["AB"] * 32)
        monkeypatch.setenv("IUSENTRA_ANDROID_PACKAGE", "it.iusentra.app")
        monkeypatch.setenv("IUSENTRA_ANDROID_SHA256", f"{impronta.lower()}, non-valida")
        monkeypatch.setenv("IUSENTRA_IOS_APP_IDS", "ABCDE12345.it.iusentra.app,sbagliato")
        android = client.get("/.well-known/assetlinks.json").get_json()
        assert android[0]["target"] == {"namespace": "android_app", "package_name": "it.iusentra.app",
                                         "sha256_cert_fingerprints": [impronta]}
        ios = client.get("/.well-known/apple-app-site-association")
        assert ios.mimetype == "application/json"
        assert ios.get_json()["applinks"]["details"][0]["appIDs"] == ["ABCDE12345.it.iusentra.app"]
        assert client.get("/offline").status_code == 200


def test_shell_dichiara_icona_ios():
    shell = (Path(__file__).resolve().parents[1] / "web" / "templates" / "react_shell.html").read_text(encoding="utf-8")
    assert 'rel="apple-touch-icon"' in shell and 'name="apple-mobile-web-app-title"' in shell
