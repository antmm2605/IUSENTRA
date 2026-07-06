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
SENTENZA_VECTOR_SCHEMA_VERSION = "sentenza_tribunale_compact_v4"
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
_MONEY_AMOUNT_PATTERN = r"(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[,.]\d{2})?"
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
_LIQUIDAZIONE_WORD_RE = re.compile(r"\bliquid(?:a|ando|ata|ato|ate|ati)\b", re.IGNORECASE)
_LIQUIDAZIONE_CONTEXT_RE = re.compile(
    r"\b(?:spese\s+di\s+lite|rifusione\s+delle\s+spese|compensi\s+professionali|onorari|"
    r"p\.?\s*q\.?\s*m\.?|definitivamente\s+pronunciando)\b",
    re.IGNORECASE,
)
_COMPENSI_AFTER_AMOUNT_RE = re.compile(
    r"^[\s,;:.]*(?:per|a\s+titolo\s+di)\s+(?:compensi(?:\s+professionali)?|onorari)\b",
    re.IGNORECASE | re.DOTALL,
)
_NON_COMPENSI_AFTER_AMOUNT_RE = re.compile(
    r"^[\s,;:.]*(?:per|a\s+titolo\s+di)\s+"
    r"(?:spese(?!\s+generali)|esbors[oi]|spese\s+vive|contribut[oi]\s+unificat[oi]|c\.?\s*u\.?)\b",
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
    r"\b(?:contributo\s+unificat[oi]|pagopa|pago\s*pa|ricevuta\s+pagamento|avviso\s+pagamento)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_LABEL_HINT_RE = re.compile(
    r"(?:^|[\s_.-])(?:c\.?\s*u\.?|cu|contributo\s+unificat[oi]|pagopa|pago\s*pa|ricevuta|avviso|f23|f24)(?:$|[\s_.-])",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_PAYMENT_ANCHOR_RE = re.compile(
    r"\b(?:pagopa|pago\s*pa|iuv|codice\s+(?:avviso|iuv)|identificativo\s+univoco\s+versamento|"
    r"ricevuta\s+(?:pagamento|telematica)|avviso\s+pagamento|esito\s+pagamento|"
    r"pagamento\s+(?:eseguito|effettuato|avvenuto)|versamento\s+(?:eseguito|effettuato)|"
    r"importo\s+(?:versato|pagato)|totale\s+(?:versato|pagato|da\s+pagare)|"
    r"rt\s*xml|f23|f24|punto\s+di\s+accesso|portale\s+servizi\s+telematici)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_PAYMENT_LABEL_RE = re.compile(
    r"\b(?:pagament[oi]|pagopa|pago\s*pa|ricevut[ae]|quietanz[ae]|versament[oi]|f23|f24)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_DUE_ANCHOR_RE = re.compile(
    r"\b(?:richiesta\s+(?:di\s+)?versamento|omesso\s+versamento|si\s+invita.{0,120}?a\s+pagare|"
    r"a\s+pagare\s+entro|somma\s+di\s+euro.{0,80}?per\s+omesso\s+versamento|"
    r"importo\s+da\s+pagare|totale\s+da\s+pagare|avviso\s+(?:di\s+)?pagamento)\b",
    re.IGNORECASE | re.DOTALL,
)
_CONTRIBUTO_DOCUMENT_NON_PAYMENT_SOURCE_RE = re.compile(
    r"\b(?:sentenza|ordinanza|decreto|verbale|ricorso|memoria|note\s+autorizzate|atto\s+introduttivo|"
    r"p\.?\s*q\.?\s*m\.?|in\s+nome\s+del\s+popolo\s+italiano|definitivamente\s+pronunciando|"
    r"liquidando|liquidazione|rifusione\s+delle\s+spese|carta\s+(?:elettronica|docente)|"
    r"aggiornamento\s+e\s+formazione\s+del\s+docente|importo\s+nominale|ann[oi]\s+scolastic[oi]|"
    r"dichiarazione\s+sostitutiva|autocertificazion[ei]|reddito|reddituale|isee|"
    r"nucleo\s+familiare|familiari\s+conviventi|d\.?\s*p\.?\s*r\.?\s*115|art\.?\s*76|"
    r"non\s+supera|limite\s+di\s+reddito|soglia\s+reddituale)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_SHORT_CU_RE = re.compile(r"\bc\.?\s*u\.?\b", re.IGNORECASE)
_CONTRIBUTO_DOCUMENT_SHORT_CU_CONTEXT_RE = re.compile(
    r"\b(?:contribut[oi]|unificat[oi]|pagament[oi]|versament[oi]|versat[aoie]?|pagat[aoie]?|"
    r"dovut[aoie]?|iscrizione\s+a\s+ruolo|spese\s+di\s+giustizia|d\.?\s*p\.?\s*r\.?\s*115|"
    r"art\.?\s*9)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_REJECT_RE = re.compile(
    r"\b(?:carta\s+(?:elettronica|docente)|aggiornamento\s+e\s+formazione\s+del\s+docente)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_AMOUNT_NOISE_RE = re.compile(
    r"\b(?:carta\s+(?:elettronica|docente)|aggiornamento\s+e\s+formazione|formazione\s+del\s+docente|"
    r"docent[ei]\s+di\s+ruolo|importo\s+nominale|ann[oi]\s+scolastic[oi]|reddito|reddituale|"
    r"nucleo\s+familiare|familiari\s+conviventi|dichiarazione\s+sostitutiva|autocertificazion[ei]|"
    r"d\.?\s*p\.?\s*r\.?\s*(?:115|445)|art\.?\s*76|non\s+supera(?:\s+l['’]?\s*importo)?|"
    r"limite\s+di\s+reddito|soglia\s+reddituale)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_SCAGLIONE_RE = re.compile(
    r"\b(?:scaglione|valore\s+(?:della\s+)?(?:domanda|causa|controversia)|"
    r"compreso\s+nello\s+scaglione|superiore\s+a|fino\s+a|tra\s+"
    + _MONEY_PREFIX_PATTERN
    + r")\b",
    re.IGNORECASE | re.DOTALL,
)
_CONTRIBUTO_DOCUMENT_DIRECT_NEAR_RE = re.compile(
    r"\b(?:importo|totale|pagamento|versamento|versato|pagato|dovuto|pari|"
    r"contributo\s+unificat[oi]|c\.?\s*u\.?)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_EXEMPT_RE = re.compile(
    r"\b(?:"
    r"contributo\s+unificat[oi]\s+non\s+dovut[oaie]|"
    r"non\s+dovut[oaie]\s+(?:il\s+)?contributo\s+unificat[oi]|"
    r"esente\s+dal\s+pagamento\s+(?:del\s+)?(?:contributo\s+unificat[oi]|c\.?\s*u\.?)|"
    r"esenzione\s+(?:(?:dal|del)\s+pagamento\s+)?(?:(?:dal|del)\s+)?(?:contributo\s+unificat[oi]|c\.?\s*u\.?)|"
    r"esenzione.{0,90}(?:iscrizione\s+a\s+ruolo|spese\s+di\s+giustizia)|"
    r"art\.?\s*9.{0,60}comma\s*1\s*[- ]?bis.{0,120}d\.?\s*p\.?\s*r\.?.{0,30}115|"
    r"d\.?\s*p\.?\s*r\.?.{0,30}115.{0,120}art\.?\s*9.{0,60}comma\s*1\s*[- ]?bis|"
    r"esente\s+(?:(?:dal|del)\s+)?(?:contributo\s+unificat[oi]|c\.?\s*u\.?)|"
    r"(?:ammess[aoie]\s+al|ammissione\s+al)\s+patrocinio\s+a\s+spese\s+dello\s+stato|"
    r"prenotazione\s+a\s+debito"
    r")\b",
    re.IGNORECASE,
)
_CONTRIBUTO_DOCUMENT_NOT_EXEMPT_RE = re.compile(
    r"\b(?:non\s+esente|nessuna\s+esenzione|esenzione\s+non\s+(?:riconosciuta|ammessa))\b",
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
_CONTRIBUTO_RT_PAYMENT_TYPE_RE = re.compile(
    r"\btipo\s+pagamento\s*:\s*contributo\s+unificat[oi]\b",
    re.IGNORECASE,
)
_CONTRIBUTO_RT_RECEIPT_RE = re.compile(
    r"\b(?:ricevuta\s+telematica\s+di\s+pagamento|rt\s*xml|pagopa|pago\s*pa)\b",
    re.IGNORECASE,
)
_CONTRIBUTO_RT_TOTAL_AMOUNT_RE = re.compile(
    r"\b(?:importo\s+totale\s+versato|importo\s+totale\s+pagato|totale\s+versato|totale\s+pagato)"
    r"\s*:\s*(?:" + _MONEY_PREFIX_PATTERN + r"\s*)?"
    r"(?P<amount>" + _MONEY_AMOUNT_PATTERN + r")",
    re.IGNORECASE,
)
_CONTRIBUTO_RT_DIRECT_AMOUNT_RE = re.compile(
    r"\bimporto\s*:\s*(?:" + _MONEY_PREFIX_PATTERN + r"\s*)?"
    r"(?P<amount>" + _MONEY_AMOUNT_PATTERN + r")",
    re.IGNORECASE,
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
    contributo_unificato_esente: bool = False
    spese_esborsi_importo: float | None = None
    spese_esborsi_titolo: str = ""
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
    meta = metadata or {}
    meta_text = " ".join(str(value or "") for value in meta.values()).casefold()
    raw_probe = raw_text[:240000].casefold()
    has_metadata_sentence_signal = any(token in meta_text for token in ("sentenza", "provvedimento"))
    if "sentenza" not in raw_probe and not has_metadata_sentence_signal:
        return SentenzaEconomicaExtraction(found=False)
    if "sentenza" not in raw_probe and not any(
        token in raw_probe
        for token in (
            "definitivamente pronunciando",
            "in nome del popolo italiano",
            "p.q.m",
            "p. q. m",
        )
    ):
        return SentenzaEconomicaExtraction(found=False)
    compact = _compact(raw_text)
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
    spese_esborsi_amount, spese_esborsi_title = _extract_contributo_unificato(compact)
    fondo_amount, fondo_title = _extract_amount_near(compact, _FONDO_PATTERNS)
    warnings: list[str] = []
    if fondo_amount is not None:
        if spese_esborsi_amount is None:
            spese_esborsi_amount = fondo_amount
            spese_esborsi_title = fondo_title
            warnings.append("fondo_spese_assorbito_in_spese_esborsi")
        elif abs(float(spese_esborsi_amount) - float(fondo_amount)) > 0.01:
            spese_esborsi_amount = fondo_amount
            spese_esborsi_title = fondo_title
            warnings.append("fondo_spese_preferito_come_spese_esborsi_unico")
        else:
            warnings.append("fondo_spese_non_duplicato_spese_esborsi")
        fondo_amount = None
        fondo_title = ""
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
        contributo_unificato_importo=None,
        contributo_unificato_titolo="",
        contributo_unificato_natura="",
        contributo_unificato_label="",
        spese_esborsi_importo=spese_esborsi_amount,
        spese_esborsi_titolo=spese_esborsi_title,
        fondo_spese_importo=fondo_amount,
        fondo_spese_titolo=fondo_title,
        beneficio_cliente_importo=beneficio_amount,
        beneficio_cliente_titolo=beneficio_title,
        beneficio_cliente_tipo=beneficio_tipo,
        spese_generali=bool(re.search(r"\bspese\s+generali\b", compact, re.IGNORECASE)),
        antistatario=bool(re.search(r"\bantistatari[oa]\b", compact, re.IGNORECASE)),
        warnings=warnings,
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
        cu_status = _contributo_payment_status(extraction)
        cu_changed = _upsert_payment(
            payments,
            "contributo_unificato",
            status=cu_status,
            amount=extraction.contributo_unificato_importo,
            date_iso=extraction.sentence_date if cu_status == "pagato" else "",
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
    elif extraction.contributo_unificato_esente:
        cu_changed = _upsert_payment(
            payments,
            "contributo_unificato",
            status="non_previsto",
            amount=None,
            date_iso="",
            note=extraction.contributo_unificato_titolo,
            operator=operator,
            now=now,
            document_key=document_key,
            extra={
                "natura": extraction.contributo_unificato_natura or "esenzione_contributo_unificato",
                "label": extraction.contributo_unificato_label or "Contributo unificato esente",
            },
        )
        if cu_changed:
            changes["payments"].append("contributo_unificato")

    spese_esborsi_amount = extraction.spese_esborsi_importo
    spese_esborsi_title = extraction.spese_esborsi_titolo
    if spese_esborsi_amount is None and extraction.fondo_spese_importo is not None:
        spese_esborsi_amount = extraction.fondo_spese_importo
        spese_esborsi_title = extraction.fondo_spese_titolo
    if spese_esborsi_amount is not None:
        spese_changed = _upsert_payment(
            payments,
            "spese_esborsi",
            status="pagato",
            amount=spese_esborsi_amount,
            date_iso=extraction.sentence_date,
            note=spese_esborsi_title,
            operator=operator,
            now=now,
            document_key=document_key,
            extra={
                "natura": "spese_esborsi",
                "label": "Spese/esborsi",
            },
        )
        if spese_changed:
            changes["payments"].append("spese_esborsi")

    if "fondo_spese" in payments:
        del payments["fondo_spese"]
        if "spese_esborsi" not in changes["payments"]:
            changes["payments"].append("spese_esborsi")

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


def _document_label_detection_text(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    raw = re.sub(r"[_]+", " ", raw)
    raw = re.sub(r"(?<=[A-Za-zÀ-ÿ])[-]+(?=[A-Za-zÀ-ÿ])", " ", raw)
    return _compact(raw)


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
    digits = re.sub(r"\D+", "", raw)
    return digits.lstrip("0") or ("0" if digits else "")


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
    compensation_candidates: list[tuple[int, re.Match[str]]] = []
    for money in _MONEY_RE.finditer(text):
        amount = _parse_money(money.group("amount"))
        if amount is None:
            continue
        after = text[money.end() : min(len(text), money.end() + 120)]
        if not _COMPENSI_AFTER_AMOUNT_RE.match(after):
            continue
        context = text[max(0, money.start() - 260) : min(len(text), money.end() + 180)]
        if not (_LIQUIDAZIONE_WORD_RE.search(context) or _LIQUIDAZIONE_CONTEXT_RE.search(context)):
            continue
        before = text[max(0, money.start() - 260) : money.start()]
        liquidazione_words = list(_LIQUIDAZIONE_WORD_RE.finditer(before))
        distance = money.start() - liquidazione_words[-1].start() if liquidazione_words else 9999
        compensation_candidates.append((distance, money))
    if compensation_candidates:
        _, match = min(compensation_candidates, key=lambda item: (item[0], item[1].start()))
        return _parse_money(match.group("amount")), _snippet(text, match.start(), match.end(), window=180)

    total_candidates: list[tuple[int, re.Match[str]]] = []
    for match in _LIQUIDAZIONE_RE.finditer(text):
        amount = _parse_money(match.group("amount"))
        if amount is None:
            continue
        amount_end = match.end("amount")
        after = text[amount_end : min(len(text), amount_end + 90)]
        if _NON_COMPENSI_AFTER_AMOUNT_RE.match(after):
            continue
        total_candidates.append((match.start(), match))
    if not total_candidates:
        return None, ""
    _, match = min(total_candidates, key=lambda item: item[0])
    return _parse_money(match.group("amount")), _snippet(text, match.start(), match.end(), window=90)


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
    if natura == "richiesta_versamento_contributo_unificato":
        return "Contributo unificato da pagare"
    if natura == "esenzione_contributo_unificato":
        return "Contributo unificato esente"
    return "Spese da recuperare"


def _contributo_voice_description(extraction: SentenzaEconomicaExtraction) -> str:
    if extraction.contributo_unificato_natura == "contributo_unificato":
        return "Contributo unificato riconosciuto in sentenza"
    if extraction.contributo_unificato_natura == "pdf_contributo_unificato":
        return "Contributo unificato confermato da PDF nel fascicolo"
    if extraction.contributo_unificato_natura == "spese_esborsi":
        return "Spese ed esborsi riconosciuti in sentenza"
    return "Spese da recuperare riconosciute in sentenza"


def _contributo_payment_status(extraction: SentenzaEconomicaExtraction) -> str:
    if extraction.contributo_unificato_natura == "richiesta_versamento_contributo_unificato":
        return "da_registrare"
    return "pagato"


def _contributo_is_billable(extraction: SentenzaEconomicaExtraction) -> bool:
    return extraction.contributo_unificato_importo is not None and _contributo_payment_status(extraction) == "pagato"


def _contributo_voice_tokens(extraction: SentenzaEconomicaExtraction) -> tuple[str, ...]:
    if extraction.contributo_unificato_natura in {"contributo_unificato", "pdf_contributo_unificato"}:
        return ("contributo", "unificato", "c u")
    return ("spese", "esborsi")


def _spese_esborsi_voice_description() -> str:
    return "Spese ed esborsi riconosciuti in sentenza"


def _spese_esborsi_voice_tokens() -> tuple[str, ...]:
    return ("spese", "esborsi")


def _contributo_document_candidate_rejected(compact: str, match: re.Match[str]) -> bool:
    amount_start = match.start("amount")
    amount_end = match.end("amount")
    snippet = _snippet(compact, match.start(), match.end(), window=70)
    if _CONTRIBUTO_DOCUMENT_REJECT_RE.search(snippet):
        return True
    amount_context = compact[max(0, amount_start - 150) : min(len(compact), amount_end + 90)]
    if _CONTRIBUTO_DOCUMENT_AMOUNT_NOISE_RE.search(amount_context):
        return True
    left = compact[max(0, amount_start - 140) : amount_start]
    near_left = compact[max(0, amount_start - 75) : amount_start]
    plain_left = _plain(left)
    plain_near_left = _plain(near_left)
    if re.search(r"\b(?:scaglione|compreso|superiore|fino|tra)\b", plain_near_left):
        return True
    if "valore" in plain_left and "scaglione" in plain_left:
        return True
    if "valore" in plain_near_left and not _CONTRIBUTO_DOCUMENT_DIRECT_NEAR_RE.search(near_left):
        return True
    near = compact[max(0, amount_start - 85) : min(len(compact), amount_end + 45)]
    if _CONTRIBUTO_DOCUMENT_SCAGLIONE_RE.search(near):
        return True
    return False


def _contributo_document_has_short_cu_context(value: str) -> bool:
    for match in _CONTRIBUTO_DOCUMENT_SHORT_CU_RE.finditer(value):
        snippet = _snippet(value, match.start(), match.end(), window=90)
        if _CONTRIBUTO_DOCUMENT_SHORT_CU_CONTEXT_RE.search(snippet):
            return True
    return False


def _contributo_document_has_hint(value: str) -> bool:
    return bool(_CONTRIBUTO_DOCUMENT_HINT_RE.search(value) or _contributo_document_has_short_cu_context(value))


def _contributo_document_label_has_hint(value: str) -> bool:
    return bool(_CONTRIBUTO_DOCUMENT_LABEL_HINT_RE.search(value))


def _contributo_document_label_is_payment_evidence(value: str) -> bool:
    return bool(
        _contributo_document_label_has_hint(value)
        and _CONTRIBUTO_DOCUMENT_PAYMENT_LABEL_RE.search(value)
        and not _contributo_document_has_due_anchor(value)
    )


def _contributo_document_has_payment_anchor(value: str) -> bool:
    return bool(_CONTRIBUTO_DOCUMENT_PAYMENT_ANCHOR_RE.search(value))


def _contributo_document_has_due_anchor(value: str) -> bool:
    return bool(_CONTRIBUTO_DOCUMENT_DUE_ANCHOR_RE.search(value))


def _contributo_document_is_non_payment_source(label: str, compact: str) -> bool:
    label_plain = _plain(label)
    probe = f"{label_plain} {_plain(compact[:5000])}"
    if _CONTRIBUTO_DOCUMENT_NON_PAYMENT_SOURCE_RE.search(probe):
        return True
    return bool(_STRUCTURAL_SENTENCE_SIGNAL_RE.search(compact[:5000]))


def _contributo_document_amount_has_direct_context(compact: str, match: re.Match[str]) -> bool:
    amount_start = match.start("amount")
    amount_end = match.end("amount")
    context = compact[max(0, amount_start - 120) : min(len(compact), amount_end + 70)]
    if _contributo_document_has_payment_anchor(context) or _contributo_document_has_due_anchor(context):
        return True
    if not re.search(r"\bcontributo\s+unificat[oi]\b|\bc\.?\s*u\.?\b", context, re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"\b(?:importo\s+(?:versato|pagato|dovuto)|pagamento\s+(?:eseguito|effettuato|avvenuto)|"
            r"versamento\s+(?:eseguito|effettuato)|totale\s+(?:versato|pagato|da\s+pagare))\b",
            context,
            re.IGNORECASE,
        )
    )


def _extract_contributo_exemption_evidence(compact: str, metadata: dict[str, Any]) -> dict[str, Any]:
    if _CONTRIBUTO_DOCUMENT_NOT_EXEMPT_RE.search(compact):
        return {}
    match = _CONTRIBUTO_DOCUMENT_EXEMPT_RE.search(compact)
    if not match:
        return {}
    title = _snippet(compact, match.start(), match.end(), window=90)
    return {
        "esente": True,
        "importo": None,
        "titolo": title,
        "natura": "esenzione_contributo_unificato",
        "label": "Contributo unificato esente",
        "filename": _text(metadata.get("filename") or metadata.get("original_filename") or metadata.get("safe_filename")),
        "document_id": _text(metadata.get("document_id") or metadata.get("documento_id")),
        "sha256": _text(metadata.get("sha256")),
        "origine": "pdf_contributo_unificato_esente",
    }


def _extract_contributo_rt_payment_evidence(compact: str, metadata: dict[str, Any]) -> dict[str, Any]:
    if not _CONTRIBUTO_RT_PAYMENT_TYPE_RE.search(compact):
        return {}
    if not _CONTRIBUTO_RT_RECEIPT_RE.search(compact):
        return {}
    for pattern in (_CONTRIBUTO_RT_TOTAL_AMOUNT_RE, _CONTRIBUTO_RT_DIRECT_AMOUNT_RE):
        match = pattern.search(compact)
        if not match:
            continue
        amount = _parse_money(match.group("amount"))
        if amount is None:
            continue
        return {
            "importo": amount,
            "titolo": _compact(match.group(0)),
            "natura": "pdf_contributo_unificato",
            "label": "Contributo unificato da ricevuta PagoPA",
            "status": "pagato",
            "filename": _text(metadata.get("filename") or metadata.get("original_filename") or metadata.get("safe_filename")),
            "document_id": _text(metadata.get("document_id") or metadata.get("documento_id")),
            "sha256": _text(metadata.get("sha256")),
            "origine": "ricevuta_telematica_pagopa_contributo_unificato",
        }
    return {}


def extract_contributo_unificato_document_evidence(
    text: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Legge l'importo da un PDF dedicato a CU/PagoPA senza confonderlo con Carta docente."""

    meta = metadata or {}
    raw_label = " ".join(
        _text(meta.get(key))
        for key in ("filename", "original_filename", "safe_filename", "tipo_documento", "classification")
    )
    label = _document_label_detection_text(raw_label)
    compact = _compact(f"{label} {_text(text)}")
    probe = f"{label} {compact}"
    exemption = _extract_contributo_exemption_evidence(compact, meta)
    label_has_hint = _contributo_document_label_has_hint(label)
    has_payment_anchor = _contributo_document_has_payment_anchor(probe)
    has_due_anchor = _contributo_document_has_due_anchor(probe)
    non_payment_source = _contributo_document_is_non_payment_source(label, compact)
    if exemption:
        return exemption
    rt_payment = _extract_contributo_rt_payment_evidence(compact, meta)
    if rt_payment:
        return rt_payment
    if not label_has_hint and not has_payment_anchor and not has_due_anchor:
        return {}
    if non_payment_source and not has_payment_anchor and not has_due_anchor:
        return exemption
    candidates: list[tuple[int, re.Match[str]]] = []
    for match in _CONTRIBUTO_DOCUMENT_AMOUNT_RE.finditer(compact):
        snippet = _snippet(compact, match.start(), match.end(), window=60)
        if _contributo_document_candidate_rejected(compact, match):
            continue
        if not _contributo_document_amount_has_direct_context(compact, match):
            continue
        priority = 0 if re.search(r"\bcontributo\s+unificat[oi]\b|\bc\.?\s*u\.?\b", snippet, re.IGNORECASE) else 1
        candidates.append((priority, match))
    if not candidates:
        money = list(_MONEY_RE.finditer(compact))
        if len(money) != 1:
            if _contributo_document_label_is_payment_evidence(label) and not non_payment_source:
                filename = _text(meta.get("filename") or meta.get("original_filename") or meta.get("safe_filename"))
                return {
                    "importo": None,
                    "titolo": "Pagamento contributo unificato classificato nel fascicolo",
                    "natura": "pdf_contributo_unificato",
                    "label": "Contributo unificato pagato",
                    "status": "pagato",
                    "filename": filename,
                    "document_id": _text(meta.get("document_id") or meta.get("documento_id")),
                    "sha256": _text(meta.get("sha256")),
                    "origine": "classificazione_documento_contributo_unificato",
                }
            return {}
        match = money[0]
        if _contributo_document_candidate_rejected(compact, match):
            return {}
        if non_payment_source and not has_payment_anchor and not has_due_anchor:
            return {}
        if not _contributo_document_amount_has_direct_context(compact, match) and not label_has_hint:
            return {}
    else:
        _, match = min(candidates, key=lambda item: (item[0], item[1].start()))
    amount = _parse_money(match.group("amount"))
    if amount is None:
        return {}
    due_evidence = has_due_anchor and not re.search(
        r"\b(?:ricevuta\s+(?:pagamento|telematica)|pagamento\s+(?:eseguito|effettuato|avvenuto)|"
        r"versamento\s+(?:eseguito|effettuato)|importo\s+(?:versato|pagato)|"
        r"totale\s+(?:versato|pagato)|esito\s+pagamento)\b",
        compact,
        re.IGNORECASE,
    )
    return {
        "importo": amount,
        "titolo": _snippet(compact, match.start(), match.end(), window=70),
        "natura": "richiesta_versamento_contributo_unificato" if due_evidence else "pdf_contributo_unificato",
        "label": "Contributo unificato da pagare" if due_evidence else "Contributo unificato da PDF",
        "status": "da_registrare" if due_evidence else "pagato",
        "filename": _text(meta.get("filename") or meta.get("original_filename") or meta.get("safe_filename")),
        "document_id": _text(meta.get("document_id") or meta.get("documento_id")),
        "sha256": _text(meta.get("sha256")),
        "origine": "richiesta_versamento_contributo_unificato" if due_evidence else "pdf_contributo_unificato",
    }


def apply_contributo_unificato_pdf_evidence(
    extraction: SentenzaEconomicaExtraction,
    metadata: dict[str, Any],
) -> None:
    raw = metadata.get("contributo_unificato_pdf")
    if not isinstance(raw, dict):
        return
    filename = _text(raw.get("filename") or raw.get("document_id") or "PDF contributo unificato")
    title = _text(raw.get("titolo")) or f"Evidenza confermata da {filename}"
    if raw.get("esente") is True or _text(raw.get("natura")) == "esenzione_contributo_unificato":
        extraction.contributo_unificato_importo = None
        extraction.contributo_unificato_titolo = f"{title} (fonte: {filename})"
        extraction.contributo_unificato_natura = "esenzione_contributo_unificato"
        extraction.contributo_unificato_label = _text(raw.get("label")) or "Contributo unificato esente"
        extraction.contributo_unificato_esente = True
        if "contributo_unificato_esente_da_pdf" not in extraction.warnings:
            extraction.warnings.append("contributo_unificato_esente_da_pdf")
        return
    amount = _parse_money(str(raw.get("importo") or ""))
    if amount is None:
        return
    title = _text(raw.get("titolo")) or f"Importo confermato da {filename}"
    extraction.contributo_unificato_esente = False
    if extraction.spese_esborsi_importo is not None:
        if abs(float(extraction.spese_esborsi_importo) - amount) <= 0.01:
            extraction.spese_esborsi_importo = None
            extraction.spese_esborsi_titolo = ""
            extraction.warnings.append("spese_esborsi_riclassificate_cu_pdf")
        else:
            extraction.warnings.append("contributo_unificato_pdf_distinto_da_spese_sentenza")
    if extraction.contributo_unificato_importo is None:
        extraction.contributo_unificato_importo = amount
        extraction.contributo_unificato_titolo = f"{title} (fonte: {filename})"
        extraction.contributo_unificato_natura = _text(raw.get("natura")) or "pdf_contributo_unificato"
        extraction.contributo_unificato_label = _text(raw.get("label")) or _contributo_recovery_label(extraction.contributo_unificato_natura)
        extraction.warnings.append("contributo_unificato_da_pdf")
        return
    if abs(float(extraction.contributo_unificato_importo) - amount) <= 0.01:
        raw_natura = _text(raw.get("natura"))
        if raw_natura in {"pdf_contributo_unificato", "richiesta_versamento_contributo_unificato"}:
            extraction.contributo_unificato_natura = raw_natura
            extraction.contributo_unificato_label = _text(raw.get("label")) or _contributo_recovery_label(raw_natura)
        elif not extraction.contributo_unificato_natura:
            extraction.contributo_unificato_natura = _classify_contributo_recovery(extraction.contributo_unificato_titolo)
            extraction.contributo_unificato_label = _contributo_recovery_label(extraction.contributo_unificato_natura)
        confirmation_label = "PDF contributo unificato"
        if f"confermato da {confirmation_label}" not in extraction.contributo_unificato_titolo:
            extraction.contributo_unificato_titolo = (
                f"{extraction.contributo_unificato_titolo} - confermato da {confirmation_label}: {filename}"
            ).strip(" -")
        extraction.warnings.append("contributo_unificato_confermato_pdf")
        return
    sentenza_amount = extraction.contributo_unificato_importo
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
    esborsi_amount, esborsi_title = _extract_amount_near(text, _ESBORSI_PATTERNS, window=110)
    if esborsi_amount is not None and not _sentenza_spese_context_is_cu(esborsi_title):
        return esborsi_amount, esborsi_title
    spese_match = _SPESE_LITE_QUOTA_RE.search(text)
    if spese_match:
        title = _snippet(text, spese_match.start(), spese_match.end(), window=70)
        if not _sentenza_spese_context_is_cu(title):
            return _parse_money(spese_match.group("amount")), title
    return None, ""


def _is_valid_contributo_unificato_before(between: str) -> bool:
    compact_between = _compact(between)
    if not compact_between or _CU_BACKWARD_REJECT_RE.search(compact_between):
        return False
    return bool(_CU_BACKWARD_ACCEPT_RE.search(compact_between))


def _sentenza_spese_context_is_cu(value: str) -> bool:
    return any(pattern.search(value) for pattern in _CU_PATTERNS)


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
    if _contributo_is_billable(extraction) and not _has_voice(
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
    spese_esborsi_amount = extraction.spese_esborsi_importo
    if spese_esborsi_amount is None:
        spese_esborsi_amount = extraction.fondo_spese_importo
    if spese_esborsi_amount is not None and not _has_voice(
        voci,
        spese_esborsi_amount,
        _spese_esborsi_voice_tokens(),
    ):
        voci.append(
            VoceParcella(
                descrizione=_spese_esborsi_voice_description(),
                quantita=1.0,
                prezzo_unitario=spese_esborsi_amount,
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
    if _contributo_is_billable(extraction):
        voci.append(
            VoceParcella(
                descrizione=_contributo_voice_description(extraction),
                quantita=1.0,
                prezzo_unitario=extraction.contributo_unificato_importo,
                tipo="ANTICIPO",
            )
        )
    spese_esborsi_amount = extraction.spese_esborsi_importo
    if spese_esborsi_amount is None:
        spese_esborsi_amount = extraction.fondo_spese_importo
    if spese_esborsi_amount is not None:
        voci.append(
            VoceParcella(
                descrizione=_spese_esborsi_voice_description(),
                quantita=1.0,
                prezzo_unitario=spese_esborsi_amount,
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
