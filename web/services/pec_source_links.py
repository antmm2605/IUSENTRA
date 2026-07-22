"""Link condivisi per aprire fonti PEC, allegati ZIP e messaggi filtrati.

Agenda, Scadenziario e modali operative devono usare la stessa decisione:
quando il nome dell'allegato PEC è noto si apre il preview sicuro dello ZIP/PDF;
quando la fonte è solo testo interno della PEC si apre la PEC filtrata.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote


GENERIC_PEC_SOURCE_LABELS = {
    "corpo",
    "corpo pec",
    "email pec",
    "href",
    "href pec",
    "link pec",
    "messaggio pec",
    "oggetto",
    "oggetto pec",
    "pec",
    "testo",
    "testo del messaggio",
    "testo messaggio",
    "testo pec",
    "testo/href",
    "testo / href",
}

PEC_ATTACHMENT_SOURCE_LABELS = (
    "Fonte documentale",
    "Fonte link udienza",
    "Allegato udienza",
    "Documento allegato",
    "Fonte allegato",
)

SOURCE_FILE_RE = re.compile(
    r"([A-Za-z0-9À-ÿ _().,'’+\-]+?\.(?:pdf\.zip|pdf\.p7m|pdf|zip|p7m|xml|eml|txt|html?|docx?|rtf))\b",
    re.IGNORECASE,
)

CONTROL_TOWER_SOURCE_MARKER_RE = re.compile(
    r"(?:^|\s)PEC_CONTROL_TOWER:([A-Za-z0-9][A-Za-z0-9._:-]{0,127})(?=\s|$)",
    re.MULTILINE,
)


def _short_text(value: Any, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def clean_pec_source_name(value: Any, *, limit: int = 140) -> str:
    """Normalizza un valore fonte preservando il nome file quando è presente."""

    text = _short_text(value, limit=limit).strip(" -:;")
    match = SOURCE_FILE_RE.search(text)
    if match:
        return match.group(1).strip().rstrip(".,;:")
    return text.rstrip(".,;:")


def is_generic_pec_source_label(value: Any) -> bool:
    """Riconosce etichette tecniche interne della PEC, non nomi di allegato."""

    text = re.sub(r"\s+", " ", str(value or "").strip()).casefold()
    return text in GENERIC_PEC_SOURCE_LABELS


def pec_original_label(source_name: str) -> str:
    """Etichetta utente per una fonte PEC: allegato vero o PEC nel suo insieme."""

    clean = clean_pec_source_name(source_name)
    if clean and not is_generic_pec_source_label(clean):
        return _short_text(f"PEC originale - {clean}", 140)
    return "PEC originale"


def pec_source_href(message_id: str, source_name: str) -> str:
    """Apre il documento utile nello ZIP quando il nome dell'allegato è noto."""

    encoded_message = quote(str(message_id or "").strip(), safe="")
    clean = clean_pec_source_name(source_name)
    if clean and not is_generic_pec_source_label(clean):
        return f"/api/v1/ui/email/source/{encoded_message}?name={quote(clean, safe='')}"
    return f"/email/?audit_id={encoded_message}"


def extract_pec_attachment_source(context: str, *, limit: int = 140) -> str:
    """Trova il nome dell'allegato PEC da aprire prima della vista casella."""

    text = str(context or "")
    for label in PEC_ATTACHMENT_SOURCE_LABELS:
        match = re.search(rf"^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = clean_pec_source_name(match.group(1), limit=limit)
            if value:
                return value
    return ""


def resolve_pec_source_name(preferred: Any, *contexts: Any, limit: int = 140) -> str:
    """Usa il nome allegato se disponibile; non lascia una label generica bloccarlo."""

    preferred_clean = clean_pec_source_name(preferred, limit=limit)
    if preferred_clean and not is_generic_pec_source_label(preferred_clean):
        return preferred_clean
    for context in contexts:
        attachment = extract_pec_attachment_source(str(context or ""), limit=limit)
        if attachment and not is_generic_pec_source_label(attachment):
            return attachment
    return preferred_clean


CONTROL_TOWER_RECEIPT_LABELS = {
    "PEC_RECEIPT_ACCEPTANCE": "PEC di accettazione",
    "PEC_RECEIPT_DELIVERY": "PEC di consegna",
    "PEC_RECEIPT_NON_DELIVERY": "PEC di mancata consegna",
    "PEC_RECEIPT_ANOMALY": "PEC con anomalia da presidiare",
}

CONTROL_TOWER_EVENT_LABELS = {
    "ricevuta_accettazione_da_presidiare": "Ricevuta di accettazione PEC da presidiare",
    "ricevuta_consegna_da_presidiare": "Ricevuta di consegna PEC da presidiare",
    "ricevuta_mancata_consegna_da_presidiare": "Mancata consegna PEC da presidiare",
    "pec_da_classificare": "PEC da classificare",
}

PEC_AUDIT_REF_RE = re.compile(r"\bPEC_AUDIT:([A-Za-z0-9][A-Za-z0-9_.:-]{1,179})", re.IGNORECASE)
PEC_AUDIT_DEADLINE_SUFFIX_RE = re.compile(r":deadline$", re.IGNORECASE)
PEC_AUDIT_HEARING_SUFFIX_RE = re.compile(r":hearing(?::[A-Za-z0-9_.-]+)?$", re.IGNORECASE)


def normalize_pec_audit_message_id(value: Any) -> str:
    """Rimuove solo i suffissi di correlazione, preservando gli ID con ``:``.

    Gli eventi derivati usano marker come ``<id>:deadline`` oppure
    ``<id>:hearing:<discriminatore>``. Il prefisso dell'ID può però essere
    legittimamente ``email:...``: per questo non si tronca genericamente al
    primo due-punti.
    """

    message_id = str(value or "").strip().rstrip(".,;:")
    while PEC_AUDIT_DEADLINE_SUFFIX_RE.search(message_id):
        message_id = PEC_AUDIT_DEADLINE_SUFFIX_RE.sub("", message_id).rstrip(".,;:")
    message_id = PEC_AUDIT_HEARING_SUFFIX_RE.sub("", message_id).rstrip(".,;:")
    return message_id


def pec_audit_message_id(item: Any) -> str:
    """Estrae l'audit PEC stabile da una riga agenda/scadenziario.

    L'ID è l'indice operativo: Agenda, Scadenziario, topbar e Web Push devono
    propagare questo riferimento invece di ricercare la PEC quando l'avvocato
    clicca sulla fonte.
    """

    if isinstance(item, str):
        context = item
        external_source_url = ""
    else:
        context = "\n".join(
            str(getattr(item, key, "") or "")
            for key in ("note", "descrizione", "titolo", "external_uid", "dedupe_key", "event_uid")
        )
        external_source_url = str(getattr(item, "external_source_url", "") or "")
    match = PEC_AUDIT_REF_RE.search(context)
    if match:
        message_id = normalize_pec_audit_message_id(match.group(1))
        return "" if message_id.casefold().startswith("docpresidio:") else message_id
    external_match = re.fullmatch(r"/api/pec/messages/([^/]+)", external_source_url.strip())
    if external_match:
        return normalize_pec_audit_message_id(external_match.group(1))
    return ""


def _source_name_rank(value: str) -> int:
    lower = clean_pec_source_name(value).casefold()
    if not lower or is_generic_pec_source_label(lower):
        return -1
    if lower.endswith(".pdf.zip"):
        return 100
    if lower.endswith(".zip"):
        return 90
    if lower.endswith(".pdf.p7m"):
        return 86
    if lower.endswith(".pdf"):
        return 84
    if lower.endswith((".docx", ".doc", ".rtf", ".odt")):
        return 70
    if lower.endswith(".p7m"):
        return 62
    if lower.endswith((".eml", ".msg")):
        return 55
    if lower.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
        return 50
    if lower.endswith(".xml"):
        if lower in {"indicebusta.xml", "comunicazione.xml", "daticert.xml"}:
            return 15
        return 35
    if lower.endswith(".txt"):
        return 25
    return 10


def _best_pec_source_name(values: Iterable[Any]) -> str:
    best: tuple[int, int, str] | None = None
    for index, value in enumerate(values):
        if isinstance(value, (list, tuple, set)):
            nested = _best_pec_source_name(value)
            candidates = [nested] if nested else []
        else:
            candidates = [value]
        for candidate in candidates:
            clean = clean_pec_source_name(candidate)
            rank = _source_name_rank(clean)
            if rank < 0:
                continue
            current = (rank, -index, clean)
            if best is None or current > best:
                best = current
    return best[2] if best else ""


def _first_specific_pec_source_name(values: Iterable[Any]) -> str:
    """Restituisce il primo legame documentale esplicito, senza ricalcolarlo per estensione."""

    for value in values:
        candidate = _best_pec_source_name(value) if isinstance(value, (list, tuple, set)) else clean_pec_source_name(value)
        if candidate and not is_generic_pec_source_label(candidate):
            return candidate
    return ""


def pec_profile_source_name(profile: Mapping[str, Any] | None) -> str:
    """Restituisce il documento PEC utile già indicizzato nel profilo.

    La priorità è professionale: se il report PEC ha individuato un PDF dentro
    uno ZIP, quello vince sulle etichette generiche del corpo PEC o sugli XML
    tecnici della busta.
    """

    if not isinstance(profile, Mapping):
        return ""
    remote = profile.get("remote_hearing") if isinstance(profile.get("remote_hearing"), Mapping) else {}
    bound_source = _first_specific_pec_source_name(
        [
        profile.get("source_name"),
        profile.get("source_file"),
        profile.get("fonte_documentale"),
        profile.get("documento_sorgente"),
        profile.get("remote_hearing_source"),
        ]
    )
    if bound_source:
        return bound_source
    inferred_sources: list[Any] = [
        remote.get("pdf_sources") if isinstance(remote, Mapping) else None,
        remote.get("document_sources") if isinstance(remote, Mapping) else None,
        remote.get("attachment_sources") if isinstance(remote, Mapping) else None,
        remote.get("hearing_sources") if isinstance(remote, Mapping) else None,
        remote.get("sources") if isinstance(remote, Mapping) else None,
        profile.get("_indexed_source_name"),
    ]
    return _best_pec_source_name(inferred_sources)


def control_tower_db_from_audit_db(pec_audit_db: str | Path) -> Path:
    """Deriva il DB Control Tower dal DB audit PEC dello stesso tenant."""

    audit_path = Path(str(pec_audit_db or "")).expanduser()
    if not audit_path.name:
        return audit_path
    return audit_path.with_name("pec_control_tower.sqlite")


def control_tower_communication_id(item: Any) -> str:
    """Estrae il riferimento persistito alla comunicazione Control Tower."""

    for field_name in ("note", "notes", "descrizione", "description", "dettaglio"):
        if isinstance(item, Mapping):
            value = item.get(field_name)
        else:
            value = getattr(item, field_name, "")
        match = CONTROL_TOWER_SOURCE_MARKER_RE.search(str(value or ""))
        if match:
            return match.group(1)
    return ""


def control_tower_source_key(item: Any) -> str:
    """Chiave univoca; il tipo/secondo resta solo per i dati storici."""

    communication_id = control_tower_communication_id(item)
    if communication_id:
        return f"id:{communication_id}"

    if isinstance(item, Mapping):
        event_type = str(item.get("source_event_type") or item.get("sourceEventType") or "").strip()
        event_at_value = item.get("source_event_at") or item.get("sourceEventAt") or item.get("data_decorrenza")
    else:
        event_type = str(getattr(item, "source_event_type", "") or "").strip()
        event_at_value = getattr(item, "source_event_at", "") or getattr(item, "data_decorrenza", "")
    event_at = _control_tower_timestamp(event_at_value)
    if not event_type or not event_at:
        return ""
    return f"{event_type}|{event_at}"


def latest_pec_profiles(
    items: Iterable[Any],
    *,
    pec_audit_db: str,
    tenant_id: str,
) -> dict[str, dict[str, Any]]:
    """Legge una sola volta i profili PEC e l'allegato utile già indicizzato.

    È il contratto condiviso per Agenda, Scadenziario, topbar e Web Push: ogni
    superficie riceve l'audit PEC e il documento sorgente persistito, senza
    riaprire MIME, ZIP o allegati riga per riga durante il rendering.
    """

    message_ids = sorted({pec_audit_message_id(item) for item in items} - {""})
    db_path = Path(str(pec_audit_db or "")).resolve()
    if not message_ids or not db_path.is_file():
        return {}

    profiles: dict[str, dict[str, Any]] = {}
    try:
        connection = sqlite3.connect(
            f"file:{db_path.as_posix()}?mode=ro",
            uri=True,
            timeout=1.0,
        )
        connection.row_factory = sqlite3.Row
        try:
            for offset in range(0, len(message_ids), 400):
                chunk = message_ids[offset : offset + 400]
                placeholders = ",".join("?" for _ in chunk)
                rows = connection.execute(
                    f"""
                    SELECT r.message_id, r.report_json
                    FROM pec_validation_reports r
                    INNER JOIN pec_messages m ON m.id = r.message_id
                    WHERE m.tenant_id = ?
                      AND r.message_id IN ({placeholders})
                      AND NOT EXISTS (
                          SELECT 1
                          FROM pec_validation_reports newer
                          WHERE newer.message_id = r.message_id
                            AND newer.rowid > r.rowid
                      )
                    """,
                    [str(tenant_id or "default"), *chunk],
                ).fetchall()
                for row in rows:
                    report = json.loads(str(row["report_json"] or "{}"))
                    profile = report.get("procedural_profile") if isinstance(report, dict) else None
                    if isinstance(profile, dict):
                        profiles[str(row["message_id"])] = dict(profile)

                try:
                    attachment_rows = connection.execute(
                        f"""
                        SELECT a.message_id, a.filename
                        FROM pec_attachments a
                        INNER JOIN pec_messages m ON m.id = a.message_id
                        WHERE m.tenant_id = ?
                          AND a.message_id IN ({placeholders})
                        ORDER BY a.message_id,
                          CASE
                            WHEN lower(a.filename) LIKE '%.pdf.zip' THEN 0
                            WHEN lower(a.filename) LIKE '%.zip' THEN 1
                            WHEN lower(a.filename) LIKE '%.pdf.p7m' THEN 2
                            WHEN lower(a.filename) LIKE '%.pdf' THEN 3
                            WHEN lower(a.filename) LIKE '%.docx' THEN 4
                            WHEN lower(a.filename) LIKE '%.doc' THEN 5
                            WHEN lower(a.filename) LIKE '%.xml' THEN 8
                            ELSE 9
                          END,
                          a.attachment_index ASC
                        """,
                        [str(tenant_id or "default"), *chunk],
                    ).fetchall()
                except sqlite3.Error:
                    attachment_rows = []
                attachment_candidates: dict[str, list[str]] = {}
                for row in attachment_rows:
                    attachment_candidates.setdefault(str(row["message_id"]), []).append(str(row["filename"] or ""))
                for message_id, filenames in attachment_candidates.items():
                    profile = profiles.setdefault(message_id, {})
                    indexed_source = _best_pec_source_name(
                        [
                            profile.get("_indexed_source_name"),
                            filenames,
                        ]
                    )
                    if indexed_source:
                        profile["_indexed_source_name"] = indexed_source
        finally:
            connection.close()
    except (OSError, sqlite3.Error, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return profiles


def latest_control_tower_sources(
    items: Any,
    *,
    pec_audit_db: str,
    tenant_id: str,
) -> dict[str, dict[str, Any]]:
    """Risolvi una volta le fonti PEC Control Tower collegate alle scadenze.

    La funzione è read-only e usa filtri su tipo evento e secondo esatto, così
    Agenda e Scadenziario non devono riaprire l'archivio PEC riga per riga.
    """

    rows = list(items or [])
    wanted_keys = {control_tower_source_key(item) for item in rows}
    wanted_keys.discard("")
    if not wanted_keys:
        return {}

    audit_path = Path(str(pec_audit_db or "")).resolve()
    tower_path = control_tower_db_from_audit_db(audit_path)
    if not tower_path.is_file():
        return {}

    exact_ids = sorted({key[3:] for key in wanted_keys if key.startswith("id:") and key[3:]})
    fallback_keys = {key for key in wanted_keys if not key.startswith("id:") and "|" in key}
    event_types = sorted({key.split("|", 1)[0] for key in fallback_keys})
    event_times = sorted({key.split("|", 1)[1] for key in fallback_keys})

    source_candidates: dict[str, dict[str, dict[str, Any]]] = {}
    try:
        tower = sqlite3.connect(f"file:{tower_path.as_posix()}?mode=ro", uri=True, timeout=1.0)
        tower.row_factory = sqlite3.Row
        audit = None
        if audit_path.is_file():
            audit = sqlite3.connect(f"file:{audit_path.as_posix()}?mode=ro", uri=True, timeout=1.0)
            audit.row_factory = sqlite3.Row
        try:
            selected_columns = """
                id, tenant_id, message_id_header, original_message_id,
                subject, sender, recipients_json, received_at, sent_at,
                mime_sha256, technical_type, legal_category, legal_event_type,
                confidence, confidence_label, requires_human_confirmation,
                status, fascicolo_id, fascicolo_score, risk_level, summary,
                extracted_json, evidence_json
            """
            for id_chunk in _chunks(exact_ids, 400):
                id_placeholders = ",".join("?" for _ in id_chunk)
                sql = f"""
                    SELECT {selected_columns}
                    FROM legal_communications
                    WHERE tenant_id = ? AND id IN ({id_placeholders})
                """
                for row in tower.execute(sql, [str(tenant_id or "default"), *id_chunk]).fetchall():
                    key = f"id:{str(row['id'] or '').strip()}"
                    source = _control_tower_source_payload(row, audit, tenant_id=str(tenant_id or "default"))
                    source_id = str(source.get("pecAuditId") or "").strip() if source else ""
                    if source and source_id:
                        source_candidates.setdefault(key, {})[source_id] = source

            if event_types and event_times:
                for type_chunk in _chunks(event_types, 80):
                    type_placeholders = ",".join("?" for _ in type_chunk)
                    for time_chunk in _chunks(event_times, 300):
                        time_placeholders = ",".join("?" for _ in time_chunk)
                        sql = f"""
                        SELECT
                            {selected_columns}
                        FROM legal_communications
                        WHERE tenant_id = ?
                          AND legal_event_type IN ({type_placeholders})
                          AND substr(received_at, 1, 19) IN ({time_placeholders})
                        """
                        for row in tower.execute(sql, [str(tenant_id or "default"), *type_chunk, *time_chunk]).fetchall():
                            key = f"{str(row['legal_event_type'] or '').strip()}|{_control_tower_timestamp(row['received_at'])}"
                            if key not in fallback_keys:
                                continue
                            source = _control_tower_source_payload(row, audit, tenant_id=str(tenant_id or "default"))
                            source_id = str(source.get("pecAuditId") or "").strip() if source else ""
                            if source and source_id:
                                per_key = source_candidates.setdefault(key, {})
                                current = per_key.get(source_id)
                                if current is None or _source_rank(source) > _source_rank(current):
                                    per_key[source_id] = source
        finally:
            if audit is not None:
                audit.close()
            tower.close()
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return {}
    # Il fallback tipo+secondo non è un identificativo sufficiente: se più PEC
    # diverse condividono lo stesso istante, nessuna può essere scelta per
    # ranking. Le superfici restano senza link finché l'evento non conserva il
    # PEC_AUDIT esatto, evitando di aprire il documento di un altro fascicolo.
    return {
        key: next(iter(candidates.values()))
        for key, candidates in source_candidates.items()
        if len(candidates) == 1
    }


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _source_rank(source: Mapping[str, Any]) -> tuple[int, int, str]:
    return (
        1 if str(source.get("pecAuditId") or "").startswith("pec_") else 0,
        int(float(source.get("confidence") or 0) * 100),
        str(source.get("receivedAt") or ""),
    )


def _control_tower_timestamp(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw.replace("Z", "+00:00")[:19]


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normal_message_id(value: Any) -> str:
    return str(value or "").strip().strip("<>").strip()


def _unique_audit_message_id(rows: list[sqlite3.Row]) -> str:
    """Restituisce l'audit PEC soltanto quando il criterio individua una riga.

    Un fallback non univoco non deve mai aprire arbitrariamente la PEC più
    recente: la fonte resta non collegata finché non è disponibile un indice
    persistito (hash MIME o Message-ID) che identifichi il messaggio esatto.
    """

    identifiers = {
        str(row["id"] or "").strip()
        for row in rows
        if str(row["id"] or "").strip()
    }
    return next(iter(identifiers)) if len(identifiers) == 1 else ""


def _audit_message_id_for_control_row(
    row: sqlite3.Row,
    audit: sqlite3.Connection | None,
    *,
    tenant_id: str,
) -> str:
    if audit is None:
        return ""
    mime_sha = str(row["mime_sha256"] or "").strip()
    if mime_sha:
        try:
            found = audit.execute(
                "SELECT id FROM pec_messages WHERE tenant_id = ? AND mime_sha256 = ? ORDER BY received_at DESC LIMIT 2",
                (tenant_id, mime_sha),
            ).fetchall()
            resolved = _unique_audit_message_id(found)
            if resolved:
                return resolved
        except sqlite3.Error:
            pass
    header = _normal_message_id(row["message_id_header"])
    if header:
        try:
            found = audit.execute(
                """
                SELECT id
                FROM pec_messages
                WHERE tenant_id = ?
                  AND replace(replace(CAST(message_id_header AS TEXT), '<', ''), '>', '') = ?
                ORDER BY received_at DESC
                LIMIT 2
                """,
                (tenant_id, header),
            ).fetchall()
            resolved = _unique_audit_message_id(found)
            if resolved:
                return resolved
        except sqlite3.Error:
            pass
    subject = str(row["subject"] or "").strip()
    received_at = _control_tower_timestamp(row["received_at"])
    if subject and received_at:
        try:
            found = audit.execute(
                """
                SELECT id
                FROM pec_messages
                WHERE tenant_id = ?
                  AND substr(received_at, 1, 19) = ?
                  AND CAST(metadata_json AS TEXT) LIKE ?
                ORDER BY received_at DESC
                LIMIT 2
                """,
                (tenant_id, received_at.replace("+00:00", "Z")[:19], f"%{subject[:80]}%"),
            ).fetchall()
            resolved = _unique_audit_message_id(found)
            if resolved:
                return resolved
        except sqlite3.Error:
            pass
    return ""


def _clean_receipt_subject(subject: Any, daticert: Mapping[str, Any]) -> str:
    text = str(daticert.get("oggetto") or subject or "").strip()
    text = re.sub(r"^\s*(?:ACCETTAZIONE|AVVENUTA\s+CONSEGNA|CONSEGNA|MANCATA\s+CONSEGNA)\s*:\s*", "", text, flags=re.IGNORECASE)
    return _short_text(text, 180).strip(" -:;")


def _receipt_label(row: sqlite3.Row, daticert: Mapping[str, Any] | None = None) -> str:
    daticert = daticert or {}
    raw_subject = " ".join(
        str(part or "")
        for part in (
            row["subject"],
            daticert.get("oggetto"),
            daticert.get("tipo"),
        )
    ).casefold()
    if "mancata consegna" in raw_subject or "non accettazione" in raw_subject:
        return "PEC di mancata consegna"
    if re.search(r"(?:^|\b)(?:avvenuta\s+consegna|consegna)\s*:", raw_subject):
        return "PEC di consegna"
    if re.search(r"(?:^|\b)accettazione\s*:", raw_subject):
        return "PEC di accettazione"
    technical = str(row["technical_type"] or "").strip()
    event_type = str(row["legal_event_type"] or "").strip()
    if technical in CONTROL_TOWER_RECEIPT_LABELS:
        return CONTROL_TOWER_RECEIPT_LABELS[technical]
    return CONTROL_TOWER_EVENT_LABELS.get(event_type, event_type.replace("_", " ").strip().title() or "PEC")


def _receipt_event_label(row: sqlite3.Row, receipt_label: str) -> str:
    event_type = str(row["legal_event_type"] or "").strip()
    if receipt_label == "PEC di consegna":
        return "Ricevuta di consegna PEC da conservare"
    if receipt_label == "PEC di accettazione":
        return "Ricevuta di accettazione PEC da presidiare"
    if receipt_label == "PEC di mancata consegna":
        return "Mancata consegna PEC da presidiare"
    return CONTROL_TOWER_EVENT_LABELS.get(event_type, receipt_label)


def _control_tower_source_payload(
    row: sqlite3.Row,
    audit: sqlite3.Connection | None,
    *,
    tenant_id: str,
) -> dict[str, Any]:
    evidence = _json_object(row["evidence_json"])
    extracted = _json_object(row["extracted_json"])
    daticert = evidence.get("daticert") if isinstance(evidence.get("daticert"), dict) else {}
    fascicolo_match = extracted.get("fascicolo_match") if isinstance(extracted.get("fascicolo_match"), dict) else {}
    pec_audit_id = _audit_message_id_for_control_row(row, audit, tenant_id=tenant_id)
    if not pec_audit_id:
        return {}
    encoded_id = quote(pec_audit_id or str(row["id"] or ""), safe="")
    subject = _clean_receipt_subject(row["subject"], daticert)
    recipient = _short_text(daticert.get("destinatario") or daticert.get("destinatari") or "", 160)
    sender = _short_text(daticert.get("mittente") or row["sender"] or "", 160)
    receipt_label = _receipt_label(row, daticert)
    source_href = f"/email/?audit_id={encoded_id}"
    event_label = _receipt_event_label(row, receipt_label)
    display_title = _short_text(": ".join(part for part in (receipt_label, subject) if part), 160)

    description_parts = [f"{receipt_label} della PEC"]
    if recipient:
        description_parts.append(f"inviata a {recipient}")
    if subject:
        description_parts.append(f"per {subject}")
    description = _short_text(" ".join(description_parts).rstrip(".") + ".", 280)

    detail_parts = [description]
    if sender:
        detail_parts.append(f"Mittente PEC: {sender}.")
    if recipient:
        detail_parts.append(f"Destinatario PEC: {recipient}.")
    if subject:
        detail_parts.append(f"Oggetto PEC: {subject}.")
    suggested_label = _short_text(fascicolo_match.get("label") or "", 140)
    suggested_score = float(fascicolo_match.get("score") or row["fascicolo_score"] or 0)
    suggested_requires_check = bool(fascicolo_match.get("requires_human_match")) or suggested_score < 3
    if suggested_label and suggested_requires_check:
        detail_parts.append(f"Possibile fascicolo da verificare: {suggested_label}.")
    if str(row["technical_type"] or "") == "PEC_RECEIPT_ACCEPTANCE":
        detail_parts.append(
            "Prova parziale: l'accettazione conferma la presa in carico dal gestore; "
            "per chiudere il presidio serve collegare anche la ricevuta di consegna o l'esito successivo."
        )
        detail_parts.append(
            "Attività per l'avvocato: verificare la ricevuta di consegna collegata, "
            "controllare se il fascicolo proposto è corretto e collegare il cliente solo quando il match è certo."
        )

    matched_fascicolo_id = str(row["fascicolo_id"] or fascicolo_match.get("fascicolo_id") or "").strip()
    if suggested_requires_check:
        matched_fascicolo_id = ""

    return {
        "sourceHref": source_href,
        "sourceLabel": receipt_label,
        "sourceKind": "pec",
        "sourceVerified": bool(pec_audit_id),
        "pecAuditId": pec_audit_id,
        "controlTowerCommunicationId": str(row["id"] or ""),
        "legalEventType": str(row["legal_event_type"] or ""),
        "legalEventTypeLabel": event_label,
        "displayTitle": display_title or receipt_label,
        "description": description,
        "detailDescription": _short_text(" ".join(detail_parts), 1000),
        "subject": subject,
        "recipient": recipient,
        "sender": sender,
        "fascicoloId": matched_fascicolo_id,
        "fascicoloSuggestedLabel": suggested_label if suggested_requires_check else "",
        "fascicoloSuggestedScore": suggested_score,
        "requiresHumanMatch": suggested_requires_check,
        "confidence": float(row["confidence"] or 0),
        "receivedAt": str(row["received_at"] or ""),
    }
