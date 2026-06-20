"""Automazione economia fascicolo da sentenze indicizzate per Lex AI."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pct.fascicoli import AvanzamentoPratica, StatoFascicolo
from pct.fatturazione import StatoParcella, VoceParcella


ORIGIN = "lex_ai_sentenza_tribunale"
AUTOMATION_KEY = "_sentenza_tribunale_lex_ai"
ROME = ZoneInfo("Europe/Rome")

_SENTENZA_DATE_RE = re.compile(
    r"\bsentenza\s+n\.?\s*(?P<num>\d+)\s*/\s*(?P<year>\d{4}).{0,120}?"
    r"\bpubbl(?:icata|icato|\.?)\s*(?:il)?\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE | re.DOTALL,
)
_RG_RE = re.compile(r"\bR\.?\s*G\.?\s*n\.?\s*(?P<num>[\d.]+)\s*/\s*(?P<year>\d{4})", re.IGNORECASE)
_MONEY_RE = re.compile(
    r"(?:\u20ac|EUR)\s*(?P<amount>\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:[,.]\d{2})?)",
    re.IGNORECASE,
)
_LIQUIDAZIONE_RE = re.compile(
    r"\bliquid(?:a|ando|ata|ato|ate|ati)\b.{0,160}?"
    r"(?:complessiv[aoe]\s+)?(?:somma|importo)\s+(?:di\s+)?(?:\u20ac|EUR)\s*"
    r"(?P<amount>\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:[,.]\d{2})?)",
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
    fondo_spese_importo: float | None = None
    fondo_spese_titolo: str = ""
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


def analyze_sentenza_tribunale_text(text: str, metadata: dict[str, Any] | None = None) -> SentenzaEconomicaExtraction:
    """Estrae data e importi da una sentenza del Tribunale con regole deterministiche."""

    raw_text = str(text or "")
    compact = _compact(raw_text)
    meta = metadata or {}
    meta_text = " ".join(str(value or "") for value in meta.values()).casefold()
    date_match = _SENTENZA_DATE_RE.search(compact)
    has_sentence_signal = bool(date_match) or "sentenza" in meta_text
    has_tribunal_signal = "tribunale" in compact.casefold() or "tribunale" in meta_text
    has_document_type_signal = any(token in meta_text for token in ("sentenza", "provvedimento"))

    if not date_match or not has_sentence_signal:
        return SentenzaEconomicaExtraction(found=False)
    if not (has_tribunal_signal or has_document_type_signal):
        return SentenzaEconomicaExtraction(found=False, warnings=["Documento con intestazione sentenza, ma senza classificazione Tribunale."])

    sentence_date = _parse_italian_date(date_match.group("date"))
    if not sentence_date:
        return SentenzaEconomicaExtraction(found=False, warnings=["Data sentenza non leggibile."])

    rg_match = _RG_RE.search(compact)
    liquidation_amount, liquidation_title = _extract_liquidazione(compact)
    cu_amount, cu_title = _extract_amount_near(compact, _CU_PATTERNS)
    fondo_amount, fondo_title = _extract_amount_near(compact, _FONDO_PATTERNS)

    return SentenzaEconomicaExtraction(
        found=True,
        sentence_date=sentence_date,
        sentence_number=str(date_match.group("num") or "").strip(),
        sentence_year=str(date_match.group("year") or "").strip(),
        rg_number=str(rg_match.group("num") or "").strip() if rg_match else "",
        rg_year=str(rg_match.group("year") or "").strip() if rg_match else "",
        liquidazione_importo=liquidation_amount,
        liquidazione_titolo=liquidation_title,
        contributo_unificato_importo=cu_amount,
        contributo_unificato_titolo=cu_title,
        fondo_spese_importo=fondo_amount,
        fondo_spese_titolo=fondo_title,
        spese_generali=bool(re.search(r"\bspese\s+generali\b", compact, re.IGNORECASE)),
        antistatario=bool(re.search(r"\bantistatari[oa]\b", compact, re.IGNORECASE)),
    )


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
        proforma_id = _text(getattr(proforma, "id", ""))

        parcella_changed = _upsert_payment(
            payments,
            "parcella",
            status="da_emettere",
            amount=None,
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


def _text(value: Any, default: str = "") -> str:
    raw = str(value if value is not None else "").strip()
    return raw or default


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _now_rome() -> str:
    return datetime.now(ROME).replace(microsecond=0).isoformat()


def _parse_italian_date(value: str) -> str:
    raw = _text(value)
    try:
        return datetime.strptime(raw, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return ""


def _parse_money(value: str) -> float | None:
    raw = _text(value).replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
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


def _document_key(metadata: dict[str, Any]) -> str:
    for key in ("document_id", "documento_id", "source_id", "sha256", "filename"):
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
    comparable_keys = {"status", "importo", "data_pagamento", "note", "proforma_id", "proforma_number"}
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
                descrizione="Contributo unificato e spese vive riconosciute in sentenza",
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
    "SentenzaAutomationOutcome",
    "SentenzaEconomicaExtraction",
    "analyze_sentenza_tribunale_text",
    "apply_sentenza_tribunale_automation",
]
