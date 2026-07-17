"""Lettura deterministica delle schede ministeriali di iscrizione a ruolo.

La scheda viene normalmente comunicata dalla cancelleria dopo il deposito e
puo' essere poi acquisita nuovamente dal PST. L'automazione consolida solo dati
coerenti con il fascicolo e conserva l'impronta della fonte per non ripetere il
trattamento di documenti invariati.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


REGISTRY_DOCUMENT_PARSER_VERSION = "2026-07-15-registry-sheet-v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value)).strip()


def _comparison(value: Any) -> str:
    normalized = unicodedata.normalize("NFD", _text(value).casefold())
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", normalized)


def _display_name(value: str) -> str:
    clean = _compact(value)
    if not clean:
        return ""
    if clean != clean.upper():
        return clean
    connectors = {
        "a",
        "ad",
        "al",
        "alla",
        "alle",
        "con",
        "da",
        "dal",
        "dalla",
        "de",
        "dei",
        "del",
        "della",
        "delle",
        "degli",
        "di",
        "dello",
        "e",
        "in",
        "per",
        "su",
        "tra",
    }
    words: list[str] = []
    for index, word in enumerate(clean.split(" ")):
        if len(word) <= 3 and word in {"MIM", "MIUR", "INPS", "INAIL", "ASL", "ASP"}:
            words.append(word)
        elif index > 0 and word.lower() in connectors:
            words.append(word.lower())
        elif "'" in word or "’" in word:
            normalized = word.replace("’", "'").lower()
            prefix, suffix = normalized.split("'", 1)
            if prefix in {"d", "dell", "all", "l", "nell", "sull"} and suffix:
                words.append(f"{prefix}'{suffix[:1].upper()}{suffix[1:]}")
            else:
                words.append(word[:1].upper() + word[1:].lower())
        else:
            words.append(word[:1].upper() + word[1:].lower())
    display = " ".join(words)
    return display.replace("Avvocatura Distrettuale di Stato", "Avvocatura Distrettuale dello Stato")


def _iso_date(value: str) -> str:
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", _text(value))
    if not match:
        return ""
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
    except ValueError:
        return ""


def _court_label(value: str) -> str:
    clean = _compact(value)
    upper = clean.upper()
    patterns = (
        ("TRIBUNALE ORDINARIO DI ", "Tribunale di "),
        ("TRIBUNALE DI ", "Tribunale di "),
        ("CORTE D'APPELLO DI ", "Corte d'Appello di "),
        ("GIUDICE DI PACE DI ", "Giudice di Pace di "),
    )
    for prefix, label in patterns:
        if upper.startswith(prefix):
            return f"{label}{_display_name(clean[len(prefix):])}"
    return _display_name(clean)


def _block(text: str, start_pattern: str, end_pattern: str) -> str:
    match = re.search(start_pattern + r"\s*:?\s*(.*?)" + end_pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _party_lines(block: str) -> tuple[list[str], list[str]]:
    parties: list[str] = []
    lawyers: list[str] = []
    institutional_party = (
        r"AVVOCATURA(?:\s+DISTRETTUALE)?(?:\s+DELLO)?\s+STATO|"
        r"MINISTERO|PRESIDENZA\s+DEL\s+CONSIGLIO|INPS|INAIL|"
        r"AGENZIA\s+DELLE\s+ENTRATE|COMUNE|REGIONE|PROVINCIA|ASL|ASP"
    )
    prepared = re.sub(
        rf"(?i)\bavv\.\s*(?=(?:{institutional_party})\b)",
        "\n",
        str(block or ""),
    )
    prepared = re.sub(
        rf"(?i)(?<=[A-Za-zÀ-ÖØ-öø-ÿ])\s+(?=(?:{institutional_party})\b)",
        "\n",
        prepared,
    )
    for raw_line in prepared.splitlines():
        line = _compact(raw_line).strip(" :-")
        if not line:
            continue
        lawyer = re.match(r"(?i)^avv\.\s*(.*)$|^avv\s+(.+)$", line)
        if lawyer:
            name = _display_name(lawyer.group(1) or lawyer.group(2) or "")
            if name and name not in lawyers:
                lawyers.append(name)
            continue
        inline_lawyer = re.search(r"(?i)(?:^|\s)avv(?:\.\s*|\s+)(?P<name>.+)$", line)
        if inline_lawyer:
            name = _display_name(inline_lawyer.group("name"))
            if name and name not in lawyers:
                lawyers.append(name)
            line = line[: inline_lawyer.start()].strip(" :-")
            if not line:
                continue
        if re.match(r"(?i)^(via|viale|piazza|corso|largo|contrada|loc\.?|frazione)\b", line):
            continue
        if re.match(r"^\d", line) or len(line) > 160:
            continue
        if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", line):
            continue
        party = _display_name(line)
        if party and party not in parties:
            parties.append(party)
    return parties, lawyers


@dataclass(frozen=True, slots=True)
class FascicoloRegistryExtraction:
    found: bool = False
    rg_number: str = ""
    rg_year: int = 0
    registration_date: str = ""
    court: str = ""
    section: str = ""
    judge: str = ""
    role: str = ""
    matter: str = ""
    object: str = ""
    claimants: tuple[str, ...] = ()
    lawyers: tuple[str, ...] = ()
    opponents: tuple[str, ...] = ()
    contribution_status: str = ""
    first_hearing_date: str = ""
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FascicoloRegistryAutomationOutcome:
    found: bool = False
    applied: bool = False
    already_processed: bool = False
    document_key: str = ""
    updated_fields: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    extraction: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_fascicolo_registry_document(text: str) -> bool:
    probe = _comparison(text[:120000])
    required = (
        "ruologeneralen",
        "ruolosezionalen",
        "attoriricorrentiappellanti",
        "resistentiingiuntiappellati",
    )
    return all(token in probe for token in required) and any(
        token in probe for token in ("tribunale", "cortedappello", "giudicedipace")
    )


def extract_fascicolo_registry_data(text: str) -> FascicoloRegistryExtraction:
    raw = str(text or "")[:240000]
    if not is_fascicolo_registry_document(raw):
        return FascicoloRegistryExtraction(found=False)

    lines = [_compact(line) for line in raw.splitlines() if _compact(line)]
    court = ""
    court_match = re.search(
        r"(?i)\b(?P<court>(?:tribunale(?:\s+ordinario)?|corte\s+d['’]appello|giudice\s+di\s+pace)"
        r"\s+di\s+[A-ZÀ-ÖØ-Ý'’ \-]+?)"
        r"(?=\s+\d{1,7}/20\d{2}\b|\s+Ruolo\s+Generale\b|\r?\n|$)",
        raw,
    )
    if court_match:
        court = _court_label(court_match.group("court"))
    else:
        for line in lines[:30]:
            if re.match(r"(?i)^(tribunale(?:\s+ordinario)?|corte\s+d['’]appello|giudice\s+di\s+pace)\s+di\b", line):
                court = _court_label(line)
                break

    rg_match = re.search(r"(?<!\d)(?P<number>\d{1,7})/(?P<year>20\d{2})(?!\d)", raw)
    registration_match = re.search(r"(?i)iscritto\s+il\s*:?\s*(?P<date>\d{2}/\d{2}/\d{4})", raw)

    section = judge = ""
    rg_area_match = re.search(r"(?i)num\.\s*r\.g\.", raw)
    if rg_area_match:
        rg_area = raw[rg_area_match.start() : rg_area_match.start() + 500]
        detail_match = re.search(
            r"(?P<number>\d{1,7})/(?P<year>20\d{2})"
            r"(?P<date>\d{2}/\d{2}/\d{4})\s+"
            r"(?P<section>\d{1,3})\s+"
            r"(?P<judge>[A-ZÀ-ÖØ-Ý][A-ZÀ-ÖØ-Ý'’ \-]{3,80}?)"
            r"(?=\s+(?:Attori\s*/|Ricorrenti\s*/|Resistenti\s*/|Contributo\s+Unificato|Udienze\s*:)|\r?\n|$)",
            rg_area,
        )
        if detail_match:
            section = detail_match.group("section")
            judge = _display_name(detail_match.group("judge"))
            if not registration_match:
                registration_match = detail_match
            if not rg_match:
                rg_match = detail_match

    object_block = _block(raw, r"\bOGGETTO\b", r"\bNum\.\s*R\.G\.")
    object_lines = [
        line
        for line in (_compact(value).strip(" :-") for value in object_block.splitlines())
        if line and line.upper() not in {"RUOLO", "MATERIA", "OGGETTO"}
    ]
    role = _display_name(object_lines[0]) if object_lines else ""
    matter = _display_name(object_lines[1]) if len(object_lines) > 1 else ""
    object_value = _display_name(object_lines[2]) if len(object_lines) > 2 else (_display_name(object_lines[-1]) if object_lines else "")

    claimants_block = _block(
        raw,
        r"Attori\s*/\s*Ricorrenti\s*/\s*Appellanti",
        r"\s*Resistenti\s*/\s*Ingiunti\s*/\s*Appellati",
    )
    opponents_block = _block(
        raw,
        r"Resistenti\s*/\s*Ingiunti\s*/\s*Appellati",
        r"\s*(?:Contributo\s+Unificato|Udienze\s*:)",
    )
    claimants, lawyers = _party_lines(claimants_block)
    opponents, _ = _party_lines(opponents_block)
    if judge:
        opponents = [party for party in opponents if _comparison(party) != _comparison(judge)]

    contribution_status = ""
    contribution_match = re.search(
        r"(?i)contributo\s+unificat[oi]\s*:\s*(esente|non\s+dovut[oa]|prenotat[oa]\s+a\s+debito|pagat[oa])",
        raw,
    )
    if contribution_match:
        value = _comparison(contribution_match.group(1))
        if value in {"esente", "nondovuto", "nondovuta"}:
            contribution_status = "esente"
        elif "prenot" in value:
            contribution_status = "prenotato_a_debito"
        elif "pagat" in value:
            contribution_status = "pagato"

    hearing_match = re.search(
        r"(?i)prima\s+discussione\s*:\s*(?:ALLEGATI\s*)?(?P<date>\d{2}/\d{2}/\d{4})",
        raw,
    )
    warnings: list[str] = []
    if not court:
        warnings.append("ufficio_non_letto")
    if not rg_match:
        warnings.append("rg_non_letto")

    return FascicoloRegistryExtraction(
        found=True,
        rg_number=rg_match.group("number") if rg_match else "",
        rg_year=int(rg_match.group("year")) if rg_match else 0,
        registration_date=_iso_date(registration_match.group("date")) if registration_match else "",
        court=court,
        section=section,
        judge=judge,
        role=role,
        matter=matter,
        object=object_value,
        claimants=tuple(claimants),
        lawyers=tuple(lawyers),
        opponents=tuple(opponents),
        contribution_status=contribution_status,
        first_hearing_date=_iso_date(hearing_match.group("date")) if hearing_match else "",
        warnings=tuple(warnings),
    )


def _document_key(metadata: dict[str, Any]) -> str:
    for field_name in ("sha256", "source_sha256", "documento_id", "source_id", "document_id", "filename"):
        value = _text(metadata.get(field_name))
        if value:
            return f"{field_name}:{value}"
    return ""


def _same_value(left: Any, right: Any) -> bool:
    return bool(_comparison(left)) and _comparison(left) == _comparison(right)


def apply_fascicolo_registry_automation(
    *,
    fascicoli_repository: Any,
    fascicolo_id: str,
    text: str,
    document_metadata: dict[str, Any] | None = None,
    actor: str = "IUSENTRA",
    persist: bool = True,
) -> FascicoloRegistryAutomationOutcome:
    """Consolida la scheda nel fascicolo senza sovrascrivere dati discordanti."""

    metadata = dict(document_metadata or {})
    extraction = extract_fascicolo_registry_data(text)
    outcome = FascicoloRegistryAutomationOutcome(
        found=extraction.found,
        document_key=_document_key(metadata),
        extraction=extraction.to_dict(),
    )
    if not extraction.found:
        return outcome
    fascicolo = fascicoli_repository.get(_text(fascicolo_id)) if fascicoli_repository is not None else None
    if fascicolo is None:
        outcome.conflicts.append("fascicolo_non_trovato")
        return outcome

    existing_rg = _text(getattr(fascicolo, "numero_rg", ""))
    existing_year = int(getattr(fascicolo, "anno_rg", 0) or 0)
    if existing_rg and extraction.rg_number and existing_rg != extraction.rg_number:
        outcome.conflicts.append("numero_rg_diverso")
    if existing_year and extraction.rg_year and existing_year != extraction.rg_year:
        outcome.conflicts.append("anno_rg_diverso")

    updates: dict[str, Any] = {}

    def propose(field_name: str, value: Any) -> None:
        if value in {None, "", 0}:
            return
        current = getattr(fascicolo, field_name, "")
        if current in {None, "", 0}:
            updates[field_name] = value
        elif not _same_value(current, value) and str(current) != str(value):
            outcome.conflicts.append(f"{field_name}_diverso")

    if not any(item in outcome.conflicts for item in ("numero_rg_diverso", "anno_rg_diverso")):
        propose("numero_rg", extraction.rg_number)
        propose("anno_rg", extraction.rg_year)
        propose("tribunale", extraction.court)
        propose("sezione", extraction.section)
        propose("giudice", extraction.judge)
        propose("oggetto", extraction.object)
        propose("nome_cliente", extraction.claimants[0] if extraction.claimants else "")
        propose("attore_principale", extraction.claimants[0] if extraction.claimants else "")
        propose("avvocato_referente", extraction.lawyers[0] if extraction.lawyers else "")
        propose("controparte", "; ".join(extraction.opponents))
        propose("data_prima_udienza", extraction.first_hearing_date)
        if extraction.first_hearing_date and extraction.first_hearing_date >= date.today().isoformat():
            propose("data_prossima_udienza", extraction.first_hearing_date)

    original_snapshot = dict(getattr(fascicolo, "source_snapshot", {}) or {})
    snapshot = dict(original_snapshot)
    automation_state = dict(snapshot.get("post_deposito_cancelleria") or {})
    documents = dict(automation_state.get("documents") or {})
    key = outcome.document_key or f"registry:{extraction.rg_number}/{extraction.rg_year}"
    previous = documents.get(key) if isinstance(documents.get(key), dict) else {}
    outcome.already_processed = previous.get("parser_version") == REGISTRY_DOCUMENT_PARSER_VERSION
    documents[key] = {
        "parser_version": REGISTRY_DOCUMENT_PARSER_VERSION,
        "processed_at": _text(previous.get("processed_at")) or datetime.now().isoformat(),
        "processed_by": _text(actor) or "IUSENTRA",
        "document_id": _text(metadata.get("documento_id") or metadata.get("source_id") or metadata.get("document_id")),
        "filename": _text(metadata.get("filename") or metadata.get("original_filename")),
        "sha256": _text(metadata.get("sha256") or metadata.get("source_sha256")),
        "extraction": extraction.to_dict(),
        "conflicts": list(dict.fromkeys(outcome.conflicts)),
    }
    automation_state.update(
        {
            "parser_version": REGISTRY_DOCUMENT_PARSER_VERSION,
            "latest_document_key": key,
            "latest_rg": f"{extraction.rg_number}/{extraction.rg_year}".strip("/"),
            "documents": documents,
        }
    )
    snapshot["post_deposito_cancelleria"] = automation_state
    updates["source_snapshot"] = snapshot

    if extraction.contribution_status == "esente":
        payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
        existing_payment = payments.get("contributo_unificato")
        existing_payment = dict(existing_payment) if isinstance(existing_payment, dict) else {}
        updated_by = _comparison(existing_payment.get("updated_by") or existing_payment.get("updatedBy"))
        origin = _comparison(existing_payment.get("origine") or existing_payment.get("origin"))
        automatic_origin = any(
            marker in f"{updated_by}{origin}"
            for marker in ("iusentra", "documentai", "pst", "importpratiche", "automatic")
        )
        manually_confirmed = bool(updated_by) and not automatic_origin
        if manually_confirmed and _text(existing_payment.get("status") or existing_payment.get("stato")) not in {"", "non_previsto"}:
            outcome.conflicts.append("contributo_unificato_conferma_manuale_diversa")
        else:
            desired_document_id = _text(metadata.get("documento_id") or metadata.get("source_id") or metadata.get("document_id"))
            desired_sha = _text(metadata.get("sha256") or metadata.get("source_sha256"))
            payment_already_aligned = (
                _text(existing_payment.get("status") or existing_payment.get("stato")) == "non_previsto"
                and _text(existing_payment.get("natura")) == "esenzione_contributo_unificato"
                and (
                    (bool(desired_sha) and _text(existing_payment.get("sha256")) == desired_sha)
                    or (bool(desired_document_id) and _text(existing_payment.get("documento_id")) == desired_document_id)
                )
            )
            if payment_already_aligned:
                existing_payment = {}
            else:
                existing_payment.update(
                    {
                        "kind": "contributo_unificato",
                        "label": "Contributo unificato esente",
                        "natura": "esenzione_contributo_unificato",
                        "status": "non_previsto",
                        "previsto": False,
                        "pagato": False,
                        "importo": None,
                        "valuta": "EUR",
                        "documento_fonte": _text(metadata.get("filename") or metadata.get("original_filename")),
                        "documento_id": desired_document_id,
                        "sha256": desired_sha,
                        "origine": "Scheda di iscrizione a ruolo",
                        "updated_by": _text(actor) or "IUSENTRA",
                        "updated_at": datetime.now().isoformat(),
                        "note": "Esenzione letta dalla scheda ufficiale del procedimento.",
                    }
                )
            if existing_payment:
                payments["contributo_unificato"] = existing_payment
                marker = payments.get("_presidio_documentale")
                if isinstance(marker, dict):
                    marker = dict(marker)
                    marker["status"] = "stale"
                    marker["reason"] = "Nuova scheda del procedimento acquisita: controllo documentale da riallineare."
                    payments["_presidio_documentale"] = marker
                updates["pagamenti"] = payments

    document_id = _text(metadata.get("documento_id") or metadata.get("source_id"))
    document_sha = _text(metadata.get("sha256") or metadata.get("source_sha256"))
    for document in list(getattr(fascicolo, "documenti", []) or []):
        same_document = (
            bool(document_id) and _text(getattr(document, "id", "")) == document_id
        ) or (
            bool(document_sha)
            and document_sha in {
                _text(getattr(document, "hash_sha256", "")),
                _text(getattr(document, "hash_contenuto_sha256", "")),
            }
        )
        if not same_document:
            continue
        tags = list(getattr(document, "tags", []) or [])
        if "scheda_iscrizione_ruolo" not in tags:
            tags.append("scheda_iscrizione_ruolo")
            setattr(document, "tags", tags)
        if hasattr(document, "ocr_estratto"):
            setattr(document, "ocr_estratto", True)
        break

    outcome.updated_fields = sorted(key for key in updates if key not in {"source_snapshot", "pagamenti"})
    if "pagamenti" in updates:
        outcome.updated_fields.append("contributo_unificato")
    outcome.applied = bool(outcome.updated_fields) or not outcome.already_processed
    should_persist = outcome.applied or snapshot != original_snapshot
    if persist and should_persist:
        updater = getattr(fascicoli_repository, "aggiorna", None)
        if not callable(updater):
            outcome.conflicts.append("repository_non_scrivibile")
            outcome.applied = False
            return outcome
        updater(_text(getattr(fascicolo, "id", fascicolo_id)), **updates)
    elif not persist:
        for field_name, value in updates.items():
            setattr(fascicolo, field_name, value)
        if hasattr(fascicolo, "modificato_il"):
            setattr(fascicolo, "modificato_il", datetime.now().isoformat())
    return outcome


__all__ = [
    "FascicoloRegistryAutomationOutcome",
    "FascicoloRegistryExtraction",
    "REGISTRY_DOCUMENT_PARSER_VERSION",
    "apply_fascicolo_registry_automation",
    "extract_fascicolo_registry_data",
    "is_fascicolo_registry_document",
]
