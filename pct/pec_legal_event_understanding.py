"""Comprensione professionale V2 degli eventi legali letti da PEC.

Il modulo resta deterministico-first: aggrega parser PEC, OCR/allegati, report
di validazione, udienze da remoto, proponente termini e workflow legale. Lex/LLM
puo' usare questo JSON come memoria strutturata, ma non diventa fonte unica per
azioni dispositive o termini processuali conclusivi.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from pct.pec_legal_deadline_proposer import propose_legal_deadline
from pct.pec_legal_workflow import classifica_pec_legale, estrai_registri

SCHEMA = "iusentra.pec.legal_event_understanding.v2"
RULEPACK_VERSION = "legal_pec_rules_v2026_07"
DEFAULT_RULEPACK_PATH = Path(__file__).with_name("data") / f"{RULEPACK_VERSION}.json"

_RULEPACK_CACHE: dict[str, dict[str, Any]] = {}
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
_TEAMS_RE = re.compile(r"https?://(?:teams\.microsoft\.com|[^/\s<>\"']+\.teams\.microsoft\.com)/[^\s<>\"']+", re.I)
_MEETING_ID_RE = re.compile(r"(?i)(?:ID\s*(?:riunione|meeting)|Meeting\s*ID)\s*[:\-]?\s*([0-9\s]{6,})")
_PASSCODE_RE = re.compile(r"(?i)(?:passcode|password|codice)\s*[:\-]?\s*([A-Za-z0-9._-]{3,})")
_AULA_RE = re.compile(r"(?i)\baula\s+([A-Za-z0-9][A-Za-z0-9./_-]{0,20})")
_PIANO_RE = re.compile(r"(?i)\b(?:piano|livello)\s+([A-Za-z0-9][A-Za-z0-9./_-]{0,20})")
_EURO_RE = re.compile(r"(?i)(?:€|euro)\s*([0-9]{1,3}(?:[.\s][0-9]{3})*(?:,[0-9]{2})|[0-9]+(?:,[0-9]{2})?)")
_CU_RE = re.compile(
    r"(?i)(?:contributo\s+unificato|c\.?\s*u\.?|contributi\s+unificati)[^€\n\r]{0,80}(?:€|euro)\s*"
    r"([0-9]{1,3}(?:[.\s][0-9]{3})*(?:,[0-9]{2})|[0-9]+(?:,[0-9]{2})?)"
)
_ESBORSI_RE = re.compile(
    r"(?i)(?:di\s+cui\s+)?(?:€|euro)\s*([0-9]{1,3}(?:[.\s][0-9]{3})*(?:,[0-9]{2})|[0-9]+(?:,[0-9]{2})?)\s+"
    r"(?:per\s+)?(?:esborsi|spese\s+vive|spese)"
)
_LIQUIDA_RE = re.compile(
    r"(?i)(?:liquid[ao](?:ndo)?|liquidata|liquidate)[^€\n\r]{0,120}(?:complessiva\s+somma\s+di\s+)?(?:€|euro)\s*"
    r"([0-9]{1,3}(?:[.\s][0-9]{3})*(?:,[0-9]{2})|[0-9]+(?:,[0-9]{2})?)"
)


def load_rulepack(path: str | Path | None = None) -> dict[str, Any]:
    resolved = str(path or DEFAULT_RULEPACK_PATH)
    cached = _RULEPACK_CACHE.get(resolved)
    if cached is None:
        cached = json.loads(Path(resolved).read_text(encoding="utf-8"))
        _RULEPACK_CACHE[resolved] = cached
    return cached


def _clean(value: Any, limit: int = 0) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()
    return text[:limit].rstrip() if limit and len(text) > limit else text


def _norm(value: Any) -> str:
    return _clean(value).lower()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _message_date(value: Any) -> str:
    text = _clean(value, 80)
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10] if re.match(r"\d{4}-\d{2}-\d{2}", text) else text


def _field_value(parsed: dict[str, Any], *names: str) -> Any:
    fields = _dict(parsed.get("fields"))
    for name in names:
        value = _dict(fields.get(name)).get("value")
        if value not in (None, ""):
            return value
    return ""


def _body_text(parsed: dict[str, Any], report: dict[str, Any] | None = None) -> str:
    body = _dict(parsed.get("body"))
    headers = _dict(parsed.get("headers"))
    pieces: list[str] = [
        headers.get("subject") or "",
        body.get("text") or "",
        body.get("html_text") or "",
        " ".join(str(item) for item in _list(body.get("href_urls"))),
        body.get("ics_text") or "",
    ]
    profile = _dict(parsed.get("procedural_profile"))
    for key in ("messaggio_operativo", "descrizione_evento", "oggetto_evento", "udienza_data_ora", "modalita_udienza"):
        pieces.append(str(profile.get(key) or ""))
    report = _dict(report)
    if isinstance(report.get("procedural_profile"), dict):
        pieces.append(json.dumps(report.get("procedural_profile"), ensure_ascii=False))
    return "\n".join(part for part in pieces if str(part or "").strip())


def _attachment_sources(parsed: dict[str, Any], attachments: Iterable[dict[str, Any]] | None) -> tuple[list[str], list[str], float | None]:
    names: list[str] = []
    sources: list[str] = []
    coverages: list[float] = []
    for item in [*_list(parsed.get("attachments")), *(list(attachments or []))]:
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("filename") or item.get("nome") or item.get("nome_file"), 240)
        if name and name not in names:
            names.append(name)
        if item.get("ocr_text"):
            sources.append(f"ocr:{name or item.get('sha256') or 'allegato'}")
        try:
            if item.get("ocr_coverage") is not None:
                coverages.append(float(item.get("ocr_coverage") or 0.0))
        except (TypeError, ValueError):
            pass
    parsed_sources = []
    if _dict(parsed.get("body")).get("text"):
        parsed_sources.append("body:text")
    if _dict(parsed.get("body")).get("html_text"):
        parsed_sources.append("body:html")
    if _dict(parsed.get("body")).get("href_urls"):
        parsed_sources.append("body:html_href")
    if _dict(parsed.get("body")).get("ics_text"):
        parsed_sources.append("body:ics")
    return names, [*parsed_sources, *sources], (sum(coverages) / len(coverages) if coverages else None)


def _evidence(source: str, text: str, *, confidence: float = 0.75) -> dict[str, Any]:
    return {"source": _clean(source, 160), "text": _clean(text, 260), "confidence": confidence}


def _money(value: str) -> float | None:
    cleaned = _clean(value).replace(".", "").replace(" ", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _amount(match: re.Match[str] | None) -> float | None:
    return _money(match.group(1)) if match else None


def _extract_links(text: str, remote_report: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    links: list[dict[str, Any]] = []
    for item in _list(remote_report.get("links")):
        if not isinstance(item, dict):
            continue
        url = _clean(item.get("url"), 1200)
        if url and url not in seen:
            seen.add(url)
            links.append(
                {
                    "url": url,
                    "source": _clean(item.get("source") or "remote_hearing_profile", 180),
                    "verified": bool(item.get("exact_match") or item.get("exact") or remote_report.get("verified")),
                    "platform": _platform_from_url(url),
                }
            )
    for pattern, source in ((_TEAMS_RE, "testo/href Teams"), (_URL_RE, "testo/href")):
        for match in pattern.finditer(text or ""):
            url = match.group(0).rstrip(").,;")
            if url and url not in seen:
                seen.add(url)
                links.append({"url": url, "source": source, "verified": _is_trusted_hearing_url(url), "platform": _platform_from_url(url)})
    return links


def _platform_from_url(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    if "teams.microsoft.com" in host:
        return "Microsoft Teams"
    if "zoom.us" in host:
        return "Zoom"
    if "meet.google" in host:
        return "Google Meet"
    return "altra" if host else ""


def _is_trusted_hearing_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host.endswith("teams.microsoft.com") or host.endswith("zoom.us") or host.endswith("meet.google.com")


def _hearing_mode(text: str, remote_report: dict[str, Any], links: list[dict[str, Any]]) -> str:
    lower = _norm(text)
    explicit = _clean(remote_report.get("mode_unified") or remote_report.get("mode"))
    if explicit in {"presenza", "remoto", "mista", "note_scritte", "incerta"}:
        return explicit
    if any(token in lower for token in ("127-ter", "127 ter", "trattazione scritta", "note scritte")):
        return "note_scritte"
    if any(token in lower for token in ("udienza mista", "aula mvc", "parte in presenza e parte da remoto")):
        return "mista"
    if links or any(token in lower for token in ("da remoto", "collegamento audiovisivo", "videoconferenza", "teams", "id riunione", "meeting id")):
        return "remoto"
    if any(token in lower for token in ("in presenza", "aula", "piano", "presso il tribunale", "comparizione personale")):
        return "presenza"
    return "incerta" if "udienza" in lower else ""


def _extract_time(text: str, remote_report: dict[str, Any], profile: dict[str, Any]) -> str | None:
    for value in _list(remote_report.get("times")):
        match = re.search(r"\b([01]?\d|2[0-3])[:.][0-5]\d\b", str(value or ""))
        if match:
            return match.group(0).replace(".", ":")
    for value in (profile.get("udienza_data_ora"), text):
        match = re.search(r"\b(?:ore\s*)?([01]?\d|2[0-3])[:.][0-5]\d\b", str(value or ""), re.I)
        if match:
            return match.group(0).lower().replace("ore", "").strip().replace(".", ":")
    return None


def _extract_hearing_date(parsed: dict[str, Any], profile: dict[str, Any]) -> str | None:
    raw = _clean(profile.get("udienza_data_ora"), 120)
    iso = _message_date(raw)
    if re.match(r"\d{4}-\d{2}-\d{2}", iso):
        return iso[:10]
    for item in _list(parsed.get("procedural_dates")):
        if not isinstance(item, dict):
            continue
        kind = _norm(item.get("deadline_kind") or item.get("kind") or item.get("label"))
        if "udienza" in kind:
            value = _message_date(item.get("date"))
            if re.match(r"\d{4}-\d{2}-\d{2}", value):
                return value[:10]
    return None


def _build_hearings(parsed: dict[str, Any], report: dict[str, Any], text: str) -> list[dict[str, Any]]:
    remote = _dict(report.get("remote_hearing")) or _dict(_dict(report.get("procedural_profile")).get("remote_hearing"))
    if not remote and isinstance(_dict(report.get("deadline_proposal")).get("remote_hearing"), dict):
        remote = _dict(_dict(report.get("deadline_proposal")).get("remote_hearing"))
    links = _extract_links(text, remote)
    mode = _hearing_mode(text, remote, links)
    if not mode:
        return []
    profile = _dict(parsed.get("procedural_profile")) or _dict(report.get("procedural_profile"))
    meeting_id = (_MEETING_ID_RE.search(text or "") or [None, ""])[1] if _MEETING_ID_RE.search(text or "") else None
    passcode = (_PASSCODE_RE.search(text or "") or [None, ""])[1] if _PASSCODE_RE.search(text or "") else None
    aula = (_AULA_RE.search(text or "") or [None, ""])[1] if _AULA_RE.search(text or "") else None
    piano = (_PIANO_RE.search(text or "") or [None, ""])[1] if _PIANO_RE.search(text or "") else None
    date_value = _extract_hearing_date(parsed, profile)
    time_value = _extract_time(text, remote, profile)
    first_link = links[0] if links else {}
    review = mode in {"remoto", "mista"} and not links
    return [
        {
            "date": date_value,
            "time": time_value,
            "mode": mode,
            "platform": first_link.get("platform") or ("Microsoft Teams" if "teams" in _norm(text) else None),
            "link": first_link.get("url") or None,
            "link_verified": bool(first_link.get("verified")),
            "meeting_id": _clean(meeting_id) or None,
            "passcode": _clean(passcode) or None,
            "aula": _clean(aula).strip(".,;:") or None,
            "piano": _clean(piano).strip(".,;:") or None,
            "indirizzo": _clean(profile.get("indirizzo") or profile.get("ufficio"), 180) or None,
            "judge": _clean(profile.get("giudice"), 120) or None,
            "agenda_action": "create" if date_value else "verify",
            "web_push_safe_title": "P0 - Udienza da remoto senza link trovato" if review else "Udienza da presidiare",
            "human_review_required": review or not date_value,
            "evidence": [_evidence(first_link.get("source") or "PEC", first_link.get("url") or mode, confidence=0.85 if links else 0.65)],
        }
    ]


def _deadline_from_legal_proposal(proposal: dict[str, Any]) -> dict[str, Any] | None:
    if not proposal:
        return None
    ok = bool(proposal.get("ok"))
    return {
        "deadline_type": _clean(proposal.get("azione") or proposal.get("template_code") or "termine_da_verificare", 180),
        "norma": _clean(proposal.get("norma"), 120),
        "duration_value": proposal.get("durata"),
        "duration_unit": "giorni" if str(proposal.get("unita") or "").startswith("day") else _clean(proposal.get("unita"), 30) or "giorni",
        "dies_a_quo_type": _clean(proposal.get("dies_a_quo_type"), 40) or "incerto",
        "dies_a_quo_date": proposal.get("dies_a_quo_date"),
        "direction": "backward" if proposal.get("direzione") == "backward" else "forward",
        "peremptory": True if proposal.get("tipo") == "perentorio" else None,
        "suggested_priority": "P0" if proposal.get("tipo") == "perentorio" else "P1",
        "create_in_scadenziario": ok,
        "requires_deterministic_calculation": True,
        "human_review_required": True,
        "evidence": [_evidence("legal_deadline_proposal", proposal.get("explanation") or proposal.get("reason") or proposal.get("azione") or "", confidence=float(proposal.get("confidence") or 0.75))],
    }


def _build_deadlines(parsed: dict[str, Any], report: dict[str, Any], text: str, *, dies_a_quo_date: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    proposal_container = _dict(report.get("deadline_proposal"))
    legal = proposal_container.get("legal_deadline_proposal")
    if not isinstance(legal, dict):
        event_type = _clean(_dict(parsed.get("legal_workflow")).get("event_type"))
        legal = propose_legal_deadline(text, dies_a_quo_date=dies_a_quo_date or _field_value(parsed, "data_consegna", "data_invio"), event_type=event_type)
    deadlines: list[dict[str, Any]] = []
    if isinstance(legal, dict):
        item = _deadline_from_legal_proposal(legal)
        if item:
            deadlines.append(item)
    lower = _norm(text)
    if any(token in lower for token in ("127-bis", "127 bis", "collegamento audiovisivo")):
        deadlines.append(
            {
                "deadline_type": "Richiesta udienza in presenza ex art. 127-bis c.p.c.",
                "norma": "Art. 127-bis c.p.c.",
                "duration_value": 5,
                "duration_unit": "giorni",
                "dies_a_quo_type": "comunicazione",
                "dies_a_quo_date": _message_date(dies_a_quo_date) or None,
                "direction": "forward",
                "peremptory": None,
                "suggested_priority": "P1",
                "create_in_scadenziario": True,
                "requires_deterministic_calculation": True,
                "human_review_required": True,
                "evidence": [_evidence("testo PEC", "Udienza audiovisiva/127-bis rilevata", confidence=0.75)],
            }
        )
    if "deposito sentenza" in lower or "pubblicazione sentenza" in lower:
        deadlines.append(
            {
                "deadline_type": "Esame sentenza senza termine breve automatico",
                "norma": "Art. 133 c.p.c. / art. 325 c.p.c.",
                "duration_value": None,
                "duration_unit": "giorni",
                "dies_a_quo_type": "notificazione",
                "dies_a_quo_date": None,
                "direction": "forward",
                "peremptory": None,
                "suggested_priority": "P1",
                "create_in_scadenziario": False,
                "requires_deterministic_calculation": True,
                "human_review_required": True,
                "evidence": [_evidence("regola art. 133 c.p.c.", "La sola comunicazione di deposito sentenza non fa decorrere il termine breve.", confidence=0.95)],
            }
        )
    return deadlines, legal if isinstance(legal, dict) else None


def _extract_payments(text: str) -> list[dict[str, Any]]:
    lower = _norm(text)
    payments: list[dict[str, Any]] = []
    if any(token in lower for token in ("patrocinio a spese dello stato", "gratuito patrocinio", "d.p.r. 115/2002", "dpr 115/2002", "siamm", "lsg", "decreto di pagamento")):
        payments.append(
            {
                "payment_event_type": "gratuito_patrocinio",
                "beneficiary": "avvocato",
                "payer": "Erario",
                "lawyer_direct_credit": True,
                "amounts": {"compensi": None, "esborsi": None, "spese_generali_15": None, "cpa": None, "iva": None, "totale_testuale": _amount(_LIQUIDA_RE.search(text)), "totale_stimato": None},
                "workflow_action": "Aprire workflow liquidazione spese di giustizia LSG/SIAMM.",
                "human_review_required": True,
                "evidence": [_evidence("testo PEC/provvedimento", "Patrocinio a spese dello Stato o decreto di pagamento rilevato.", confidence=0.85)],
            }
        )
    if re.search(r"(?i)\bcompensa\s+(?:integralmente|parzialmente)?\s*le\s+spese|spese\s+compensate\b", text or ""):
        payments.append(
            {
                "payment_event_type": "nessuno",
                "beneficiary": "incerto",
                "payer": None,
                "lawyer_direct_credit": False,
                "amounts": {"compensi": None, "esborsi": None, "spese_generali_15": None, "cpa": None, "iva": None, "totale_testuale": None, "totale_stimato": None},
                "workflow_action": "Non aprire incasso automatico: spese compensate o ridotte.",
                "human_review_required": True,
                "evidence": [_evidence("testo sentenza", "Spese compensate rilevate.", confidence=0.85)],
            }
        )
        return payments
    has_spese = re.search(r"(?i)\b(condanna.*spese|liquid[ao].*spese|compensi|esborsi|spese\s+generali|iva|cpa|accessori)\b", text or "")
    if has_spese:
        direct = bool(re.search(r"(?i)\b(distrae|distrazione|antistatario|procuratore\s+antistatario|in\s+favore\s+dell['’]?\s*avv)\b", text or ""))
        total = _amount(_LIQUIDA_RE.search(text)) or (_money(_EURO_RE.findall(text)[0]) if _EURO_RE.findall(text) else None)
        esborsi = _amount(_ESBORSI_RE.search(text))
        compensi = round(total - esborsi, 2) if total is not None and esborsi is not None and total >= esborsi else total
        payments.append(
            {
                "payment_event_type": "spese_distratte_avvocato" if direct else "spese_parte",
                "beneficiary": "avvocato" if direct else "parte",
                "payer": None,
                "lawyer_direct_credit": direct,
                "amounts": {
                    "compensi": compensi,
                    "esborsi": esborsi,
                    "spese_generali_15": None,
                    "cpa": None,
                    "iva": None,
                    "totale_testuale": total,
                    "totale_stimato": total,
                },
                "workflow_action": "Aprire pratica incasso avvocato." if direct else "Registrare credito spese della parte; non assumere pagamento diretto avvocato.",
                "human_review_required": True,
                "evidence": [_evidence("testo sentenza", has_spese.group(0), confidence=0.8)],
            }
        )
    cu = _amount(_CU_RE.search(text))
    if cu is not None:
        payments.append(
            {
                "payment_event_type": "contributo_unificato",
                "beneficiary": "parte",
                "payer": None,
                "lawyer_direct_credit": False,
                "amounts": {"compensi": None, "esborsi": None, "spese_generali_15": None, "cpa": None, "iva": None, "totale_testuale": cu, "totale_stimato": cu},
                "workflow_action": "Registrare contributo unificato/spesa documentata solo se confermata da documento CU o dispositivo.",
                "human_review_required": True,
                "evidence": [_evidence("testo sentenza/CU", "Contributo unificato rilevato.", confidence=0.75)],
            }
        )
    return payments


def _pct_receipts(parsed: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    receipt = _dict(parsed.get("pct_deposit_receipt"))
    lifecycle = _dict(report.get("deposit_lifecycle"))
    current = _dict(lifecycle.get("current_stage"))
    stage = _clean(current.get("id") or receipt.get("receipt_stage") or receipt.get("stage"))
    ignored_stages = {"deposito_da_ricondurre", "not_applicable", "non_applicabile"}
    meaningful_receipt = bool(receipt) and (not stage or stage not in ignored_stages)
    meaningful_lifecycle = bool(stage) and stage not in ignored_stages
    if not (meaningful_receipt or meaningful_lifecycle):
        return {
            "is_pct_receipt": False,
            "receipt_stage": None,
            "deposit_chain_status": "not_applicable",
            "can_close_deposit_workflow": False,
            "blocking_errors": [],
            "evidence": [],
        }
    blocking = []
    text = " ".join(
        str(value or "")
        for value in (
            stage,
            receipt.get("receipt_stage"),
            receipt.get("stage"),
            receipt.get("status"),
            current.get("label"),
            current.get("status"),
            current.get("outcome"),
        )
    ).lower()
    if any(token in text for token in ("rifiuto", "notifica eccezione", "errore fatale", "mancata consegna")):
        blocking.append("Esito PCT/PEC critico da verificare subito.")
    complete = stage == "accettazione_deposito" and not blocking
    return {
        "is_pct_receipt": True,
        "receipt_stage": stage or None,
        "deposit_chain_status": "complete" if complete else "error" if blocking else "incomplete" if receipt or lifecycle else "not_applicable",
        "can_close_deposit_workflow": complete,
        "blocking_errors": blocking,
        "evidence": [_evidence("pct_deposit_receipt", current.get("label") or stage or "catena PCT non applicabile", confidence=0.8)],
    }


def _classify(parsed: dict[str, Any], text: str, attachment_names: list[str]) -> dict[str, Any]:
    workflow = _dict(parsed.get("legal_workflow"))
    if not workflow:
        headers = _dict(parsed.get("headers"))
        workflow = classifica_pec_legale(
            subject=str(headers.get("subject") or ""),
            body=text,
            sender=str(headers.get("from") or ""),
            attachments=[{"filename": name} for name in attachment_names],
            message_id=str(headers.get("message_id") or ""),
        )
    family = _clean(workflow.get("family"))
    event = _clean(workflow.get("event_type"))
    events = [event] if event else []
    lower = _norm(text)
    additional = [
        ("deposito_sentenza", ("deposito sentenza", "pubblicazione sentenza")),
        ("sentenza_con_distrazione_spese", ("distrae", "antistatario", "procuratore antistatario")),
        ("sentenza_con_spese_compensate", ("compensa le spese", "spese compensate")),
        ("udienza_sostituita_da_note_scritte", ("127-ter", "trattazione scritta", "note scritte")),
        ("decreto_171_bis", ("171-bis", "171 bis")),
        ("memorie_171_ter", ("171-ter", "171 ter")),
        ("nomina_ctu", ("nomina ctu", "consulente tecnico d'ufficio")),
        ("rifiuto_deposito", ("rifiuto deposito", "deposito rifiutato")),
    ]
    for code, keywords in additional:
        if any(keyword in lower for keyword in keywords) and code not in events:
            events.append(code)
    confidence = float(workflow.get("confidence") or (0.78 if event else 0.45))
    return {
        "family": family or "pec_non_riconosciuta",
        "events": events,
        "primary_event": event or (events[0] if events else "evento_ambiguo_revisione"),
        "confidence": confidence,
        "human_review_required": bool(workflow.get("human_review_required", True)),
        "reason": _clean(workflow.get("azione_proposta") or workflow.get("event_label") or "Evento da presidiare", 360),
    }


def _priority(classification: dict[str, Any], deadlines: list[dict[str, Any]], hearings: list[dict[str, Any]], payments: list[dict[str, Any]], pct: dict[str, Any]) -> str:
    if pct.get("blocking_errors"):
        return "P0"
    if any(item.get("mode") in {"remoto", "mista"} and not item.get("link") for item in hearings):
        return "P0"
    if any(item.get("suggested_priority") == "P0" for item in deadlines):
        return "P0"
    if any(item.get("peremptory") for item in deadlines):
        return "P1"
    if payments:
        return "P1"
    if hearings or deadlines:
        return "P1"
    primary = str(classification.get("primary_event") or "")
    return "P0" if primary in {"rifiuto_deposito", "mancata_consegna_pec"} else "P2"


def _actions(classification: dict[str, Any], deadlines: list[dict[str, Any]], hearings: list[dict[str, Any]], payments: list[dict[str, Any]], pct: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for hearing in hearings:
        actions.append(
            {
                "action_type": "agenda",
                "title": "Udienza da registrare in agenda" if hearing.get("agenda_action") == "create" else "Udienza da verificare",
                "description": "Riportare data, ora, modalità e link/aula nel fascicolo e in agenda.",
                "priority": "P0" if hearing.get("mode") in {"remoto", "mista"} and not hearing.get("link") else "P1",
                "due_hint": hearing.get("date"),
                "requires_lawyer_confirmation": True,
            }
        )
        if hearing.get("mode") in {"remoto", "mista"} and not hearing.get("link"):
            actions.append(
                {
                    "action_type": "notifica_web_push",
                    "title": "Udienza da remoto senza link trovato",
                    "description": "Avvisare subito senza dati sensibili nella push.",
                    "priority": "P0",
                    "due_hint": hearing.get("date"),
                    "requires_lawyer_confirmation": False,
                }
            )
    for deadline in deadlines:
        actions.append(
            {
                "action_type": "scadenziario",
                "title": deadline.get("deadline_type") or "Termine da verificare",
                "description": "Il motore deterministico deve calcolare o confermare il termine prima della registrazione conclusiva.",
                "priority": deadline.get("suggested_priority") or "P1",
                "due_hint": deadline.get("dies_a_quo_date"),
                "requires_lawyer_confirmation": True,
            }
        )
    for payment in payments:
        if payment.get("payment_event_type") != "nessuno":
            actions.append(
                {
                    "action_type": "incasso",
                    "title": "Pagamento/liquidazione da presidiare",
                    "description": payment.get("workflow_action") or "Verificare beneficiario, importi e documento fonte.",
                    "priority": "P1",
                    "due_hint": None,
                    "requires_lawyer_confirmation": True,
                }
            )
    if pct.get("is_pct_receipt") and not pct.get("can_close_deposit_workflow"):
        actions.append(
            {
                "action_type": "task_avvocato",
                "title": "Catena deposito PCT da completare",
                "description": "Non chiudere il deposito finché accettazione, consegna, controlli automatici e accettazione cancelleria non sono coerenti.",
                "priority": "P0" if pct.get("blocking_errors") else "P1",
                "due_hint": None,
                "requires_lawyer_confirmation": True,
            }
        )
    actions.append(
        {
            "action_type": "lex_ingest",
            "title": "Memoria Lex strutturata",
            "description": "Alimentare Lex con evento, evidenze e limiti di inferenza.",
            "priority": _priority(classification, deadlines, hearings, payments, pct),
            "due_hint": None,
            "requires_lawyer_confirmation": False,
        }
    )
    return actions


def _safe_title(priority: str, classification: dict[str, Any], hearings: list[dict[str, Any]], deadlines: list[dict[str, Any]], payments: list[dict[str, Any]]) -> str:
    if any(item.get("mode") in {"remoto", "mista"} and not item.get("link") for item in hearings):
        return "P0 - Udienza da remoto senza link trovato"
    if any(item.get("peremptory") for item in deadlines):
        return "Termine perentorio rilevato in PEC"
    if payments:
        return f"{priority} - Provvedimento con importi da verificare"
    primary = _clean(classification.get("primary_event") or "evento legale", 60).replace("_", " ")
    return f"{priority} - {primary.capitalize()}"


def build_legal_event_understanding(
    parsed: dict[str, Any],
    report: dict[str, Any] | None = None,
    *,
    dies_a_quo_date: str = "",
    attachments: Iterable[dict[str, Any]] | None = None,
    rulepack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce il JSON V2 unico per PEC, Lex, audit, agenda e scadenziario.

    La funzione non invia PEC, non deposita atti e non calcola termini conclusivi:
    estrae fatti, proposte e rischi con evidenze e revisione umana obbligatoria nei
    casi critici.
    """

    parsed = _dict(parsed)
    report = _dict(report)
    rules = rulepack or load_rulepack()
    headers = _dict(parsed.get("headers"))
    attachment_names, text_sources, ocr_confidence = _attachment_sources(parsed, attachments)
    text = _body_text(parsed, report)
    if attachments:
        text = "\n".join(
            [
                text,
                "\n".join(_clean(item.get("ocr_text"), 20000) for item in attachments if isinstance(item, dict) and item.get("ocr_text")),
            ]
        )
    classification = _classify(parsed, text, attachment_names)
    profile = _dict(parsed.get("procedural_profile"))
    registri = _list(_dict(parsed.get("legal_workflow")).get("registri")) or estrai_registri(text)
    first_registry = registri[0] if registri and isinstance(registri[0], dict) else {}
    if not dies_a_quo_date:
        dies_a_quo_date = str(_field_value(parsed, "data_consegna", "data_invio") or headers.get("date") or "")
    hearings = _build_hearings(parsed, report, text)
    deadlines, legacy_deadline = _build_deadlines(parsed, report, text, dies_a_quo_date=dies_a_quo_date)
    payments = _extract_payments(text)
    pct = _pct_receipts(parsed, report)
    priority = _priority(classification, deadlines, hearings, payments, pct)
    actions = _actions(classification, deadlines, hearings, payments, pct)
    human_review = bool(
        classification.get("human_review_required")
        or any(item.get("human_review_required") for item in hearings)
        or any(item.get("human_review_required") for item in deadlines)
        or any(item.get("human_review_required") for item in payments)
        or pct.get("blocking_errors")
        or priority in {"P0", "P1"}
    )
    source_hashes = [str(item.get("sha256") or "") for item in _list(parsed.get("attachments")) if isinstance(item, dict) and item.get("sha256")]
    result = {
        "schema": SCHEMA,
        "language": "it",
        "input_quality": {
            "ocr_confidence": ocr_confidence,
            "text_sources_used": text_sources,
            "missing_sources": [] if text_sources else ["testo_pec_non_disponibile"],
            "warnings": [] if text else ["Nessun testo utile disponibile: revisione umana obbligatoria."],
        },
        "message": {
            "message_id": _clean(headers.get("message_id") or parsed.get("message_id"), 160),
            "received_at": _clean(headers.get("date"), 80),
            "sender": _clean(headers.get("from"), 180),
            "subject_normalized": _clean(headers.get("subject"), 240),
            "tenant_safe": True,
        },
        "procedimento": {
            "ufficio": _clean(profile.get("ufficio"), 180) or None,
            "sezione": _clean(profile.get("sezione"), 120) or None,
            "giudice": _clean(profile.get("giudice"), 120) or None,
            "rg_numero": first_registry.get("numero") or profile.get("numero_rg") or None,
            "rg_anno": first_registry.get("anno") or profile.get("anno_rg") or None,
            "registro": first_registry.get("registro_normalizzato") or profile.get("registro") or None,
            "canale": first_registry.get("canale") or None,
            "parti": _list(profile.get("parti_processuali")) or _list(profile.get("soggetti_parti")),
        },
        "classification": classification,
        "deadlines": deadlines,
        "hearings": hearings,
        "payments": payments,
        "pct_receipts": pct,
        "actions": actions,
        "lex_memory": {
            "summary_for_lex": _clean(
                f"{classification.get('primary_event')} - priorità {priority}. "
                f"Udienze: {len(hearings)}; termini: {len(deadlines)}; pagamenti: {len(payments)}.",
                500,
            ),
            "facts": [
                *[f"Evento rilevato: {item}" for item in _list(classification.get("events"))],
                *([f"Udienza {hearings[0].get('mode')} rilevata"] if hearings else []),
                *([f"Pagamento/liquidazione: {payments[0].get('payment_event_type')}"] if payments else []),
            ],
            "do_not_infer": [
                "Non inviare PEC, depositare atti o chiudere workflow senza conferma umana.",
                "Non assumere decorrenza del termine breve di impugnazione dalla sola comunicazione di deposito sentenza.",
                "Non assumere pagamento diretto all'avvocato senza distrazione o titolo equivalente.",
                "Non applicare regole civili automatiche a penale, PAT, PTT o SIGIT senza ruleset dedicato.",
            ],
            "source_hashes": source_hashes,
        },
        "audit": {
            "rulepack_version": str(rules.get("version") or RULEPACK_VERSION),
            "model_should_not_be_sole_source": True,
            "evidence_count": sum(len(_list(item.get("evidence"))) for item in [*deadlines, *hearings, *payments, pct]),
            "unresolved_issues": [
                *([hearing.get("web_push_safe_title") for hearing in hearings if hearing.get("human_review_required")]),
                *([deadline.get("deadline_type") for deadline in deadlines if deadline.get("human_review_required")]),
            ],
        },
        "human_review_required": human_review,
        "priority": priority,
        "web_push_safe_title": _safe_title(priority, classification, hearings, deadlines, payments),
    }
    # Compatibilita' con la prima integrazione V2 gia' esposta dalle API.
    result["hearing"] = hearings[0] if hearings else None
    result["deadline"] = legacy_deadline
    result["pct_receipt"] = pct
    result["event_sha256"] = _sha256_json(result)
    return result


__all__ = ["build_legal_event_understanding", "load_rulepack", "SCHEMA", "RULEPACK_VERSION"]
