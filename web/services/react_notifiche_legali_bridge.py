"""Payload React per il workflow notifiche legali e comunicazioni cliente."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from pct.notifiche_legali import (
    DOCUMENT_ORIGIN_LABELS,
    LEGAL_NOTIFICATION_SUBJECT,
    LEGAL_RECIPIENT_ROLES,
    NON_PEC_NOTIFICATION_TYPES,
    PUBLIC_PEC_REGISTERS,
    UNEP_NOTIFICATION_TYPES,
    UNEP_REQUEST_TYPES,
    available_template_fields,
    client_communication_templates_version,
    list_client_communication_templates,
    list_notification_templates,
    legal_notification_automation_payload,
    is_plausible_pec_address,
    normalise_public_register,
    normalise_custom_template,
    normalise_document_origin,
    notification_directive_matrix,
    office_notification_evidence_from_pec,
    public_register_capability,
    template_preview_text,
    template_catalog_version,
)
from pct.studio_address import normalize_studio_location


_LEGACY_IMPORT_CONTENT_LABEL_CACHE: dict[str, str] = {}
_UI_TECHNICAL_LABEL_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:QuickOrganizer|Studio\s+Telematico)\b", re.IGNORECASE), "gestionale precedente"),
    (re.compile(r"\bDatiAtto(?:\.xml)?\b", re.IGNORECASE), "riepilogo del deposito"),
    (re.compile(r"\bTAVOLA\b", re.IGNORECASE), "prospetto dati"),
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _unep_office_catalog() -> list[dict[str, Any]]:
    """Espone il catalogo UNEP dalla stessa fonte usata da Tribunali / PEC."""

    from pct.uffici_giudiziari import get_gestore, indirizzi_telematici_ufficio

    gestore = get_gestore()
    rows = [
        row
        for row in gestore.carica()
        if _text(row.get("tipo")).upper() == "UNEP"
    ]
    updated_at = _text(gestore.stato().get("aggiornato_il"))
    offices: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        addresses = indirizzi_telematici_ufficio(row, data_rilevazione=updated_at)
        pec = _text(row.get("pec") or row.get("pec_ministero")).lower()
        offices.append({
            "id": _text(row.get("codice_ministero") or row.get("codice")) or f"unep-{index}",
            "codice": _text(row.get("codice_ministero") or row.get("codice")),
            "nome": _text(row.get("nome") or row.get("descrizione_ministero")),
            "distretto": _text(row.get("distretto_ministero") or row.get("distretto")),
            "comune": _text(row.get("comune_ministero") or row.get("comune")),
            "provincia": _text(row.get("provincia_ministero") or row.get("provincia")),
            "regione": _text(row.get("regione_ministero") or row.get("regione")),
            "pec": pec,
            "fonte": _text(addresses[0].get("fonte")) if addresses else "PST",
            "aggiornatoIl": updated_at,
        })
    offices.sort(key=lambda item: (
        item["comune"].casefold(),
        item["nome"].casefold(),
        item["codice"],
    ))
    return offices


def _sanitize_ui_string(value: str) -> str:
    cleaned = value
    for pattern, replacement in _UI_TECHNICAL_LABEL_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def _sanitize_ui_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_ui_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_ui_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_ui_payload(item) for item in value)
    if isinstance(value, str):
        return _sanitize_ui_string(value)
    return value


def sanitize_react_notifiche_legali_payload(value: Any) -> Any:
    return _sanitize_ui_payload(value)


def _display_text(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    cleaned = re.sub(r"\b(demo|sample|repository)\b", "", raw, flags=re.IGNORECASE)
    cleaned = _sanitize_ui_string(cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"[-–—]\s*$", "", cleaned).strip()
    return cleaned or raw


def _config_object(config_manager_or_config: Any) -> Any:
    return getattr(config_manager_or_config, "config", config_manager_or_config)


def _enum_value(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _first_attr(obj: Any, *names: str) -> str:
    for name in names:
        value = _text(getattr(obj, name, ""))
        if value:
            return value
    return ""


def _first_mapping_value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = _text(row.get(name))
        if value:
            return value
    return ""


def _safe_call(label: str, callback: Any, fallback: Any) -> Any:
    try:
        return callback() if callable(callback) else fallback
    except Exception:
        return fallback


def _repo_from_getter(getter: Any) -> Any:
    if callable(getter):
        return _safe_call("repo", getter, None)
    return getter


def _subject_identity(soggetto: Any, pec: str = "") -> str:
    identity = " ".join(
        part
        for part in (
            _text(getattr(soggetto, "nome_completo", "")),
            _text(getattr(soggetto, "ragione_sociale", "")),
            _text(getattr(soggetto, "qualifica", "")),
            _text(pec),
        )
        if part
    ).casefold()
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", identity)
        if not unicodedata.combining(character)
    )


def _is_state_attorney_subject(soggetto: Any, pec: str = "") -> bool:
    identity = _subject_identity(soggetto, pec)
    return bool(
        "avvocaturastato.it" in identity
        or re.search(r"\bavvocatura\b.{0,48}\b(?:dello|di)\s+stato\b", identity)
    )


def _is_public_administration_subject(soggetto: Any, pec: str = "") -> bool:
    if _enum_value(getattr(soggetto, "tipo", "")).upper() == "PUBBLICA_AMMINISTRAZIONE":
        return True
    identity = _subject_identity(soggetto, pec)
    institutional_name = re.search(
        r"\b(?:ministero|mim|miur|usr|usp|ufficio\s+scolastico|comune\s+di|"
        r"regione|provincia|citta\s+metropolitana|agenzia\s+delle\s+entrate|"
        r"agenzia\s+entrate.riscossione|rts|inps|inail|universita\s+degli\s+studi|"
        r"azienda\s+sanitaria|a\.s\.l\.|a\.s\.p\.)\b",
        identity,
    )
    institutional_pec = re.search(
        r"@[^\s@]*(?:\.gov\.it|giustiziacert\.it|pec\.istruzione\.it|"
        r"postacert\.istruzione\.it|postacert\.inps\.gov\.it)\b",
        identity,
    )
    return bool(institutional_name or institutional_pec)


def _infer_public_register(soggetto: Any, ruolo: str = "", pec: str = "") -> str:
    for tag in (getattr(soggetto, "tag", []) or []):
        raw_tag = _text(tag)
        if raw_tag.casefold().startswith("pubblico-elenco:"):
            explicit = normalise_public_register(raw_tag.split(":", 1)[1])
            if explicit in PUBLIC_PEC_REGISTERS:
                return explicit
    tipo = _enum_value(getattr(soggetto, "tipo", "")).upper()
    qualifica = _text(getattr(soggetto, "qualifica", "")).lower()
    ruolo = ruolo.upper()
    if _is_state_attorney_subject(soggetto, pec):
        return "reginde"
    if "DIFENSORE" in ruolo:
        return "reginde"
    if _is_public_administration_subject(soggetto, pec):
        return "registro_ppaa"
    if tipo in {"PERSONA_GIURIDICA", "ENTE", "CONDOMINIO", "ASSOCIAZIONE"}:
        return "ini_pec"
    if tipo == "PROFESSIONISTA":
        return "ini_pec"
    if "avv" in qualifica or "avvocato" in qualifica:
        return "reginde"
    return "inad"


def _infer_recipient_role(soggetto: Any, ruolo: str = "", pec: str = "") -> str:
    tipo = _enum_value(getattr(soggetto, "tipo", "")).upper()
    qualifica = _text(getattr(soggetto, "qualifica", "")).lower()
    ruolo = ruolo.upper()
    if _is_state_attorney_subject(soggetto, pec):
        return "difensore"
    if "DIFENSORE" in ruolo or "avv" in qualifica or "avvocato" in qualifica:
        return "difensore"
    if _is_public_administration_subject(soggetto, pec):
        return "pa"
    if tipo == "PROFESSIONISTA":
        return "professionista"
    if tipo in {"PERSONA_GIURIDICA", "ENTE", "CONDOMINIO", "ASSOCIAZIONE"}:
        return "impresa"
    if "CONTROPARTE" in ruolo or "DEBITORE" in ruolo or "CREDITORE" in ruolo:
        return "controparte"
    return "terzo"


_TITLE_PARTS_RE = re.compile(r"^\s*(?:RG\s+\d+\s*/\s*\d{4}\s*[–—-]\s*)?(?P<left>.+?)\s+(?:c\.|contro|/)\s+(?P<right>.+?)\s*$", re.IGNORECASE)
_RG_RE = re.compile(r"\b(?:R\.?\s*G\.?|NRG|N\.?\s*RG)\s*:?\s*0*(?P<num>\d{1,8})(?:\s*/\s*|\s+)(?P<anno>20\d{2})\b", re.IGNORECASE)
_PEC_RE = re.compile(r"\b[A-Z0-9._%+\-']+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)
def _derive_parties_from_title(title: str) -> tuple[str, str]:
    clean = re.sub(r"\s+", " ", _text(title))
    match = _TITLE_PARTS_RE.search(clean)
    if not match:
        return "", ""
    return _display_text(match.group("left")), _display_text(match.group("right"))


def _derive_rg_from_text(*values: Any) -> tuple[str, str]:
    haystack = " ".join(_text(value) for value in values if _text(value))
    match = _RG_RE.search(haystack)
    if not match:
        return "", ""
    return match.group("num"), match.group("anno")


def _is_timestamp_filename(value: str) -> bool:
    stem = re.sub(r"\.[A-Za-z0-9.]+$", "", _text(value))
    return bool(re.fullmatch(r"\d{12,20}", stem))


def _clean_operational_filename(value: str) -> str:
    cleaned = _display_text(value)
    replacements = {
        "conformit_": "conformità",
        "identit_": "identità",
        "annualit_": "annualità",
        "l¿udienza": "l'udienza",
        "¿CARTA DEL DOCENTE¿": "Carta del docente",
        "RG_": "RG ",
        "_": " ",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -")
    return cleaned


def _is_import_pratiche_marker(value: Any) -> bool:
    text = _text(value).casefold()
    return any(
        marker in text
        for marker in (
            "quickorganizer",
            "import pratiche",
            "gestionale precedente",
            "pacchetto pratiche",
        )
    )


def _import_pratiche_note_filename(documento: Any) -> str:
    note = _text(getattr(documento, "note", ""))
    match = re.search(r"(?:QuickOrganizer|Import\s+pratiche)\.\s*(.+)", note, flags=re.IGNORECASE)
    if not match:
        return ""
    candidate = match.group(1).strip()
    if not candidate:
        return ""
    candidate = re.split(r"\s+-\s+Depositante:|\s+-\s+Tipologia:|\s+copia informatica|\s+data notifica:", candidate, maxsplit=1, flags=re.IGNORECASE)[0]
    candidate = _clean_operational_filename(candidate)
    if not candidate or candidate.lower() in {"scaricato dal polisweb", "conformità"}:
        return ""
    return candidate


def _clean_ocr_document_title(value: str) -> str:
    title = _display_text(value)
    title = title.replace("“", " ").replace("”", " ").replace("«", " ").replace("»", " ")
    title = re.sub(r"\b(?:c\.?\s*f\.?|codice\s+fiscale|nato\s+a|nata\s+a)\b.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\b(?:stipulato|sottoscritto)\s+tra\b.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s{2,}", " ", title).strip(" .,:;-")
    if not title:
        return ""
    return title[:1].upper() + title[1:160]


def _derive_document_title_from_text(text: str) -> str:
    lines = [
        _display_text(line)
        for line in str(text or "").replace("\r", "\n").split("\n")
        if _display_text(line)
    ]
    if not lines:
        return ""
    joined = " ".join(lines[:18])
    upper_joined = joined.upper()
    if "CONTRATTO INDIVIDUALE DI LAVORO" in upper_joined and "TEMPO DETERMINATO" in upper_joined:
        return "Contratto individuale di lavoro a tempo determinato"
    if "CARTA DEL DOCENTE" in upper_joined and "RICORSO" in upper_joined and "RECUPERO" in upper_joined:
        return "Ricorso per il recupero della Carta del docente"
    if "CARTA DEL DOCENTE" in upper_joined and "RICHIESTA" in upper_joined and "PAGAMENTO" in upper_joined:
        return "Richiesta pagamento Carta del docente"
    if "CORTE SUPREMA DI CASSAZIONE" in upper_joined and "CARTA DOCENTE" in upper_joined and "SENTENZA" in upper_joined:
        return "Sentenza Cassazione Carta del docente"
    if "RICORSO EX ART. 414" in upper_joined and (
        "DIRITTO INSEGNANTI PRECARI" in upper_joined or "LEGGE N. 107/2015" in upper_joined
    ):
        return "Ricorso lavoro Carta del docente"
    if "TRIBUNALE ORDINARIO" in upper_joined and "SENTENZA" in upper_joined and "DOCENTE" in upper_joined and "TEMPO DETERMINATO" in upper_joined:
        return "Sentenza lavoro personale docente a tempo determinato"
    if "ATTESTAZIONE DI CONFORMIT" in upper_joined:
        return "Attestazione di conformità"
    if "RELATA DI NOTIFICA" in upper_joined:
        return "Relata di notifica"
    if "DIRITTO INSEGNANTI PRECARI" in upper_joined and "CARTA DEL DOCENTE" in upper_joined:
        return "Approfondimento Carta del docente"
    oggetto = re.search(r"\bOggetto\s*:\s*(.{18,180})", joined, flags=re.IGNORECASE)
    if oggetto:
        title = re.split(r"\b(?:Dirigente|PREMESSO|Il/La|Spett\.le)\b|\.\s+[A-Z]", oggetto.group(1), maxsplit=1)[0]
        title = _clean_ocr_document_title(title)
        if len(title) >= 16:
            return title
    for marker, title in (
        ("RICORSO", "Ricorso"),
        ("PROCURA", "Procura alle liti"),
        ("CONTRATTO INDIVIDUALE DI LAVORO", "Contratto individuale di lavoro"),
        ("AUTOCERTIFICAZIONE DELLA SITUAZIONE REDDITUALE", "Autocertificazione della situazione reddituale"),
        ("ESENZIONE DAL CONTRIBUTO UNIFICATO", "Dichiarazione esenzione contributo unificato"),
        ("ATTESTAZIONE DI CONFORMIT", "Attestazione di conformità"),
        ("RELATA DI NOTIFICA", "Relata di notifica"),
        ("STUDIO LEGALE", "Comunicazione dello studio legale"),
    ):
        if marker in upper_joined:
            return title
    for line in lines[:8]:
        upper = line.upper()
        if len(line) >= 18 and not upper.startswith(("MINISTERO", "ISTITUTO", "REPUBBLICA", "TRIBUNALE")):
            return _clean_ocr_document_title(line)[:110]
    return ""


def _resolve_document_path(documento: Any) -> Path | None:
    raw_path = _text(getattr(documento, "percorso", ""))
    raw_name = _first_attr(documento, "nome", "nome_originale")
    if not raw_path and not raw_name:
        return None
    candidates: list[Path] = []
    if raw_path:
        path = Path(raw_path)
        if path.is_absolute():
            candidates.append(path)
    try:
        from flask import g

        docs_root = _text((getattr(g, "data_paths", {}) or {}).get("FASCICOLI_DOCS"))
        if docs_root:
            if raw_path:
                candidates.append(Path(docs_root) / raw_path)
                candidates.append(Path(docs_root) / raw_path.replace("\\", "/"))
            if raw_name:
                candidates.extend(Path(docs_root).glob(f"**/{raw_name}"))
    except Exception:
        pass
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _extract_first_page_text(path: Path) -> str:
    cache_key = ""
    try:
        stat = path.stat()
        cache_key = f"{path}:{stat.st_size}:{int(stat.st_mtime)}"
        if cache_key in _LEGACY_IMPORT_CONTENT_LABEL_CACHE:
            return _LEGACY_IMPORT_CONTENT_LABEL_CACHE[cache_key]
        if stat.st_size > int(os.getenv("IUSENTRA_NOTIFICHE_OCR_MAX_BYTES", "6000000")):
            return ""
    except (OSError, ValueError):
        return ""
    extracted = ""
    try:
        result = subprocess.run(
            ["pdftotext", "-l", "1", str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        extracted = _text(result.stdout)
    except (OSError, subprocess.SubprocessError):
        extracted = ""
    if not extracted:
        with tempfile.TemporaryDirectory(prefix="iusentra-doc-label-") as tmpdir:
            image_prefix = str(Path(tmpdir) / "page")
            try:
                subprocess.run(
                    ["pdftoppm", "-f", "1", "-l", "1", "-png", "-r", "140", str(path), image_prefix],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                image_path = Path(f"{image_prefix}-1.png")
                if image_path.exists():
                    result = subprocess.run(
                        ["tesseract", str(image_path), "stdout", "-l", "ita", "--psm", "6"],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=18,
                    )
                    extracted = _text(result.stdout)
            except (OSError, subprocess.SubprocessError):
                extracted = ""
    if cache_key:
        _LEGACY_IMPORT_CONTENT_LABEL_CACHE[cache_key] = extracted
    return extracted


def _legacy_import_content_label(documento: Any) -> str:
    name = _first_attr(documento, "nome", "titolo", "nome_portale", "nome_originale", "percorso")
    marker = _first_attr(documento, "classificazione_portale", "note", "fonte_documento")
    tags = " ".join(_text(item) for item in (getattr(documento, "tags", []) or []))
    if not (_is_timestamp_filename(name) and _is_import_pratiche_marker(f"{marker} {tags}")):
        return ""
    path = _resolve_document_path(documento)
    if path is None:
        return ""
    return _derive_document_title_from_text(_extract_first_page_text(path))


def _infer_fallback_recipient_role(name: str) -> str:
    text = _text(name).lower()
    if "avvocatura" in text and "stato" in text:
        return "difensore"
    if any(token in text for token in ("ministero", "mim", "miur", "comune", "agenzia", "inps", "inail")):
        return "pa"
    if any(token in text for token in ("s.p.a", "spa", "s.r.l", "srl", "banca", "ass.ni", "assicur")):
        return "impresa"
    return "controparte"


def _recipient_from_plain(
    *,
    recipient_id: str,
    name: str,
    pec: str = "",
    represented: str = "",
    role: str = "",
    source: str = "",
) -> dict[str, Any]:
    clean_name = _display_text(name)
    clean_pec = _text(pec).lower()
    resolved_role = role or _infer_fallback_recipient_role(clean_name)
    resolved_source = source or (
        "reginde"
        if resolved_role == "difensore"
        else "registro_ppaa"
        if resolved_role == "pa"
        else "ini_pec"
    )
    return {
        "id": recipient_id,
        "label": clean_name or clean_pec,
        "nome": clean_name,
        "codiceFiscalePiva": "",
        "pec": clean_pec,
        "ruolo": resolved_role,
        "ruoloPratica": resolved_role,
        "fontePecSuggerita": resolved_source,
        "parteRappresentata": _display_text(represented or clean_name),
        "verificaRichiesta": bool(clean_pec),
    }


def _canonical_recipient_identity(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", _text(value).casefold())
    if normalized in {"mim", "miur", "ministeroistruzione", "ministerodellistruzione"}:
        return "ministerodellistruzioneedelmerito"
    if normalized.startswith("ministerodellistruzioneedelmerito"):
        return "ministerodellistruzioneedelmerito"
    return normalized


def _merge_notification_recipients(recipients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unisce alias della stessa parte privilegiando il recapito PEC completo."""
    merged: list[dict[str, Any]] = []
    by_identity: dict[str, int] = {}
    by_pec: dict[str, int] = {}
    for raw in recipients:
        candidate = dict(raw)
        pec = _text(candidate.get("pec")).lower()
        identity = _canonical_recipient_identity(candidate.get("nome") or candidate.get("label"))
        existing_index = by_pec.get(pec) if pec else None
        if existing_index is None and identity:
            identity_index = by_identity.get(identity)
            # Due domicili digitali diversi dello stesso ente restano due
            # destinatari distinti. Il nome serve a fondere solo alias privi di PEC.
            if identity_index is not None and (
                not pec or not _text(merged[identity_index].get("pec"))
            ):
                existing_index = identity_index
        if existing_index is None:
            existing_index = len(merged)
            merged.append(candidate)
        else:
            current = merged[existing_index]
            # Se il record attuale e' soltanto un alias senza PEC, il record
            # completo diventa quello operativo conservando i dati utili gia' noti.
            if pec and not _text(current.get("pec")):
                replacement = candidate
                for key, value in current.items():
                    if not _text(replacement.get(key)) and _text(value):
                        replacement[key] = value
                merged[existing_index] = replacement
                current = replacement
            else:
                for key, value in candidate.items():
                    if not _text(current.get(key)) and _text(value):
                        current[key] = value
        current = merged[existing_index]
        current_identity = _canonical_recipient_identity(current.get("nome") or current.get("label"))
        current_pec = _text(current.get("pec")).lower()
        if identity:
            by_identity.setdefault(identity, existing_index)
        if current_identity:
            by_identity.setdefault(current_identity, existing_index)
        if pec:
            by_pec[pec] = existing_index
        if current_pec:
            by_pec[current_pec] = existing_index
    return sorted(merged, key=lambda item: (not bool(_text(item.get("pec"))),))


def _recipient_source_from_pec(address: str) -> tuple[str, str]:
    lower = address.lower()
    if "avvocaturastato" in lower or "mailcert.avvocaturastato" in lower:
        return "Avvocatura dello Stato", "reginde"
    if "istruzione" in lower or "postcert" in lower or "pec.istruzione" in lower:
        return "Ministero dell'Istruzione e del Merito", "registro_ppaa"
    return address, "ini_pec"


def _recipients_from_document_notes(documenti: list[Any], *, represented: str) -> list[dict[str, Any]]:
    recipients: list[dict[str, Any]] = []
    seen: set[str] = set()
    for documento in documenti:
        note = _text(getattr(documento, "note", ""))
        for match in _PEC_RE.finditer(note):
            pec = match.group(0).lower()
            if pec in seen:
                continue
            seen.add(pec)
            label, source = _recipient_source_from_pec(pec)
            recipients.append(
                _recipient_from_plain(
                    recipient_id=f"pec:{pec}",
                    name=label,
                    pec=pec,
                    represented=represented or label,
                    role="pa" if source == "registro_ppaa" else "difensore" if source == "reginde" else "",
                    source=source,
                )
            )
    return recipients


def _recipient_from_subject(soggetto: Any, *, ruolo: str = "", note: str = "", fascicolo: Any = None) -> dict[str, Any]:
    pec = _text(getattr(getattr(soggetto, "recapiti", None), "pec", ""))
    role = _infer_recipient_role(soggetto, ruolo, pec)
    source = _infer_public_register(soggetto, ruolo, pec)
    fascicolo_counterparty = _text(getattr(fascicolo, "controparte", ""))
    _, title_counterparty = _derive_parties_from_title(_text(getattr(fascicolo, "titolo", "")))
    if role == "difensore" and _is_state_attorney_subject(soggetto, pec):
        counterparty_identity = re.sub(r"[^a-z0-9]+", "", fascicolo_counterparty.casefold())
        if not fascicolo_counterparty or "avvocatura" in counterparty_identity:
            fascicolo_counterparty = title_counterparty
        represented_identity = re.sub(r"[^a-z0-9]+", "", fascicolo_counterparty.casefold())
        if represented_identity in {"mim", "miur"}:
            fascicolo_counterparty = "Ministero dell'Istruzione e del Merito"
    note_text = _text(note)
    represented = (
        fascicolo_counterparty or note_text
        if role == "difensore"
        else note_text or fascicolo_counterparty
    )
    if fascicolo is None and role == "difensore" and _is_state_attorney_subject(soggetto, pec) and not note_text:
        represented = ""
    if not represented and role in {"difensore", "controparte", "impresa", "professionista", "terzo"}:
        if not (fascicolo is None and role == "difensore" and _is_state_attorney_subject(soggetto, pec)):
            represented = _text(getattr(soggetto, "nome_completo", "")) or _text(getattr(soggetto, "ragione_sociale", ""))
    return {
        "id": _text(getattr(soggetto, "id", "")),
        "label": _display_text(getattr(soggetto, "nome_completo", "")) or _display_text(getattr(soggetto, "ragione_sociale", "")),
        "nome": _text(getattr(soggetto, "nome_completo", "")) or _text(getattr(soggetto, "ragione_sociale", "")),
        "codiceFiscalePiva": _text(getattr(soggetto, "identificativo", "")),
        "pec": pec,
        "ruolo": role,
        "ruoloPratica": role,
        "fontePecSuggerita": source,
        "parteRappresentata": represented,
        "verificaRichiesta": bool(pec),
    }


def _infer_document_origin(documento: Any) -> str:
    fonte = _text(getattr(documento, "fonte_documento", "")).upper()
    tags = " ".join(_text(item).lower() for item in (getattr(documento, "tags", []) or []))
    if "cancelleria" in fonte.lower() or "comunicazione_cancelleria" in tags:
        return "comunicazione_cancelleria"
    if fonte in {"PORTALE_TELEMATICO", "PST", "PDP", "PAT", "PTT"}:
        return "copia_fascicolo_informatico"
    if _text(getattr(documento, "id_documento_portale", "")) or _text(getattr(documento, "nome_portale", "")):
        return "copia_fascicolo_informatico"
    if "scansione" in tags or "analogico" in tags:
        return "scansione_analogico"
    return "originale_informatico"


def _document_label(documento: Any) -> str:
    name = _first_attr(documento, "nome", "titolo", "nome_portale", "nome_originale", "percorso")
    operational_name = _import_pratiche_note_filename(documento)
    if operational_name and (_is_timestamp_filename(name) or _is_import_pratiche_marker(_first_attr(documento, "classificazione_portale", "note"))):
        name = operational_name
    return _display_text(name)


def _portal_acquisition_href(fascicolo: Any, *, portale: str = "pst") -> str:
    params = {
        "id_fasc": _text(getattr(fascicolo, "id", "")),
        "numero": _text(getattr(fascicolo, "numero_rg", "")),
        "anno": _text(getattr(fascicolo, "anno_rg", "")),
        "ufficio": _text(getattr(fascicolo, "tribunale", "")),
        "focus": "documenti",
        "mode": "update_existing",
    }
    query = urlencode({key: value for key, value in params.items() if value})
    return f"/portali/{portale}/acquisizione{f'?{query}' if query else ''}"


def _normalise_document_match(value: Any) -> str:
    raw = _text(value).lower()
    if raw.endswith(".pdf.p7m"):
        raw = raw[:-4]
    elif raw.endswith(".p7m") and ".pdf" not in raw:
        raw = raw[:-4]
    return re.sub(r"[^a-z0-9]+", "", raw)


def _office_pec_messages() -> list[Any]:
    try:
        from web.helpers import get_email_pec

        return list(get_email_pec().tutte())[:500]
    except Exception:
        return []


def _document_notification_required(documento: Any, *, origin: str) -> bool:
    haystack = " ".join(
        _text(value).lower()
        for value in (
            getattr(documento, "tipo_atto_portale", ""),
            getattr(documento, "classificazione_portale", ""),
            getattr(documento, "note", ""),
            getattr(documento, "nome_originale", ""),
            getattr(documento, "nome_portale", ""),
            getattr(documento, "nome", ""),
            " ".join(str(item) for item in (getattr(documento, "tags", []) or [])),
        )
    )
    if bool(getattr(documento, "notifica_richiesta", False)) or bool(getattr(documento, "notificaRichiesta", False)):
        return True
    return origin == "comunicazione_cancelleria" and any(
        token in haystack for token in ("notifica", "notificare", "relata", "termine breve", "sentenza", "ordinanza", "decreto", "provvedimento")
    )


def _notification_proof_kind(documento: Any, *, origin: str) -> str:
    haystack = " ".join(
        _text(value).lower()
        for value in (
            getattr(documento, "tipo", ""),
            getattr(documento, "tipo_atto_portale", ""),
            getattr(documento, "classificazione_portale", ""),
            getattr(documento, "note", ""),
            getattr(documento, "nome_originale", ""),
            getattr(documento, "nome_portale", ""),
            getattr(documento, "nome", ""),
            " ".join(str(item) for item in (getattr(documento, "tags", []) or [])),
        )
    )
    notification_context = any(
        token in haystack
        for token in (
            "notifica",
            "notificaz",
            "originale notificato",
            "legge n. 53",
            "legge 53",
            "l. 53",
            "notifica_id",
            "notificazione ai sensi",
        )
    )
    if "relata" in haystack and notification_context:
        return "relata"
    if "originale notificato" in haystack and any(
        token in haystack for token in ("ricorso", "citazione", "comparsa", "memoria", "istanza", "atto", "decreto", "provvedimento")
    ):
        return "atto"
    if notification_context and any(token in haystack for token in ("accettazione", "rac")):
        return "rac"
    if notification_context and any(token in haystack for token in ("consegna", "rdac", "avvenuta consegna")):
        return "rdac"
    if notification_context and any(token in haystack for token in ("pec inviata", "postacert", ".eml", "messaggio pec")):
        return "pec"
    if notification_context and "attestazione di conform" in haystack:
        return "attestazione"
    if bool(getattr(documento, "prova_notifica", False)) or origin == "notifica_l53":
        return "atto"
    return ""


def _document_from_fascicolo(
    documento: Any,
    *,
    office_names: set[str] | None = None,
    office_hashes: set[str] | None = None,
    resolve_content_label: bool = False,
) -> dict[str, Any]:
    origin = normalise_document_origin(_infer_document_origin(documento))
    name = _first_attr(documento, "nome", "titolo", "nome_portale", "nome_originale", "percorso")
    original_name = name
    operational_name = _import_pratiche_note_filename(documento)
    raw_description = _first_attr(documento, "tipo_atto_portale", "classificazione_portale", "note")
    if operational_name and (_is_timestamp_filename(name) or _is_import_pratiche_marker(raw_description)):
        name = operational_name
    content_label = _legacy_import_content_label(documento) if resolve_content_label and not operational_name else ""
    label = content_label or _document_label(documento) or _display_text(name)
    description = raw_description or name
    if operational_name and _is_import_pratiche_marker(description):
        description = "Documento importato dal fascicolo"
    elif content_label and _is_import_pratiche_marker(description):
        description = f"Nome file originale: {original_name}"
    portal_ref = _first_attr(documento, "id_documento_portale", "id_portale", "codice_portale", "riferimento_portale")
    source_name = _text(getattr(documento, "fonte_documento", ""))
    portal_service = _first_attr(documento, "servizio_portale", "nome_portale")
    acquired_from_portal = bool(
        portal_ref
        or source_name.upper() in {"PORTALE_TELEMATICO", "PST", "POLISWEB", "PDP", "PAT", "PTT", "SIGIT"}
        or portal_service.upper() in {"PST", "POLISWEB", "PDP", "PAT", "PTT", "SIGIT"}
    )
    name_key = _normalise_document_match(name)
    sha_key = _text(getattr(documento, "hash_sha256", "")).lower()
    pec_evidence = bool((name_key and name_key in (office_names or set())) or (sha_key and sha_key in (office_hashes or set())))
    notification_proof_kind = _notification_proof_kind(documento, origin=origin)
    notification_required = pec_evidence or _document_notification_required(documento, origin=origin)
    office_document = (
        pec_evidence
        or bool(getattr(documento, "documento_ufficio", False))
        or bool(getattr(documento, "notifica_richiesta", False))
        or origin == "comunicazione_cancelleria"
    )
    return {
        "id": _text(getattr(documento, "id", "")) or name,
        "label": label,
        "nomeFile": name,
        "nomeOriginale": original_name,
        "descrizione": _display_text(description),
        "origine": origin,
        "hashSha256": _text(getattr(documento, "hash_sha256", "")),
        "dataDocumento": _text(getattr(documento, "data_documento", "")) or _text(getattr(documento, "data_deposito_portale", "")),
        "fonte": source_name,
        "riferimentoPortale": _text(portal_ref),
        "servizioPortale": portal_service,
        "documentoUfficio": office_document,
        "acquisitoDaPortale": acquired_from_portal,
        "notificaRichiesta": notification_required,
        "provaNotifica": bool(notification_proof_kind),
        "tipoProvaNotifica": notification_proof_kind,
        "dataRilascioPortale": _text(getattr(documento, "data_deposito_portale", "")) or _text(getattr(documento, "data_documento", "")),
        "necessitaAttestazione": origin in {"copia_fascicolo_informatico", "comunicazione_cancelleria", "scansione_analogico"},
    }


def _cliente_option(cliente: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(cliente, "id", "")),
        "nome": _display_text(getattr(cliente, "nome_completo", "")),
        "codiceFiscalePiva": _text(getattr(cliente, "identificativo_fiscale", "")),
        "pec": _text(getattr(getattr(cliente, "recapiti", None), "pec", "")),
    }


def _fascicolo_index_option(fascicolo: Any, *, cliente: Any = None) -> dict[str, Any]:
    title = _text(getattr(fascicolo, "titolo", ""))
    title_assistito, title_controparte = _derive_parties_from_title(title)
    derived_numero_rg, derived_anno_rg = _derive_rg_from_text(
        getattr(fascicolo, "numero", ""),
        title,
        getattr(fascicolo, "note", ""),
        getattr(fascicolo, "oggetto", ""),
    )
    explicit_numero_rg = _text(getattr(fascicolo, "numero_rg", ""))
    raw_anno_rg = _text(getattr(fascicolo, "anno_rg", ""))
    numero_rg = explicit_numero_rg or derived_numero_rg
    anno_rg = ("" if raw_anno_rg in {"0", "0.0"} else raw_anno_rg) or derived_anno_rg
    if not explicit_numero_rg:
        anno_rg = derived_anno_rg or anno_rg
    status = _enum_value(getattr(fascicolo, "stato", ""))
    number = _text(getattr(fascicolo, "numero", ""))
    client_name = (
        _text(getattr(cliente, "nome_completo", ""))
        or _text(getattr(fascicolo, "nome_cliente", ""))
        or title_assistito
    )
    return {
        "id": _text(getattr(fascicolo, "id", "")),
        "label": _display_text(" - ".join(part for part in (number, title) if part)),
        "numero": number,
        "titolo": _display_text(title),
        "assistitoNome": _display_text(client_name),
        "controparte": _display_text(_text(getattr(fascicolo, "controparte", "")) or title_controparte),
        "ufficio": _display_text(getattr(fascicolo, "tribunale", "")),
        "numeroRg": numero_rg,
        "annoRg": anno_rg,
        "oggetto": _display_text(getattr(fascicolo, "oggetto", "")),
        "stato": status,
        "archiviata": status.upper() == "ARCHIVIATO",
    }


def _fascicolo_option(fascicolo: Any, *, cliente: Any = None, soggetti_repo: Any = None, pec_emails: list[Any] | None = None) -> dict[str, Any]:
    title = _text(getattr(fascicolo, "titolo", ""))
    title_assistito, title_controparte = _derive_parties_from_title(title)
    derived_numero_rg, derived_anno_rg = _derive_rg_from_text(
        getattr(fascicolo, "numero", ""),
        title,
        getattr(fascicolo, "note", ""),
        getattr(fascicolo, "oggetto", ""),
    )
    explicit_numero_rg = _text(getattr(fascicolo, "numero_rg", ""))
    raw_anno_rg = _text(getattr(fascicolo, "anno_rg", ""))
    numero_rg = explicit_numero_rg or derived_numero_rg
    if explicit_numero_rg:
        anno_rg = "" if raw_anno_rg in {"0", "0.0"} else raw_anno_rg
        anno_rg = anno_rg or derived_anno_rg
    else:
        anno_rg = derived_anno_rg or ("" if raw_anno_rg in {"0", "0.0"} else raw_anno_rg)
    proceeding_present = bool(
        _text(getattr(fascicolo, "tribunale", ""))
        or numero_rg
        or anno_rg
    )
    recipients: list[dict[str, Any]] = []
    if soggetti_repo is not None:
        parti = _safe_call(
            "parti_fascicolo",
            lambda: soggetti_repo.parti_fascicolo(_text(getattr(fascicolo, "id", ""))),
            [],
        )
        for parte, soggetto in parti:
            ruolo = _enum_value(getattr(parte, "ruolo", ""))
            if ruolo == "ASSISTITO":
                continue
            recipient = _recipient_from_subject(
                soggetto,
                ruolo=ruolo,
                note=_text(getattr(parte, "note", "")),
                fascicolo=fascicolo,
            )
            if recipient["nome"] or recipient["pec"]:
                recipients.append(recipient)
    pec_evidence = office_notification_evidence_from_pec(fascicolo, pec_emails or [])
    office_names = {
        _normalise_document_match(item.get("nome"))
        for item in pec_evidence
        if item.get("acquisito")
    }
    office_hashes = {
        _text(item.get("hashSha256")).lower()
        for item in pec_evidence
        if item.get("acquisito") and _text(item.get("hashSha256"))
    }
    documents = [
        _document_from_fascicolo(documento, office_names=office_names, office_hashes=office_hashes)
        for documento in (getattr(fascicolo, "documenti", []) or [])[:60]
    ]
    client_name = (
        _text(getattr(cliente, "nome_completo", ""))
        or _text(getattr(fascicolo, "nome_cliente", ""))
        or title_assistito
    )
    client_cf = _text(getattr(cliente, "identificativo_fiscale", ""))
    counterpart_name = _text(getattr(fascicolo, "controparte", "")) or title_controparte
    counterpart_cf = _text(getattr(fascicolo, "cf_controparte", ""))
    if counterpart_name and not any(
        _text(item.get("nome")).lower() == counterpart_name.lower()
        or _text(item.get("label")).lower() == counterpart_name.lower()
        for item in recipients
    ):
        recipients.append(
            _recipient_from_plain(
                recipient_id=f"fascicolo:{_text(getattr(fascicolo, 'id', ''))}:controparte",
                name=counterpart_name,
                represented=counterpart_name,
                role=_infer_fallback_recipient_role(counterpart_name),
                source="",
            )
        )
    for recipient in _recipients_from_document_notes(getattr(fascicolo, "documenti", []) or [], represented=counterpart_name or client_name):
        recipient_key = _text(recipient.get("pec")).lower() or _text(recipient.get("nome")).lower()
        if recipient_key and not any(
            (_text(item.get("pec")).lower() or _text(item.get("nome")).lower()) == recipient_key
            for item in recipients
        ):
            recipients.append(recipient)
    office_documents = [
        documento
        for documento in documents
        if documento["documentoUfficio"] or documento["notificaRichiesta"]
    ]
    acquired_office_documents = [documento for documento in office_documents if documento["notificaRichiesta"] or documento["documentoUfficio"]]
    pending_releases = [item for item in pec_evidence if not item.get("acquisito")]
    monitor_status = (
        "da_acquisire"
        if pending_releases
        else "acquisito"
        if acquired_office_documents
        else "da_verificare"
        if proceeding_present
        else "non_rilevato"
    )
    label = _display_text(" - ".join(part for part in (_text(getattr(fascicolo, "numero", "")), _text(getattr(fascicolo, "titolo", ""))) if part))
    return {
        "id": _text(getattr(fascicolo, "id", "")),
        "label": label,
        "numero": _text(getattr(fascicolo, "numero", "")),
        "titolo": _display_text(getattr(fascicolo, "titolo", "")),
        "assistitoNome": client_name,
        "assistitoCf": client_cf,
        "clienteId": _text(getattr(fascicolo, "id_cliente", "")),
        "controparte": counterpart_name,
        "controparteCf": counterpart_cf,
        "procedimento": {
            "presente": proceeding_present,
            "ufficio": _text(getattr(fascicolo, "tribunale", "")),
            "sezione": _text(getattr(fascicolo, "sezione", "")),
            "numeroRg": numero_rg,
            "annoRg": anno_rg,
            "giudice": _text(getattr(fascicolo, "giudice", "")),
            "tipoProcedimento": _text(getattr(fascicolo, "tipo_procedimento", "")),
        },
        "destinatari": _merge_notification_recipients(recipients),
        "documenti": documents,
        "portaleAcquisizioneHref": _portal_acquisition_href(fascicolo),
        "documentoUfficioMonitor": {
            "stato": monitor_status,
            "rilascioRilevato": bool(office_documents or pending_releases),
            "documentiAcquisiti": len(acquired_office_documents),
            "documentiDaAcquisire": len(pending_releases),
            "documentiDaNotificare": len([documento for documento in office_documents if documento["notificaRichiesta"]]),
            "documentiRilevati": pec_evidence[:20],
            "documentiRilasciati": pending_releases[:20],
            "messaggio": (
                "PEC dell'ufficio ricevuta: scarica dal portale solo il provvedimento indicato e collegalo ai Documenti e atti prima della relata."
                if pending_releases
                else "Documento comunicato dall'ufficio già presente nei Documenti e atti."
                if acquired_office_documents
                else "Nessuna PEC dell'ufficio richiede oggi una relata su provvedimento da notificare."
                if proceeding_present
                else "Nessun procedimento telematico da controllare."
            ),
        },
        "modelloSuggerito": "relata_pec_in_corso_di_causa" if proceeding_present else "relata_pec_base_l53",
    }


def _build_prefill_payload(*, get_clienti: Any = None, get_fascicoli: Any = None, get_soggetti: Any = None) -> dict[str, Any]:
    clienti_repo = _repo_from_getter(get_clienti)
    fascicoli_repo = _repo_from_getter(get_fascicoli)
    soggetti_repo = _repo_from_getter(get_soggetti)
    clienti_by_id = {}
    if clienti_repo is not None:
        clienti_recenti = _safe_call("clienti", lambda: clienti_repo.tutti(), [])
        clienti_by_id = {
            _text(getattr(cliente, "id", "")): cliente
            for cliente in clienti_recenti
        }
    tutti_fascicoli = []
    if fascicoli_repo is not None:
        tutti_fascicoli = _safe_call(
            "fascicoli_indice",
            lambda: fascicoli_repo.tutti(archiviati=True),
            [],
        )
    destinatari = []
    if soggetti_repo is not None:
        for soggetto in _safe_call("soggetti", lambda: soggetti_repo.tutti(), []):
            recipient = _recipient_from_subject(soggetto)
            if recipient["pec"] and is_plausible_pec_address(recipient["pec"]):
                destinatari.append(recipient)
    return {
        # L'indice iniziale resta leggero. Parti, documenti ed evidenze PEC vengono
        # caricati dalla rotta della singola pratica solo dopo la selezione.
        "pratiche": [],
        "indicePratiche": [
            item
            for item in (
                _fascicolo_index_option(
                    fascicolo,
                    cliente=clienti_by_id.get(_text(getattr(fascicolo, "id_cliente", ""))),
                )
                for fascicolo in tutti_fascicoli
            )
            if item["id"]
        ],
        "totalePratiche": len([fascicolo for fascicolo in tutti_fascicoli if _text(getattr(fascicolo, "id", ""))]),
        "clienti": [_cliente_option(cliente) for cliente in clienti_by_id.values()],
        "destinatari": destinatari,
        "note": [
            "I dati di pratica, assistito, procedimento e documenti sono proposti dai fascicoli IUSENTRA.",
            "La fonte PEC viene suggerita in base al ruolo e al tipo di soggetto; la verifica sul pubblico elenco resta da confermare.",
            "La data di verifica PEC non viene inventata: va registrata quando l'elenco pubblico viene controllato.",
        ],
    }


def build_react_notifiche_legali_practice_payload(
    id_fascicolo: str,
    *,
    get_clienti: Any = None,
    get_fascicoli: Any = None,
    get_soggetti: Any = None,
) -> dict[str, Any]:
    fascicoli_repo = _repo_from_getter(get_fascicoli)
    fascicolo = (
        _safe_call("fascicolo", lambda: fascicoli_repo.get(_text(id_fascicolo)), None)
        if fascicoli_repo is not None
        else None
    )
    if fascicolo is None:
        return _sanitize_ui_payload({"ok": False, "message": "Pratica non trovata.", "pratica": {}})

    clienti_repo = _repo_from_getter(get_clienti)
    cliente = None
    id_cliente = _text(getattr(fascicolo, "id_cliente", ""))
    if clienti_repo is not None and id_cliente:
        cliente = _safe_call("cliente", lambda: clienti_repo.get(id_cliente), None)
    pratica = _fascicolo_option(
        fascicolo,
        cliente=cliente,
        soggetti_repo=_repo_from_getter(get_soggetti),
        pec_emails=_office_pec_messages(),
    )
    return _sanitize_ui_payload({"ok": True, "pratica": pratica})


def build_react_notifiche_legali_practice_documents_payload(
    id_fascicolo: str,
    *,
    selected_document_ids: Iterable[str] | None = None,
    get_fascicoli: Any = None,
) -> dict[str, Any]:
    repo = _repo_from_getter(get_fascicoli)
    fascicolo = _safe_call("fascicolo", lambda: repo.get(_text(id_fascicolo)), None) if repo is not None else None
    if fascicolo is None:
        return _sanitize_ui_payload({"ok": False, "message": "Pratica non trovata.", "documenti": []})
    raw_documents = list(getattr(fascicolo, "documenti", []) or [])
    requested = {_text(item).strip().lower() for item in (selected_document_ids or []) if _text(item).strip()}
    if requested:
        def _matches_requested_document(documento: Any) -> bool:
            values = {
                _text(getattr(documento, "id", "")),
                _text(getattr(documento, "nome", "")),
                _text(getattr(documento, "titolo", "")),
                _text(getattr(documento, "nome_portale", "")),
                _text(getattr(documento, "nome_originale", "")),
                _text(getattr(documento, "id_documento_portale", "")),
                _text(getattr(documento, "id_portale", "")),
                _text(getattr(documento, "codice_portale", "")),
                _text(getattr(documento, "riferimento_portale", "")),
            }
            return any(value.strip().lower() in requested for value in values if value.strip())

        raw_documents = [documento for documento in raw_documents if _matches_requested_document(documento)]
    else:
        raw_documents = raw_documents[:40]
    documents = [
        _document_from_fascicolo(documento, resolve_content_label=True)
        for documento in raw_documents
    ]
    return _sanitize_ui_payload({
        "ok": True,
        "practiceId": _text(getattr(fascicolo, "id", "")) or _text(id_fascicolo),
        "documenti": documents,
    })


def build_react_notifiche_legali_payload(
    *,
    config_studio: Any = None,
    get_clienti: Any = None,
    get_fascicoli: Any = None,
    get_soggetti: Any = None,
    custom_templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cfg = _config_object(config_studio)
    studio = getattr(cfg, "studio", None)
    pec = getattr(cfg, "pec", None)

    avvocato_nome = _text(getattr(studio, "avvocato", ""))
    studio_nome = _text(getattr(studio, "nome", "")) or "IUSENTRA"
    studio_location = normalize_studio_location(
        indirizzo=getattr(studio, "indirizzo", ""),
        cap=getattr(studio, "cap", ""),
        city=getattr(studio, "city", ""),
        province=getattr(studio, "province", ""),
    )
    return _sanitize_ui_payload({
        "source": "configurazione_studio",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "contracts": {
            "separateLegalNotification": True,
            "clientCommunicationWithoutRelata": True,
            "depositProofWithOriginalReceipts": True,
            "parametricTemplateEngine": True,
            "officeDocumentPortalAcquisition": True,
            "officeDocumentPecEvidence": True,
            "recipientCaseMatrix": True,
        },
        "templateCatalogVersion": template_catalog_version(),
        "mandatorySubject": LEGAL_NOTIFICATION_SUBJECT,
        "defaults": {
            "studioNome": studio_nome,
            "avvocatoNome": avvocato_nome,
            "avvocatoCf": _text(getattr(studio, "codice_fiscale_avvocato", "")) or _text(getattr(studio, "cf", "")),
            "avvocatoForo": _text(getattr(studio, "ordine_avvocati", "")),
            "studioIndirizzo": studio_location["indirizzo"],
            "studioCap": studio_location["cap"],
            "studioCitta": studio_location["city"],
            "studioProvincia": studio_location["province"],
            "mittentePec": _text(getattr(pec, "indirizzo", "")),
            "fontePecMittente": "ReGIndE",
        },
        "registriPec": [
            {
                "value": key,
                "label": label if public_register_capability(key)["valid_for_notification"] else f"{label} (non certifica PEC)",
                "verificationMode": public_register_capability(key)["verification_mode"],
                "officialUrl": public_register_capability(key)["official_url"],
                "automatic": public_register_capability(key)["automatic"],
                "requiresPin": public_register_capability(key)["requires_pin"],
                "requiresUserConfirmation": public_register_capability(key)["requires_user_confirmation"],
                "validForNotification": public_register_capability(key)["valid_for_notification"],
                "actionLabel": public_register_capability(key)["action_label"],
            }
            for key, label in PUBLIC_PEC_REGISTERS.items()
        ],
        "matriceNotifica": notification_directive_matrix(),
        "ruoliDestinatario": [
            {"value": role, "label": _recipient_role_label(role)}
            for role in sorted(LEGAL_RECIPIENT_ROLES)
        ],
        "tipiNotificaUnep": [
            {"value": key, "label": label}
            for key, label in UNEP_NOTIFICATION_TYPES.items()
        ],
        "tipiRichiestaUnep": [
            {"value": key, "label": value["label"], "schema": value["schema"]}
            for key, value in UNEP_REQUEST_TYPES.items()
        ],
        "ufficiUnep": _unep_office_catalog(),
        "tipiNotificaNonPec": [
            {"value": key, "label": label}
            for key, label in NON_PEC_NOTIFICATION_TYPES.items()
        ],
        "originiDocumento": [
            {"value": key, "label": label, "needsAttestazione": key in {"copia_fascicolo_informatico", "comunicazione_cancelleria", "scansione_analogico"}}
            for key, label in DOCUMENT_ORIGIN_LABELS.items()
        ],
        "modelliRelata": [
            _template_option(template)
            for template in (
                list_notification_templates(kind="relata")
                + [normalise_custom_template(item) for item in (custom_templates or [])]
            )
        ],
        "modelliControllo": [
            _template_option(template)
            for template in list_notification_templates()
            if template.get("kind") in {"control_document", "audit_document", "workflow"}
        ],
        "modelliComunicazioneCliente": [
            _client_template_option(template)
            for template in list_client_communication_templates()
        ],
        "clientCommunicationTemplateVersion": client_communication_templates_version(),
        "precompilazione": _build_prefill_payload(
            get_clienti=get_clienti,
            get_fascicoli=get_fascicoli,
            get_soggetti=get_soggetti,
        ),
        "campiDisponibili": available_template_fields(),
        "automazioneGuidata": legal_notification_automation_payload(),
        "portaleServizi": {
            "defaultPortal": "pst",
            "label": "Portale Servizi Telematici",
            "acquisizioneHref": "/portali/pst/acquisizione?focus=documenti",
            "assistantStartApi": "/api/portali/pst/assistant/start",
            "downloadWatchApi": "/api/portali/pst/assistant/{session_id}/watch-downloads",
            "collectApi": "/api/portali/pst/assistant/{session_id}/collect",
            "localSignerRequired": True,
        },
        "azioni": {
            "notifica": "/api/v1/ui/notifiche-legali/notifica",
            "anteprimaRelata": "/api/v1/ui/notifiche-legali/anteprima-relata",
            "attestazioneConformita": "/api/v1/ui/notifiche-legali/attestazione-conformita",
            "relataPdf": "/api/v1/ui/notifiche-legali/relata-pdf",
            "relataFirmata": "/api/v1/ui/notifiche-legali/relata-firmata",
            "bozzaRelata": "/api/v1/ui/notifiche-legali/bozze-relata",
            "comunicazioneCliente": "/api/v1/ui/notifiche-legali/comunicazione-cliente",
            "provaDeposito": "/api/v1/ui/notifiche-legali/prova-deposito",
            "verificaPecConsultata": "/api/v1/ui/notifiche-legali/verifica-pec-consultata",
            "unep": "/api/v1/ui/notifiche-legali/unep",
            "nonPec": "/api/v1/ui/notifiche-legali/non-pec",
            "areaWebPst": "/api/v1/ui/notifiche-legali/area-web-pst",
            "pecCompose": "/email/scrivi?tipo=notifica_l53",
            "clientCompose": "/email-ordinaria/scrivi?tipo=comunicazione_cliente",
            "firmaDigitale": "/guida/firma-digitale",
            "fascicoli": "/fascicoli",
            "depositoChecklist": "/deposito/checklist",
        },
        "fontiOperative": [
            "Portale Servizi Telematici: notificazioni via PEC degli avvocati, L. 53/1994.",
            "Art. 16-ter D.L. 179/2012: pubblici elenchi rilevanti per notificazioni e comunicazioni.",
            "Controllo ricevute e documenti collegati al fascicolo prima dell'invio.",
        ],
    })


def _recipient_role_label(value: str) -> str:
    return {
        "controparte": "Controparte",
        "difensore": "Difensore avversario",
        "impresa": "Impresa",
        "pa": "Pubblica amministrazione",
        "professionista": "Professionista",
        "terzo": "Terzo destinatario",
    }.get(value, value.replace("_", " ").title())


def _template_option(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": _text(template.get("id")),
        "code": _text(template.get("code")),
        "label": _text(template.get("label")),
        "description": _text(template.get("description")),
        "requiresProceeding": bool(template.get("requires_proceeding")),
        "privacyDescription": bool(template.get("privacy_description")),
        "custom": bool(template.get("custom")),
        "previewText": template_preview_text(template),
        "fields": [
            {
                "name": _text(field.get("name")),
                "label": _text(field.get("label")),
            }
            for field in (template.get("fields") or [])
            if isinstance(field, dict) and _text(field.get("name"))
        ],
    }


def _client_template_option(template: dict[str, Any]) -> dict[str, Any]:
    body = "\n".join(str(line) for line in (template.get("body_lines") or []))
    return {
        "value": _text(template.get("id")),
        "label": _text(template.get("label")),
        "description": _text(template.get("description")),
        "subjectPreview": _text(template.get("subject")),
        "bodyPreview": body.strip(),
    }
