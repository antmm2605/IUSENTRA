"""Diagnostica sicura della configurazione Web Push."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .web_push import load_web_push_config, web_push_config_diagnostics, web_push_recommendation


def diagnostics_payload() -> dict[str, object]:
    config = load_web_push_config()
    diagnostics = web_push_config_diagnostics(config, include_subject=True)
    return {
        "enabled": diagnostics["enabled"],
        "public_key_present": diagnostics["hasPublicKey"],
        "private_key_present": diagnostics["hasPrivateKey"],
        "subject": diagnostics["subject"],
        "configured": diagnostics["configured"],
        "pywebpush_installed": diagnostics["pywebpushInstalled"],
        "missing": diagnostics["missing"],
        "recommendation": web_push_recommendation(config),
    }


def _yes(value: object) -> str:
    return "si" if bool(value) else "no"


def print_human(payload: dict[str, object]) -> None:
    print("Web Push status:")
    print(f"- enabled: {str(payload['enabled']).lower()}")
    print(f"- public key: {_yes(payload['public_key_present'])}")
    print(f"- private key: {_yes(payload['private_key_present'])}")
    print(f"- subject: {payload['subject']}")
    print(f"- configured: {str(payload['configured']).lower()}")
    print(f"- pywebpush installato: {_yes(payload['pywebpush_installed'])}")
    missing = payload.get("missing") or []
    if missing:
        print("- variabili mancanti: " + ", ".join(str(item) for item in missing))
    print(f"- raccomandazione: {payload['recommendation']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica la configurazione Web Push IUSENTRA.")
    parser.add_argument("--json", action="store_true", help="Stampa la diagnostica in JSON.")
    args = parser.parse_args(argv)
    payload = diagnostics_payload()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human(payload)
    return 0 if payload["configured"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
