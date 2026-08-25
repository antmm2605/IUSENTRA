"""Screening locale su fonti pubbliche ufficiali, con prova riproducibile.

La ricerca non invia nominativi a terzi: scarica nel tenant lo snapshot XML
della lista consolidata UE e confronta localmente il nominativo normalizzato.
Un eventuale match è sempre soltanto ``POTENZIALE_RISCONTRO``: richiede la
valutazione dell'avvocato e non è una decisione automatica.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen


EU_FINANCIAL_SANCTIONS_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/"
    "xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw"
)
EU_FINANCIAL_SANCTIONS_LANDING_URL = (
    "https://finance.ec.europa.eu/eu-and-world/sanctions-restrictive-measures/"
    "overview-sanctions-and-related-resources_en"
)
EU_FINANCIAL_SANCTIONS_PROVIDER = "eu-consolidated-financial-sanctions"
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024


class ScreeningSourceUnavailable(RuntimeError):
    """La fonte non è raggiungibile o non è verificabile in sicurezza."""


@dataclass(frozen=True)
class ScreeningSnapshot:
    provider_key: str
    source_url: str
    landing_url: str
    source_version: str
    snapshot_hash: str
    acquired_at: str
    path: str


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", plain.casefold()).strip()


def _name_signature(value: str) -> str:
    """Confronto prudente anche per la forma ``cognome nome``/``nome cognome``."""

    tokens = [token for token in _normalize(value).split() if token]
    return " ".join(sorted(tokens)) if len(tokens) > 1 else ""


def _local_name(tag: str) -> str:
    return str(tag or "").split("}")[-1].casefold()


def _cache_paths(cache_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "eu-financial-sanctions.xml", directory / "eu-financial-sanctions.json"


def _load_cached_snapshot(cache_dir: str | Path, *, max_age: timedelta) -> ScreeningSnapshot | None:
    xml_path, meta_path = _cache_paths(cache_dir)
    if not xml_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        acquired_at = datetime.fromisoformat(str(meta["acquired_at"]).replace("Z", "+00:00"))
        if acquired_at.tzinfo is None:
            acquired_at = acquired_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - acquired_at > max_age:
            return None
        contents = xml_path.read_bytes()
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    digest = hashlib.sha256(contents).hexdigest()
    if digest != str(meta.get("snapshot_hash") or ""):
        return None
    return ScreeningSnapshot(
        provider_key=EU_FINANCIAL_SANCTIONS_PROVIDER,
        source_url=str(meta.get("source_url") or EU_FINANCIAL_SANCTIONS_URL),
        landing_url=EU_FINANCIAL_SANCTIONS_LANDING_URL,
        source_version=str(meta.get("source_version") or ""),
        snapshot_hash=digest,
        acquired_at=str(meta["acquired_at"]),
        path=str(xml_path),
    )


def refresh_eu_financial_sanctions(
    cache_dir: str | Path,
    *,
    timeout_seconds: int = 45,
    open_url: Callable[..., Any] = urlopen,
) -> ScreeningSnapshot:
    """Acquisisce e versiona la lista UE dal canale pubblico ufficiale.

    Il file viene prima scritto in ``.part`` e pubblicato solo dopo hash e
    controllo XML; una risposta HTML, un file troncato o una fonte non XML non
    diventano mai uno snapshot usabile.
    """

    xml_path, meta_path = _cache_paths(cache_dir)
    part_path = xml_path.with_suffix(".xml.part")
    digest = hashlib.sha256()
    total = 0
    try:
        request = Request(EU_FINANCIAL_SANCTIONS_URL, headers={"Accept": "application/xml"})
        with open_url(request, timeout=timeout_seconds) as response:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if "xml" not in content_type:
                raise ScreeningSourceUnavailable("La fonte UE non ha restituito un documento XML verificabile.")
            source_version = str(response.headers.get("Last-Modified") or response.headers.get("ETag") or "")
            with part_path.open("wb") as target:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_SNAPSHOT_BYTES:
                        raise ScreeningSourceUnavailable("Lo snapshot UE supera il limite di sicurezza previsto.")
                    digest.update(chunk)
                    target.write(chunk)
        if not total:
            raise ScreeningSourceUnavailable("La fonte UE ha restituito uno snapshot vuoto.")
        try:
            for _event, _node in ET.iterparse(part_path, events=("start",)):
                break
        except ET.ParseError as exc:
            raise ScreeningSourceUnavailable("Lo snapshot UE non è XML valido.") from exc
        os.replace(part_path, xml_path)
    except ScreeningSourceUnavailable:
        part_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        part_path.unlink(missing_ok=True)
        raise ScreeningSourceUnavailable(f"Fonte UE non raggiungibile: {exc}") from exc

    acquired_at = _now()
    snapshot_hash = digest.hexdigest()
    meta = {
        "provider_key": EU_FINANCIAL_SANCTIONS_PROVIDER,
        "source_url": EU_FINANCIAL_SANCTIONS_URL,
        "landing_url": EU_FINANCIAL_SANCTIONS_LANDING_URL,
        "source_version": source_version,
        "snapshot_hash": snapshot_hash,
        "acquired_at": acquired_at,
        "bytes": total,
    }
    tmp_meta = meta_path.with_suffix(".json.part")
    tmp_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_meta, meta_path)
    return ScreeningSnapshot(
        provider_key=EU_FINANCIAL_SANCTIONS_PROVIDER,
        source_url=EU_FINANCIAL_SANCTIONS_URL,
        landing_url=EU_FINANCIAL_SANCTIONS_LANDING_URL,
        source_version=source_version,
        snapshot_hash=snapshot_hash,
        acquired_at=acquired_at,
        path=str(xml_path),
    )


def _candidate_names(entity: ET.Element) -> set[str]:
    candidates: set[str] = set()
    for node in entity.iter():
        tag = _local_name(node.tag)
        if tag not in {"namealias", "name", "alias"}:
            continue
        attributes = {str(key).casefold(): str(value or "") for key, value in node.attrib.items()}
        whole = attributes.get("wholename") or attributes.get("name") or ""
        composed = " ".join(
            part for part in (
                attributes.get("firstname", ""),
                attributes.get("middlename", ""),
                attributes.get("lastname", ""),
            ) if part
        )
        for raw in (whole, composed, node.text or ""):
            normalized = _normalize(raw)
            if normalized:
                candidates.add(normalized)
    return candidates


def screen_eu_financial_sanctions(
    subject_label: str,
    *,
    cache_dir: str | Path,
    max_age: timedelta = timedelta(days=1),
) -> dict[str, Any]:
    """Confronta localmente un nominativo contro la lista UE versionata.

    Il confronto è volutamente esatto sul nome normalizzato: riduce i falsi
    positivi automatici. Anche in caso di match l'esito resta da valutare.
    """

    normalized_subject = _normalize(subject_label)
    subject_signature = _name_signature(subject_label)
    if not normalized_subject:
        raise ValueError("Per lo screening serve il nominativo del soggetto.")
    snapshot = _load_cached_snapshot(cache_dir, max_age=max_age)
    if snapshot is None:
        snapshot = refresh_eu_financial_sanctions(cache_dir)

    matches: list[dict[str, Any]] = []
    try:
        for _event, entity in ET.iterparse(snapshot.path, events=("end",)):
            if _local_name(entity.tag) not in {"sanctionentity", "entity"}:
                continue
            aliases = _candidate_names(entity)
            if normalized_subject in aliases or (
                subject_signature and any(_name_signature(alias) == subject_signature for alias in aliases)
            ):
                raw_aliases = sorted(aliases)[:5]
                matches.append({
                    "entity_id": str(entity.attrib.get("logicalId") or entity.attrib.get("id") or ""),
                    "matched_name": normalized_subject,
                    "aliases": raw_aliases,
                    "match_type": "nome_normalizzato_esatto",
                    "manual_review_required": True,
                })
            entity.clear()
    except ET.ParseError as exc:
        raise ScreeningSourceUnavailable("Lo snapshot UE salvato non è più leggibile.") from exc
    return {
        "provider_key": snapshot.provider_key,
        "source_url": snapshot.source_url,
        "source_version": snapshot.source_version,
        "snapshot_hash": snapshot.snapshot_hash,
        "subject_label": str(subject_label).strip(),
        "outcome": "POTENZIALE_RISCONTRO" if matches else "NESSUN_RISCONTRO",
        "matches": matches[:20],
        "checked_at": _now(),
        "note": (
            "Match nominativo nella lista UE: verifica professionale obbligatoria."
            if matches
            else "Nessun riscontro sul nominativo normalizzato nello snapshot UE consultato."
        ),
    }
