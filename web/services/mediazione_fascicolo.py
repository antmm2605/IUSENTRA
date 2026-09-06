"""Composizione del procedimento privato e delle risorse pubbliche dell'ente."""
from __future__ import annotations

import hashlib
import io
import json
from copy import deepcopy
from datetime import datetime
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile, BadZipFile
from zoneinfo import ZoneInfo

from pct.mediazione_public_sources import fetch_public, public_url
from web.services.mediazione_directory_surface import directory


def _website(raw):
    try:
        return public_url(raw)
    except ValueError:
        return ""


def organismi(config):
    repo = directory(config)
    if repo is None:
        raise RuntimeError("Registro degli organismi non disponibile.")
    offices = repo.office_snapshots()
    return [{"numero": str(row["registration_number"]), "nome": row["name"],
             "sito": _website(row.get("website")),
             "territori": [dict(regione=r, provincia=p, comune=c) for r, p, c in sorted({
                 (o["region"], o["province"], o["city"])
                 for o in offices.get(str(row["registration_number"]), {}).get("offices", [])})]}
            for row in repo.records(include_checks=False)]


def organismo(config, number):
    repo = directory(config)
    if repo is None:
        raise RuntimeError("Registro degli organismi non disponibile.")
    row = next(iter(repo.records(number=number)), None)
    if row is None:
        raise ValueError("Organismo non presente fra gli attivi nell'ultimo registro acquisito.")
    snapshot = repo.office_snapshots(number).get(number, {})
    offices = []
    for office in snapshot.get("offices", []):
        identity = json.dumps({k: office[k] for k in ("legal", "address", "city", "postal_code", "province", "region")}, sort_keys=True)
        identifier = hashlib.sha256(identity.encode()).hexdigest()[:20]
        offices.append(dict(office, id=identifier))
    check = row.get("directory_check") or {}
    from pct.mediazione_source_history import source_status
    from pct.mediazione_resource_catalog import resource_catalog
    monitoring = source_status(repo, number)
    current_resources, observed_at = resource_catalog(row, monitoring)
    resources = [dict(item, url=_website(item.get("url"))) for item in current_resources]
    return {"numero": number, "nome": row["name"], "sito": _website(row.get("website")),
            "registro_fonte": row.get("official_registry_url", ""),
            "registro_verificato_il": row.get("registry_checked_at", ""),
            "sedi": offices, "sedi_fonte": snapshot.get("source_url", ""),
            "sedi_verificate_il": snapshot.get("checked_at", ""),
            "risorse": [item for item in resources if item["url"]],
            "risorse_verificate_il": observed_at,
            "risorse_stato": check.get("status", "non_verificato"), "controllo_fonti": monitoring}


def collega_organismo(payload, previous, config):
    payload["moduli_organismo"] = deepcopy((previous or {}).get("moduli_organismo", []))
    number = payload["organismo_numero"]
    if not number:
        payload["organismo"] = None
        payload["modulo_fonte"] = None
        return
    current = organismo(config, number)
    selected = next((office for office in current["sedi"] if office["id"] == payload["sede_id"]), None)
    if payload["sede_id"] and not selected:
        raise ValueError("La sede selezionata non appartiene all'organismo corrente.")
    changed = previous and previous.get("organismo_numero") != number
    if changed and (payload.get("modulo_verificato") or payload.get("modulo_ufficiale_documento")):
        raise ValueError("Hai cambiato organismo: scegli e verifica nuovamente il modulo dell'ente.")
    payload["organismo"] = {key: current[key] for key in ("numero", "nome", "sito", "registro_fonte", "registro_verificato_il")}
    payload["organismo"]["sede"] = selected
    entry = next((m for m in payload["moduli_organismo"] if m["documento"] == payload.get("modulo_ufficiale_documento")), None)
    if payload.get("modulo_ufficiale_documento") and not entry:
        raise ValueError("Scegli un modulo acquisito dalle risorse dell'organismo, non un documento generico del fascicolo.")
    if entry and entry["fonte"]["organismo_numero"] != number:
        raise ValueError("Il modulo acquisito appartiene a un altro organismo.")
    previous_source = (previous or {}).get("modulo_fonte")
    payload["modulo_fonte"] = entry["fonte"] if entry else previous_source if previous_source and not changed and (
        payload.get("modulo_ufficiale_documento") == previous.get("modulo_ufficiale_documento")) else None


def acquisisci_modulo(config, number, source_url):
    org = organismo(config, number)
    resource = next((r for r in org["risorse"] if r["url"] == source_url), None)
    if not resource or resource.get("kind") not in {"istanza", "modulistica", "adesione", "procura", "privacy", "proroga", "proposta", "verbale", "incarico", "regolamento", "tariffe"}:
        raise ValueError("Scegli un modulo pubblicato fra le risorse dell'organismo.")
    # GET anonima: nessun dato dello studio viene inviato al sito pubblico.
    response = fetch_public(source_url, max_bytes=12_000_000)
    raw = response["body"]
    if response["status"] != 200:
        raise ValueError("Il sito non ha restituito il modulo richiesto.")
    filename = unquote(urlsplit(response["url"]).path.rsplit("/", 1)[-1])
    if raw.startswith(b"%PDF-"):
        import fitz
        with fitz.open(stream=raw, filetype="pdf") as doc:
            if doc.is_encrypted or not doc.page_count:
                raise ValueError("Il modulo è protetto o non contiene pagine leggibili.")
        if not filename.lower().endswith(".pdf"):
            filename = f"Modulo_organismo_{number}.pdf"
    elif filename.lower().endswith(".docx"):
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                if (len(entries) > 2000 or sum(e.file_size for e in entries) > 60_000_000
                        or "word/document.xml" not in archive.namelist()
                        or any("vbaproject" in e.filename.lower() or e.flag_bits & 1 for e in entries)):
                    raise ValueError("Il modulo Word contiene elementi non supportati o protetti.")
        except BadZipFile as exc:
            raise ValueError("Il modulo Word non è leggibile.") from exc
    elif not (filename.lower().endswith(".doc") and raw.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))):
        raise ValueError("Il collegamento non restituisce un modulo PDF o Word riconoscibile.")
    return raw, filename, {"organismo_numero": number, "url": source_url,
                           "url_finale": response["url"], "titolo": resource["label"],
                           "sha256": hashlib.sha256(raw).hexdigest(), "tipo": resource["kind"],
                           "acquisito_il": datetime.now(ZoneInfo("Europe/Rome")).isoformat()}
