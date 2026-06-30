from __future__ import annotations

import sys
from typing import Any, Callable


def _safe_print(message: object = "") -> None:
    text = str(message)
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        sys.stdout.write(safe_text + "\n")
        sys.stdout.flush()


def print_startup_banner(
    *,
    version: str,
    port: int,
    platform_name: str,
    lib_path: str | None,
    curl_available: bool,
    token_info_fetcher: Callable[[str], list[dict[str, Any]]],
) -> None:
    _safe_print("=" * 60)
    _safe_print(f"  IUSENTRA Local Signer v{version}")
    _safe_print(f"  In ascolto su  http://127.0.0.1:{port}")
    _safe_print(f"  Piattaforma:   {platform_name}")
    _safe_print("=" * 60)

    if lib_path:
        _safe_print(f"  Libreria PKCS#11 : {lib_path}")
        try:
            tokens = token_info_fetcher(lib_path)
            if tokens:
                for tok in tokens:
                    label = tok.get("label") or tok.get("manufacturer") or "Token"
                    _safe_print(f"  Token trovato    : {label} (slot {tok.get('slot_id')})")
            else:
                _safe_print("  Token            : libreria OK - inserire smart card/token")
        except RuntimeError as exc:
            _safe_print(f"  AVVISO token     : {str(exc).splitlines()[0]}")
        except Exception as exc:
            _safe_print(f"  AVVISO token     : {exc}")
    else:
        _safe_print("  AVVISO: Libreria PKCS#11 non trovata.")
        _safe_print("  - Verificare middleware PKCS#11 del dispositivo.")
        _safe_print(f"  - Diagnostica completa: http://127.0.0.1:{port}/diagnosi")

    if curl_available:
        _safe_print("  curl             : disponibile (PST abilitato)")
    else:
        _safe_print("  AVVISO: curl non trovato nel PATH (PST non disponibile)")
