"""Generazione chiavi VAPID per Web Push IUSENTRA."""

from __future__ import annotations

import argparse
import base64
import json
from dataclasses import dataclass
from typing import Sequence

from cryptography.hazmat.primitives.asymmetric import ec

DEFAULT_VAPID_SUBJECT = "mailto:admin@example.com"


@dataclass(frozen=True)
class VapidKeyPair:
    public_key: str
    private_key: str

    def as_env(self, *, subject: str = DEFAULT_VAPID_SUBJECT) -> dict[str, str]:
        return {
            "IUSENTRA_WEB_PUSH_ENABLED": "1",
            "IUSENTRA_VAPID_PUBLIC_KEY": self.public_key,
            "IUSENTRA_VAPID_PRIVATE_KEY": self.private_key,
            "IUSENTRA_VAPID_SUBJECT": subject or DEFAULT_VAPID_SUBJECT,
        }


def _base64url_no_padding(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def generate_vapid_key_pair() -> VapidKeyPair:
    """Genera una coppia VAPID EC P-256 compatibile con pywebpush."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_numbers = private_key.private_numbers()
    public_numbers = private_numbers.public_numbers
    public_raw = b"\x04" + public_numbers.x.to_bytes(32, "big") + public_numbers.y.to_bytes(32, "big")
    private_raw = private_numbers.private_value.to_bytes(32, "big")
    return VapidKeyPair(
        public_key=_base64url_no_padding(public_raw),
        private_key=_base64url_no_padding(private_raw),
    )


def format_env(pair: VapidKeyPair, *, subject: str = DEFAULT_VAPID_SUBJECT) -> str:
    env = pair.as_env(subject=subject)
    return "\n".join(f"{key}={value}" for key, value in env.items())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera chiavi VAPID EC P-256 per le notifiche Web Push IUSENTRA."
    )
    parser.add_argument(
        "--subject",
        default=DEFAULT_VAPID_SUBJECT,
        help="Subject VAPID, ad esempio mailto:admin@example.com.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Stampa un oggetto JSON invece delle righe ambiente.",
    )
    args = parser.parse_args(argv)
    pair = generate_vapid_key_pair()
    if args.json:
        print(json.dumps(pair.as_env(subject=args.subject), ensure_ascii=False, indent=2))
    else:
        print(format_env(pair, subject=args.subject))
        print("# IUSENTRA_VAPID_PRIVATE_KEY e' un segreto: conservarla solo nell'ambiente del server.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
