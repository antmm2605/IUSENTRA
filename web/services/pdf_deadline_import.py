"""Importazione controllata di scadenze dai PDF dei fascicoli."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from pct.document_intelligence.extraction import extract_text_from_document
from pct.scadenziario import TipoTermine


SOURCE_MARKER_PREFIX = "pdf-deadline:"
URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)
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
    existing = _existing_import_markers(gestione_scadenziario)
    candidates: list[PdfDeadlineCandidate] = []
    warnings: list[str] = []
    scanned_documents = 0
    skipped_documents = 0

    for fascicolo in fascicoli:
        for documento in list(getattr(fascicolo, "documenti", []) or []):
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
                    existing=existing,
                )
            )
    candidates.sort(key=lambda item: (item.duplicate, item.due_date, item.fascicolo_label, item.document_name))
    return PdfDeadlinePreview(candidates, len(fascicoli), scanned_documents, skipped_documents, warnings)


def import_pdf_deadlines(
    *,
    gestione_fascicoli: Any,
    gestione_scadenziario: Any,
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
    skipped = 0
    for candidate in preview.candidates:
        if candidate.id not in selected:
            continue
        if candidate.duplicate:
            skipped += 1
            continue
        scadenza = _create_deadline_from_candidate(gestione_scadenziario, candidate, user_id=user_id)
        created.append({"id": scadenza.id, "title": scadenza.titolo, "href": f"/scadenziario/{scadenza.id}"})
    return {
        "ok": True,
        "message": _import_message(len(created), skipped),
        "created": len(created),
        "skipped": skipped,
        "items": created,
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
    existing: dict[str, str],
) -> list[PdfDeadlineCandidate]:
    content = path.read_bytes()
    filename = str(getattr(documento, "nome", "") or path.name)
    result = extract_text_from_document(content, filename, "pdf")
    if not result.ok or not result.text.strip():
        return []
    page_links = _extract_pdf_links_by_page(content)
    rows: list[PdfDeadlineCandidate] = []
    for page in result.pages or []:
        page_number = int(getattr(page, "page_number", 0) or 0)
        text = str(getattr(page, "text", "") or "")
        if not text.strip():
            continue
        links = _unique([*page_links.get(page_number, []), *URL_RE.findall(text)])
        for match, due_date in _date_matches(text):
            context = _context_around(text, match.start(), match.end())
            kind, label, confidence = _classify_context(context)
            if confidence < 0.64:
                continue
            urls = _links_for_context(context, links)
            signature = _signature(fascicolo, documento, due_date, kind.value, context)
            existing_id = existing.get(signature, "")
            rows.append(
                PdfDeadlineCandidate(
                    id=signature,
                    fascicolo_id=str(getattr(fascicolo, "id", "") or ""),
                    fascicolo_label=_fascicolo_label(fascicolo),
                    document_id=str(getattr(documento, "id", "") or ""),
                    document_name=filename,
                    document_href=f"/fascicoli/{getattr(fascicolo, 'id', '')}/documenti/{getattr(documento, 'id', '')}/visualizza",
                    page=page_number,
                    due_date=due_date,
                    title=f"{label} da PDF - {_italian_date(due_date)}",
                    description=f"{filename}, pagina {page_number}: {context}",
                    context=context,
                    type=kind.value,
                    type_label=label,
                    confidence=round(confidence, 2),
                    urls=urls[:5],
                    duplicate=bool(existing_id),
                    existing_deadline_id=existing_id,
                    selected=not bool(existing_id) and confidence >= 0.68,
                    warnings=list(result.warnings[:2]),
                )
            )
    return _deduplicate_candidates(rows)


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


def _existing_import_markers(gestione_scadenziario: Any) -> dict[str, str]:
    rows: dict[str, str] = {}
    try:
        scadenze = list(gestione_scadenziario.tutte(solo_aperte=False))
    except Exception:
        scadenze = []
    for scadenza in scadenze:
        haystack = "\n".join(
            str(getattr(scadenza, field_name, "") or "")
            for field_name in ("note", "descrizione", "trace_json")
        )
        for match in re.finditer(rf"{re.escape(SOURCE_MARKER_PREFIX)}([0-9a-f]+)", haystack):
            rows[match.group(1)] = str(getattr(scadenza, "id", "") or "")
    return rows


def _create_deadline_from_candidate(gestione_scadenziario: Any, candidate: PdfDeadlineCandidate, *, user_id: str = "") -> Any:
    source_marker = f"{SOURCE_MARKER_PREFIX}{candidate.id}"
    links_text = "\n".join(f"Link PDF: {url}" for url in candidate.urls)
    trace = [
        f"Scadenza estratta da PDF: {candidate.document_name}, pagina {candidate.page}.",
        f"Fascicolo: {candidate.fascicolo_label}.",
        f"Documento: {candidate.document_href}.",
        source_marker,
    ]
    trace.extend(f"Link trovato nel PDF: {url}" for url in candidate.urls)
    note = "\n".join(
        part
        for part in (
            f"Fonte PDF: {candidate.document_name}, pagina {candidate.page}.",
            f"Apri documento: {candidate.document_href}",
            links_text,
            source_marker,
        )
        if part
    )
    return gestione_scadenziario.nuova(
        titolo=candidate.title,
        tipo=TipoTermine(candidate.type),
        data_scadenza=candidate.due_date,
        id_fascicolo=candidate.fascicolo_id,
        descrizione=candidate.description,
        data_decorrenza=candidate.due_date,
        note=note,
        perentorio=_is_peremptory(candidate.context),
        source_event_type=candidate.type.lower(),
        source_event_at=candidate.due_date,
        trace_json=json.dumps(trace, ensure_ascii=False),
        id_utente_responsabile=user_id,
        giorni_preavviso=[30, 15, 7, 3, 1, 0],
    )


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
    replacements = str.maketrans("àèéìòù", "aeeiou")
    return re.sub(r"\s+", " ", str(value or "").lower().translate(replacements)).strip()


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


def _import_message(created: int, skipped: int) -> str:
    if created == 1 and skipped:
        return "1 scadenza importata; le scadenze già presenti sono state saltate."
    if created == 1:
        return "1 scadenza importata nello Scadenziario e visibile in Agenda."
    if created:
        return f"{created} scadenze importate nello Scadenziario e visibili in Agenda."
    if skipped:
        return "Nessuna nuova scadenza: quelle selezionate erano già presenti."
    return "Nessuna scadenza importata."
