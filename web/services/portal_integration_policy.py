"""Policy centrale per i canali dei portali telematici.

La regola e' fail-closed: solo PST resta integrazione interna diretta.
PTT, PAT e PDP usano il portale ufficiale assistito finche' non esiste
un manifest completo, verificato, non scaduto e con test reali passati.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
import re


MODE_DIRECT_INTERNAL = "direct_internal"
MODE_OFFICIAL_PORTAL_ASSISTED = "official_portal_assisted"
MODE_DIRECT_VERIFIED = "direct_verified"

_ASSISTED_PORTALS = {"ptt", "pat", "pdp"}
_ALLOWED_CHANNEL_KINDS = {"official_api", "official_wsdl", "authorized_pda", "model_office"}
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class PortalIntegrationPolicy:
    portale: str
    mode: str
    direct_allowed: bool
    assistant_required: bool
    reason: str = ""
    manifest: dict[str, Any] = field(default_factory=dict)
    validation_errors: tuple[str, ...] = ()


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _https_url(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _manifest_for(config: dict[str, Any] | None, portale: str) -> dict[str, Any]:
    channels = {}
    if isinstance(config, dict):
        channels = config.get("PORTAL_DIRECT_CHANNELS") or {}
    if not isinstance(channels, dict):
        return {}
    manifest = channels.get(portale) or channels.get(portale.upper()) or channels.get(portale.lower())
    return dict(manifest) if isinstance(manifest, dict) else {}


def _validate_manifest(manifest: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    if manifest.get("allow_direct") is not True:
        errors.append("allow_direct")
    if str(manifest.get("status") or "").strip().lower() != "verified":
        errors.append("status")
    if not _https_url(manifest.get("official_source_url")):
        errors.append("official_source_url")
    if not _SHA256_RE.fullmatch(str(manifest.get("evidence_sha256") or "").strip()):
        errors.append("evidence_sha256")
    if _parse_iso_datetime(manifest.get("verified_at")) is None:
        errors.append("verified_at")
    expires_at = _parse_iso_datetime(manifest.get("expires_at"))
    if expires_at is None:
        errors.append("expires_at")
    elif expires_at <= datetime.now(timezone.utc):
        errors.append("expires_at_scaduto")
    if manifest.get("integration_tests_passed") is not True:
        errors.append("integration_tests_passed")
    if str(manifest.get("channel_kind") or "").strip() not in _ALLOWED_CHANNEL_KINDS:
        errors.append("channel_kind")
    if not str(manifest.get("verified_by") or "").strip():
        errors.append("verified_by")
    return not errors, tuple(errors)


def get_portal_integration_policy(
    portale: str,
    config: dict[str, Any] | None = None,
) -> PortalIntegrationPolicy:
    portale_norm = str(portale or "").strip().lower()
    if portale_norm == "pst":
        return PortalIntegrationPolicy(
            portale="pst",
            mode=MODE_DIRECT_INTERNAL,
            direct_allowed=True,
            assistant_required=False,
            reason="PST / PolisWeb resta il canale interno diretto autorizzato.",
        )

    if portale_norm in _ASSISTED_PORTALS:
        manifest = _manifest_for(config, portale_norm)
        ok, errors = _validate_manifest(manifest)
        if ok:
            return PortalIntegrationPolicy(
                portale=portale_norm,
                mode=MODE_DIRECT_VERIFIED,
                direct_allowed=True,
                assistant_required=False,
                reason="Manifest diretto verificato, completo e non scaduto.",
                manifest=manifest,
            )
        return PortalIntegrationPolicy(
            portale=portale_norm,
            mode=MODE_OFFICIAL_PORTAL_ASSISTED,
            direct_allowed=False,
            assistant_required=True,
            reason="Canale diretto non verificato: usare portale ufficiale assistito.",
            manifest=manifest,
            validation_errors=errors,
        )

    return PortalIntegrationPolicy(
        portale=portale_norm,
        mode=MODE_OFFICIAL_PORTAL_ASSISTED,
        direct_allowed=False,
        assistant_required=True,
        reason="Portale non riconosciuto dalla policy diretta: accesso fail-closed.",
        validation_errors=("portale_non_supportato",),
    )
