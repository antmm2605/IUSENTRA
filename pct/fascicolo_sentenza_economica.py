"""Automazione economia fascicolo da sentenze indicizzate per Lex AI."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pct.fascicoli import AvanzamentoPratica, StatoFascicolo
from pct.fatturazione import StatoParcella, VoceParcella


ORIGIN = "lex_ai_sentenza_tribunale"
AUTOMATION_KEY = "_sentenza_tribunale_lex_ai"
SENTENZA_VECTOR_SCHEMA_VERSION = "sentenza_tribunale_compact_v3"
ROME = ZoneInfo("Europe/Rome")

_ITALIAN_MONTHS = {
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
_ITALIAN_DATE_TEXT_PATTERN = (
    r"\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{4}"
)
_SENTENZA_DATE_RE = re.compile(
    r"\bsentenza\s+n\.?\s*(?P<num>\d+)\s*/\s*(?P<year>\d{4}).{0,120}?"
    r"\bpubbl(?:icata|icato|\.?)\s*(?:il)?\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE | re.DOTALL,
)
_SENTENZA_TEXTUAL_DATE_RE = re.compile(
    r"(?:\bSentenza\s+resa\b.{0,180}?|(?:^|[.;]\s*)[A-ZÀ-Ü][A-Za-zÀ-ÿ' -]{1,40},\s*)"
    r"(?P<date>" + _ITALIAN_DATE_TEXT_PATTERN + r")",
    re.IGNORECASE | re.DOTALL,
)
_RG_RE = re.compile(
    r"\b(?:n\.?\s*)?R\.?\s*G\.?\s*(?:n\.?\s*)?(?P<num>[\d.]+)\s*/\s*(?P<year>\d{4})",
    re.IGNORECASE,
)
_MONEY_AMOUNT_PATTERN = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:[,.]\d{2})?"
_MOJIBAKE_EURO = "\u00e2\u201a\u00ac"
_MONEY_PREFIX_PATTERN = r"(?:\u20ac|EUR|euro|" + re.escape(_MOJIBAKE_EURO) + r"|\?)"
_MONEY_RE = re.compile(
    _MONEY_PREFIX_PATTERN + r"\s*(?P<amount>" + _MONEY_AMOUNT_PATTERN + r")",
    re.IGNORECASE,
)
_LIQUIDAZIONE_RE = re.compile(
    r"\bliquid(?:a|ando|ata|ato|ate|ati)\b.{0,160}?"
    r"(?:(?:complessiv[aoei]\s+)?(?:somma|importo)\s+(?:di\s+)?|(?:in\s+)?complessiv[aoei]\s+)"
    + _MONEY_PREFIX_PATTERN
    + r"\s*"
    r"(?P<amount>" + _MONEY_AMOUNT_PATTERN + r")",
    re.IGNORECASE | re.DOTALL,
)
_CU_PATTERNS = (
    re.compile(r"\bc\.?\s*u\.?\b", re.IGNORECASE),
    re.compile(r"\bcontribut[oi]\s+unificat[oi]\b", re.IGNORECASE),
)
_FONDO_PATTERNS = (
    re.compile(r"\bfondo\s+spese\b", re.IGNORECASE),
    re.compile(r"\bfondi\s+spese\b", re.IGNORECASE),
    re.compile(r"\bspese\s+anticipate\b", re.IGNORECASE),
)
_ESBORSI_PATTERNS = (
    re.compile(r"\besbors[oi]\b", re.IGNORECASE),
    re.compile(r"\bspese\s+vive\b", re.IGNORECASE),
)
_SPESE_LITE_QUOTA_RE = re.compile(
    r"\bdi\s+cui\s+"
    + _MONEY_PREFIX_PATTERN
    + r"\s*(?P<amount>"
    + _MONEY_AMOUNT_PATTERN
    + r")\s+(?:per|a\s+titolo\s+di)\s+spese\b(?!\s+generali)",
    re.IGNORECASE | re.DOTALL,
)
_CARTA_DOCENTE_BENEFICIO_RE = re.compile(
    r"\b(?:carta\s+(?:elettronica|docente)|aggiornamento\s+e\s+formazione\s+del\s+docente)\b"
    r".{0,260}?"
    + _MONEY_PREFIX_PATTERN
    + r"\s*(?P<amount>"
    + _MONEY_AMOUNT_PATTERN
    + r")",
    re.IGNORECASE | re.DOTALL,
)
_CONTRIBUTO_DOCUMENT_HINT_RE = re.compile(
    r"\b(?:contributo\s+unificat[oi]|c\.?\s*u\.?|pagopa|pago\s*pa|ricevuta\s+pagamento|avviso\s+pagamento)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_REJECT_RE = re.compile(
    r"\b(?:carta\s+(?:elettronica|docente)|aggiornamento\s+e\s+formazione\s+del\s+docente)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_AMOUNT_RE = re.compile(
    r"\b(?:importo|totale|pagamento|versamento|contributo\s+unificat[oi]|c\.?\s*u\.?)\b"
    r".{0,90}?"
    + _MONEY_PREFIX_PATTERN
    + r"\s*(?P<amount>"
    + _MONEY_AMOUNT_PATTERN
    + r")",
    re.IGNORECASE | re.DOTALL,
)
_CU_BACKWARD_ACCEPT_RE = re.compile(
    r"\b(?:c\.?\s*u\.?|contribut[oi]\s+unificat[oi]|spese\s+vive|spese|sommatoria|versat[eiio]?|anticipat[ei])\b",
    re.IGNORECASE,
)
_CU_BACKWARD_REJECT_RE = re.compile(
    r"\b(?:liquidat[aeio]?|liquidando|complessiv[aoei]|spese\s+generali|accessori\s+di\s+legge|iva|cpa)\b",
    re.IGNORECASE,
)
_OFFICIAL_HEADER_SIGNAL_RE = re.compile(
    r"\b(?:Firmato\s+Da|Emesso\s+Da|Repert\.\s*n\.|Sentenza\s+n\.\s+cronol\.|Serial#)\b",
    re.IGNORECASE,
)
_STRUCTURAL_SENTENCE_SIGNAL_RE = re.compile(
    r"\b(?:P\.?\s*Q\.?\s*M\.?|definitivamente\s+pronunciando|in\s+nome\s+del\s+popolo\s+italiano|"
    r"ha\s+pronunciato\s+la\s+seguente\s+sentenza|sentenza\s+resa\s+ex\s+art\.)\b",
    re.IGNORECASE,
)
_VECTOR_EXCERPT_PATTERNS = (
    re.compile(r"\bliquidando\b", re.IGNORECASE),
    re.compile(r"\bcontribut[oi]\s+unificat[oi]\b", re.IGNORECASE),
    re.compile(r"\bc\.?\s*u\.?\b", re.IGNORECASE),
    re.compile(r"\besbors[oi]\b", re.IGNORECASE),
    re.compile(r"\bspese\s+vive\b", re.IGNORECASE),
    re.compile(r"\bfond[oi]\s+spese\b", re.IGNORECASE),
    re.compile(r"\bspese\s+generali\b", re.IGNORECASE),
    re.compile(r"\bantistatari[oa]\b", re.IGNORECASE),
)
_NAME_STOPWORDS = {
    "c",
    "ca",
    "contro",
    "vs",
    "versus",
    "ministero",
    "mim",
    "miur",
    "rg",
    "n",
    "nr",
}


@dataclass(slots=True)
class SentenzaEconomicaExtraction:
    found: bool = False
    sentence_date: str = ""
    sentence_number: str = ""
    sentence_year: str = ""
    rg_number: str = ""
    rg_year: str = ""
    liquidazione_importo: float | None = None
    liquidazione_titolo: str = ""
    contributo_unificato_importo: float | None = None
    contributo_unificato_titolo: str = ""
    contributo_unificato_natura: str = ""
    contributo_unificato_label: str = ""
    fondo_spese_importo: float | None = None
    fondo_spese_titolo: str = ""
    beneficio_cliente_importo: float | None = None
    beneficio_cliente_titolo: str = ""
    beneficio_cliente_tipo: str = ""
    spese_generali: bool = False
    antistatario: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SentenzaAutomationOutcome:
    applied: bool
    extraction: SentenzaEconomicaExtraction
    changes: dict[str, Any] = field(default_factory=dict)
    proforma_id: str = ""
    proforma_number: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SentenzaFascicoloContext:
    ok: bool
    fascicolo_id_match: bool = True
    cliente_match: bool = False
    rg_match: bool = False
    expected_cliente: str = ""
    expected_rg: str = ""
    found_rg: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_sentenza_tribunale_text(text: str, metadata: dict[str, Any] | None = None) -> SentenzaEconomicaExtraction:
    """Estrae data e importi da una sentenza del Tribunale con regole deterministiche."""

    raw_text = str(text or "")
    compact = _compact(raw_text)
    meta = metadata or {}
    meta_text = " ".join(str(value or "") for value in meta.values()).casefold()
    date_match = _SENTENZA_DATE_RE.search(compact)
    if not date_match:
        date_match = _SENTENZA_TEXTUAL_DATE_RE.search(compact)
    has_sentence_signal = bool(date_match) and ("sentenza" in compact.casefold() or "sentenza" in meta_text)
    has_tribunal_signal = "tribunale" in compact.casefold() or "tribunale" in meta_text
    has_document_type_signal = any(token in meta_text for token in ("sentenza", "provvedimento"))
    header_window = compact[max(0, date_match.start() - 220) : min(len(compact), date_match.end() + 320)] if date_match else ""
    has_official_header_signal = bool(
        date_match
        and _RG_RE.search(compact[date_match.end() : min(len(compact), date_match.end() + 260)])
        and _OFFICIAL_HEADER_SIGNAL_RE.search(header_window)
    )
    has_structural_sentence_signal = bool(_STRUCTURAL_SENTENCE_SIGNAL_RE.search(compact))

    if not date_match or not has_sentence_signal:
        return SentenzaEconomicaExtraction(found=False)
    if not (has_tribunal_signal or has_document_type_signal or has_official_header_signal or has_structural_sentence_signal):
        return SentenzaEconomicaExtraction(found=False, warnings=["Documento con intestazione sentenza, ma senza classificazione Tribunale."])

    sentence_date = _parse_italian_date(date_match.group("date"))
    if not sentence_date:
        return SentenzaEconomicaExtraction(found=False, warnings=["Data sentenza non leggibile."])

    rg_match = _extract_rg_near_sentence(compact, date_match)
    liquidation_amount, liquidation_title = _extract_liquidazione(compact)
    cu_amount, cu_title = _extract_contributo_unificato(compact)
    cu_natura = _classify_contributo_recovery(cu_title) if cu_amount is not None else ""
    fondo_amount, fondo_title = _extract_amount_near(compact, _FONDO_PATTERNS)
    beneficio_amount, beneficio_title, beneficio_tipo = _extract_beneficio_cliente(compact)
    groups = date_match.groupdict()

    return SentenzaEconomicaExtraction(
        found=True,
        sentence_date=sentence_date,
        sentence_number=str(groups.get("num") or "").strip(),
        sentence_year=str(groups.get("year") or "").strip(),
        rg_number=str(rg_match.group("num") or "").strip() if rg_match else "",
        rg_year=str(rg_match.group("year") or "").strip() if rg_match else "",
        liquidazione_importo=liquidation_amount,
        liquidazione_titolo=liquidation_title,
        contributo_unificato_importo=cu_amount,
        contributo_unificato_titolo=cu_title,
        contributo_unificato_natura=cu_natura,
        contributo_unificato_label=_contributo_recovery_label(cu_natura),
        fondo_spese_importo=fondo_amount,
        fondo_spese_titolo=fondo_title,
        beneficio_cliente_importo=beneficio_amount,
        beneficio_cliente_titolo=beneficio_title,
        beneficio_cliente_tipo=beneficio_tipo,
        spese_generali=bool(re.search(r"\bspese\s+generali\b", compact, re.IGNORECASE)),
        antistatario=bool(re.search(r"\bantistatari[oa]\b", compact, re.IGNORECASE)),
    )


def _extract_rg_near_sentence(compact_text: str, sentence_match: re.Match[str]) -> re.Match[str] | None:
    """Preferisce l'RG dell'intestazione rispetto a riferimenti citati nel corpo."""

    after_start = sentence_match.end()
    after_end = min(len(compact_text), after_start + 260)
    header_match = _RG_RE.search(compact_text[after_start:after_end])
    if header_match:
        return header_match

    start = max(0, sentence_match.start() - 120)
    before_match = _RG_RE.search(compact_text[start:sentence_match.start()])
    if before_match:
        return before_match

    early_match = _RG_RE.search(compact_text[: min(len(compact_text), sentence_match.end() + 900)])
    if early_match:
        return early_match
    return _RG_RE.search(compact_text)


def apply_sentenza_tribunale_automation(
    *,
    fascicoli_repository: Any,
    fatturazione_repository: Any,
    fascicolo_id: str,
    text: str,
    document_metadata: dict[str, Any] | None = None,
    actor: str = "",
) -> SentenzaAutomationOutcome:
    """Applica al fascicolo la matrice economica derivata dalla sentenza indicizzata."""

    metadata = dict(document_metadata or {})
    extraction = analyze_sentenza_tribunale_text(text, metadata)
    if not extraction.found:
        return SentenzaAutomationOutcome(applied=False, extraction=extraction, message="Documento non riconosciuto come Sentenza Tribunale.")

    fascicolo = fascicoli_repository.get(str(fascicolo_id or "").strip())
    if not fascicolo:
        return SentenzaAutomationOutcome(applied=False, extraction=extraction, message="Fascicolo non trovato.")

    context = validate_sentenza_fascicolo_context(
        text=text,
        extraction=extraction,
        fascicolo=fascicolo,
        metadata=metadata,
        fascicolo_id=fascicolo_id,
    )
    if not context.ok:
        extraction.warnings.extend(context.warnings)
        return SentenzaAutomationOutcome(
            applied=False,
            extraction=extraction,
            changes={"context": context.to_dict()},
            message=context.message,
            warnings=list(context.warnings),
        )
    apply_contributo_unificato_pdf_evidence(extraction, metadata)

    document_key = _document_key(metadata)
    payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
    automation = _automation_state(payments)
    processed = set(str(item) for item in automation.get("processed_documents") or [])
    already_processed = bool(document_key and document_key in processed)
    proforma_id = _text((automation.get("proforme") or {}).get(document_key)) if document_key else ""
    existing_proforma = _find_existing_proforma(
        fatturazione_repository,
        str(getattr(fascicolo, "id", fascicolo_id)),
        document_key,
        extraction,
    )
    if existing_proforma:
        proforma_id = _text(getattr(existing_proforma, "id", "")) or proforma_id

    changes: dict[str, Any] = {
        "payments": [],
        "statusChanged": False,
        "nextDeadlineChanged": False,
        "proformaCreated": False,
        "alreadyProcessed": already_processed,
    }
    now = _now_rome()
    operator = _text(actor, "Lex AI")

    fields: dict[str, Any] = {}
    if _is_missing_visible_date(getattr(fascicolo, "data_prossima_udienza", "")):
        fields["data_prossima_udienza"] = extraction.sentence_date
        changes["nextDeadlineChanged"] = True
    if not _text(getattr(fascicolo, "data_chiusura", "")):
        fields["data_chiusura"] = extraction.sentence_date

    previous_status = _enum_value(getattr(fascicolo, "stato", ""))
    if previous_status != StatoFascicolo.DEFINITO.value:
        fields["stato"] = StatoFascicolo.DEFINITO
        changes["statusChanged"] = True
        advancement = list(getattr(fascicolo, "avanzamento", []) or [])
        advancement.append(
            AvanzamentoPratica(
                data=now,
                descrizione="Sentenza indicizzata da Lex AI: fascicolo definito",
                stato_precedente=previous_status,
                stato_nuovo=StatoFascicolo.DEFINITO.value,
                note=_sentenza_note(extraction, metadata),
                avvocato=operator,
            )
        )
        fields["avanzamento"] = advancement

    if extraction.contributo_unificato_importo is not None:
        cu_changed = _upsert_payment(
            payments,
            "contributo_unificato",
            status="pagato",
            amount=extraction.contributo_unificato_importo,
            date_iso=extraction.sentence_date,
            note=extraction.contributo_unificato_titolo,
            operator=operator,
            now=now,
            document_key=document_key,
            extra={
                "natura": extraction.contributo_unificato_natura or "spese_recuperate",
                "label": extraction.contributo_unificato_label
                or _contributo_recovery_label(extraction.contributo_unificato_natura),
            },
        )
        if cu_changed:
            changes["payments"].append("contributo_unificato")

    fondo_changed = False
    if extraction.fondo_spese_importo is not None:
        fondo_changed = _upsert_payment(
            payments,
            "fondo_spese",
            status="pagato",
            amount=extraction.fondo_spese_importo,
            date_iso=extraction.sentence_date,
            note=extraction.fondo_spese_titolo,
            operator=operator,
            now=now,
            document_key=document_key,
        )
        if fondo_changed:
            changes["payments"].append("fondo_spese")

    if extraction.liquidazione_importo is not None:
        liq_changed = _upsert_payment(
            payments,
            "liquidazione_giudice",
            status="pagato",
            amount=extraction.liquidazione_importo,
            date_iso=extraction.sentence_date,
            note=extraction.liquidazione_titolo,
            operator=operator,
            now=now,
            document_key=document_key,
        )
        if liq_changed:
            changes["payments"].append("liquidazione_giudice")

    proforma = existing_proforma
    if proforma is None and extraction.liquidazione_importo is not None:
        proforma = _create_proforma(
            fatturazione_repository=fatturazione_repository,
            fascicolo=fascicolo,
            extraction=extraction,
            metadata=metadata,
            actor=operator,
        )
        changes["proformaCreated"] = proforma is not None
    if proforma is not None:
        proforma = _sync_existing_proforma_from_extraction(
            fatturazione_repository=fatturazione_repository,
            proforma=proforma,
            extraction=extraction,
            metadata=metadata,
        )
        proforma_id = _text(getattr(proforma, "id", ""))

        parcella_changed = _upsert_payment(
            payments,
            "parcella",
            status="da_emettere",
            amount=_proforma_total(proforma) or extraction.liquidazione_importo,
            date_iso=extraction.sentence_date,
            note="Proforma predisposta automaticamente dalla sentenza indicizzata.",
            operator=operator,
            now=now,
            document_key=document_key,
            extra={
                "proforma_id": proforma_id,
                "proforma_number": _text(getattr(proforma, "numero", "")),
                "origine": ORIGIN,
            },
        )
        if parcella_changed:
            changes["payments"].append("parcella")

    has_data_changes = bool(fields) or bool(changes["payments"]) or bool(changes["proformaCreated"])
    if already_processed and not has_data_changes:
        return SentenzaAutomationOutcome(
            applied=False,
            extraction=extraction,
            changes=changes,
            proforma_id=proforma_id,
            proforma_number=_text(getattr(existing_proforma, "numero", "")) if existing_proforma is not None else "",
            message="Sentenza Tribunale già applicata al fascicolo.",
        )

    if document_key:
        processed.add(document_key)
    automation["processed_documents"] = sorted(processed)
    automation.setdefault("proforme", {})
    if document_key and proforma_id:
        automation["proforme"][document_key] = proforma_id
    automation["last_applied_at"] = now
    automation["last_extraction"] = extraction.to_dict()
    payments[AUTOMATION_KEY] = automation
    fields["pagamenti"] = payments

    if fields:
        fascicoli_repository.aggiorna(str(getattr(fascicolo, "id", fascicolo_id)), **fields)

    return SentenzaAutomationOutcome(
        applied=True,
        extraction=extraction,
        changes=changes,
        proforma_id=proforma_id,
        proforma_number=_text(getattr(proforma, "numero", "")) if proforma is not None else "",
        message="Sentenza Tribunale applicata al fascicolo.",
    )


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _plain(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.casefold()).strip()


def _tokens(value: Any) -> list[str]:
    return [token for token in _plain(value).split() if len(token) > 1 and token not in _NAME_STOPWORDS]


def _client_candidates(fascicolo: Any, metadata: dict[str, Any] | None = None) -> list[str]:
    meta = metadata or {}
    candidates = [
        _text(getattr(fascicolo, "nome_cliente", "")),
        _text(meta.get("cliente") or meta.get("client_name") or meta.get("nome_cliente")),
    ]
    title = _text(getattr(fascicolo, "titolo", ""))
    if title:
        for separator in (" c. ", " c ", " contro ", " vs ", " / "):
            if separator in title.casefold():
                candidates.append(title[: title.casefold().find(separator)].strip())
                break
        else:
            candidates.append(title)
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        normalized = " ".join(_tokens(candidate))
        if len(normalized.split()) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        result.append(candidate)
    return result


def _client_name_in_text(text: str, fascicolo: Any, metadata: dict[str, Any] | None = None) -> tuple[bool, str]:
    plain_text = f" {_plain(text)} "
    for candidate in _client_candidates(fascicolo, metadata):
        tokens = _tokens(candidate)
        if len(tokens) < 2:
            continue
        phrase = " ".join(tokens)
        if f" {phrase} " in plain_text:
            return True, candidate
        if all(f" {token} " in plain_text for token in tokens):
            return True, candidate
    expected = _text(getattr(fascicolo, "nome_cliente", "")) or _text((metadata or {}).get("cliente"))
    return False, expected


def _normalize_rg_number(value: Any) -> str:
    raw = _text(value)
    if "/" in raw:
        raw = raw.split("/", 1)[0]
    return re.sub(r"\D+", "", raw)


def _rg_candidates_from_fascicolo(fascicolo: Any) -> list[tuple[str, str]]:
    raw_number = _text(getattr(fascicolo, "numero_rg", ""))
    raw_year = _text(getattr(fascicolo, "anno_rg", ""))
    candidates: list[tuple[str, str]] = []
    if raw_number and raw_year and raw_year not in {"0", "0.0"}:
        candidates.append((_normalize_rg_number(raw_number), re.sub(r"\D+", "", raw_year)))
    for value in (
        getattr(fascicolo, "rg_completo", ""),
        raw_number,
        getattr(fascicolo, "numero", ""),
        getattr(fascicolo, "source_external_id", ""),
    ):
        match = _RG_RE.search(str(value or ""))
        if match:
            candidates.append((_normalize_rg_number(match.group("num")), re.sub(r"\D+", "", match.group("year"))))
        elif "/" in str(value or ""):
            left, right = str(value).split("/", 1)
            candidates.append((_normalize_rg_number(left), re.sub(r"\D+", "", right)[:4]))
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for number, year in candidates:
        if not number or not year or (number, year) in seen:
            continue
        seen.add((number, year))
        result.append((number, year))
    return result


def _rg_matches_fascicolo(extraction: SentenzaEconomicaExtraction, fascicolo: Any) -> tuple[bool, str]:
    found = (_normalize_rg_number(extraction.rg_number), re.sub(r"\D+", "", extraction.rg_year))
    expected = _rg_candidates_from_fascicolo(fascicolo)
    if not found[0] or not found[1]:
        label = ", ".join(f"{num}/{year}" for num, year in expected)
        return False, label
    return found in expected, ", ".join(f"{num}/{year}" for num, year in expected)


def validate_sentenza_fascicolo_context(
    *,
    text: str,
    extraction: SentenzaEconomicaExtraction,
    fascicolo: Any,
    metadata: dict[str, Any] | None = None,
    fascicolo_id: str = "",
) -> SentenzaFascicoloContext:
    """Conferma che la sentenza appartenga davvero al fascicolo, non a una fonte strategica."""

    meta = metadata or {}
    expected_fascicolo_id = _text(getattr(fascicolo, "id", "")) or _text(fascicolo_id)
    meta_fascicolo_id = _text(meta.get("fascicolo_id"))
    fascicolo_id_match = not meta_fascicolo_id or not expected_fascicolo_id or meta_fascicolo_id == expected_fascicolo_id
    cliente_match, expected_cliente = _client_name_in_text(text, fascicolo, meta)
    rg_match, expected_rg = _rg_matches_fascicolo(extraction, fascicolo)
    found_number = _normalize_rg_number(extraction.rg_number)
    found_year = re.sub(r"\D+", "", extraction.rg_year)
    found_rg = f"{found_number}/{found_year}".strip("/")
    warnings: list[str] = []
    if not fascicolo_id_match:
        warnings.append("fascicolo_id_documento_non_coincidente")
    if not cliente_match:
        warnings.append("cliente_non_presente_nella_sentenza")
    if not rg_match:
        warnings.append("rg_sentenza_non_coincidente_con_fascicolo")
    ok = fascicolo_id_match and cliente_match and rg_match
    if ok:
        return SentenzaFascicoloContext(
            ok=True,
            fascicolo_id_match=True,
            cliente_match=True,
            rg_match=True,
            expected_cliente=expected_cliente,
            expected_rg=expected_rg,
            found_rg=found_rg,
            message="Sentenza confermata sullo stesso cliente e fascicolo.",
        )
    return SentenzaFascicoloContext(
        ok=False,
        fascicolo_id_match=fascicolo_id_match,
        cliente_match=cliente_match,
        rg_match=rg_match,
        expected_cliente=expected_cliente,
        expected_rg=expected_rg,
        found_rg=found_rg,
        message=(
            "Sentenza non applicata: il documento non contiene una conferma completa "
            "di cliente e RG del fascicolo. Può essere materiale strategico o giurisprudenza di supporto."
        ),
        warnings=warnings,
    )


def sentenza_vector_relevant_excerpt(text: str, *, max_chars: int = 12000) -> str:
    """Riduce il testo per Lex mantenendo intestazione e passaggi economici."""

    compact = _compact(text)
    if len(compact) <= max_chars:
        return compact
    windows: list[tuple[int, int]] = [(0, min(len(compact), 1800))]
    for pattern in _VECTOR_EXCERPT_PATTERNS:
        for match in pattern.finditer(compact):
            windows.append((max(0, match.start() - 1400), min(len(compact), match.end() + 2600)))
            if len(windows) >= 8:
                break
        if len(windows) >= 8:
            break
    windows.sort()
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if not merged or start > merged[-1][1] + 80:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    pieces: list[str] = []
    for start, end in merged:
        piece = compact[start:end].strip()
        if piece:
            pieces.append(piece)
        if sum(len(p) for p in pieces) >= max_chars:
            break
    excerpt = "\n...\n".join(pieces).strip()
    if len(excerpt) > max_chars:
        excerpt = excerpt[:max_chars].rsplit(" ", 1)[0].strip()
    return excerpt


def _text(value: Any, default: str = "") -> str:
    raw = str(value if value is not None else "").strip()
    return raw or default


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _now_rome() -> str:
    return datetime.now(ROME).replace(microsecond=0).isoformat()


def _parse_italian_date(value: str) -> str:
    raw = _compact(_text(value)).strip(" .")
    for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    match = re.fullmatch(
        r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-zÀ-ÿ]+)\s+(?P<year>\d{4})",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return ""
    month = _ITALIAN_MONTHS.get(_plain(match.group("month")))
    if not month:
        return ""
    try:
        return date(int(match.group("year")), month, int(match.group("day"))).isoformat()
    except ValueError:
        return ""


def _parse_money(value: str) -> float | None:
    raw = _text(value).replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def _snippet(text: str, start: int, end: int, *, window: int = 90) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    return _compact(text[left:right])[:360]


def _extract_liquidazione(text: str) -> tuple[float | None, str]:
    match = _LIQUIDAZIONE_RE.search(text)
    if not match:
        return None, ""
    amount = _parse_money(match.group("amount"))
    title = _snippet(text, match.start(), match.end(), window=40)
    return amount, title


def _extract_beneficio_cliente(text: str) -> tuple[float | None, str, str]:
    match = _CARTA_DOCENTE_BENEFICIO_RE.search(text)
    if not match:
        return None, "", ""
    return _parse_money(match.group("amount")), _snippet(text, match.start(), match.end(), window=80), "carta_docente"


def _classify_contributo_recovery(title: str) -> str:
    plain = _plain(title)
    if "contributo unificato" in plain or re.search(r"\bc\s*u\b", plain):
        return "contributo_unificato"
    if "esbors" in plain or "spese vive" in plain or re.search(r"\bper spese\b", plain):
        return "spese_esborsi"
    return "spese_recuperate"


def _contributo_recovery_label(natura: str) -> str:
    if natura == "contributo_unificato":
        return "Contributo unificato"
    if natura == "spese_esborsi":
        return "Spese/esborsi"
    if natura == "pdf_contributo_unificato":
        return "Contributo unificato da PDF"
    return "Spese da recuperare"


def _contributo_voice_description(extraction: SentenzaEconomicaExtraction) -> str:
    if extraction.contributo_unificato_natura == "contributo_unificato":
        return "Contributo unificato riconosciuto in sentenza"
    if extraction.contributo_unificato_natura == "pdf_contributo_unificato":
        return "Contributo unificato confermato da PDF nel fascicolo"
    if extraction.contributo_unificato_natura == "spese_esborsi":
        return "Spese ed esborsi riconosciuti in sentenza"
    return "Spese da recuperare riconosciute in sentenza"


def _contributo_voice_tokens(extraction: SentenzaEconomicaExtraction) -> tuple[str, ...]:
    if extraction.contributo_unificato_natura in {"contributo_unificato", "pdf_contributo_unificato"}:
        return ("contributo", "unificato", "c u")
    return ("spese", "esborsi")


def extract_contributo_unificato_document_evidence(
    text: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Legge l'importo da un PDF dedicato a CU/PagoPA senza confonderlo con Carta docente."""

    meta = metadata or {}
    compact = _compact(text)
    label = " ".join(
        _text(meta.get(key))
        for key in ("filename", "original_filename", "safe_filename", "tipo_documento", "classification")
    )
    probe = f"{label} {compact}"
    if not _CONTRIBUTO_DOCUMENT_HINT_RE.search(probe):
        return {}
    if _CONTRIBUTO_DOCUMENT_REJECT_RE.search(probe) and not re.search(r"\bcontributo\s+unificat[oi]\b|\bc\.?\s*u\.?\b", probe, re.IGNORECASE):
        return {}
    candidates: list[tuple[int, re.Match[str]]] = []
    for match in _CONTRIBUTO_DOCUMENT_AMOUNT_RE.finditer(compact):
        snippet = _snippet(compact, match.start(), match.end(), window=60)
        if _CONTRIBUTO_DOCUMENT_REJECT_RE.search(snippet):
            continue
        priority = 0 if re.search(r"\bcontributo\s+unificat[oi]\b|\bc\.?\s*u\.?\b", snippet, re.IGNORECASE) else 1
        candidates.append((priority, match))
    if not candidates:
        money = list(_MONEY_RE.finditer(compact))
        if len(money) != 1:
            return {}
        match = money[0]
    else:
        _, match = min(candidates, key=lambda item: (item[0], item[1].start()))
    amount = _parse_money(match.group("amount"))
    if amount is None:
        return {}
    return {
        "importo": amount,
        "titolo": _snippet(compact, match.start(), match.end(), window=70),
        "natura": "pdf_contributo_unificato",
        "label": "Contributo unificato da PDF",
        "filename": _text(meta.get("filename") or meta.get("original_filename") or meta.get("safe_filename")),
        "document_id": _text(meta.get("document_id") or meta.get("documento_id")),
        "sha256": _text(meta.get("sha256")),
        "origine": "pdf_contributo_unificato",
    }


def apply_contributo_unificato_pdf_evidence(
    extraction: SentenzaEconomicaExtraction,
    metadata: dict[str, Any],
) -> None:
    raw = metadata.get("contributo_unificato_pdf")
    if not isinstance(raw, dict):
        return
    amount = _parse_money(str(raw.get("importo") or ""))
    if amount is None:
        return
    filename = _text(raw.get("filename") or raw.get("document_id") or "PDF contributo unificato")
    title = _text(raw.get("titolo")) or f"Importo confermato da {filename}"
    if extraction.contributo_unificato_importo is None:
        extraction.contributo_unificato_importo = amount
        extraction.contributo_unificato_titolo = f"{title} (fonte: {filename})"
        extraction.contributo_unificato_natura = _text(raw.get("natura")) or "pdf_contributo_unificato"
        extraction.contributo_unificato_label = _text(raw.get("label")) or _contributo_recovery_label(extraction.contributo_unificato_natura)
        extraction.warnings.append("contributo_unificato_da_pdf")
        return
    if abs(float(extraction.contributo_unificato_importo) - amount) <= 0.01:
        if not extraction.contributo_unificato_natura:
            extraction.contributo_unificato_natura = _classify_contributo_recovery(extraction.contributo_unificato_titolo)
            extraction.contributo_unificato_label = _contributo_recovery_label(extraction.contributo_unificato_natura)
        confirmation_label = (
            "PDF del fascicolo"
            if extraction.contributo_unificato_natura == "spese_esborsi"
            else "PDF contributo unificato"
        )
        if f"confermato da {confirmation_label}" not in extraction.contributo_unificato_titolo:
            extraction.contributo_unificato_titolo = (
                f"{extraction.contributo_unificato_titolo} - confermato da {confirmation_label}: {filename}"
            ).strip(" -")
        extraction.warnings.append(
            "spese_esborsi_confermate_pdf" if extraction.contributo_unificato_natura == "spese_esborsi" else "contributo_unificato_confermato_pdf"
        )
        return
    sentenza_amount = extraction.contributo_unificato_importo
    if extraction.contributo_unificato_natura == "spese_esborsi":
        extraction.warnings.append("contributo_unificato_pdf_diverso_da_spese_sentenza")
        if "PDF contributo unificato discordante" not in extraction.contributo_unificato_titolo:
            extraction.contributo_unificato_titolo = (
                f"{extraction.contributo_unificato_titolo} - PDF contributo unificato discordante: "
                f"{filename} importo {amount}"
            ).strip(" -")
        return
    extraction.warnings.append("contributo_unificato_pdf_diverso_da_sentenza")
    extraction.contributo_unificato_importo = amount
    extraction.contributo_unificato_titolo = (
        f"{title} (fonte diretta: {filename}; importo sentenza: {sentenza_amount})"
    )
    extraction.contributo_unificato_natura = _text(raw.get("natura")) or "pdf_contributo_unificato"
    extraction.contributo_unificato_label = _text(raw.get("label")) or _contributo_recovery_label(extraction.contributo_unificato_natura)


def _extract_amount_near(text: str, patterns: tuple[re.Pattern[str], ...], *, window: int = 140) -> tuple[float | None, str]:
    best: tuple[int, re.Match[str]] | None = None
    for pattern in patterns:
        for keyword in pattern.finditer(text):
            left = max(0, keyword.start() - window)
            right = min(len(text), keyword.end() + window)
            for money in _MONEY_RE.finditer(text, left, right):
                distance = min(abs(money.start() - keyword.start()), abs(money.end() - keyword.end()))
                if best is None or distance < best[0]:
                    best = (distance, money)
    if best is None:
        return None, ""
    match = best[1]
    return _parse_money(match.group("amount")), _snippet(text, match.start(), match.end(), window=70)


def _extract_contributo_unificato(text: str, *, window: int = 140) -> tuple[float | None, str]:
    candidates: list[tuple[int, int, re.Match[str]]] = []
    for pattern in _CU_PATTERNS:
        for keyword in pattern.finditer(text):
            right = min(len(text), keyword.end() + window)
            for money in _MONEY_RE.finditer(text, keyword.end(), right):
                between = text[keyword.end() : money.start()]
                if _CU_BACKWARD_REJECT_RE.search(between):
                    continue
                candidates.append((0, money.start() - keyword.end(), money))

            left = max(0, keyword.start() - window)
            for money in _MONEY_RE.finditer(text, left, keyword.start()):
                between = text[money.end() : keyword.start()]
                if not _is_valid_contributo_unificato_before(between):
                    continue
                candidates.append((1, keyword.start() - money.end(), money))

    if not candidates:
        esborsi_amount, esborsi_title = _extract_amount_near(text, _ESBORSI_PATTERNS, window=110)
        if esborsi_amount is not None:
            return esborsi_amount, esborsi_title
        spese_match = _SPESE_LITE_QUOTA_RE.search(text)
        if spese_match:
            return _parse_money(spese_match.group("amount")), _snippet(text, spese_match.start(), spese_match.end(), window=70)
        return None, ""
    _, _, match = min(candidates, key=lambda item: (item[0], item[1]))
    return _parse_money(match.group("amount")), _snippet(text, match.start(), match.end(), window=70)


def _is_valid_contributo_unificato_before(between: str) -> bool:
    compact_between = _compact(between)
    if not compact_between or _CU_BACKWARD_REJECT_RE.search(compact_between):
        return False
    return bool(_CU_BACKWARD_ACCEPT_RE.search(compact_between))


def _document_key(metadata: dict[str, Any]) -> str:
    for key in ("sentenza_key", "document_id", "documento_id", "source_id", "sha256", "filename"):
        value = _text(metadata.get(key))
        if value:
            return f"{key}:{value}"
    return ""


def _automation_state(payments: dict[str, Any]) -> dict[str, Any]:
    raw = payments.get(AUTOMATION_KEY)
    return dict(raw) if isinstance(raw, dict) else {"processed_documents": [], "proforme": {}}


def _is_missing_visible_date(value: Any) -> bool:
    raw = _text(value).casefold()
    return raw in {"", "n.d.", "nd", "n d", "non definita", "non disponibile"}


def _history_entry(
    *,
    previous: dict[str, Any],
    status: str,
    amount: float | None,
    operator: str,
    now: str,
    note: str,
) -> dict[str, Any]:
    return {
        "at": now,
        "by": operator,
        "fromStatus": _text(previous.get("status") or previous.get("stato")),
        "toStatus": status,
        "fromImporto": previous.get("importo"),
        "toImporto": amount,
        "note": note[:160],
        "origine": ORIGIN,
    }


def _upsert_payment(
    payments: dict[str, Any],
    kind: str,
    *,
    status: str,
    amount: float | None,
    date_iso: str,
    note: str,
    operator: str,
    now: str,
    document_key: str,
    extra: dict[str, Any] | None = None,
) -> bool:
    previous = dict(payments.get(kind) or {}) if isinstance(payments.get(kind), dict) else {}
    next_payload = dict(previous)
    next_payload.update(
        {
            "kind": kind,
            "status": status,
            "previsto": status != "non_previsto",
            "pagato": status == "pagato",
            "importo": amount,
            "valuta": "EUR",
            "data_pagamento": date_iso,
            "metodo": _payment_method(previous, status),
            "note": note[:400],
            "updated_at": now,
            "updated_by": operator,
            "origine": ORIGIN,
            "documento_fonte": document_key,
        }
    )
    if extra:
        next_payload.update({key: value for key, value in extra.items() if value not in (None, "")})
    comparable_keys = {"status", "importo", "data_pagamento", "note", "proforma_id", "proforma_number", "natura", "label"}
    changed = any(previous.get(key) != next_payload.get(key) for key in comparable_keys)
    if changed:
        history = list(previous.get("history") or previous.get("storico") or [])
        history.append(_history_entry(previous=previous, status=status, amount=amount, operator=operator, now=now, note=note))
        next_payload["history"] = history[-25:]
    payments[kind] = next_payload
    return changed


def _sentenza_note(extraction: SentenzaEconomicaExtraction, metadata: dict[str, Any]) -> str:
    pieces = []
    if extraction.sentence_number and extraction.sentence_year:
        pieces.append(f"Sentenza n. {extraction.sentence_number}/{extraction.sentence_year}")
    if extraction.rg_number and extraction.rg_year:
        pieces.append(f"RG n. {extraction.rg_number}/{extraction.rg_year}")
    filename = _text(metadata.get("filename") or metadata.get("original_filename"))
    if filename:
        pieces.append(f"Documento: {filename}")
    return "; ".join(pieces)


def _payment_method(previous: dict[str, Any], status: str) -> str:
    existing = _text(previous.get("metodo") or previous.get("method") or previous.get("metodo_pagamento"))
    if existing:
        return existing
    return "Bonifico bancario" if status == "pagato" else ""


def _sentenza_fingerprint(extraction: SentenzaEconomicaExtraction | dict[str, Any] | None) -> str:
    if not extraction:
        return ""
    getter = extraction.get if isinstance(extraction, dict) else lambda key, default="": getattr(extraction, key, default)
    parts = [
        _text(getter("sentence_date", "")),
        _text(getter("sentence_number", "")),
        _text(getter("sentence_year", "")),
        _text(getter("rg_number", "")),
        _text(getter("rg_year", "")),
    ]
    fingerprint = "|".join(parts)
    return fingerprint if any(parts) else ""


def _find_existing_proforma(
    fatturazione_repository: Any,
    fascicolo_id: str,
    document_key: str,
    extraction: SentenzaEconomicaExtraction | None = None,
) -> Any | None:
    getter = getattr(fatturazione_repository, "per_fascicolo", None)
    if not callable(getter):
        return None
    current_fingerprint = _sentenza_fingerprint(extraction)
    for item in getter(fascicolo_id):
        if _enum_value(getattr(item, "stato", "")) == StatoParcella.ANNULLATA.value:
            continue
        if _text(getattr(item, "origine", "")) != ORIGIN:
            continue
        data = getattr(item, "dati_personalizzati", {}) or {}
        lex = data.get("lex_sentenza") if isinstance(data, dict) else {}
        if not document_key or _text((lex or {}).get("document_key")) == document_key:
            return item
        if current_fingerprint and current_fingerprint == _sentenza_fingerprint((lex or {}).get("extraction")):
            return item
    return None


def _voice_amount(voice: Any) -> float:
    try:
        quantity = float(getattr(voice, "quantita", 1.0) or 1.0)
        price = float(getattr(voice, "prezzo_unitario", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return round(quantity * price, 2)


def _has_voice(voci: list[Any], amount: float, tokens: tuple[str, ...]) -> bool:
    expected = round(float(amount or 0.0), 2)
    for voice in voci:
        if abs(_voice_amount(voice) - expected) > 0.01:
            continue
        description = _plain(getattr(voice, "descrizione", ""))
        if any(token in description for token in tokens):
            return True
    return False


def _proforma_total(proforma: Any) -> float | None:
    if proforma is None:
        return None
    try:
        return round(float(getattr(proforma, "totale") or 0.0), 2)
    except (TypeError, ValueError):
        return None


def _sync_existing_proforma_from_extraction(
    *,
    fatturazione_repository: Any,
    proforma: Any,
    extraction: SentenzaEconomicaExtraction,
    metadata: dict[str, Any],
) -> Any:
    """Completa una proforma Lex gia' creata quando il parser impara nuovi importi."""

    if proforma is None:
        return None
    if _enum_value(getattr(proforma, "stato", "")) != StatoParcella.BOZZA.value:
        return proforma
    updater = getattr(fatturazione_repository, "aggiorna", None)
    if not callable(updater):
        return proforma
    voci = list(getattr(proforma, "voci", []) or [])
    changed = False
    if extraction.liquidazione_importo is not None and not _has_voice(
        voci,
        extraction.liquidazione_importo,
        ("compensi", "liquidati", "liquidazione"),
    ):
        voci.append(
            VoceParcella(
                descrizione="Compensi liquidati in sentenza",
                quantita=1.0,
                prezzo_unitario=extraction.liquidazione_importo,
                tipo="ONORARIO",
            )
        )
        changed = True
    if extraction.contributo_unificato_importo is not None and not _has_voice(
        voci,
        extraction.contributo_unificato_importo,
        _contributo_voice_tokens(extraction),
    ):
        voci.append(
            VoceParcella(
                descrizione=_contributo_voice_description(extraction),
                quantita=1.0,
                prezzo_unitario=extraction.contributo_unificato_importo,
                tipo="ANTICIPO",
            )
        )
        changed = True
    if extraction.fondo_spese_importo is not None and not _has_voice(
        voci,
        extraction.fondo_spese_importo,
        ("fondo", "spese"),
    ):
        voci.append(
            VoceParcella(
                descrizione="Fondo spese riconosciuto in sentenza",
                quantita=1.0,
                prezzo_unitario=extraction.fondo_spese_importo,
                tipo="ANTICIPO",
            )
        )
        changed = True

    data = dict(getattr(proforma, "dati_personalizzati", {}) or {})
    lex_data = dict(data.get("lex_sentenza") or {})
    lex_data.update(
        {
            "origin": ORIGIN,
            "document_key": _document_key(metadata),
            "document_id": _text(metadata.get("document_id")),
            "sha256": _text(metadata.get("sha256")),
            "filename": _text(metadata.get("filename") or metadata.get("original_filename")),
            "extraction": extraction.to_dict(),
        }
    )
    data["lex_sentenza"] = lex_data
    if changed or data != getattr(proforma, "dati_personalizzati", {}):
        proforma = updater(_text(getattr(proforma, "id", "")), voci=voci, dati_personalizzati=data)
    return proforma


def _create_proforma(
    *,
    fatturazione_repository: Any,
    fascicolo: Any,
    extraction: SentenzaEconomicaExtraction,
    metadata: dict[str, Any],
    actor: str,
) -> Any | None:
    creator = getattr(fatturazione_repository, "crea", None)
    if not callable(creator):
        return None
    id_cliente = _text(getattr(fascicolo, "id_cliente", ""))
    if not id_cliente:
        return None
    voci: list[VoceParcella] = []
    if extraction.liquidazione_importo is not None:
        voci.append(
            VoceParcella(
                descrizione="Compensi liquidati in sentenza",
                quantita=1.0,
                prezzo_unitario=extraction.liquidazione_importo,
                tipo="ONORARIO",
            )
        )
    if extraction.contributo_unificato_importo is not None:
        voci.append(
            VoceParcella(
                descrizione=_contributo_voice_description(extraction),
                quantita=1.0,
                prezzo_unitario=extraction.contributo_unificato_importo,
                tipo="ANTICIPO",
            )
        )
    if extraction.fondo_spese_importo is not None:
        voci.append(
            VoceParcella(
                descrizione="Fondo spese riconosciuto in sentenza",
                quantita=1.0,
                prezzo_unitario=extraction.fondo_spese_importo,
                tipo="ANTICIPO",
            )
        )
    if not voci:
        return None
    due = (date.fromisoformat(extraction.sentence_date) + timedelta(days=30)).isoformat()
    data = {
        "document": {
            "tipo_documento": "TD01",
            "tipo_documento_label": "Proforma",
            "numero_documento": "",
            "data_documento": extraction.sentence_date,
            "causale_oggetto": _sentenza_note(extraction, metadata) or "Proforma da sentenza",
            "documento_operativo": "PROFORMA",
            "fascicolo_label": _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "numero_rg", "")),
        },
        "payment": {
            "modalita_pagamento": "MP05",
            "modalita_pagamento_label": "Bonifico",
            "modalita_pagamento_codice": "MP05",
            "data_decorrenza": due,
            "giorni_termini": "30",
            "importo_pagamento": "",
        },
        "lex_sentenza": {
            "origin": ORIGIN,
            "document_key": _document_key(metadata),
            "document_id": _text(metadata.get("document_id")),
            "sha256": _text(metadata.get("sha256")),
            "filename": _text(metadata.get("filename") or metadata.get("original_filename")),
            "extraction": extraction.to_dict(),
        },
    }
    proforma = creator(
        id_cliente=id_cliente,
        id_fascicolo=_text(getattr(fascicolo, "id", "")),
        voci=voci,
        creato_da=actor,
        data_emissione=extraction.sentence_date,
        data_scadenza=due,
        applica_iva=True,
        applica_cassa=True,
        applica_ritenuta=False,
        applica_bollo=False,
        percentuale_spese_generali=15.0 if extraction.spese_generali else 0.0,
        note="Proforma predisposta automaticamente da Sentenza Tribunale indicizzata da Lex AI.",
        origine=ORIGIN,
        tipo_compenso="Liquidazione giudiziale",
        tipo_procedimento=_text(getattr(fascicolo, "tipo_procedimento", "")),
        valore_controversia=float(getattr(fascicolo, "valore_causa", 0.0) or 0.0),
        dati_personalizzati=data,
    )
    data["document"]["numero_documento"] = _text(getattr(proforma, "numero", ""))
    updater = getattr(fatturazione_repository, "aggiorna", None)
    if callable(updater):
        proforma = updater(_text(getattr(proforma, "id", "")), dati_personalizzati=data)
    return proforma


__all__ = [
    "AUTOMATION_KEY",
    "ORIGIN",
    "SENTENZA_VECTOR_SCHEMA_VERSION",
    "SentenzaAutomationOutcome",
    "SentenzaEconomicaExtraction",
    "SentenzaFascicoloContext",
    "analyze_sentenza_tribunale_text",
    "apply_sentenza_tribunale_automation",
    "apply_contributo_unificato_pdf_evidence",
    "extract_contributo_unificato_document_evidence",
    "sentenza_vector_relevant_excerpt",
    "validate_sentenza_fascicolo_context",
]
