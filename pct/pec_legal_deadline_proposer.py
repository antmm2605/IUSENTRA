"""Proponente-termini legali per la PEC (deterministico).

Estrae dal testo della PEC la norma citata, il tipo di dies a quo e la direzione,
risolve la norma nel template versionato e delega il CALCOLO della data al motore
deterministico `termini_processuali.ItalianDeadlineCalculator` (avanti/a ritroso,
sospensione feriale, audit). **Non calcola date da solo** e **non è mai fonte unica**:
propone, con revisione umana obbligatoria; il motore scadenziario persiste.

Regole bloccanti (fonti certe):
- `deposito_sentenza` ⇒ nessun termine breve ex art. 325 dalla sola comunicazione
  (art. 133 c.p.c.);
- "assegna termine" senza durata chiara ⇒ revisione umana, nessun calcolo.

Ambito: civile. Penale/PAT/PTT/SIGIT ⇒ nessun calcolo automatico (ruleset dedicato assente).
Controversie di lavoro e previdenza: nessuna sospensione feriale (art. 3 L. 742/1969,
art. 92 R.D. 12/1941), riconosciute con `is_labour_matter` come in `pec_provvedimento_terms`.

Ogni proposta porta la `provenienza` (versione e file del ruleset, parola chiave
riconosciuta con il passaggio di testo, modello e versione, norma) che la pipeline
PEC persiste nella Scadenza per la verifica professionale.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pct.pec_provvedimento_terms import is_labour_matter
from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator


DEFAULT_RULESET_PATH = Path(__file__).with_name("data") / "legal_pec_deadline_rules_v2026_07.json"
_RULESET_CACHE: dict[str, dict[str, Any]] = {}
_TEMPLATES_BY_CODE = {template.code: template for template in DEFAULT_TEMPLATES}


def load_ruleset(path: str | Path | None = None) -> dict[str, Any]:
    resolved = str(path or DEFAULT_RULESET_PATH)
    cached = _RULESET_CACHE.get(resolved)
    if cached is None:
        cached = json.loads(Path(resolved).read_text(encoding="utf-8"))
        # Nome del file di regole, per la provenienza delle proposte (chiave tecnica interna).
        cached.setdefault("_rule_file", Path(resolved).name)
        _RULESET_CACHE[resolved] = cached
    return cached


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _has_any(text_norm: str, markers: tuple[str, ...]) -> bool:
    return any(_norm(marker) in text_norm for marker in markers)


_DECISION_SENTENCE_MARKERS = (
    "sentenza a verbale",
    "sentenza in nome del popolo italiano",
    "decide la causa con sentenza",
    "decide con sentenza",
    "sentenza resa ex art. 429",
    "sentenza resa ex art. 429 cpc",
)

_WRITTEN_TREATMENT_MARKERS = (
    "127-ter",
    "127 ter",
    "trattazione scritta",
    "note scritte",
    "sostituzione dell'udienza",
)

_PROSPECTIVE_127_TER_MARKERS = (
    "sostituisce l'udienza",
    "in sostituzione dell'udienza",
    "assegna un termine perentorio",
    "deposito note scritte",
    "deposito delle note",
    "note contenenti istanze e conclusioni",
    "ciascuna parte costituita può opporsi",
    "ciascuna parte costituita puo' opporsi",
    "possono opporsi",
    "può opporsi",
    "puo' opporsi",
    "entro cinque giorni dalla comunicazione",
    "entro 5 giorni dalla comunicazione",
    # Il provvedimento che dispone la trattazione scritta è quello da cui decorre
    # l'opposizione (art. 127-ter co. 2 c.p.c.): «dispone» guarda avanti, una
    # sentenza che richiama il 127-ter come modalità già svolta non lo usa.
    "dispone la trattazione scritta",
    "disposta la trattazione scritta",
    "disporre la trattazione scritta",
    "depositare le note scritte",
    "assegna termine per note",
    "assegna alle parti termine",
)


def _is_sentence_decision_context(text_norm: str) -> bool:
    if _has_any(text_norm, _DECISION_SENTENCE_MARKERS):
        return True
    has_judgment_noun = "sentenza" in text_norm
    has_decisive_outcome = _has_any(
        text_norm,
        (
            "definitivamente decidendo",
            "accerta il diritto",
            "condanna",
            "liquida",
            "rigetta",
            "accoglie",
        ),
    )
    has_judicial_context = _has_any(
        text_norm,
        ("tribunale", "il giudice", "la corte", "p.q.m.", "p. q. m.", "pqm", "dispositivo"),
    )
    return has_judgment_noun and has_decisive_outcome and has_judicial_context


def _is_prospective_127_ter_context(text_norm: str) -> bool:
    return _has_any(text_norm, _PROSPECTIVE_127_TER_MARKERS)


def _sentence_decision_review_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "human_review_required": True,
        "reason": (
            "Il testo è una sentenza/provvedimento decisorio che cita il 127-ter come modalità "
            "dell'udienza già svolta: non proporre opposizione alla trattazione scritta; "
            "aprire presidio post-sentenza e valutare eventuale notifica della sentenza."
        ),
        "norma": "Art. 133 c.p.c. / artt. 325-326 c.p.c. / art. 429 c.p.c.",
        "template_code": "",
        "azione": "Valutare/preparare notifica sentenza",
    }


_DATA_PUBBLICAZIONE = r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"
_PUBBLICAZIONE = re.compile(
    r"\b(?:depositat[ao]|pubblicat[ao]|data\s+(?:di\s+|del\s+)?(?:deposito|pubblicazione))\b[^.\n]{0,40}?\b"
    + _DATA_PUBBLICAZIONE + r"\b"
    + r"|\bin\s+data\s+" + _DATA_PUBBLICAZIONE + r"\s*,?\s*(?:è|e'|e)\s+stat[ao]\s+(?:depositat[ao]|pubblicat[ao])\b",
    re.IGNORECASE,
)


def _termine_lungo_327(text: str, *, labour: bool | None = None) -> dict[str, Any] | None:
    """Termine lungo di impugnazione (art. 327 c.p.c.): sei mesi dalla pubblicazione della sentenza.

    La comunicazione di cancelleria non fa decorrere alcun termine: né il breve (art. 325), né il lungo.
    Il termine lungo decorre dalla pubblicazione, cioè dal deposito della sentenza (art. 133 c.p.c.), e vale
    se la sentenza non viene notificata. Si calcola solo dalla data di deposito letta nel testo; se manca,
    resta un promemoria senza data da completare con la data di deposito. Sospensione feriale salvo lavoro
    e previdenza (art. 3 L. 742/1969).
    """
    trovata = _PUBBLICAZIONE.search(str(text or ""))
    pubblicazione: date | None = None
    if trovata:
        giorno, mese, anno = (int(parte) for parte in trovata.groups() if parte is not None)
        try:
            pubblicazione = date(anno, mese, giorno)
        except ValueError:
            pubblicazione = None
    if pubblicazione is None:
        if trovata:
            return None
        return {
            "ok": False,
            "human_review_required": True,
            "tipo": "perentorio",
            "azione": "Impugnazione della sentenza — termine lungo: indicare la data di deposito",
            "norma": "Art. 327 c.p.c.",
            "template_code": "",
            "reason": (
                "Sentenza depositata: il termine lungo di sei mesi decorre dalla data di deposito (pubblicazione, "
                "art. 133 c.p.c.), non dalla comunicazione di cancelleria. La data di deposito non si legge nella "
                "comunicazione: indicarla per calcolare il termine."
            ),
        }
    template = _TEMPLATES_BY_CODE.get("CIV_APPELLO_LUNGO")
    if template is None:
        return None
    lavoro = is_labour_matter(text) if labour is None else bool(labour)
    result = ItalianDeadlineCalculator().calculate(
        pubblicazione, template.base_value, direction="forward", template_code=template.code,
        template_name=template.name, template_version=template.version, period_type="months",
        matter_type="labor" if lavoro else template.matter_type, suspend_august=not lavoro,
        reference_law=template.reference_law,
    )
    return {
        **result,
        "ok": True,
        "tipo": "perentorio",
        "azione": "Impugnazione della sentenza — termine lungo (se la sentenza non viene notificata)",
        "norma": "Art. 327 c.p.c.",
        "template_code": template.code,
        "dies_a_quo_type": "pubblicazione",
        "dies_a_quo_date": pubblicazione.isoformat(),
        "deadline": result["deadline"],
        "raw_deadline": result.get("rawDeadline"),
        "human_review_required": True,
        "confidence": 0.8,
        "explanation": (
            f"Sei mesi dalla pubblicazione (data di deposito letta nella comunicazione: {pubblicazione.strftime('%d/%m/%Y')})"
            f"{'' if lavoro else ', con la sospensione feriale'}. Se la sentenza viene notificata vale il termine "
            "breve dell'art. 325 c.p.c. dalla notifica."
        ),
    }


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text[:len(fmt) + 2], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _resolve_rule_match(text_norm: str, ruleset: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Regola riconosciuta e parola chiave che l'ha attivata."""

    for rule in ruleset.get("regole", []):
        for kw in rule.get("keywords", []):
            if _norm(kw) and _norm(kw) in text_norm:
                return rule, str(kw)
    return None, ""


def _resolve_rule(text_norm: str, ruleset: dict[str, Any]) -> dict[str, Any] | None:
    return _resolve_rule_match(text_norm, ruleset)[0]


_SNIPPET_MARGINE = 60


def _matched_snippet(text_norm: str, keyword: str) -> str:
    """Breve passaggio del testo (normalizzato) attorno alla parola chiave riconosciuta."""

    kw = _norm(keyword)
    pos = text_norm.find(kw) if kw else -1
    if pos < 0:
        return ""
    start = max(0, pos - _SNIPPET_MARGINE)
    end = min(len(text_norm), pos + len(kw) + _SNIPPET_MARGINE)
    return ("…" if start else "") + text_norm[start:end] + ("…" if end < len(text_norm) else "")


def _provenienza(rules: dict[str, Any], rule: dict[str, Any], template: Any, keyword: str, text_norm: str) -> dict[str, Any]:
    return {
        "ruleset_version": str(rules.get("version") or ""),
        "rule_file": str(rules.get("_rule_file") or "ruleset_fornito"),
        "matched_keyword": keyword,
        "matched_snippet": _matched_snippet(text_norm, keyword),
        "template_code": template.code,
        "template_version": int(template.version),
        "reference_law": template.reference_law,
        "articolo": str(rule.get("articolo") or template.reference_law),
    }


def propose_legal_deadline(
    text: str,
    *,
    dies_a_quo_date: Any,
    event_type: str = "",
    ruleset: dict[str, Any] | None = None,
    labour: bool | None = None,
) -> dict[str, Any] | None:
    """Propone un termine LEGALE calcolato dal motore deterministico, o None se non
    riconosciuto. Ogni proposta porta `human_review_required=True` (mai definitiva).

    ``labour``: controversia di lavoro/previdenza; se None si riconosce dal testo.
    """

    rules = ruleset or load_ruleset()
    text_norm = _norm(text)
    if event_type in {"pct_deposito", "ricevuta_accettazione", "ricevuta_consegna", "esito_controlli", "accettazione_deposito"}:
        return None  # a deposit receipt does not communicate a new judicial order

    sentence_decision_context = event_type in {"sentenza_a_verbale_429", "deposito_sentenza"} or _is_sentence_decision_context(text_norm)
    if (
        sentence_decision_context
        and _has_any(text_norm, _WRITTEN_TREATMENT_MARKERS)
        and not _is_prospective_127_ter_context(text_norm)
    ):
        return _sentence_decision_review_payload()

    blocco = rules.get("blocco_art_325", {})
    is_deposito_sentenza = event_type in {"deposito_sentenza", "sentenza_a_verbale_429"} or any(
        _norm(kw) in text_norm for kw in blocco.get("keywords", [])
    )

    rule, matched_keyword = _resolve_rule_match(text_norm, rules)
    if rule is None and is_deposito_sentenza:
        return _termine_lungo_327(text, labour=labour)
    if rule is None:
        if any(_norm(kw) in text_norm for kw in rules.get("assegnazione_generica_keywords", [])):
            return {
                "ok": False,
                "human_review_required": True,
                "reason": "Termine assegnato dal giudice senza durata chiara: revisione umana.",
                "norma": "",
                "template_code": "",
            }
        return None

    template = _TEMPLATES_BY_CODE.get(str(rule.get("template_code") or ""))
    if template is None:
        return None
    if template.code == "CIV_OPPOSIZIONE_127_TER" and not _is_prospective_127_ter_context(text_norm):
        return None
    provenienza = _provenienza(rules, rule, template, matched_keyword, text_norm)


    if (
        sentence_decision_context
        and template.code == "CIV_OPPOSIZIONE_127_TER"
        and not _is_prospective_127_ter_context(text_norm)
    ):
        return _sentence_decision_review_payload()

    # Regola #1 (art. 133/325): la sola comunicazione di deposito sentenza NON fa
    # decorrere il termine breve. Se la PEC è un deposito sentenza e la regola è un
    # termine breve ex art. 325, blocca sempre: il breve parte dalla notificazione
    # (evento distinto), mai dalla comunicazione di cancelleria.
    if template.reference_law.startswith("Art. 325") and is_deposito_sentenza:
        lungo = _termine_lungo_327(text, labour=labour)
        if lungo is not None:
            return lungo
        return {
            "ok": False,
            "human_review_required": True,
            "reason": blocco.get("regola", "Termine breve non calcolabile dalla sola comunicazione."),
            "norma": template.reference_law,
            "template_code": template.code,
            "provenienza": provenienza,
        }

    dies = _parse_date(dies_a_quo_date)
    if dies is None:
        return {
            "ok": False,
            "human_review_required": True,
            "reason": "Data di decorrenza (dies a quo) non disponibile o non riconosciuta.",
            "norma": template.reference_law,
            "template_code": template.code,
            "provenienza": provenienza,
        }

    # Lavoro e previdenza: la sospensione feriale non si applica (art. 3 L. 742/1969,
    # art. 92 R.D. 12/1941). Il motore lo registra in rulesApplied (matter_type="labor").
    lavoro = is_labour_matter(text) if labour is None else bool(labour)
    senza_feriale_lavoro = lavoro and template.suspend_august
    result = ItalianDeadlineCalculator().calculate(
        dies,
        template.base_value,
        direction=template.direction,
        template_code=template.code,
        template_name=template.name,
        template_version=template.version,
        matter_type="labor" if lavoro else template.matter_type,
        period_type=template.period_type,
        free_term=template.free_term,
        suspend_august=template.suspend_august,
        ferial_suspension_policy=template.ferial_suspension_policy,
        urgent=template.urgent,
        reference_law=template.reference_law,
    )
    explanation = str(result.get("explanation", ""))
    if senza_feriale_lavoro and "labour_no_ferial_suspension_art_3_l742_1969" not in (result.get("rulesApplied") or []):
        explanation = (explanation + " Controversia di lavoro o previdenza: sospensione feriale non applicata "
                       "(art. 3 L. 742/1969; art. 92 R.D. 12/1941).").strip()
    return {
        "ok": True,
        "norma": template.reference_law,
        "template_code": template.code,
        "dies_a_quo_type": rule.get("dies_a_quo_type", ""),
        "dies_a_quo_date": dies.isoformat(),
        "direzione": template.direction,
        "durata": template.base_value,
        "unita": template.period_type,
        "tipo": rule.get("tipo", "non_specificato"),
        "deadline": result.get("deadline"),
        "raw_deadline": result.get("rawDeadline"),
        "requires_legal_review": bool(result.get("requiresLegalReview")),
        "steps": result.get("steps", []),
        "explanation": explanation,
        "materia_lavoro": lavoro,
        "rules_applied": list(result.get("rulesApplied") or []),
        "ruleset_version": provenienza["ruleset_version"],
        "rule_file": provenienza["rule_file"],
        "matched_keyword": provenienza["matched_keyword"],
        "matched_snippet": provenienza["matched_snippet"],
        "template_version": provenienza["template_version"],
        "reference_law": provenienza["reference_law"],
        "provenienza": provenienza,
        "confidence": float(rule.get("confidence", 0.75)),
        "azione": rule.get("azione", ""),
        "human_review_required": True,
    }


def _resolve_dies_a_quo(dtype: str, *, comunicazione_date: str, udienza_date: str) -> str:
    if dtype in ("udienza", "pronuncia_udienza"):
        return udienza_date
    if dtype == "comunicazione":
        return comunicazione_date
    if dtype == "notificazione":
        # Fail-closed: il termine breve NON si calcola dalla PEC di cancelleria;
        # serve la data di notifica (evento distinto) -> revisione umana.
        return ""
    return comunicazione_date  # pronuncia_decreto ecc.: best-effort, resta human_review


def propose_from_parsed(
    parsed: dict[str, Any],
    *,
    event_type: str = "",
    comunicazione_date: str = "",
    udienza_date: str = "",
    ruleset: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Proponente dal PEC parsato: risolve la norma, sceglie il dies a quo corretto
    (comunicazione/udienza/notificazione) dai dati disponibili e delega al motore."""

    rules = ruleset or load_ruleset()
    parsed = parsed if isinstance(parsed, dict) else {}
    headers = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    body = parsed.get("body") if isinstance(parsed.get("body"), dict) else {}
    text = " ".join(str(value) for value in (headers.get("subject"), body.get("text"), body.get("ics_text")) if value)
    subject = _norm(str(headers.get("subject") or ""))
    if any(marker in subject for marker in ("esito controlli automatici", "accettazione deposito", "consegna: deposito", "accettazione: deposito")):
        return None
    # Materia di lavoro/previdenza riconosciuta da oggetto e testo (es. «Sezione Lavoro», «RG 123/2026 LAV»).
    lavoro = is_labour_matter(headers.get("subject"), text)
    rule = _resolve_rule(_norm(text), rules)
    if rule is None:
        return propose_legal_deadline(
            text, dies_a_quo_date=comunicazione_date, event_type=event_type, ruleset=rules, labour=lavoro
        )
    dies = _resolve_dies_a_quo(
        str(rule.get("dies_a_quo_type") or ""), comunicazione_date=comunicazione_date, udienza_date=udienza_date
    )
    return propose_legal_deadline(text, dies_a_quo_date=dies, event_type=event_type, ruleset=rules, labour=lavoro)


__all__ = ["load_ruleset", "propose_legal_deadline", "propose_from_parsed"]
