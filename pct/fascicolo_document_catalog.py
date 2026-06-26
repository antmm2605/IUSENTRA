"""Catalogazione professionale dei documenti del fascicolo.

La classificazione e' intenzionalmente deterministica: usa prima metadati e
testo OCR gia' estratto, senza avviare OCR sincrono durante il caricamento UI.
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pct.fascicoli import TipoDocumento


MAX_CATALOG_TEXT_CHARS = 60000


@dataclass(frozen=True, slots=True)
class DocumentCatalogClassification:
    role: str
    label: str
    section: str
    confidence: int
    evidence: str
    tipo_documento: TipoDocumento
    deposit_role: str
    deposit_candidate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "label": self.label,
            "section": self.section,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "tipo_documento": self.tipo_documento.value,
            "deposit_role": self.deposit_role,
            "deposit_candidate": self.deposit_candidate,
        }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _tipo(value: Any) -> TipoDocumento:
    try:
        return value if isinstance(value, TipoDocumento) else TipoDocumento(_enum_value(value))
    except ValueError:
        return TipoDocumento.ALTRO


def _slug(value: Any) -> str:
    raw = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", _text(value))
    raw = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", raw)
    text = unicodedata.normalize("NFD", raw.casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _names_for_document(doc: Any, filename: str = "") -> list[str]:
    values = [
        filename,
        getattr(doc, "nome", ""),
        getattr(doc, "nome_originale", ""),
        getattr(doc, "nome_portale", ""),
        getattr(doc, "percorso", ""),
    ]
    out: list[str] = []
    for value in values:
        text = _text(value)
        if not text:
            continue
        out.append(Path(text).name)
        if text != Path(text).name:
            out.append(text)
    return out


def _metadata_for_document(doc: Any, *, filename: str = "", tipo: Any = "") -> tuple[TipoDocumento, str, str]:
    current_type = _tipo(tipo or getattr(doc, "tipo", ""))
    names = _names_for_document(doc, filename)
    values = [
        current_type.value,
        *names,
        getattr(doc, "classificazione_portale", ""),
        getattr(doc, "tipo_atto_portale", ""),
        getattr(doc, "servizio_portale", ""),
        getattr(doc, "mittente_portale", ""),
        getattr(doc, "note", ""),
        " ".join(str(item or "") for item in (getattr(doc, "tags", []) or [])),
    ]
    return current_type, _slug(" ".join(names)), _slug(" ".join(values))


def _result(
    *,
    role: str,
    label: str,
    section: str,
    confidence: int,
    evidence: str,
    tipo_documento: TipoDocumento,
    deposit_role: str,
    deposit_candidate: bool,
) -> DocumentCatalogClassification:
    return DocumentCatalogClassification(
        role=role,
        label=label,
        section=section,
        confidence=max(0, min(int(confidence), 100)),
        evidence=evidence,
        tipo_documento=tipo_documento,
        deposit_role=deposit_role,
        deposit_candidate=deposit_candidate,
    )


def _default_result(current_type: TipoDocumento) -> DocumentCatalogClassification:
    if current_type == TipoDocumento.RICORSO:
        return _result(
            role="atto_principale",
            label="Ricorso - atto principale",
            section="atti",
            confidence=95,
            evidence="tipo documento: ricorso",
            tipo_documento=TipoDocumento.RICORSO,
            deposit_role="atto_principale",
            deposit_candidate=True,
        )
    if current_type == TipoDocumento.ATTO_GIUDIZIARIO:
        return _result(
            role="da_verificare",
            label="Atto da verificare",
            section="da-verificare",
            confidence=35,
            evidence="tipo storico generico",
            tipo_documento=TipoDocumento.ATTO_GIUDIZIARIO,
            deposit_role="allegato",
            deposit_candidate=False,
        )
    return _result(
        role="da_verificare",
        label="Da verificare",
        section="da-verificare",
        confidence=20,
        evidence="nessun indicatore certo",
        tipo_documento=current_type if current_type != TipoDocumento.ALTRO else TipoDocumento.ALTRO,
        deposit_role="allegato",
        deposit_candidate=False,
    )


def _has_contributo_context(text: str) -> bool:
    if _contains(text, r"\b(contributo\s+unificato|pagopa|pago\s+pa|avviso\s+pagamento|ricevuta\s+telematica|rt\s+xml)\b"):
        return True
    return _contains(text, r"\bc\s*u\b") and _contains(
        text,
        r"\b(contributo|unificato|pagamento|pagopa|versamento|iscrizione\s+a\s+ruolo|diritti\s+di\s+cancelleria)\b",
    )


def _provvedimento_result(
    tipo_documento: TipoDocumento,
    *,
    confidence: int,
    evidence: str,
) -> DocumentCatalogClassification:
    labels = {
        TipoDocumento.SENTENZA: "Sentenza",
        TipoDocumento.ORDINANZA: "Ordinanza",
        TipoDocumento.DECRETO: "Decreto",
        TipoDocumento.VERBALE: "Verbale",
    }
    return _result(
        role="provvedimento",
        label=labels[tipo_documento],
        section="provvedimenti",
        confidence=confidence,
        evidence=evidence,
        tipo_documento=tipo_documento,
        deposit_role="allegato",
        deposit_candidate=True,
    )


def classify_fascicolo_document(
    doc: Any | None = None,
    *,
    extracted_text: str = "",
    filename: str = "",
    tipo: Any = "",
) -> DocumentCatalogClassification:
    """Classifica un documento del fascicolo per catalogo, deposito e indice.

    Regola utente: un documento identificato come Ricorso e' sempre atto
    principale, salvo che nome/metadati lo qualifichino chiaramente come
    ricevuta, PEC o prova di notifica del ricorso.
    """

    current_type, name_text, metadata_text = _metadata_for_document(doc, filename=filename, tipo=tipo)
    ocr_text = _slug(_text(extracted_text)[:MAX_CATALOG_TEXT_CHARS])
    head_text = ocr_text[:8000]
    full_text = re.sub(r"\s+", " ", f"{metadata_text} {ocr_text}").strip()
    if not full_text:
        return _default_result(current_type)

    name_is_communication = _contains(
        name_text,
        r"\b(pec|postacert|ricevuta|accettazione|consegna|rdac|rac|esito|cancelleria|comunicazione|relata|notifica)\b",
    )
    communication = name_is_communication or _contains(
        head_text[:3000],
        r"\b(postacert|messaggio\s+pec|pec\s+(inviata|accettata|consegnata)|ricevuta\s+di\s+accettazione|avvenuta\s+consegna|ricevuta\s+di\s+avvenuta\s+consegna|rdac|rac|esito\s+controlli|comunicazione\s+di\s+cancelleria)\b",
    )
    notification = _contains(name_text, r"\b(relata|notifica|notificazione|originale\s+notificato)\b") or _contains(
        head_text[:3000],
        r"\b(relata|notifica|notificazione|originale\s+notificato|legge\s+n?\s*53|l\s*53)\b",
    )

    if (name_is_communication or communication) and not (
        current_type == TipoDocumento.RICORSO and not name_is_communication
    ):
        if notification and _contains(full_text, r"\b(relata)\b"):
            return _result(
                role="relata",
                label="Relata / notifica",
                section="comunicazioni",
                confidence=92,
                evidence="nome o testo: relata/notifica",
                tipo_documento=TipoDocumento.NOTIFICA,
                deposit_role="prova_notifica",
                deposit_candidate=True,
            )
        return _result(
            role="comunicazione",
            label="Comunicazione / ricevuta",
            section="comunicazioni",
            confidence=90,
            evidence="nome o testo: PEC/ricevuta/cancelleria",
            tipo_documento=TipoDocumento.COMUNICAZIONE,
            deposit_role="fuori_busta",
            deposit_candidate=False,
        )

    if current_type == TipoDocumento.RICORSO or _contains(name_text, r"\bricorso\b"):
        return _result(
            role="atto_principale",
            label="Ricorso - atto principale",
            section="atti",
            confidence=98,
            evidence="nome, tipo o OCR: ricorso",
            tipo_documento=TipoDocumento.RICORSO,
            deposit_role="atto_principale",
            deposit_candidate=True,
        )

    if _contains(name_text, r"\b(produzione\s+documenti\s+richiesti|documento\s+richiesto|documentazione\s+richiesta|perizia|ctu|ctp|perital|inizio\s+attivita\s+peritali)\b"):
        return _result(
            role="allegato",
            label="Allegato di prova",
            section="allegati",
            confidence=92,
            evidence="nome file: allegato/prova",
            tipo_documento=TipoDocumento.ALLEGATO,
            deposit_role="allegato",
            deposit_candidate=True,
        )

    if _contains(
        name_text,
        r"\b(memoria|note\s+(?:di\s+)?trattazione|note\s+(?:di\s+)?conclusive|note\s+(?:di\s+)?udienza|scritti\s+difensivi|istanza|costituzione|comparsa|replica|deduzioni)\b",
    ):
        tipo_doc = TipoDocumento.COMPARSA if _contains(name_text, r"\b(comparsa|costituzione)\b") else TipoDocumento.MEMORIA
        return _result(
            role="atto_difensivo",
            label="Atto difensivo",
            section="atti",
            confidence=92,
            evidence="nome file: memoria/note/istanza",
            tipo_documento=tipo_doc,
            deposit_role="atto_principale",
            deposit_candidate=True,
        )

    if _contains(name_text, r"\b(richiesta\s+visibilita|visibilita)\b"):
        return _result(
            role="comunicazione",
            label="Comunicazione / richiesta visibilita",
            section="comunicazioni",
            confidence=86,
            evidence="nome file: richiesta visibilita",
            tipo_documento=TipoDocumento.COMUNICAZIONE,
            deposit_role="fuori_busta",
            deposit_candidate=False,
        )

    if _has_contributo_context(full_text) or _contains(full_text, r"\b(marca\s+da\s+bollo|bollo\s+digitale|diritti\s+di\s+cancelleria)\b"):
        label = "Contributo unificato / pagamento"
        if _contains(full_text, r"\b(esente|esenzione|non\s+dovuto|prenotazione\s+a\s+debito)\b"):
            label = "Contributo unificato / esenzione"
        return _result(
            role="contributo_unificato",
            label=label,
            section="pagamenti",
            confidence=95,
            evidence="nome o OCR: contributo/PagoPA/CU contestuale",
            tipo_documento=TipoDocumento.DEPOSITO_PCT,
            deposit_role="contributo_unificato",
            deposit_candidate=True,
        )

    if _contains(name_text, r"\b(nota\s+di\s+iscrizione\s+a\s+ruolo|iscrizione\s+a\s+ruolo|nir)\b") or _contains(
        head_text[:2000],
        r"\b(nota\s+di\s+iscrizione\s+a\s+ruolo|iscrizione\s+a\s+ruolo|nir)\b",
    ):
        return _result(
            role="nota_iscrizione_ruolo",
            label="Nota iscrizione a ruolo",
            section="pagamenti",
            confidence=90,
            evidence="nome o OCR: nota iscrizione a ruolo",
            tipo_documento=TipoDocumento.DEPOSITO_PCT,
            deposit_role="allegato",
            deposit_candidate=True,
        )

    if _contains(name_text, r"\b(procura|mandato)\b") or _contains(
        head_text[:2500],
        r"\b(procura\s+alle\s+liti|mandato\s+alle\s+liti|delega\s+alle\s+liti)\b",
    ):
        return _result(
            role="procura",
            label="Procura alle liti",
            section="allegati",
            confidence=94,
            evidence="nome o OCR: procura/mandato",
            tipo_documento=TipoDocumento.PROCURA,
            deposit_role="procura",
            deposit_candidate=True,
        )

    if _contains(name_text, r"\bsentenza\b"):
        return _provvedimento_result(TipoDocumento.SENTENZA, confidence=94, evidence="nome file: sentenza")
    if _contains(name_text, r"\bordinanza\b"):
        return _provvedimento_result(TipoDocumento.ORDINANZA, confidence=92, evidence="nome file: ordinanza")
    if _contains(name_text, r"\b(decreto|decreto\s+ingiuntivo)\b"):
        return _provvedimento_result(TipoDocumento.DECRETO, confidence=90, evidence="nome file: decreto")
    if _contains(name_text, r"\bverbale\b"):
        return _provvedimento_result(TipoDocumento.VERBALE, confidence=90, evidence="nome file: verbale")

    if current_type == TipoDocumento.SENTENZA:
        return _provvedimento_result(TipoDocumento.SENTENZA, confidence=92, evidence="tipo documento: sentenza")
    if current_type == TipoDocumento.ORDINANZA:
        return _provvedimento_result(TipoDocumento.ORDINANZA, confidence=90, evidence="tipo documento: ordinanza")
    if current_type == TipoDocumento.DECRETO:
        return _provvedimento_result(TipoDocumento.DECRETO, confidence=88, evidence="tipo documento: decreto")
    if current_type == TipoDocumento.VERBALE:
        return _provvedimento_result(TipoDocumento.VERBALE, confidence=86, evidence="tipo documento: verbale")

    if _contains(full_text, r"\b(sentenza)\b"):
        return _provvedimento_result(TipoDocumento.SENTENZA, confidence=88, evidence="OCR: sentenza")
    if _contains(full_text, r"\b(ordinanza)\b"):
        return _provvedimento_result(TipoDocumento.ORDINANZA, confidence=86, evidence="OCR: ordinanza")
    if _contains(full_text, r"\b(decreto|decreto\s+ingiuntivo)\b"):
        return _provvedimento_result(TipoDocumento.DECRETO, confidence=84, evidence="OCR: decreto")
    if _contains(full_text, r"\b(verbale|verbale\s+di\s+udienza|udienza)\b"):
        return _provvedimento_result(TipoDocumento.VERBALE, confidence=82, evidence="OCR: verbale/udienza")

    if notification:
        return _result(
            role="prova_notifica",
            label="Prova notifica",
            section="comunicazioni",
            confidence=86,
            evidence="nome o OCR: notifica",
            tipo_documento=TipoDocumento.NOTIFICA,
            deposit_role="prova_notifica",
            deposit_candidate=True,
        )

    if _contains(full_text, r"\b(citazione|atto\s+di\s+citazione)\b"):
        return _result(
            role="atto_principale",
            label="Atto di citazione - atto principale",
            section="atti",
            confidence=94,
            evidence="nome o OCR: citazione",
            tipo_documento=TipoDocumento.CITAZIONE,
            deposit_role="atto_principale",
            deposit_candidate=True,
        )

    if _contains(head_text[:2500], r"\bricorso\b") and not _contains(
        head_text[:5000],
        r"\b(sentenza|ordinanza|decreto|verbale|in\s+nome\s+del\s+popolo\s+italiano|p\s+q\s+m)\b",
    ):
        return _result(
            role="atto_principale",
            label="Ricorso - atto principale",
            section="atti",
            confidence=86,
            evidence="OCR iniziale: ricorso",
            tipo_documento=TipoDocumento.RICORSO,
            deposit_role="atto_principale",
            deposit_candidate=True,
        )

    if _contains(full_text, r"\b(documento\s+richiesto|documentazione\s+richiesta|prova\s+interesse|prova\s+documentale)\b"):
        return _result(
            role="allegato",
            label="Allegato di prova",
            section="allegati",
            confidence=88,
            evidence="nome o OCR: documento richiesto/prova",
            tipo_documento=TipoDocumento.ALLEGATO,
            deposit_role="allegato",
            deposit_candidate=True,
        )

    if _contains(full_text, r"\b(comparsa|memoria|istanza|appello|reclamo|opposizione|deduzioni|note\s+scritte|conclusionale|replica)\b"):
        tipo_doc = TipoDocumento.MEMORIA
        if _contains(full_text, r"\bcomparsa\b"):
            tipo_doc = TipoDocumento.COMPARSA
        return _result(
            role="atto_difensivo",
            label="Atto difensivo",
            section="atti",
            confidence=86,
            evidence="nome o OCR: memoria/comparsa/istanza",
            tipo_documento=tipo_doc,
            deposit_role="atto_principale",
            deposit_candidate=True,
        )

    if _contains(full_text, r"\b(contratto|accordo|scrittura\s+privata|quietanza|cedolino|busta\s+paga|documento\s+identita|carta\s+identita|perizia|ctu|ctp)\b"):
        return _result(
            role="allegato",
            label="Allegato di prova",
            section="allegati",
            confidence=82,
            evidence="nome o OCR: allegato/prova",
            tipo_documento=TipoDocumento.CONTRATTO if _contains(full_text, r"\b(contratto|accordo|scrittura\s+privata)\b") else TipoDocumento.ALLEGATO,
            deposit_role="allegato",
            deposit_candidate=True,
        )

    if _contains(full_text, r"\b(parcella|fattura|proforma|nota\s+spese|onorari|compenso)\b"):
        return _result(
            role="economia_fascicolo",
            label="Economia fascicolo",
            section="pagamenti",
            confidence=84,
            evidence="nome o OCR: parcella/fattura/nota spese",
            tipo_documento=TipoDocumento.PARCELLA,
            deposit_role="fuori_busta",
            deposit_candidate=False,
        )

    if _contains(name_text, r"\batto\b") or current_type == TipoDocumento.ATTO_GIUDIZIARIO:
        return _result(
            role="atto_generico",
            label="Atto da verificare",
            section="da-verificare",
            confidence=55,
            evidence="solo indicatore generico: atto",
            tipo_documento=TipoDocumento.ATTO_GIUDIZIARIO,
            deposit_role="allegato",
            deposit_candidate=False,
        )

    if current_type not in {TipoDocumento.ALTRO, TipoDocumento.ATTO_GIUDIZIARIO}:
        label = current_type.value.replace("_", " ").title()
        section = "allegati"
        if current_type in {TipoDocumento.COMUNICAZIONE, TipoDocumento.NOTIFICA, TipoDocumento.DEPOSITO_PCT}:
            section = "comunicazioni"
        if current_type in {TipoDocumento.SENTENZA, TipoDocumento.ORDINANZA, TipoDocumento.DECRETO, TipoDocumento.VERBALE}:
            section = "provvedimenti"
        return _result(
            role="classificato_storico",
            label=label,
            section=section,
            confidence=65,
            evidence="tipo documento esistente",
            tipo_documento=current_type,
            deposit_role="allegato",
            deposit_candidate=section != "comunicazioni",
        )

    return _default_result(current_type)


def catalog_tipo_documento_per_nome(filename: str) -> TipoDocumento:
    classification = classify_fascicolo_document(filename=filename)
    if classification.confidence >= 50 and classification.tipo_documento != TipoDocumento.ALTRO:
        return classification.tipo_documento
    suffix = Path(_text(filename)).suffix.casefold()
    if suffix in {".pdf", ".doc", ".docx", ".rtf", ".odt", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        return TipoDocumento.ALLEGATO
    return TipoDocumento.ALTRO


def should_apply_catalog_type(current: Any, classification: DocumentCatalogClassification) -> bool:
    current_type = _tipo(current)
    next_type = classification.tipo_documento
    if current_type == next_type:
        return False
    if current_type == TipoDocumento.RICORSO:
        return False
    if classification.role == "atto_principale" and next_type == TipoDocumento.RICORSO:
        return classification.confidence >= 80
    if classification.confidence < 75:
        return False
    if current_type in {TipoDocumento.ALTRO, TipoDocumento.ALLEGATO, TipoDocumento.ATTO_GIUDIZIARIO}:
        return True
    if classification.evidence.startswith("nome file:") and classification.confidence >= 90:
        specific_current = {
            TipoDocumento.SENTENZA,
            TipoDocumento.ORDINANZA,
            TipoDocumento.DECRETO,
            TipoDocumento.VERBALE,
        }
        if classification.role in {"atto_difensivo", "provvedimento"} and current_type in specific_current:
            return True
    return False


def _document_local_indexes(documents: Iterable[Any]) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    by_id: dict[str, str] = {}
    by_hash_candidates: dict[str, list[str]] = {}
    by_name_candidates: dict[str, list[str]] = {}
    for doc in documents or []:
        doc_id = _text(getattr(doc, "id", ""))
        if not doc_id:
            continue
        by_id[doc_id.casefold()] = doc_id
        digest = _text(getattr(doc, "hash_sha256", "")).casefold()
        if digest:
            by_hash_candidates.setdefault(digest, []).append(doc_id)
        for name in _names_for_document(doc):
            key = _name_key(name)
            if key:
                by_name_candidates.setdefault(key, []).append(doc_id)
    by_hash = {key: values[0] for key, values in by_hash_candidates.items() if len(set(values)) == 1}
    by_name = {key: values[0] for key, values in by_name_candidates.items() if len(set(values)) == 1}
    return by_id, by_hash, by_name


def _name_key(value: Any) -> str:
    text = Path(_text(value)).name
    if text.casefold().endswith(".p7m"):
        text = text[:-4]
    stem = Path(text).stem or text
    return _slug(stem)


def _tenant_candidates(values: Iterable[str] | None = None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        text = _text(value)
        if text and text not in out:
            out.append(text)
    for fallback in ("single-studio", "default"):
        if fallback not in out:
            out.append(fallback)
    return out


def _read_extracted_text_payload(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    text = _text(payload.get("text")) if isinstance(payload, dict) else ""
    if text:
        return text
    pages = payload.get("pages") if isinstance(payload, dict) else []
    if isinstance(pages, list):
        return "\n".join(_text((page or {}).get("text")) for page in pages if isinstance(page, dict))
    return ""


def _resolve_storage_path(storage_root: Path, value: Any) -> Path | None:
    raw = _text(value)
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return storage_root / raw


def _match_document_id(row: dict[str, Any], by_id: dict[str, str], by_hash: dict[str, str], by_name: dict[str, str]) -> str:
    for key in ("document_id", "id", "documento_id"):
        value = _text(row.get(key)).casefold()
        if value and value in by_id:
            return by_id[value]
    digest = _text(row.get("sha256")).casefold()
    if digest and digest in by_hash:
        return by_hash[digest]
    for key in ("original_filename", "safe_filename", "filename", "storage_path", "extracted_text_path"):
        name = _name_key(row.get(key))
        if name and name in by_name:
            return by_name[name]
    return ""


def _rows_from_repository(repo: Any, tenant_ids: list[str], fascicolo_id: str, storage_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tenant_id in tenant_ids:
        try:
            records = repo.list_documents(tenant_id, fascicolo_id)
        except Exception:
            continue
        for record in records:
            row = record.to_dict() if hasattr(record, "to_dict") else dict(record or {})
            text = ""
            try:
                extracted = repo.get_extracted_text(tenant_id, fascicolo_id, row.get("id"))
                text = _text(getattr(extracted, "text", ""))
            except Exception:
                text = ""
            if not text:
                try:
                    versions = repo.list_versions(tenant_id, fascicolo_id, row.get("id"))
                except Exception:
                    versions = []
                current_version_id = _text(row.get("current_version_id"))
                for version in versions:
                    version_row = version.to_dict() if hasattr(version, "to_dict") else dict(version or {})
                    if current_version_id and _text(version_row.get("id")) != current_version_id:
                        continue
                    path = _resolve_storage_path(storage_root, version_row.get("extracted_text_path"))
                    if path and path.exists():
                        text = _read_extracted_text_payload(path)
                    if text:
                        break
            row["text"] = text
            rows.append(row)
    return rows


def _rows_from_json(json_path: Path, tenant_ids: list[str], fascicolo_id: str, storage_root: Path) -> list[dict[str, Any]]:
    if not json_path.exists():
        return []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    texts_by_key: dict[tuple[str, str], str] = {}
    for item in data.get("texts") or []:
        if not isinstance(item, dict):
            continue
        texts_by_key[(_text(item.get("document_id")), _text(item.get("version_id")))] = _text(item.get("text"))
    versions_by_doc: dict[str, list[dict[str, Any]]] = {}
    for item in data.get("versions") or []:
        if isinstance(item, dict):
            versions_by_doc.setdefault(_text(item.get("document_id")), []).append(item)
    rows: list[dict[str, Any]] = []
    for item in data.get("documents") or []:
        if not isinstance(item, dict):
            continue
        if _text(item.get("fascicolo_id")) != fascicolo_id:
            continue
        tenant_value = _text(item.get("tenant_id"))
        if tenant_value and tenant_value not in tenant_ids:
            continue
        row = dict(item)
        doc_id = _text(row.get("id"))
        version_id = _text(row.get("current_version_id"))
        text = texts_by_key.get((doc_id, version_id), "")
        if not text:
            for version in versions_by_doc.get(doc_id, []):
                if version_id and _text(version.get("id")) != version_id:
                    continue
                path = _resolve_storage_path(storage_root, version.get("extracted_text_path"))
                if path and path.exists():
                    text = _read_extracted_text_payload(path)
                if text:
                    break
        row["text"] = text
        rows.append(row)
    return rows


def _rows_from_sqlite(sqlite_path: Path, tenant_ids: list[str], fascicolo_id: str) -> list[dict[str, Any]]:
    if not sqlite_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(sqlite_path))
        conn.row_factory = sqlite3.Row
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    try:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fascicolo_documenti_ai'"
        ).fetchone()
        if not table:
            return []
        for tenant_id in tenant_ids:
            selected = conn.execute(
                """
                SELECT d.*, COALESCE(t.text, '') AS text
                FROM fascicolo_documenti_ai d
                LEFT JOIN fascicolo_documenti_ai_testi t
                  ON t.tenant_id = d.tenant_id
                 AND t.fascicolo_id = d.fascicolo_id
                 AND t.document_id = d.id
                 AND (d.current_version_id IS NULL OR t.version_id = d.current_version_id)
                WHERE d.tenant_id = ? AND d.fascicolo_id = ?
                """,
                (tenant_id, fascicolo_id),
            ).fetchall()
            rows.extend(dict(row) for row in selected)
    except Exception:
        return []
    finally:
        conn.close()
    return rows


def _rows_from_extracted_files(storage_root: Path, tenant_ids: list[str], fascicolo_id: str) -> list[dict[str, Any]]:
    if not storage_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(storage_root.rglob("extracted_text.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        payload_fid = _text(payload.get("fascicolo_id"))
        if payload_fid and payload_fid != fascicolo_id:
            continue
        payload_tenant = _text(payload.get("tenant_id"))
        if payload_tenant and payload_tenant not in tenant_ids:
            continue
        text = _text(payload.get("text")) or _read_extracted_text_payload(path)
        row = {
            "id": _text(payload.get("document_id")) or path.parent.parent.name,
            "document_id": _text(payload.get("document_id")) or path.parent.parent.name,
            "fascicolo_id": payload_fid or fascicolo_id,
            "tenant_id": payload_tenant,
            "original_filename": _text(payload.get("filename") or payload.get("original_filename")),
            "safe_filename": _text(payload.get("safe_filename") or payload.get("filename")),
            "sha256": _text(payload.get("sha256")),
            "extracted_text_path": str(path),
            "text": text,
        }
        rows.append(row)
    return rows


def document_ai_texts_for_catalog(
    *,
    tenant_ids: Iterable[str] | None = None,
    fascicolo_id: str,
    documents: Iterable[Any],
    fascicoli_db_path: str | Path | None = None,
    structured_db: Any = None,
    storage_root: str | Path | None = None,
) -> dict[str, str]:
    """Restituisce testo OCR indicizzato per id documento fascicolo.

    Il match usa ID locale quando coincide, poi SHA-256, poi nome normalizzato.
    """

    fid = _text(fascicolo_id)
    if not fid:
        return {}
    by_id, by_hash, by_name = _document_local_indexes(documents)
    if not by_id:
        return {}
    if storage_root is not None:
        base = Path(storage_root)
    elif fascicoli_db_path is not None:
        base = Path(fascicoli_db_path).resolve().parent / "documenti_ai"
    else:
        base = Path("data") / "fascicoli" / "documenti_ai"
    candidates = _tenant_candidates(tenant_ids)
    rows: list[dict[str, Any]] = []
    if structured_db is not None and fascicoli_db_path is not None:
        try:
            from pct.document_intelligence.repository import DocumentAIRepository

            repo = DocumentAIRepository.from_fascicoli_db(fascicoli_db_path, structured_db=structured_db)
            rows.extend(_rows_from_repository(repo, candidates, fid, base))
        except Exception:
            rows = []
    if not rows:
        rows.extend(_rows_from_sqlite(base / "documenti_ai.sqlite", candidates, fid))
    if not rows:
        rows.extend(_rows_from_json(base / "documenti_ai.json", candidates, fid, base))
    if not rows:
        rows.extend(_rows_from_extracted_files(base, candidates, fid))
    matched: dict[str, str] = {}
    for row in rows:
        doc_id = _match_document_id(row, by_id, by_hash, by_name)
        if not doc_id:
            continue
        text = _text(row.get("text"))[:MAX_CATALOG_TEXT_CHARS]
        if text and (doc_id not in matched or len(text) > len(matched[doc_id])):
            matched[doc_id] = text
    return matched
