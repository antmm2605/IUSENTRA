#!/usr/bin/env python
"""Offline verifier for IUSENTRA legal-grade audit bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.canonical import canonicalize
from audit.hashing import sha256_bytes, sha256_file
from audit.merkle import verify_merkle_proof
from audit.signing import JwsAuditSigner, build_signing_payload
from audit.tsa import verify_timestamp_token


def _load_json_bytes(data: bytes) -> dict[str, Any]:
    return json.loads(data.decode("utf-8"))


def _event_hash(envelope: dict[str, Any]) -> str:
    return sha256_bytes(canonicalize(envelope.get("signed_event") or {}))


def _snapshot_hash(envelope: dict[str, Any]) -> str:
    return sha256_bytes(canonicalize(envelope.get("signed_snapshot") or {}))


def _load_keys_from_zip(zf: ZipFile) -> dict[str, str]:
    keys: dict[str, str] = {}
    for name in zf.namelist():
        if name.startswith("signers/") and name.endswith(".pem"):
            kid = Path(name).stem
            keys[kid] = zf.read(name).decode("ascii")
    return keys


def _load_keys_from_path(public_key: str = "") -> dict[str, str]:
    if not public_key:
        return {}
    path = Path(public_key)
    return {path.stem: path.read_text(encoding="ascii")}


def _verify_signature(payload: dict[str, Any], signature: dict[str, Any], keys: dict[str, str]) -> tuple[bool, str]:
    kid = str(signature.get("kid") or "")
    alg = str(signature.get("alg") or "RS256")
    key = keys.get(kid) or (next(iter(keys.values())) if len(keys) == 1 else "")
    if not key:
        return False, f"chiave pubblica mancante per kid {kid}"
    signer = JwsAuditSigner(public_key_pem=key.encode("ascii"), kid=kid or next(iter(keys.keys())), alg=alg)
    return signer.verify(payload, signature), ""


def verify_event_envelope(envelope: dict[str, Any], keys: dict[str, str]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if envelope.get("format") != "audit-envelope-v1":
        errors.append("formato envelope evento non valido")
    event_hash = _event_hash(envelope)
    if event_hash != str(envelope.get("event_hash") or "").lower():
        errors.append("event_hash non coincide con canonicalizzazione JCS")
    signature = envelope.get("signature") if isinstance(envelope.get("signature"), dict) else {}
    ok, reason = _verify_signature(
        build_signing_payload(signed_event=envelope.get("signed_event") or {}, event_hash=event_hash),
        signature,
        keys,
    )
    if not ok:
        errors.append(reason or "firma evento non valida")
    return not errors, errors


def verify_snapshot_envelope(envelope: dict[str, Any], keys: dict[str, str]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if envelope.get("format") != "audit-snapshot-envelope-v1":
        errors.append("formato envelope snapshot non valido")
    snapshot_hash = _snapshot_hash(envelope)
    if snapshot_hash != str(envelope.get("snapshot_hash") or "").lower():
        errors.append("snapshot_hash non coincide con canonicalizzazione JCS")
    signature = envelope.get("signature") if isinstance(envelope.get("signature"), dict) else {}
    ok, reason = _verify_signature(
        build_signing_payload(signed_event=envelope.get("signed_snapshot") or {}, event_hash=snapshot_hash),
        signature,
        keys,
    )
    if not ok:
        errors.append(reason or "firma snapshot non valida")
    return not errors, errors


def _report(ok: bool, messages: list[str], *, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"ok": ok, "messages": messages}, ensure_ascii=False, indent=2))
    else:
        print("VALIDO" if ok else "NON VALIDO")
        for message in messages:
            print(f"- {message}")
    return 0 if ok else 2


def cmd_verify_event(args: argparse.Namespace) -> int:
    envelope = _load_json_bytes(Path(args.event).read_bytes())
    keys = _load_keys_from_path(args.public_key)
    ok, errors = verify_event_envelope(envelope, keys)
    messages = [f"event_id={((envelope.get('signed_event') or {}).get('event_id') or '')}"]
    messages.extend(errors or ["hash e firma evento verificati"])
    return _report(ok, messages, json_mode=args.json)


def cmd_verify_snapshot(args: argparse.Namespace) -> int:
    envelope = _load_json_bytes(Path(args.snapshot).read_bytes())
    keys = _load_keys_from_path(args.public_key)
    ok, errors = verify_snapshot_envelope(envelope, keys)
    messages = [f"snapshot_id={((envelope.get('signed_snapshot') or {}).get('snapshot_id') or '')}"]
    messages.extend(errors or ["hash e firma snapshot verificati"])
    return _report(ok, messages, json_mode=args.json)


def cmd_verify_proof(args: argparse.Namespace) -> int:
    proof = _load_json_bytes(Path(args.proof).read_bytes())
    ok = verify_merkle_proof(str(proof.get("event_hash") or ""), list(proof.get("proof") or []), str(proof.get("merkle_root") or ""))
    return _report(ok, ["Merkle proof verificata" if ok else "Merkle proof non valida"], json_mode=args.json)


def _bundle_events(zf: ZipFile) -> list[dict[str, Any]]:
    events = []
    for name in sorted(item for item in zf.namelist() if item.startswith("events/") and item.endswith(".json")):
        events.append(_load_json_bytes(zf.read(name)))
    return events


def _verify_chain_events(events: list[dict[str, Any]], fascicolo_id: str = "") -> tuple[bool, list[str]]:
    errors: list[str] = []
    selected = []
    for envelope in events:
        event = envelope.get("signed_event") or {}
        if fascicolo_id and event.get("fascicolo_id") != fascicolo_id:
            continue
        selected.append(envelope)
    selected.sort(key=lambda item: ((item.get("signed_event") or {}).get("event_ts_utc") or "", (item.get("signed_event") or {}).get("event_id") or ""))
    previous = ""
    for envelope in selected:
        event = envelope.get("signed_event") or {}
        prev = ((event.get("chain") or {}).get("prev_event_hash") or "")
        if prev != previous:
            errors.append(f"catena interrotta su {event.get('event_id')}")
        previous = str(envelope.get("event_hash") or "")
    if not selected:
        errors.append("nessun evento nel perimetro richiesto")
    return not errors, errors or [f"catena verificata su {len(selected)} eventi"]


def cmd_verify_chain(args: argparse.Namespace) -> int:
    with ZipFile(args.bundle, "r") as zf:
        ok, messages = _verify_chain_events(_bundle_events(zf), args.fascicolo_id)
    return _report(ok, messages, json_mode=args.json)


def cmd_verify_bundle(args: argparse.Namespace) -> int:
    messages: list[str] = []
    ok = True
    with ZipFile(args.bundle, "r") as zf:
        keys = _load_keys_from_zip(zf)
        events = _bundle_events(zf)
        for envelope in events:
            valid, errors = verify_event_envelope(envelope, keys)
            ok = ok and valid
            messages.extend(errors)
        chain_ok, chain_messages = _verify_chain_events(events, "")
        ok = ok and chain_ok
        messages.extend(chain_messages)
        for name in sorted(item for item in zf.namelist() if item.startswith("snapshots/") and item.endswith(".json")):
            valid, errors = verify_snapshot_envelope(_load_json_bytes(zf.read(name)), keys)
            ok = ok and valid
            messages.extend(errors or [f"{name}: snapshot verificato"])
        for name in sorted(item for item in zf.namelist() if item.startswith("proofs/") and item.endswith(".json")):
            proof = _load_json_bytes(zf.read(name))
            valid = verify_merkle_proof(str(proof.get("event_hash") or ""), list(proof.get("proof") or []), str(proof.get("merkle_root") or ""))
            ok = ok and valid
            messages.append(f"{name}: {'proof verificata' if valid else 'proof non valida'}")
        for name in sorted(item for item in zf.namelist() if item.startswith("tsa/")):
            # The bundle stores snapshot hash in the matching snapshot envelope.
            messages.append(f"{name}: token timestamp presente")
        if "files_manifest.json" in zf.namelist():
            manifest = _load_json_bytes(zf.read("files_manifest.json"))
            messages.append(f"manifest file: {len(manifest.get('files') or [])} riferimenti hash")
    if not messages:
        messages.append("bundle vuoto")
        ok = False
    return _report(ok, messages, json_mode=args.json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verifica offline audit probatorio IUSENTRA.")
    parser.add_argument("--json", action="store_true", help="Output machine-readable.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("verify-bundle")
    p.add_argument("bundle")
    p.set_defaults(func=cmd_verify_bundle)
    p = sub.add_parser("verify-event")
    p.add_argument("event")
    p.add_argument("--public-key", default="")
    p.set_defaults(func=cmd_verify_event)
    p = sub.add_parser("verify-proof")
    p.add_argument("proof")
    p.set_defaults(func=cmd_verify_proof)
    p = sub.add_parser("verify-chain")
    p.add_argument("bundle")
    p.add_argument("--fascicolo-id", default="")
    p.set_defaults(func=cmd_verify_chain)
    p = sub.add_parser("verify-snapshot")
    p.add_argument("snapshot")
    p.add_argument("--public-key", default="")
    p.set_defaults(func=cmd_verify_snapshot)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
