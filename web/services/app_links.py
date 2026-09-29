"""Collegamento fra l'app installata dagli store e il dominio di IUSENTRA.

- Android (Trusted Web Activity): ``/.well-known/assetlinks.json`` dichiara il pacchetto e
  l'impronta SHA-256 del certificato di firma dell'app, così Chrome apre l'app a schermo intero
  senza barra dell'indirizzo (Digital Asset Links).
- iOS: ``/.well-known/apple-app-site-association`` dichiara l'app autorizzata ad aprire i
  collegamenti del dominio (universal links), se lo studio pubblica un'app iOS.

I valori si leggono solo dalle variabili d'ambiente del server: senza configurazione le risposte
sono vuote e nessuna app è associata al dominio.
"""

from __future__ import annotations

import os
import re

_PACCHETTO = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")
_IMPRONTA = re.compile(r"^([0-9A-F]{2}:){31}[0-9A-F]{2}$")
_APP_ID_IOS = re.compile(r"^[A-Z0-9]{10}\.[a-zA-Z0-9.-]+$")


def assetlinks() -> list[dict]:
    pacchetto = os.getenv("IUSENTRA_ANDROID_PACKAGE", "").strip()
    impronte = [v.strip().upper() for v in os.getenv("IUSENTRA_ANDROID_SHA256", "").split(",") if v.strip()]
    impronte = [v for v in impronte if _IMPRONTA.match(v)]
    if not _PACCHETTO.match(pacchetto) or not impronte:
        return []
    return [{"relation": ["delegate_permission/common.handle_all_urls"],
             "target": {"namespace": "android_app", "package_name": pacchetto, "sha256_cert_fingerprints": impronte}}]


def apple_app_site_association() -> dict:
    app_ids = [v.strip() for v in os.getenv("IUSENTRA_IOS_APP_IDS", "").split(",") if _APP_ID_IOS.match(v.strip())]
    return {"applinks": {"details": [{"appIDs": app_ids, "components": [{"/": "/*"}]}] if app_ids else []}}


__all__ = ["apple_app_site_association", "assetlinks"]
