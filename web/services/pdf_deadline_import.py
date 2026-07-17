"""Importazione controllata di scadenze dai PDF dei fascicoli."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from time import monotonic
from typing import Any, Iterable

from pct.document_intelligence.extraction import extract_text_from_document
from pct.scadenziario import TipoTermine


SOURCE_MARKER_PREFIX = "pdf-deadline:"
MAX_PREVIEW_PAGES_PER_DOCUMENT = 8
MAX_PREVIEW_PDF_BYTES = 15 * 1024 * 1024
MAX_LEGACY_EXTRACTION_BYTES = 2 * 1024 * 1024
MAX_PREVIEW_SECONDS = 8.0
URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)
RG_RE = re.compile(r"\b(?:N\.?\s*R\.?\s*G\.?|R\.?\s*G\.?|RG)\s*(?:n\.?)?\s*:?\s*(\d{1,8}\s*/\s*\d{4}(?:/[A-Z]+)?)\b", re.IGNORECASE)
TIME_RE = re.compile(r"\b(?:alle\s+)?(?:ore|h\.?)?\s*(?P<hour>[0-2]?\d)[:.](?P<minute>[0-5]\d)\b", re.IGNORECASE)
NUMERIC_DATE_RE = re.compile(
    r"\b(?P<day>[0-3]?\d)[\/\-.](?P<month>[01]?\d)[\/\-.](?P<year>\d{2}|\d{4})\b"
)
ISO_DATE_RE = re.compile(r"\b(?P<year>20\d{2}|19\d{2})-(?P<month>[01]\d)-(?P<day>[0-3]\d)\b")
TEXT_DATE_RE = re.compile(
    r"\b(?P<day>[0-3]?\d)\s+(?:di\s+)?(?P<month>"
    r"gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
    r")\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)

MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

TYPE_RULES: tuple[tuple[TipoTermine, tuple[str, ...], str, float], ...] = (
    (TipoTermine.UDIENZA, ("udienza", "comparizione", "comparire", "trattazione", "rinvio"), "Udienza", 0.9),
    (TipoTermine.DEPOSITO_MEMORIA, ("memoria", "memorie", "note scritte", "conclusionale", "replica"), "Deposito memoria", 0.86),
    (TipoTermine.DEPOSITO_ATTO, ("deposito", "depositare", "produzione", "atto"), "Deposito atto", 0.82),
    (TipoTermine.NOTIFICA, ("notifica", "notificare", "notificato", "relata"), "Notifica", 0.82),
    (TipoTermine.IMPUGNAZIONE, ("impugnazione", "appello", "reclamo", "ricorso per cassazione"), "Impugnazione", 0.84),
    (TipoTermine.PAGAMENTO, ("pagamento", "pagare", "contributo unificato", "spese"), "Pagamento", 0.76),
    (TipoTermine.PRESCRIZIONE, ("prescrizione", "prescrive"), "Prescrizione", 0.82),
    (TipoTermine.DECADENZA, ("decadenza", "decade", "a pena di decadenza"), "Decadenza", 0.86),
    (TipoTermine.ADEMPIMENTO, ("adempimento", "adempiere", "entro", "termine", "scadenza"), "Adempimento", 0.68),
)


@dataclass(slots=True)
class PdfDeadlineCandidate:
    id: str
    fascicolo_id: str
    fascicolo_label: str
    matter_label: str
    client_label: str
    document_id: str
    document_name: str
    document_href: str
    page: int
    due_date: str
    title: str
    description: str
    context: str
    type: str
    type_label: str
    confidence: float
    urls: list[str] = field(default_factory=list)
    event_time: str = ""
    event_datetime: str = ""
    remote_hearing_url: str = ""
    remote_hearing_source: str = ""
    remote_hearing_verified: bool = False
    semantic_key: str = ""
    duplicate: bool = False
    existing_deadline_id: str = ""
    selected: bool = True
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PdfDeadlinePreview:
    candidates: list[PdfDeadlineCandidate]
    scanned_fascicoli: int
    scanned_documents: int
    skipped_documents: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "summary": {
                "scannedFascicoli": self.scanned_fascicoli,
                "scannedDocuments": self.scanned_documents,
                "skippedDocuments": self.skipped_documents,
                "newCandidates": sum(1 for item in self.candidates if not item.duplicate),
                "duplicates": sum(1 for item in self.candidates if item.duplicate),
                "warnings": len(self.warnings) + sum(len(item.warnings) for item in self.candidates),
            },
            "warnings": list(self.warnings),
        }


def preview_pdf_deadlines(
    *,
    gestione_fascicoli: Any,
    gestione_scadenziario: Any,
    id_fascicolo: str = "",
    max_documents: int = 0,
) -> PdfDeadlinePreview:
    fascicoli = _fascicoli_da_scansionare(gestione_fascicoli, id_fascicolo)
    existing_markers, existing_semantic = _existing_import_markers(gestione_scadenziario)
    candidates: list[PdfDeadlineCandidate] = []
    warnings: list[str] = []
    scanned_documents = 0
    skipped_documents = 0
    started_at = monotonic()

    for fascicolo in fascicoli:
        for documento in list(getattr(fascicolo, "documenti", []) or []):
            if monotonic() - started_at >= MAX_PREVIEW_SECONDS:
                warnings.append("Scansione fermata per mantenere reattiva la pagina.")
                return PdfDeadlinePreview(candidates, len(fascicoli), scanned_documents, skipped_documents, warnings)
            if max_documents and scanned_documents >= max_documents:
                warnings.append(f"Scansione fermata a {max_documents} documenti per mantenere la pagina reattiva.")
                return PdfDeadlinePreview(candidates, len(fascicoli), scanned_documents, skipped_documents, warnings)
            path = _document_path(gestione_fascicoli, fascicolo, documento)
            if not _is_pdf_document(documento, path):
                skipped_documents += 1
                continue
            scanned_documents += 1
            candidates.extend(
                _candidates_from_document(
                    fascicolo=fascicolo,
                    documento=documento,
                    path=path,
                    existing_markers=existing_markers,
                    existing_semantic=existing_semantic,
                )
            )
    candidates.sort(key=lambda item: (item.duplicate, item.due_date, item.fascicolo_label, item.document_name))
    return PdfDeadlinePreview(candidates, len(fascicoli), scanned_documents, skipped_documents, warnings)


def import_pdf_deadlines(
    *,
    gestione_fascicoli: Any,
    gestione_scadenziario: Any,
    gestione_agenda: Any = None,
    selected_ids: Iterable[str],
    id_fascicolo: str = "",
    max_documents: int = 0,
    user_id: str = "",
) -> dict[str, Any]:
    selected = {str(item or "").strip() for item in selected_ids if str(item or "").strip()}
    if not selected:
        return {"ok": False, "message": "Seleziona almeno una scadenza da importare.", "created": 0, "skipped": 0}
    preview = preview_pdf_deadlines(
        gestione_fascicoli=gestione_fascicoli,
        gestione_scadenziario=gestione_scadenziario,
        id_fascicolo=id_fascicolo,
        max_documents=max_documents,
    )
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    skipped = 0
    for candidate in preview.candidates:
        if candidate.id not in selected:
            continue
        if candidate.duplicate:
            enriched = _enrich_existing_deadline_from_candidate(
                gestione_scadenziario,
                gestione_agenda,
                candidate,
                user_id=user_id,
            )
            if enriched:
                updated.append(enriched)
            else:
                skipped += 1
            continue
        if _semantic_deadline_exists(gestione_scadenziario, candidate):
            skipped += 1
            continue
        scadenza = _create_deadline_from_candidate(gestione_scadenziario, candidate, user_id=user_id)
        agenda_result = _sync_candidate_to_agenda(gestione_agenda, candidate, scadenza)
        _link_agenda_to_deadline(gestione_scadenziario, scadenza, agenda_result)
        created.append(
            {
                "id": scadenza.id,
                "title": scadenza.titolo,
                "href": f"/scadenziario/{scadenza.id}",
                "agenda": agenda_result,
            }
        )
    return {
        "ok": True,
        "message": _import_message(len(created), skipped, len(updated)),
        "created": len(created),
        "updated": len(updated),
        "skipped": skipped,
        "items": created,
        "updatedItems": updated,
    }


def _fascicoli_da_scansionare(gestione_fascicoli: Any, id_fascicolo: str) -> list[Any]:
    if id_fascicolo:
        fascicolo = gestione_fascicoli.get(id_fascicolo)
        return [fascicolo] if fascicolo else []
    try:
        return list(gestione_fascicoli.tutti(archiviati=False))
    except TypeError:
        return list(gestione_fascicoli.tutti())


def _document_path(gestione_fascicoli: Any, fascicolo: Any, documento: Any) -> Path:
    try:
        return Path(gestione_fascicoli.percorso_documento_lettura(fascicolo.id, documento.id))
    except Exception:
        base = Path(getattr(gestione_fascicoli, "documents_dir", ""))
        return base / str(getattr(documento, "percorso", "") or "")


def _is_pdf_document(documento: Any, path: Path) -> bool:
    name = " ".join(
        str(value or "").lower()
        for value in (
            getattr(documento, "nome", ""),
            getattr(documento, "nome_originale", ""),
            getattr(documento, "nome_portale", ""),
            getattr(documento, "percorso", ""),
            path.name,
        )
    )
    return ".pdf" in name and path.exists() and path.is_file()


def _candidates_from_document(
    *,
    fascicolo: Any,
    documento: Any,
    path: Path,
    existing_markers: dict[str, str],
    existing_semantic: dict[str, str],
) -> list[PdfDeadlineCandidate]:
    try:
        if path.stat().st_size > MAX_PREVIEW_PDF_BYTES:
            return []
    except OSError:
        return []
    content = path.read_bytes()
    filename = str(getattr(documento, "nome", "") or path.name)
    pages, extraction_warnings = _quick_pdf_text_pages(content, filename)
    if not pages:
        return []
    page_links = _extract_pdf_links_by_page(content)
    rows: list[PdfDeadlineCandidate] = []
    for page_number, text in pages:
        links = _unique([*page_links.get(page_number, []), *URL_RE.findall(text)])
        rg_label = _extract_rg_label(text) or _fascicolo_rg_label(fascicolo)
        for match, due_date in _date_matches(text):
            context = _context_around(text, match.start(), match.end())
            kind, label, confidence = _classify_context(context)
            if confidence < 0.64:
                continue
            urls = _links_for_context(context, links)
            remote_url = _first_remote_hearing_url(urls, context)
            event_time = _time_near_match(text, match.start(), match.end()) if kind == TipoTermine.UDIENZA else ""
            if kind == TipoTermine.UDIENZA and not _is_actionable_hearing_context(context, event_time):
                continue
            event_datetime = f"{due_date}T{event_time}:00" if event_time else ""
            semantic_key = _semantic_signature(
                fascicolo_id=str(getattr(fascicolo, "id", "") or ""),
                rg_label=rg_label,
                due_date=due_date,
                kind=kind.value,
                event_time=event_time,
                remote_url=remote_url,
            )
            signature = _signature(fascicolo, documento, due_date, kind.value, context)
            existing_id = existing_markers.get(signature, "") or existing_semantic.get(semantic_key, "")
            title = _candidate_title(label, due_date, from_document=True, remote=bool(remote_url))
            description = _candidate_description(filename, page_number, context, rg_label, remote_url)
            rows.append(
                PdfDeadlineCandidate(
                    id=signature,
                    fascicolo_id=str(getattr(fascicolo, "id", "") or ""),
                    fascicolo_label=_fascicolo_label(fascicolo),
                    matter_label=_fascicolo_matter_label(fascicolo, rg_label),
                    client_label=_fascicolo_client_label(fascicolo),
                    document_id=str(getattr(documento, "id", "") or ""),
                    document_name=filename,
                    document_href=f"/fascicoli/{getattr(fascicolo, 'id', '')}/documenti/{getattr(documento, 'id', '')}/visualizza",
                    page=page_number,
                    due_date=due_date,
                    title=title,
                    description=description,
                    context=context,
                    type=kind.value,
                    type_label=label,
                    confidence=round(confidence, 2),
                    urls=urls[:5],
                    event_time=event_time,
                    event_datetime=event_datetime,
                    remote_hearing_url=remote_url,
                    remote_hearing_source=filename if remote_url else "",
                    remote_hearing_verified=bool(remote_url and remote_url in page_links.get(page_number, [])),
                    semantic_key=semantic_key,
                    duplicate=bool(existing_id),
                    existing_deadline_id=existing_id,
                    selected=not bool(existing_id) and confidence >= 0.68,
                    warnings=list(extraction_warnings[:2]),
                )
            )
    return _deduplicate_candidates(rows)


def _quick_pdf_text_pages(content: bytes, filename: str) -> tuple[list[tuple[int, str]], list[str]]:
    if len(content) > MAX_PREVIEW_PDF_BYTES:
        return [], ["PDF troppo grande per l’anteprima rapida: aprilo dal fascicolo o indicizzalo prima."]
    try:
        import pdfplumber  # type: ignore

        pages: list[tuple[int, str]] = []
        page_count = 0
        with pdfplumber.open(BytesIO(content)) as pdf:
            page_count = len(pdf.pages)
            for index, page in enumerate(pdf.pages[:MAX_PREVIEW_PAGES_PER_DOCUMENT], start=1):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                if text.strip():
                    pages.append((index, text))
        warnings: list[str] = []
        if page_count > MAX_PREVIEW_PAGES_PER_DOCUMENT:
            warnings.append(
                f"Anteprima limitata alle prime {MAX_PREVIEW_PAGES_PER_DOCUMENT} pagine per mantenere reattiva la pagina."
            )
        if pages:
            return pages, warnings
        return [], ["PDF senza testo selezionabile: serve indicizzazione OCR prima dell’estrazione automatica."]
    except Exception:
        return _legacy_pdf_text_pages(content, filename)


def _legacy_pdf_text_pages(content: bytes, filename: str) -> tuple[list[tuple[int, str]], list[str]]:
    if len(content) > MAX_LEGACY_EXTRACTION_BYTES:
        return [], ["PDF non letto in anteprima rapida: usa indicizzazione documento prima dell’estrazione automatica."]
    try:
        result = extract_text_from_document(content, filename, "pdf")
    except Exception:
        return [], ["PDF non letto in anteprima rapida."]
    if not result.ok or not result.text.strip():
        return [], list(result.warnings[:2])
    pages: list[tuple[int, str]] = []
    for page in (result.pages or [])[:MAX_PREVIEW_PAGES_PER_DOCUMENT]:
        page_number = int(getattr(page, "page_number", 0) or 0)
        text = str(getattr(page, "text", "") or "")
        if text.strip():
            pages.append((page_number, text))
    return pages, list(result.warnings[:2])


def _date_matches(text: str) -> list[tuple[re.Match[str], str]]:
    rows: list[tuple[re.Match[str], str]] = []
    for regex in (NUMERIC_DATE_RE, ISO_DATE_RE, TEXT_DATE_RE):
        for match in regex.finditer(text):
            parsed = _parse_match_date(match)
            if parsed:
                rows.append((match, parsed.isoformat()))
    rows.sort(key=lambda item: item[0].start())
    return rows


def _parse_match_date(match: re.Match[str]) -> date | None:
    try:
        day = int(match.group("day"))
        year = int(match.group("year"))
        if year < 100:
            year += 2000 if year < 70 else 1900
        month_raw = match.group("month")
        month = MONTHS.get(month_raw.lower(), 0) if not month_raw.isdigit() else int(month_raw)
        parsed = date(year, month, day)
    except Exception:
        return None
    today = date.today()
    if parsed.year < today.year - 2 or parsed.year > today.year + 10:
        return None
    return parsed


def _context_around(text: str, start: int, end: int, *, window: int = 210) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    sentence_left = max(text.rfind("\n", 0, start), text.rfind(".", 0, start), text.rfind(";", 0, start))
    sentence_right_candidates = [
        position
        for position in (text.find("\n", end), text.find(".", end), text.find(";", end))
        if position != -1
    ]
    if sentence_left >= left:
        left = sentence_left + 1
    if sentence_right_candidates:
        sentence_right = min(sentence_right_candidates)
        if sentence_right <= right:
            right = sentence_right + 1
    context = re.sub(r"\s+", " ", text[left:right]).strip(" .,:;\n\t")
    if len(context) > 420:
        context = context[:417].rstrip() + "..."
    return context


def _classify_context(context: str) -> tuple[TipoTermine, str, float]:
    normalized = _normalise(context)
    for kind, keywords, label, confidence in TYPE_RULES:
        if any(keyword in normalized for keyword in keywords):
            if "perentorio" in normalized or "a pena di decadenza" in normalized:
                confidence = min(0.98, confidence + 0.06)
            return kind, label, confidence
    return TipoTermine.ALTRO, "Scadenza", 0.35


def _links_for_context(context: str, page_links: list[str]) -> list[str]:
    context_links = URL_RE.findall(context)
    return _unique([*context_links, *page_links])


def _extract_rg_label(text: str) -> str:
    match = RG_RE.search(str(text or ""))
    if not match:
        return ""
    return "RG " + re.sub(r"\s+", "", match.group(1).upper())


def _fascicolo_rg_label(fascicolo: Any) -> str:
    rg = str(getattr(fascicolo, "rg_completo", "") or getattr(fascicolo, "numero_rg", "") or "").strip()
    if not rg:
        return ""
    return rg if rg.upper().startswith("RG") else f"RG {rg}"


def _fascicolo_matter_label(fascicolo: Any, rg_label: str = "") -> str:
    rg = rg_label or _fascicolo_rg_label(fascicolo)
    title = str(getattr(fascicolo, "oggetto", "") or getattr(fascicolo, "titolo", "") or "").strip()
    return " - ".join(part for part in (rg, title) if part) or _fascicolo_label(fascicolo)


def _fascicolo_client_label(fascicolo: Any) -> str:
    return str(getattr(fascicolo, "nome_cliente", "") or getattr(fascicolo, "cliente", "") or "").strip()


def _time_label_from_text(value: str) -> str:
    match = TIME_RE.search(str(value or ""))
    if not match:
        return ""
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if hour > 23:
        return ""
    return f"{hour:02d}:{minute:02d}"


def _time_near_match(text: str, start: int, end: int) -> str:
    source = str(text or "")
    window = source[max(0, start - 120) : min(len(source), end + 190)]
    return _time_label_from_text(window)


def _first_remote_hearing_url(urls: Iterable[str], context: str) -> str:
    try:
        from pct.pec_pipeline import _is_remote_hearing_url
    except Exception:
        _is_remote_hearing_url = None  # type: ignore[assignment]
    for url in urls:
        value = str(url or "").strip()
        if not value:
            continue
        if callable(_is_remote_hearing_url):
            try:
                accepted, _reason = _is_remote_hearing_url(value, context=context)
            except Exception:
                accepted = False
            if accepted:
                return value
        elif any(host in value.lower() for host in ("teams.microsoft", "zoom.us", "webex", "meet.google")):
            return value
    return ""


def _is_actionable_hearing_context(context: str, event_time: str = "") -> bool:
    normalized = _normalise(context)
    if event_time:
        return True
    if "cronol" in normalized or "firmato" in normalized:
        return False
    return bool(
        re.search(
            r"\b(?:fissa|fissata|fissato|rinvia|rinviata|rinviato|differisce|differita|differito|conferma|confermata|confermato)\b"
            r".{0,120}\budienza\b"
            r"|\budienza\b.{0,120}\b(?:fissata|fissato|rinviata|rinviato|differita|differito|confermata|confermato)\b"
            r"|\budienza\b.{0,120}\b(?:in data|il giorno|alle ore|ore)\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def _candidate_title(label: str, due_date: str, *, from_document: bool, remote: bool) -> str:
    if label.lower() == "udienza":
        if remote:
            return f"Udienza audiovisiva da documento notificato - {_italian_date(due_date)}"
        return f"Udienza da documento notificato - {_italian_date(due_date)}"
    if from_document:
        return f"{label} da documento notificato - {_italian_date(due_date)}"
    return f"{label} - {_italian_date(due_date)}"


def _candidate_description(filename: str, page_number: int, context: str, rg_label: str, remote_url: str) -> str:
    parts = [f"Documento notificato nel fascicolo: {filename}, pagina {page_number}."]
    if rg_label:
        parts.append(f"Fascicolo {rg_label}.")
    if remote_url:
        parts.append("Collegamento audiovisivo rilevato nel documento.")
    parts.append(_short_context(context))
    return " ".join(part for part in parts if part)


def _short_context(context: str, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(context or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _semantic_signature(
    *,
    fascicolo_id: str,
    rg_label: str,
    due_date: str,
    kind: str,
    event_time: str,
    remote_url: str = "",
) -> str:
    raw = "|".join(
        [
            str(fascicolo_id or "").strip().lower(),
            _normalise(rg_label),
            str(due_date or "").strip()[:10],
            str(kind or "").strip().upper(),
            str(event_time or "").strip()[:5],
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _extract_pdf_links_by_page(content: bytes) -> dict[int, list[str]]:
    links: dict[int, list[str]] = {}
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(BytesIO(content))
        for index, page in enumerate(reader.pages, start=1):
            page_links: list[str] = []
            annotations = page.get("/Annots") or []
            for annotation in annotations:
                try:
                    obj = annotation.get_object()
                    action = obj.get("/A") or {}
                    uri = action.get("/URI")
                    if uri:
                        page_links.append(str(uri))
                except Exception:
                    continue
            if page_links:
                links[index] = _unique(page_links)
    except Exception:
        return {}
    return links


def _existing_import_markers(gestione_scadenziario: Any) -> tuple[dict[str, str], dict[str, str]]:
    rows: dict[str, str] = {}
    semantic_rows: dict[str, str] = {}
    try:
        scadenze = list(gestione_scadenziario.tutte(solo_aperte=False))
    except Exception:
        scadenze = []
    for scadenza in scadenze:
        scadenza_id = str(getattr(scadenza, "id", "") or "")
        haystack = "\n".join(
            str(getattr(scadenza, field_name, "") or "")
            for field_name in ("note", "descrizione", "trace_json")
        )
        for match in re.finditer(rf"{re.escape(SOURCE_MARKER_PREFIX)}([0-9a-f]+)", haystack):
            rows[match.group(1)] = scadenza_id
        for match in re.finditer(r"pdf-semantic:([0-9a-f]+)", haystack, flags=re.I):
            semantic_rows[match.group(1)] = scadenza_id
        semantic = _semantic_from_scadenza(scadenza)
        if semantic and scadenza_id:
            semantic_rows.setdefault(semantic, scadenza_id)
    return rows, semantic_rows


def _semantic_from_scadenza(scadenza: Any) -> str:
    due_date = str(getattr(scadenza, "data_scadenza", "") or getattr(scadenza, "legal_due_at", "") or "").strip()[:10]
    if not due_date:
        return ""
    kind = str(getattr(getattr(scadenza, "tipo", ""), "value", getattr(scadenza, "tipo", "")) or "").strip()
    if not kind:
        return ""
    source_time = (
        _time_label_from_text(str(getattr(scadenza, "source_event_at", "") or ""))
        or _time_label_from_text(str(getattr(scadenza, "remote_hearing_time", "") or ""))
    )
    note = str(getattr(scadenza, "note", "") or "")
    remote_match = re.search(r"Link udienza audiovisiva:\s*(https?://\S+|www\.\S+)", note, flags=re.I)
    remote_url = str(getattr(scadenza, "remote_hearing_url", "") or (remote_match.group(1) if remote_match else "") or "").strip()
    rg_label = _extract_rg_label(
        "\n".join(
            str(getattr(scadenza, field_name, "") or "")
            for field_name in ("titolo", "descrizione", "note", "id_fascicolo")
        )
    )
    return _semantic_signature(
        fascicolo_id=str(getattr(scadenza, "id_fascicolo", "") or ""),
        rg_label=rg_label,
        due_date=due_date,
        kind=kind,
        event_time=source_time,
        remote_url=remote_url,
    )


def _create_deadline_from_candidate(gestione_scadenziario: Any, candidate: PdfDeadlineCandidate, *, user_id: str = "") -> Any:
    source_marker = f"{SOURCE_MARKER_PREFIX}{candidate.id}"
    semantic_marker = f"pdf-semantic:{candidate.semantic_key}" if candidate.semantic_key else ""
    remote_lines = _remote_hearing_note_lines_from_candidate(candidate)
    links_text = "\n".join(f"Link PDF: {url}" for url in candidate.urls if url != candidate.remote_hearing_url)
    trace = [
        f"Scadenza estratta da documento notificato: {candidate.document_name}, pagina {candidate.page}.",
        f"Fascicolo: {candidate.fascicolo_label}.",
        f"Documento: {candidate.document_href}.",
        source_marker,
    ]
    if semantic_marker:
        trace.append(semantic_marker)
    trace.extend(f"Link trovato nel PDF: {url}" for url in candidate.urls)
    note = "\n".join(
        part
        for part in (
            f"Documento notificato nel fascicolo: {candidate.document_name}, pagina {candidate.page}.",
            f"Apri documento: {candidate.document_href}",
            *remote_lines,
            links_text,
            source_marker,
            semantic_marker,
        )
        if part
    )
    return gestione_scadenziario.nuova(
        titolo=candidate.title,
        tipo=TipoTermine(candidate.type),
        data_scadenza=candidate.due_date,
        id_fascicolo=candidate.fascicolo_id,
        descrizione=candidate.description,
        data_decorrenza=candidate.event_datetime or candidate.due_date,
        note=note,
        perentorio=_is_peremptory(candidate.context),
        source_event_type="documento_fascicolo",
        source_event_at=candidate.event_datetime or candidate.due_date,
        trace_json=json.dumps(trace, ensure_ascii=False),
        id_utente_responsabile=user_id,
        giorni_preavviso=[30, 15, 7, 3, 1, 0],
        remote_hearing_detected=bool(candidate.remote_hearing_url),
        remote_hearing_mode="audiovisiva" if candidate.remote_hearing_url else "",
        remote_hearing_url=candidate.remote_hearing_url,
        remote_hearing_source=candidate.remote_hearing_source,
        remote_hearing_verified=bool(candidate.remote_hearing_verified),
        remote_hearing_integrity="exact" if candidate.remote_hearing_verified else "",
        remote_hearing_time=f"{_italian_date(candidate.due_date)} ore {candidate.event_time}" if candidate.event_time else "",
        remote_hearing_pdf_required=False,
    )


def _remote_hearing_note_lines_from_candidate(candidate: PdfDeadlineCandidate) -> list[str]:
    if not candidate.remote_hearing_url:
        return []
    lines = ["Udienza da remoto: audiovisiva"]
    if candidate.event_time:
        lines.append(f"Orario collegamento: {_italian_date(candidate.due_date)} ore {candidate.event_time}")
    lines.append(f"Link udienza audiovisiva: {candidate.remote_hearing_url}")
    if candidate.remote_hearing_source:
        lines.append(f"Fonte link udienza: {candidate.remote_hearing_source}")
    lines.append(
        "Verifica link udienza: identico alla fonte letta."
        if candidate.remote_hearing_verified
        else "Verifica link udienza: link da controllare sul documento notificato."
    )
    return lines


def _semantic_deadline_exists(gestione_scadenziario: Any, candidate: PdfDeadlineCandidate) -> bool:
    if not candidate.semantic_key:
        return False
    _markers, semantic = _existing_import_markers(gestione_scadenziario)
    return candidate.semantic_key in semantic


def _enrich_existing_deadline_from_candidate(
    gestione_scadenziario: Any,
    gestione_agenda: Any,
    candidate: PdfDeadlineCandidate,
    *,
    user_id: str = "",
) -> dict[str, Any] | None:
    deadline_id = str(candidate.existing_deadline_id or "").strip()
    if not deadline_id:
        return None
    getter = getattr(gestione_scadenziario, "get", None)
    if not callable(getter):
        return None
    try:
        existing = getter(deadline_id)
    except Exception:
        existing = None
    if not existing:
        return None
    updates: dict[str, Any] = {}
    note = str(getattr(existing, "note", "") or "")
    add_lines: list[str] = []
    source_marker = f"{SOURCE_MARKER_PREFIX}{candidate.id}"
    semantic_marker = f"pdf-semantic:{candidate.semantic_key}" if candidate.semantic_key else ""
    if source_marker not in note:
        add_lines.append(source_marker)
    if semantic_marker and semantic_marker not in note:
        add_lines.append(semantic_marker)
    if candidate.remote_hearing_url:
        if not str(getattr(existing, "remote_hearing_url", "") or "").strip():
            updates.update(
                {
                    "remote_hearing_detected": True,
                    "remote_hearing_mode": "audiovisiva",
                    "remote_hearing_url": candidate.remote_hearing_url,
                    "remote_hearing_source": candidate.remote_hearing_source,
                    "remote_hearing_verified": bool(candidate.remote_hearing_verified),
                    "remote_hearing_integrity": "exact" if candidate.remote_hearing_verified else "",
                    "remote_hearing_time": f"{_italian_date(candidate.due_date)} ore {candidate.event_time}" if candidate.event_time else "",
                    "remote_hearing_pdf_required": False,
                }
            )
        for line in _remote_hearing_note_lines_from_candidate(candidate):
            if line not in note:
                add_lines.append(line)
    if candidate.event_datetime and not _time_label_from_text(str(getattr(existing, "source_event_at", "") or "")):
        updates["source_event_at"] = candidate.event_datetime
    if add_lines:
        updates["note"] = "\n".join(part for part in (note, *add_lines) if str(part or "").strip())
    if updates:
        try:
            existing = gestione_scadenziario.aggiorna(deadline_id, **updates)
        except Exception:
            pass
    agenda_result = _sync_candidate_to_agenda(gestione_agenda, candidate, existing)
    _link_agenda_to_deadline(gestione_scadenziario, existing, agenda_result)
    if updates or agenda_result.get("ok"):
        return {
            "id": deadline_id,
            "title": str(getattr(existing, "titolo", "") or candidate.title),
            "href": f"/scadenziario/{deadline_id}",
            "agenda": agenda_result,
            "source": "documento_notificato",
        }
    return None


def _sync_candidate_to_agenda(gestione_agenda: Any, candidate: PdfDeadlineCandidate, scadenza: Any) -> dict[str, Any]:
    if not gestione_agenda:
        return {"ok": False, "agendaSkipped": True, "message": "Agenda non configurata."}
    if candidate.type != TipoTermine.UDIENZA.value or not candidate.event_datetime:
        return {"ok": False, "agendaSkipped": True, "message": "Agenda non aggiornata: manca un orario certo."}
    duplicate = _find_existing_agenda_event(gestione_agenda, candidate)
    if duplicate:
        return {
            "ok": True,
            "agendaId": str(getattr(duplicate, "id", "") or ""),
            "agendaHref": f"/agenda/{getattr(duplicate, 'id', '')}" if getattr(duplicate, "id", "") else "/agenda",
            "outcome": "already_exists",
            "message": "Evento agenda equivalente già presente.",
        }
    try:
        from pct.agenda import TipoAppuntamento
        from pct.ical_import import EventoImportato

        event = EventoImportato(
            uid=f"DOCUMENTO_FASCICOLO:{candidate.semantic_key}:agenda",
            titolo=candidate.title[:120],
            data_ora=candidate.event_datetime,
            durata_minuti=60,
            tutto_giorno=False,
            luogo="Udienza da remoto" if candidate.remote_hearing_url else "",
            descrizione=_agenda_description_from_candidate(candidate, scadenza),
            stato_ical="CONFIRMED",
            organizzatore="Documento notificato nel fascicolo",
        )
        report = gestione_agenda.upsert_da_evento_importato(
            event,
            provider="documento_fascicolo",
            source_url=candidate.document_href,
            profile_id="documento_notificato",
            default_tipo=TipoAppuntamento.UDIENZA,
            reminder_minuti=1440,
            allow_overlap=True,
        )
        appuntamento = report.get("appuntamento")
        agenda_id = str(getattr(appuntamento, "id", "") or "")
        if agenda_id:
            try:
                appuntamento = gestione_agenda.modifica(
                    agenda_id,
                    procedimento=candidate.matter_label,
                    cliente=candidate.client_label,
                )
            except Exception:
                pass
        return {
            "ok": bool(agenda_id),
            "agendaId": agenda_id,
            "agendaHref": f"/agenda/{agenda_id}" if agenda_id else "/agenda",
            "outcome": str(report.get("outcome") or ""),
            "message": "Evento agenda aggiornato dal documento notificato." if agenda_id else str(report.get("message") or ""),
        }
    except Exception as exc:
        return {"ok": False, "agendaSkipped": True, "message": f"Agenda non aggiornata: {exc}"}


def _find_existing_agenda_event(gestione_agenda: Any, candidate: PdfDeadlineCandidate) -> Any | None:
    try:
        appuntamenti = list(gestione_agenda.tutti())
    except Exception:
        return None
    target_start = candidate.event_datetime[:16]
    matter = _normalise(candidate.matter_label or candidate.fascicolo_label)
    rg = _normalise(_extract_rg_label(candidate.matter_label or candidate.fascicolo_label))
    for item in appuntamenti:
        data_ora = str(getattr(item, "data_ora", "") or "")
        if data_ora[:16] != target_start:
            continue
        text = _normalise(
            " ".join(
                str(getattr(item, field_name, "") or "")
                for field_name in ("titolo", "procedimento", "cliente", "note", "luogo")
            )
        )
        if "udienza" not in text:
            continue
        if matter and matter in text:
            return item
        if rg and rg in text:
            return item
        if candidate.fascicolo_id and candidate.fascicolo_id.lower() in text:
            return item
    return None


def _agenda_description_from_candidate(candidate: PdfDeadlineCandidate, scadenza: Any) -> str:
    lines = [
        f"Documento notificato nel fascicolo: {candidate.document_name}, pagina {candidate.page}.",
        f"Fascicolo/RG: {candidate.matter_label or candidate.fascicolo_label}.",
        f"Cliente/parte: {candidate.client_label}." if candidate.client_label else "",
        f"Scadenza: {getattr(scadenza, 'id', '')}" if getattr(scadenza, "id", "") else "",
        *_remote_hearing_note_lines_from_candidate(candidate),
    ]
    return "\n".join(line for line in lines if str(line or "").strip())


def _link_agenda_to_deadline(gestione_scadenziario: Any, scadenza: Any, agenda_result: dict[str, Any]) -> None:
    agenda_id = str(agenda_result.get("agendaId") or agenda_result.get("agenda_id") or "").strip()
    deadline_id = str(getattr(scadenza, "id", "") or "").strip()
    if not agenda_id or not deadline_id:
        return
    try:
        if not str(getattr(scadenza, "id_appuntamento", "") or "").strip():
            gestione_scadenziario.aggiorna(deadline_id, id_appuntamento=agenda_id)
    except Exception:
        pass


def _signature(fascicolo: Any, documento: Any, due_date: str, kind: str, context: str) -> str:
    raw = "|".join(
        [
            str(getattr(fascicolo, "id", "") or ""),
            str(getattr(documento, "id", "") or ""),
            due_date,
            kind,
            _normalise(context)[:240],
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _fascicolo_label(fascicolo: Any) -> str:
    rg = str(getattr(fascicolo, "rg_completo", "") or getattr(fascicolo, "numero", "") or "").strip()
    title = str(getattr(fascicolo, "oggetto", "") or getattr(fascicolo, "titolo", "") or "").strip()
    cliente = str(getattr(fascicolo, "nome_cliente", "") or "").strip()
    return " - ".join(part for part in (rg, title, cliente) if part) or str(getattr(fascicolo, "id", "") or "Fascicolo")


def _italian_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return value
    return parsed.strftime("%d/%m/%Y")


def _normalise(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", str(value or "").lower())
    ascii_value = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", ascii_value).strip()


def _unique(values: Iterable[str]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip().rstrip(".,;)")
        if not clean or clean in seen:
            continue
        seen.add(clean)
        rows.append(clean)
    return rows


def _deduplicate_candidates(candidates: list[PdfDeadlineCandidate]) -> list[PdfDeadlineCandidate]:
    rows: list[PdfDeadlineCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.id in seen:
            continue
        seen.add(candidate.id)
        rows.append(candidate)
    return rows


def _is_peremptory(context: str) -> bool:
    normalized = _normalise(context)
    return "perentorio" in normalized or "a pena di decadenza" in normalized


def _import_message(created: int, skipped: int, updated: int = 0) -> str:
    if created and updated:
        return f"{created} nuove scadenze importate; {updated} scadenze già presenti aggiornate dal documento notificato."
    if updated and skipped:
        return f"{updated} scadenze già presenti aggiornate dal documento notificato; le altre erano già allineate."
    if updated:
        return f"{updated} scadenze già presenti aggiornate dal documento notificato."
    if created == 1 and skipped:
        return "1 scadenza importata; le scadenze già presenti sono state saltate."
    if created == 1:
        return "1 scadenza importata nello Scadenziario e visibile in Agenda."
    if created:
        return f"{created} scadenze importate nello Scadenziario e visibili in Agenda."
    if skipped:
        return "Nessuna nuova scadenza: quelle selezionate erano già presenti."
    return "Nessuna scadenza importata."
