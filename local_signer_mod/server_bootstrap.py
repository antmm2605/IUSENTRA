from __future__ import annotations

from typing import Any, Callable


def print_startup_banner(
    *,
    version: str,
    port: int,
    platform_name: str,
    lib_path: str | None,
    curl_available: bool,
    token_info_fetcher: Callable[[str], list[dict[str, Any]]],
) -> None:
    print("=" * 60)
    print(f"  IUSENTRA Local Signer v{version}")
    print(f"  In ascolto su  http://127.0.0.1:{port}")
    print(f"  Piattaforma:   {platform_name}")
    print("=" * 60)

    if lib_path:
        print(f"  Libreria PKCS#11 : {lib_path}")
        try:
            tokens = token_info_fetcher(lib_path)
            if tokens:
                for tok in tokens:
                    label = tok.get("label") or tok.get("manufacturer") or "Token"
                    print(f"  Token trovato    : {label} (slot {tok.get('slot_id')})")
            else:
                print("  Token            : libreria OK — inserire smart card/token")
        except RuntimeError as exc:
            print(f"  AVVISO token     : {str(exc).splitlines()[0]}")
        except Exception as exc:
            print(f"  AVVISO token     : {exc}")
    else:
        print("  AVVISO: Libreria PKCS#11 non trovata.")
        print("  → Verificare middleware PKCS#11 del dispositivo.")
        print(f"  → Diagnostica completa: http://127.0.0.1:{port}/diagnosi")

    if curl_available:
        print("  curl             : disponibile (PST abilitato)")
    else:
        print("  AVVISO: curl non trovato nel PATH (PST non disponibile)")
