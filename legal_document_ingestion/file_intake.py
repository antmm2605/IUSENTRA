"""Pipeline end-to-end per Legal Document Understanding, OCR forense e gate Lex."""

from __future__ import annotations

import email
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email import policy
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable

from .archive_extractor import ExtractedArchiveFile, extract_zip_bytes
from .evidence_hash import sha256_bytes, utc_now
from .mime_detector import detect_mime
from .repository import LegalDocumentRepository, sanitize_filename
from .zip_safety import ZipSafetyConfig


class LegalDocumentIngestionError(RuntimeError):
    """Errore applicativo della pipeline documentale."""


@dataclass(slots=True)
class LegalDocumentIngestionConfig:
    zip_safety: ZipSafetyConfig = field(default_factory=ZipSafetyConfig)
    token_review_threshold: float = 0.85
    document_review_threshold: float = 0.78
    classification_review_threshold: float = 0.62
    enable_forensic_ocr: bool = True
    enable_archive_extraction: bool = True
    lex_validated_documents_only: bool = True
    language: str = "ita"
    legal_ocr_primary_engine: str = "tesseract"
    legal_ocr_fallback_engine: str = "native-text-fallback"
    legal_ocr_local_first_only: bool = True


@dataclass(frozen=True, slots=True)
class ClassificationRule:
    document_type: str
    legal_area: str
    macro_area: str
    rito: str
    fase: str
    procedimento: str
    portale_probabile: str
    patterns: tuple[str, ...]


CLASSIFICATION_RULES: tuple[ClassificationRule, ...] = (
    ClassificationRule("atto di citazione", "civile", "giudiziale", "ordinario", "introduttiva", "contenzioso ordinario", "PST civile", (r"\batto di citazione\b", r"\bcita\b", r"\bconvenire\b")),
    ClassificationRule("comparsa di risposta", "civile", "giudiziale", "ordinario", "costituzione", "contenzioso ordinario", "PST civile", (r"\bcomparsa di risposta\b", r"\bsi costituisce\b")),
    ClassificationRule("memoria 183", "civile", "giudiziale", "ordinario", "istruttoria", "contenzioso ordinario", "PST civile", (r"\bmemoria\b.*\b183\b", r"\b183\s*,?\s*sesto comma\b")),
    ClassificationRule("comparsa conclusionale", "civile", "giudiziale", "ordinario", "decisionale", "contenzioso ordinario", "PST civile", (r"\bcomparsa conclusionale\b",)),
    ClassificationRule("memoria replica", "civile", "giudiziale", "ordinario", "decisionale", "contenzioso ordinario", "PST civile", (r"\bmemoria di replica\b", r"\breplica\b")),
    ClassificationRule("decreto ingiuntivo", "civile", "giudiziale", "monitorio", "provvedimento", "decreto ingiuntivo", "PST civile", (r"\bdecreto ingiuntivo\b", r"\bingiunge\b")),
    ClassificationRule("opposizione a decreto ingiuntivo", "civile", "giudiziale", "monitorio", "introduttiva", "opposizione a decreto ingiuntivo", "PST civile", (r"\bopposizione\b.*\bdecreto ingiuntivo\b",)),
    ClassificationRule("ricorso", "civile", "giudiziale", "camerale", "introduttiva", "ricorso civile", "PST civile", (r"\bricorso\b", r"\bricorrente\b")),
    ClassificationRule("ordinanza", "civile", "giudiziale", "ordinario", "provvedimento", "contenzioso ordinario", "PST civile", (r"\bordinanza\b", r"\bil giudice\b")),
    ClassificationRule("sentenza", "civile", "giudiziale", "ordinario", "decisionale", "contenzioso ordinario", "PST civile", (r"\bsentenza\b", r"\brepubblica italiana\b", r"\bin nome del popolo italiano\b")),
    ClassificationRule("verbale udienza", "civile", "giudiziale", "ordinario", "udienza", "contenzioso ordinario", "PST civile", (r"\bverbale\b.*\budienza\b", r"\budienza del\b")),
    ClassificationRule("nota iscrizione ruolo", "civile", "giudiziale", "iscrizione", "iscrizione ruolo", "contenzioso ordinario", "PST civile", (r"\bnota di iscrizione a ruolo\b", r"\biscrizione a ruolo\b")),
    ClassificationRule("ricevuta PEC accettazione", "trasversale", "comunicazioni", "PEC", "notifica", "ricevuta PEC", "PEC", (r"\bricevuta di accettazione\b", r"\bpostacert\b.*\baccettazione\b")),
    ClassificationRule("ricevuta PEC consegna", "trasversale", "comunicazioni", "PEC", "notifica", "ricevuta PEC", "PEC", (r"\bricevuta di avvenuta consegna\b", r"\bconsegnat[ao]\b", r"\bpostacert\b.*\bconsegna\b")),
    ClassificationRule("mancata consegna PEC", "trasversale", "comunicazioni", "PEC", "notifica", "ricevuta PEC", "PEC", (r"\bmancata consegna\b", r"\bavviso di mancata consegna\b")),
    ClassificationRule("esito controlli automatici", "civile", "telematico", "deposito telematico", "controlli", "deposito", "PST civile", (r"\besito controlli automatici\b", r"\bcontrolli automatici\b")),
    ClassificationRule("ricevuta deposito", "civile", "telematico", "deposito telematico", "deposito", "deposito", "PST civile", (r"\bricevuta deposito\b", r"\bdeposito accettato\b", r"\besito deposito\b")),
    ClassificationRule("comunicazione cancelleria", "civile", "telematico", "cancelleria", "comunicazione", "comunicazione cancelleria", "PST civile", (r"\bcomunicazione di cancelleria\b", r"\bcancelleria\b")),
    ClassificationRule("relata notifica", "civile", "notifiche", "notifica", "notifica", "notificazione", "PST civile", (r"\brelata di notifica\b", r"\bnotifica ai sensi\b")),
    ClassificationRule("procura", "trasversale", "allegati", "mandato", "allegato", "procura", "", (r"\bprocura alle liti\b", r"\bconferisce procura\b")),
    ClassificationRule("documento identità", "trasversale", "allegati", "documento", "allegato", "identificazione", "", (r"\bcarta d'identit", r"\bdocumento di identit", r"\bpatente\b")),
    ClassificationRule("fattura", "stragiudiziale", "economico", "contabile", "documento", "fatturazione", "", (r"\bfattura\b", r"\bpartita iva\b", r"\btotale fattura\b")),
    ClassificationRule("quietanza", "stragiudiziale", "economico", "contabile", "documento", "pagamento", "", (r"\bquietanza\b", r"\bpagamento ricevuto\b")),
    ClassificationRule("CTU", "civile", "giudiziale", "istruttoria", "consulenza", "ctu", "PST civile", (r"\bctu\b", r"\bconsulenza tecnica d'ufficio\b")),
    ClassificationRule("CTP", "civile", "giudiziale", "istruttoria", "consulenza", "ctp", "PST civile", (r"\bctp\b", r"\bconsulenza tecnica di parte\b")),
    ClassificationRule("perizia", "trasversale", "allegati", "perizia", "documento", "perizia", "", (r"\bperizia\b", r"\bperitale\b")),
    ClassificationRule("contratto", "stragiudiziale", "contratti", "contratto", "documento", "contratto", "", (r"\bcontratto\b", r"\btra le parti\b")),
    ClassificationRule("diffida", "stragiudiziale", "comunicazioni", "diffida", "precontenzioso", "diffida", "", (r"\bdiffida\b", r"\bsi intima\b")),
    ClassificationRule("messa in mora", "stragiudiziale", "comunicazioni", "messa in mora", "precontenzioso", "messa in mora", "", (r"\bmessa in mora\b", r"\bcostituisce in mora\b")),
    ClassificationRule("sollecito", "stragiudiziale", "comunicazioni", "sollecito", "precontenzioso", "sollecito", "", (r"\bsollecito\b", r"\bsollecitiamo\b")),
    ClassificationRule("transazione", "stragiudiziale", "accordi", "transazione", "accordo", "transazione", "", (r"\btransazione\b", r"\baccordo transattivo\b")),
    ClassificationRule("istanza cautelare", "amministrativo", "giudiziale", "PAT", "cautelare", "ricorso TAR", "PAT", (r"\bistanza cautelare\b", r"\bsospensiva\b")),
    ClassificationRule("motivi aggiunti", "amministrativo", "giudiziale", "PAT", "integrazione", "ricorso TAR", "PAT", (r"\bmotivi aggiunti\b",)),
    ClassificationRule("ricorso TAR", "amministrativo", "giudiziale", "PAT", "introduttiva", "ricorso TAR", "PAT", (r"\btribunale amministrativo regionale\b", r"\btar\b", r"\bricorso\b")),
    ClassificationRule("appello Consiglio di Stato", "amministrativo", "giudiziale", "PAT", "impugnazione", "appello Consiglio di Stato", "PAT", (r"\bconsiglio di stato\b", r"\bappello\b")),
    ClassificationRule("ricorso tributario", "tributario", "giudiziale", "PTT", "introduttiva", "ricorso tributario", "PTT", (r"\bricorso tributario\b", r"\bcorte di giustizia tributaria\b", r"\bagenzia delle entrate\b")),
    ClassificationRule("reclamo mediazione", "tributario", "precontenzioso", "PTT", "reclamo", "reclamo mediazione", "PTT", (r"\breclamo\b", r"\bmediazione tributaria\b")),
    ClassificationRule("controdeduzioni", "tributario", "giudiziale", "PTT", "costituzione", "contenzioso tributario", "PTT", (r"\bcontrodeduzioni\b", r"\bsi costituisce l'ufficio\b")),
    ClassificationRule("appello CGT", "tributario", "giudiziale", "PTT", "impugnazione", "appello CGT", "PTT", (r"\bappello\b", r"\bcorte di giustizia tributaria\b")),
    ClassificationRule("opposizione sanzione", "giudice di pace", "giudiziale", "SIGP", "introduttiva", "opposizione sanzioni", "SIGP", (r"\bgiudice di pace\b", r"\bopposizione\b.*\bsanzion", r"\bverbale di accertamento\b")),
    ClassificationRule("avviso 415 bis", "penale", "giudiziale", "PDP", "indagini", "avviso 415 bis", "PDP penale", (r"\b415\s*bis\b", r"\bavviso di conclusione delle indagini\b")),
    ClassificationRule("nomina difensore", "penale", "giudiziale", "PDP", "difesa", "nomina difensore", "PDP penale", (r"\bnomina del difensore\b", r"\bnomina difensore\b")),
    ClassificationRule("riesame", "penale", "giudiziale", "PDP", "impugnazione cautelare", "riesame", "PDP penale", (r"\briesame\b", r"\btribunale del riesame\b")),
    ClassificationRule("misura cautelare", "penale", "giudiziale", "PDP", "cautelare", "misure cautelari", "PDP penale", (r"\bmisura cautelare\b", r"\bcustodia cautelare\b")),
    ClassificationRule("costituzione parte civile", "penale", "giudiziale", "PDP", "costituzione", "parte civile", "PDP penale", (r"\bcostituzione di parte civile\b", r"\bparte civile\b")),
    ClassificationRule("appello penale", "penale", "giudiziale", "PDP", "impugnazione", "appello penale", "PDP penale", (r"\bappello penale\b", r"\bpropone appello\b")),
    ClassificationRule("decreto GIP/GUP/PM", "penale", "giudiziale", "PDP", "provvedimento", "provvedimento penale", "PDP penale", (r"\bgip\b", r"\bgup\b", r"\bpubblico ministero\b", r"\bdecreto\b")),
)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _searchable(value: str) -> str:
    text = normalize_text(value).lower()
    return text


class LegalDocumentIngestionService:
    def __init__(
        self,
        repository: LegalDocumentRepository,
        fascicoli_repository: Any = None,
        *,
        config: LegalDocumentIngestionConfig | None = None,
    ) -> None:
        self.repository = repository
        self.fascicoli_repository = fascicoli_repository
        self.config = config or LegalDocumentIngestionConfig()

    def ingest_bytes(
        self,
        *,
        tenant_id: str,
        filename: str,
        content: bytes,
        source_type: str = "upload manuale",
        source_message_id: str = "",
        fascicolo_id: str = "",
        parent_document_id: str = "",
        root_document_id: str = "",
        root_pec_id: str = "",
        actor: str = "sistema",
        auto_process: bool = True,
    ) -> dict[str, Any]:
        data = bytes(content or b"")
        if not data:
            raise LegalDocumentIngestionError("File vuoto o non leggibile.")
        _require_direct_filename(filename)
        mime = detect_mime(data, filename, allowed_extensions=self.config.zip_safety.allowed_extensions)
        document_id = uuid.uuid4().hex
        root_id = root_document_id or document_id
        security_status = "validated" if mime.supported else "quarantined"
        status = "acquired" if mime.supported else "needs_review"
        row = self.repository.insert_document(
            {
                "id": document_id,
                "tenant_id": tenant_id,
                "fascicolo_id": fascicolo_id or None,
                "parent_document_id": parent_document_id or None,
                "root_document_id": root_id,
                "source_type": source_type,
                "source_message_id": source_message_id or None,
                "original_filename": filename or "documento",
                "normalized_filename": sanitize_filename(filename or f"{document_id}{mime.extension or '.bin'}"),
                "mime_type": mime.mime_type,
                "extension": mime.extension,
                "sha256": sha256_bytes(data),
                "file_size": len(data),
                "status": status,
                "security_status": security_status,
                "processing_status": "queued" if mime.supported else "needs_review",
                "created_by": actor,
                "metadata": {"mime": mime.to_dict()},
                "root_pec_id": root_pec_id,
            },
            content=data,
            actor=actor,
        )
        self._audit(tenant_id, actor, "document.normalized", document_id, {"mime": mime.to_dict()})
        processed: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        children: list[dict[str, Any]] = []
        if auto_process and mime.supported:
            if mime.mime_type == "application/zip" and self.config.enable_archive_extraction:
                archive = self.extract_archive(tenant_id, row["id"], actor=actor, root_pec_id=root_pec_id)
                children = list(archive.get("children") or [])
                blocked = list(archive.get("blocked") or [])
                for child in children:
                    child_doc = child.get("document") or {}
                    if child_doc and child_doc.get("mime_type") != "application/zip" and child_doc.get("security_status") == "validated":
                        processed.append(self.process_document(tenant_id, str(child_doc["id"]), actor=actor))
                self.repository.update_document_status(
                    tenant_id,
                    row["id"],
                    status="validated" if not blocked else "needs_review",
                    processing_status="archive_extracted" if not blocked else "archive_extracted_with_warnings",
                )
            else:
                processed.append(self.process_document(tenant_id, row["id"], actor=actor))
        elif not mime.supported:
            self.repository.create_review_task(
                tenant_id,
                row["id"],
                task_type="security",
                reason="Formato non ammesso dalla configurazione.",
                fields={"mime": mime.to_dict()},
                actor=actor,
            )
        return {"document": self.repository.get_document(tenant_id, row["id"]), "children": children, "blocked": blocked, "processed": processed}

    def process_pec_message(
        self,
        *,
        tenant_id: str,
        pec_id: str,
        raw_mime: bytes,
        actor: str = "pec-pipeline",
        fascicolo_id: str = "",
    ) -> dict[str, Any]:
        message = email.message_from_bytes(bytes(raw_mime or b""), policy=policy.default)
        subject = str(message.get("subject") or pec_id or "PEC")
        root = self.ingest_bytes(
            tenant_id=tenant_id,
            filename=f"{pec_id or uuid.uuid4().hex}.eml",
            content=bytes(raw_mime or b""),
            source_type="PEC",
            source_message_id=pec_id,
            fascicolo_id=fascicolo_id,
            root_pec_id=pec_id,
            actor=actor,
            auto_process=False,
        )["document"]
        attachments: list[dict[str, Any]] = []
        if root:
            self._audit(tenant_id, actor, "pec.received", root["id"], {"subject": subject, "source_message_id": pec_id})
        for part in message.iter_attachments():
            raw_payload = part.get_payload(decode=True)
            payload = bytes(raw_payload) if isinstance(raw_payload, (bytes, bytearray)) else b""
            name = part.get_filename() or f"allegato-{len(attachments) + 1}.bin"
            child = self.ingest_bytes(
                tenant_id=tenant_id,
                filename=name,
                content=payload,
                source_type="allegato PEC",
                source_message_id=pec_id,
                fascicolo_id=fascicolo_id,
                parent_document_id=str(root["id"]) if root else "",
                root_document_id=str(root["id"]) if root else "",
                root_pec_id=pec_id,
                actor=actor,
                auto_process=True,
            )
            if root and child.get("document"):
                doc = child["document"]
                self.repository.link_archive_child(
                    tenant_id,
                    str(root["id"]),
                    str(doc["id"]),
                    str(root["id"]),
                    root_pec_id=pec_id,
                    extraction_path=str(doc.get("original_filename") or name),
                    extraction_depth=0,
                    security_status=str(doc.get("security_status") or "validated"),
                    actor=actor,
                )
            attachments.append(child)
        return {"document": root, "attachments": attachments}

    def extract_archive(self, tenant_id: str, document_id: str, *, actor: str = "archive-extractor", root_pec_id: str = "") -> dict[str, Any]:
        document = self._require_document(tenant_id, document_id)
        data = self.repository.read_file(str(document["stored_uri"]))
        self._audit(tenant_id, actor, "archive.detected", document_id, {"sha256": document["sha256"], "filename": document["original_filename"]})
        result = extract_zip_bytes(
            data,
            filename=str(document["original_filename"]),
            parent_document_id=document_id,
            root_document_id=str(document.get("root_document_id") or document_id),
            root_pec_id=root_pec_id or str(document.get("source_message_id") or ""),
            config=self.config.zip_safety,
        )
        children: list[dict[str, Any]] = []
        archive_parent_by_path: dict[str, str] = {"": document_id}
        root_id = str(document.get("root_document_id") or document_id)
        for extracted in sorted(result.files, key=lambda item: (item.extraction_depth, item.extraction_path_virtuale)):
            parent_id = self._parent_for_extracted(extracted, archive_parent_by_path, document_id)
            child = self.repository.insert_document(
                {
                    "tenant_id": tenant_id,
                    "fascicolo_id": document.get("fascicolo_id") or None,
                    "parent_document_id": parent_id,
                    "root_document_id": root_id,
                    "source_type": "ZIP da PEC" if (root_pec_id or document.get("source_type") == "PEC") else "ZIP",
                    "source_message_id": document.get("source_message_id") or root_pec_id or None,
                    "original_filename": extracted.original_filename,
                    "normalized_filename": extracted.normalized_filename,
                    "mime_type": extracted.mime.mime_type,
                    "extension": extracted.mime.extension,
                    "sha256": extracted.sha256,
                    "file_size": extracted.size,
                    "status": "acquired" if extracted.security_status == "validated" else "needs_review",
                    "security_status": extracted.security_status,
                    "processing_status": extracted.processing_status,
                    "created_by": actor,
                    "metadata": extracted.to_metadata(),
                    "root_pec_id": extracted.root_pec_id or root_pec_id,
                    "extraction_path_virtuale": extracted.extraction_path_virtuale,
                    "extraction_depth": extracted.extraction_depth,
                },
                content=extracted.data,
                actor=actor,
            )
            self.repository.link_archive_child(
                tenant_id,
                parent_id,
                str(child["id"]),
                root_id,
                root_pec_id=extracted.root_pec_id or root_pec_id,
                extraction_path=extracted.extraction_path_virtuale,
                extraction_depth=extracted.extraction_depth,
                security_status=extracted.security_status,
                actor=actor,
            )
            if extracted.is_archive:
                archive_parent_by_path[extracted.extraction_path_virtuale] = str(child["id"])
            if extracted.security_status != "validated":
                self.repository.create_review_task(
                    tenant_id,
                    str(child["id"]),
                    task_type="security",
                    reason=extracted.blocked_reason or "File interno ZIP da verificare.",
                    fields=extracted.to_metadata(),
                    actor=actor,
                )
            children.append({"document": child, "metadata": extracted.to_metadata()})
        for blocked in result.blocked:
            self._audit(tenant_id, actor, "archive.unsafe_blocked", document_id, dict(blocked))
            self.repository.create_review_task(
                tenant_id,
                document_id,
                task_type="archive_security",
                reason=str(blocked.get("reason") or "Elemento ZIP bloccato."),
                fields=dict(blocked),
                actor=actor,
            )
        return {"document": document, "children": children, "blocked": result.blocked, "warnings": result.warnings}

    def process_document(self, tenant_id: str, document_id: str, *, actor: str = "legal-document-understanding") -> dict[str, Any]:
        self._require_document(tenant_id, document_id)
        ocr = self.run_ocr(tenant_id, document_id, actor=actor) if self.config.enable_forensic_ocr else self.repository.get_ocr_overlay(tenant_id, document_id)
        text = str((ocr.get("ocr_run") or {}).get("corrected_text") or (ocr.get("ocr_run") or {}).get("raw_text") or self.repository.latest_ocr_text(tenant_id, document_id))
        classification = self.classify_document(tenant_id, document_id, text=text, actor=actor)
        entities = self.extract_entities(tenant_id, document_id, text=text, actor=actor)
        validation = self.validate_document(tenant_id, document_id, text=text, classification=classification, entities=entities, ocr=ocr, actor=actor)
        case_match = self.match_case(tenant_id, document_id, entities=entities, text=text, actor=actor)
        events = self.propose_events(tenant_id, document_id, text=text, actor=actor)
        lex = self.request_lex_index(tenant_id, document_id, actor=actor)
        if validation.get("result") != "valid" or classification.get("status") != "classified":
            self.repository.create_review_task(
                tenant_id,
                document_id,
                task_type="document_review",
                reason="Documento con dati mancanti, incoerenti o classificazione da verificare.",
                fields={"validation": validation, "classification": classification},
                actor=actor,
            )
        if case_match.get("status") in {"suggested_match", "needs_manual_match"} or case_match.get("conflicts"):
            self.repository.create_review_task(
                tenant_id,
                document_id,
                task_type="case_identity",
                reason="Abbinamento fascicolo da verificare: identità cliente o RG non pienamente coerenti.",
                fields={"case_match": case_match, "document_fascicolo_id": (self.repository.get_document(tenant_id, document_id) or {}).get("fascicolo_id")},
                actor=actor,
            )
        return {
            "document": self.repository.get_document(tenant_id, document_id),
            "ocr": ocr,
            "classification": classification,
            "entities": entities,
            "validation": validation,
            "case_match": case_match,
            "events": events,
            "lex": lex,
        }

    def run_ocr(self, tenant_id: str, document_id: str, *, actor: str = "ocr-forense") -> dict[str, Any]:
        document = self._require_document(tenant_id, document_id)
        data = self.repository.read_file(str(document["stored_uri"]))
        mime_type = str(document.get("mime_type") or "")
        extension = str(document.get("extension") or "").lstrip(".")
        started = utc_now()
        self._audit(tenant_id, actor, "ocr.started", document_id, {"engine": "iusentra-forensic-ocr", "mime_type": mime_type})
        if self.config.enable_forensic_ocr and _legal_ocr_supported(mime_type, extension):
            try:
                from legal_ocr import LegalOcrConfig, LegalOcrEvidenceStore, LegalOcrPipeline

                store = LegalOcrEvidenceStore(self.repository.storage_root / "legal_ocr", tenant_id)
                pipeline = LegalOcrPipeline(
                    LegalOcrConfig(
                        tenant_id=tenant_id,
                        primary_engine=self.config.legal_ocr_primary_engine,
                        fallback_engine=self.config.legal_ocr_fallback_engine,
                        language=self.config.language,
                        local_first_only=self.config.legal_ocr_local_first_only,
                    ),
                    store,
                )
                evidences = pipeline.run_bytes(data, filename=str(document.get("original_filename") or "documento"), tenant_id=tenant_id, fascicolo_id=str(document.get("fascicolo_id") or ""), document_id=document_id, source_type=str(document.get("source_type") or "documento"))
                if evidences:
                    evidence = evidences[0]
                    overlay = self._persist_legal_ocr_overlay(tenant_id, document_id, evidence, started=started, actor=actor)
                    if evidence.get("qc", {}).get("hil_required"):
                        self.repository.create_review_task(
                            tenant_id,
                            document_id,
                            task_type="ocr_hil",
                            reason="Lettura OCR da verificare prima dell'uso probatorio pieno.",
                            fields={"run_id": evidence.get("run_id"), "metrics": evidence.get("metrics"), "regex_summary": evidence.get("regex_summary"), "reasons": evidence.get("qc", {}).get("hil_reasons") or []},
                            actor=actor,
                        )
                    return overlay
            except Exception as exc:
                self._audit(tenant_id, actor, "ocr.legal_grade_fallback", document_id, {"reason": str(exc)})
        raw_text = ""
        warnings: list[str] = []
        errors: list[str] = []
        engine = "iusentra-forensic-ocr"
        page_count = 1
        try:
            if mime_type == "application/xml" or extension == "xml":
                raw_text = _decode_bytes(data)
                engine = "xml-parser"
            elif mime_type in {"text/plain", "text/csv", "application/json", "message/rfc822"} or extension in {"txt", "csv", "json", "eml"}:
                raw_text = _decode_bytes(data)
                engine = "native-text"
            elif extension in {"pdf", "docx", "doc"} or mime_type in {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
                raw_text, page_count, engine, warnings, errors = _extract_native_document_text(data, str(document.get("original_filename") or ""), extension)
            elif mime_type.startswith("image/"):
                raw_text, engine, warnings, errors = _extract_image_text(data, str(document.get("original_filename") or ""), self.config.language)
            elif extension == "p7m":
                raw_text, page_count, engine, warnings, errors = _extract_native_document_text(data, str(document.get("original_filename") or ""), "p7m")
            elif mime_type == "application/zip":
                raw_text = ""
                warnings.append("Archivio ZIP conservato come evidenza; l'OCR viene eseguito sui file interni validati.")
            else:
                warnings.append("Formato non leggibile dal motore OCR forense.")
        except Exception as exc:
            errors.append(f"OCR non completato: {exc}")
        corrected = _correct_ocr_text(raw_text)
        tokens = _build_tokens(corrected, self.config.token_review_threshold, base_confidence=_base_confidence(engine, corrected, errors))
        confidence = _document_confidence(tokens, corrected, errors)
        run = {
            "engine": engine,
            "engine_version": "2026.05.21",
            "language": self.config.language,
            "started_at": started,
            "completed_at": utc_now(),
            "page_count": page_count if corrected.strip() else 0,
            "confidence_document": confidence,
            "raw_text": raw_text,
            "corrected_text": corrected,
            "warnings": warnings,
            "errors": errors,
        }
        overlay = self.repository.insert_ocr_run(tenant_id, document_id, run, tokens, actor=actor)
        if confidence < self.config.document_review_threshold and mime_type != "application/zip":
            self.repository.create_review_task(
                tenant_id,
                document_id,
                task_type="ocr",
                reason="Confidenza OCR sotto soglia o documento non leggibile.",
                fields={"confidence_document": confidence, "warnings": warnings, "errors": errors},
                actor=actor,
            )
        return overlay

    def _persist_legal_ocr_overlay(self, tenant_id: str, document_id: str, evidence: dict[str, Any], *, started: str, actor: str) -> dict[str, Any]:
        token_rows: list[dict[str, Any]] = []
        for token in list(evidence.get("token_index") or []):
            bbox = token.get("bbox") or []
            bbox_dict = {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]} if isinstance(bbox, (list, tuple)) and len(bbox) >= 4 else (bbox if isinstance(bbox, dict) else {})
            confidence = float(token.get("confidence") or 0.0)
            token_rows.append({"page_number": int(token.get("page") or token.get("page_number") or 1), "token_text": str(token.get("token") or token.get("token_text") or ""), "confidence": confidence, "bbox": bbox_dict, "warning": "parola_da_verificare" if confidence < self.config.token_review_threshold else ""})
        errors: list[str] = []
        warnings: list[str] = []
        for attempt in list(evidence.get("qc", {}).get("engine_attempts") or []):
            warnings.extend(str(item) for item in attempt.get("warnings") or [])
            errors.extend(str(item) for item in attempt.get("errors") or [])
        warnings.extend(str(item) for item in evidence.get("qc", {}).get("hil_reasons") or [])
        metrics = evidence.get("metrics") or {}
        run = {
            "id": evidence.get("run_id"),
            "engine": evidence.get("selected_engine") or "iusentra-legal-ocr",
            "engine_version": str((evidence.get("engine_version") or {}).get("selected") or "2026.05.24"),
            "language": self.config.language,
            "started_at": started,
            "completed_at": evidence.get("audit", {}).get("finish_ts") or utc_now(),
            "page_count": len(evidence.get("pages") or []),
            "confidence_document": float(metrics.get("avg_confidence") or 0.0),
            "raw_text": _read_legal_ocr_text(self.repository.storage_root, evidence.get("raw_text_path")) or "",
            "corrected_text": _read_legal_ocr_text(self.repository.storage_root, evidence.get("ocr_text_path")) or "",
            "warnings": warnings,
            "errors": errors,
        }
        overlay = self.repository.insert_ocr_run(tenant_id, document_id, run, token_rows, actor=actor)
        self._audit(tenant_id, actor, "ocr.evidence_ready", document_id, {"run_id": evidence.get("run_id"), "avg_confidence": metrics.get("avg_confidence"), "banding": evidence.get("event", {}).get("banding"), "hil_required": evidence.get("qc", {}).get("hil_required"), "notification_proposals": len(evidence.get("notification_proposals") or [])})
        return overlay

    def classify_document(self, tenant_id: str, document_id: str, *, text: str | None = None, actor: str = "classifier") -> dict[str, Any]:
        document = self._require_document(tenant_id, document_id)
        content = _searchable(text if text is not None else self.repository.latest_ocr_text(tenant_id, document_id))
        if str(document.get("mime_type")) == "application/zip":
            classification = {
                "document_type": "archivio ZIP",
                "legal_area": "trasversale",
                "macro_area": "evidenza",
                "rito": "archivio",
                "fase": "acquisizione",
                "procedimento": "allegati PEC/upload",
                "portale_probabile": "",
                "confidence": 0.99,
                "motivation": "Archivio ZIP identificato da magic bytes e conservato come evidenza.",
                "signals": ["application/zip"],
                "status": "classified",
            }
            return self.repository.replace_classification(tenant_id, document_id, classification, actor=actor)
        best: tuple[float, ClassificationRule | None, list[str]] = (0.0, None, [])
        for rule in CLASSIFICATION_RULES:
            signals = [pattern for pattern in rule.patterns if re.search(pattern, content, flags=re.IGNORECASE | re.DOTALL)]
            if not signals:
                continue
            score = min(0.98, 0.48 + 0.16 * len(signals) + _area_bonus(rule, content))
            if rule.document_type in {"diffida", "messa in mora", "istanza cautelare", "motivi aggiunti", "avviso 415 bis"}:
                score = min(0.98, score + 0.18)
            if rule.document_type == "istanza cautelare" and "istanza cautelare" in content:
                score = 0.99
            if score > best[0]:
                best = (score, rule, signals)
        if not best[1] or best[0] < self.config.classification_review_threshold:
            classification = {
                "document_type": "unknown",
                "legal_area": "unknown",
                "macro_area": "unknown",
                "rito": "",
                "fase": "",
                "procedimento": "",
                "portale_probabile": "",
                "confidence": round(best[0], 3),
                "motivation": "Segnali insufficienti per una classificazione affidabile.",
                "signals": best[2],
                "status": "needs_review" if best[0] else "unknown",
            }
        else:
            rule = best[1]
            classification = {
                "document_type": rule.document_type,
                "legal_area": rule.legal_area,
                "macro_area": rule.macro_area,
                "rito": rule.rito,
                "fase": rule.fase,
                "procedimento": rule.procedimento,
                "portale_probabile": rule.portale_probabile,
                "confidence": round(best[0], 3),
                "motivation": "Classificazione basata su segnali testuali coerenti.",
                "signals": best[2],
                "status": "classified" if best[0] >= 0.72 else "needs_review",
            }
        return self.repository.replace_classification(tenant_id, document_id, classification, actor=actor)

    def extract_entities(self, tenant_id: str, document_id: str, *, text: str | None = None, actor: str = "entity-extractor") -> list[dict[str, Any]]:
        source = text if text is not None else self.repository.latest_ocr_text(tenant_id, document_id)
        entities: list[dict[str, Any]] = []
        entities.extend(_regex_entities(document_id, source))
        entities.extend(_context_entities(document_id, source))
        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for entity in entities:
            key = (str(entity.get("entity_type")), str(entity.get("value")).strip().casefold())
            if not key[1]:
                continue
            current = unique.get(key)
            if not current or float(entity.get("confidence") or 0) > float(current.get("confidence") or 0):
                unique[key] = entity
        return self.repository.replace_entities(tenant_id, document_id, unique.values(), actor=actor)

    def validate_document(
        self,
        tenant_id: str,
        document_id: str,
        *,
        text: str | None = None,
        classification: dict[str, Any] | None = None,
        entities: list[dict[str, Any]] | None = None,
        ocr: dict[str, Any] | None = None,
        actor: str = "validator",
    ) -> dict[str, Any]:
        document = self._require_document(tenant_id, document_id)
        classification = classification or self.repository.latest_classification(tenant_id, document_id) or {}
        entities = entities or self.repository.list_entities(tenant_id, document_id)
        text = text if text is not None else self.repository.latest_ocr_text(tenant_id, document_id)
        ocr = ocr or self.repository.get_ocr_overlay(tenant_id, document_id)
        issues: list[str] = []
        missing: list[str] = []
        consistency: dict[str, Any] = {}
        if str(document.get("security_status")) not in {"validated", "directory"}:
            result = "unsafe_file"
            issues.append("File in quarantena o bloccato dai controlli di sicurezza.")
        elif str(document.get("mime_type")) == "application/zip":
            result = "valid"
        else:
            result = "valid"
        if str(document.get("mime_type")) != "application/zip" and not normalize_text(text or ""):
            issues.append("Documento non leggibile.")
            result = "unreadable_document"
        confidence = float(((ocr or {}).get("ocr_run") or {}).get("confidence_document") or 0.0)
        if str(document.get("mime_type")) != "application/zip" and confidence < self.config.document_review_threshold:
            issues.append("Confidenza OCR sotto soglia.")
            result = "needs_review"
        if classification.get("status") in {"unknown", "needs_review"}:
            issues.append("Classificazione da revisionare.")
            result = "needs_review"
        entity_map = _entity_map(entities)
        for invalid in _invalid_labeled_values(text or ""):
            issues.append(invalid)
            result = "needs_review"
        for required in _critical_fields_for(str(classification.get("document_type") or "")):
            if required not in entity_map:
                missing.append(required)
        if missing and result == "valid":
            result = "needs_review"
        future_issue = _future_document_date_issue(text or "")
        if future_issue:
            issues.append(future_issue)
            result = "needs_review"
        consistency["critical_fields"] = {key: bool(entity_map.get(key)) for key in sorted(set(_critical_fields_for(str(classification.get("document_type") or ""))))}
        validation = {
            "result": result,
            "valid": result == "valid",
            "missing_critical_fields": missing,
            "issues": issues,
            "consistency": consistency,
        }
        return self.repository.replace_validation(tenant_id, document_id, validation, actor=actor)

    def match_case(
        self,
        tenant_id: str,
        document_id: str,
        *,
        entities: list[dict[str, Any]] | None = None,
        text: str = "",
        actor: str = "case-matcher",
    ) -> dict[str, Any]:
        document = self._require_document(tenant_id, document_id)
        if document.get("fascicolo_id"):
            current_case = _find_case_by_id(_fascicoli_candidates(self.fascicoli_repository), str(document.get("fascicolo_id") or ""))
            if current_case:
                entity_values = _entity_map(entities or self.repository.list_entities(tenant_id, document_id))
                score, signals, conflicts = _score_case(current_case, entity_values, _searchable(text))
                if conflicts or (_document_mentions_party(text) and not _has_client_identity_signal(signals)):
                    return self.repository.replace_case_match(
                        tenant_id,
                        document_id,
                        {"matched_case_id": document["fascicolo_id"], "confidence": round(min(score, 0.74), 3), "matched_signals": signals, "conflicts": conflicts or ["Cliente del fascicolo non confermato nel documento."], "status": "needs_manual_match"},
                        actor=actor,
                    )
            return self.repository.replace_case_match(
                tenant_id,
                document_id,
                {"matched_case_id": document["fascicolo_id"], "confidence": 0.99, "matched_signals": ["fascicolo già indicato"], "conflicts": [], "status": "auto_matched"},
                actor=actor,
            )
        candidates = _fascicoli_candidates(self.fascicoli_repository)
        entities = entities or self.repository.list_entities(tenant_id, document_id)
        scores: list[tuple[float, str, list[str], list[str]]] = []
        entity_values = _entity_map(entities)
        haystack = _searchable(text)
        for case in candidates:
            case_id = str(case.get("id") or case.get("id_fascicolo") or "")
            if not case_id:
                continue
            score, signals, conflicts = _score_case(case, entity_values, haystack)
            if score > 0:
                scores.append((score, case_id, signals, conflicts))
        scores.sort(reverse=True, key=lambda item: item[0])
        match: dict[str, Any]
        if not scores:
            match = {"matched_case_id": None, "confidence": 0.0, "matched_signals": [], "conflicts": [], "status": "no_match"}
        elif len(scores) > 1 and scores[0][0] - scores[1][0] < 0.16:
            match = {"matched_case_id": scores[0][1], "confidence": round(scores[0][0], 3), "matched_signals": scores[0][2], "conflicts": ["Più fascicoli compatibili"], "status": "suggested_match"}
        elif scores[0][0] >= 0.82 and not scores[0][3] and _has_client_identity_signal(scores[0][2]) and "NRG" in scores[0][2]:
            match = {"matched_case_id": scores[0][1], "confidence": round(scores[0][0], 3), "matched_signals": scores[0][2], "conflicts": [], "status": "auto_matched"}
        else:
            match = {"matched_case_id": scores[0][1], "confidence": round(scores[0][0], 3), "matched_signals": scores[0][2], "conflicts": scores[0][3], "status": "suggested_match" if scores[0][0] >= 0.45 else "needs_manual_match"}
        return self.repository.replace_case_match(tenant_id, document_id, match, actor=actor)

    def propose_events(self, tenant_id: str, document_id: str, *, text: str | None = None, actor: str = "event-engine") -> list[dict[str, Any]]:
        source = text if text is not None else self.repository.latest_ocr_text(tenant_id, document_id)
        events = _extract_events(source or "")
        return self.repository.replace_events(tenant_id, document_id, events, actor=actor)

    def request_lex_index(self, tenant_id: str, document_id: str, *, actor: str = "lex-indexer") -> dict[str, Any]:
        document = self._require_document(tenant_id, document_id)
        validation = self.repository.latest_validation(tenant_id, document_id) or {}
        if self.config.lex_validated_documents_only and validation.get("result") != "valid":
            return self.repository.create_lex_index_job(
                tenant_id,
                document_id,
                status="blocked",
                reason="Lex indicizza solo documenti validati.",
                chunks=[],
                metadata={"document_id": document_id, "validation": validation.get("result") or "missing"},
                actor=actor,
            )
        if document.get("security_status") != "validated" or document.get("status") in {"needs_review", "rejected"}:
            return self.repository.create_lex_index_job(
                tenant_id,
                document_id,
                status="blocked",
                reason="Documento non validato o non sicuro.",
                chunks=[],
                metadata={"document_id": document_id, "status": document.get("status"), "security_status": document.get("security_status")},
                actor=actor,
            )
        case_match = self.repository.latest_case_match(tenant_id, document_id) or {}
        if case_match.get("conflicts") or case_match.get("status") in {"suggested_match", "needs_manual_match"}:
            return self.repository.create_lex_index_job(tenant_id, document_id, status="blocked", reason="Documento non indicizzato: abbinamento fascicolo-cliente da verificare.", chunks=[], metadata={"document_id": document_id, "case_match": case_match.get("status"), "conflicts": case_match.get("conflicts") or []}, actor=actor)
        text = _latest_legal_ocr_lex_text(self.repository.storage_root, tenant_id, document_id) or self.repository.latest_ocr_text(tenant_id, document_id)
        chunks = _chunk_for_lex(text)
        metadata = _lex_metadata(document, self.repository.latest_classification(tenant_id, document_id) or {}, self.repository.list_entities(tenant_id, document_id), self.repository.get_ocr_overlay(tenant_id, document_id))
        return self.repository.create_lex_index_job(
            tenant_id,
            document_id,
            status="completed" if chunks else "blocked",
            reason="Documento validato indicizzato in Lex." if chunks else "Nessun testo indicizzabile.",
            chunks=chunks,
            metadata=metadata,
            actor=actor,
        )

    def request_fascicolo_lex_index(self, tenant_id: str, fascicolo_id: str, *, actor: str = "lex-indexer") -> dict[str, Any]:
        clean_fascicolo = str(fascicolo_id or "").strip()
        if not clean_fascicolo:
            raise LegalDocumentIngestionError("Fascicolo non indicato.")
        included: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for document in self.repository.list_documents(tenant_id, fascicolo_id=clean_fascicolo, limit=500):
            document_id = str(document.get("id") or "")
            validation = self.repository.latest_validation(tenant_id, document_id) or {}
            case_match = self.repository.latest_case_match(tenant_id, document_id) or {}
            if document.get("security_status") != "validated" or document.get("status") in {"needs_review", "rejected"}:
                skipped.append({"document_id": document_id, "reason": "documento non validato o da revisione"})
                continue
            if self.config.lex_validated_documents_only and validation.get("result") != "valid":
                skipped.append({"document_id": document_id, "reason": "validazione documentale non completata"})
                continue
            if case_match.get("conflicts") or case_match.get("status") in {"suggested_match", "needs_manual_match"}:
                skipped.append({"document_id": document_id, "reason": "identità fascicolo-cliente da verificare"})
                continue
            text = _latest_legal_ocr_lex_text(self.repository.storage_root, tenant_id, document_id) or self.repository.latest_ocr_text(tenant_id, document_id)
            chunks = _chunk_for_lex(text)
            if not chunks:
                skipped.append({"document_id": document_id, "reason": "testo non indicizzabile"})
                continue
            metadata = _lex_metadata(document, self.repository.latest_classification(tenant_id, document_id) or {}, self.repository.list_entities(tenant_id, document_id), self.repository.get_ocr_overlay(tenant_id, document_id))
            metadata.update({"fascicolo_index": True, "source_document_id": document_id, "source_filename": document.get("original_filename")})
            job = self.repository.create_lex_index_job(tenant_id, document_id, status="completed", reason="Documento validato indicizzato nella conoscenza del fascicolo.", chunks=[_chunk_with_document_metadata(chunk, document) for chunk in chunks], metadata=metadata, actor=actor)
            included.append({"document_id": document_id, "filename": document.get("original_filename"), "chunks": len(chunks), "job_id": job.get("id") or job.get("job_id")})
        with self.repository.connect() as conn:
            self.repository.append_audit(conn, tenant_id=tenant_id, actor=actor, action="lex.fascicolo_index.completed", resource_type="fascicolo", resource_id=clean_fascicolo, payload={"included": len(included), "skipped": len(skipped)})
            conn.commit()
        return {"fascicolo_id": clean_fascicolo, "included": included, "skipped": skipped, "status": "completed" if included else "blocked", "reason": "Conoscenza del fascicolo aggiornata con documenti validati." if included else "Nessun documento del fascicolo pronto per Lex."}

    def review_document(self, tenant_id: str, document_id: str, decision: dict[str, Any], *, actor: str) -> dict[str, Any]:
        result = self.repository.complete_review(tenant_id, document_id, decision, actor=actor)
        if str(decision.get("status") or "").lower() in {"validated", "valid", "approvato"}:
            self.repository.replace_validation(
                tenant_id,
                document_id,
                {
                    "result": "valid",
                    "valid": True,
                    "missing_critical_fields": [],
                    "issues": [],
                    "consistency": {"human_review": "approved"},
                },
                actor=actor,
            )
        return result

    def _require_document(self, tenant_id: str, document_id: str) -> dict[str, Any]:
        document = self.repository.get_document(tenant_id, document_id)
        if not document:
            raise KeyError("Documento non trovato o non accessibile per questo studio.")
        return document

    def _audit(self, tenant_id: str, actor: str, action: str, document_id: str, payload: dict[str, Any]) -> None:
        with self.repository.connect() as conn:
            self.repository.append_audit(conn, tenant_id=tenant_id, actor=actor, action=action, resource_type="document", resource_id=document_id, payload=payload)
            conn.commit()

    @staticmethod
    def _parent_for_extracted(extracted: ExtractedArchiveFile, archive_parent_by_path: dict[str, str], fallback: str) -> str:
        path = str(extracted.extraction_path_virtuale or "")
        parent_id = fallback
        for archive_path, document_id in archive_parent_by_path.items():
            if archive_path and path.startswith(f"{archive_path}/"):
                parent_id = document_id
        return parent_id


def _legal_ocr_supported(mime_type: str, extension: str) -> bool:
    ext = str(extension or "").lower().lstrip(".")
    mime = str(mime_type or "").lower()
    return ext in {"pdf", "png", "jpg", "jpeg", "tif", "tiff", "zip", "p7m"} or mime in {
        "application/pdf",
        "application/zip",
        "application/x-pkcs7-mime",
        "application/pkcs7-mime",
        "image/png",
        "image/jpeg",
        "image/tiff",
    }


def _read_legal_ocr_text(storage_root: str | Path, rel_path: Any) -> str:
    rel = str(rel_path or "").strip()
    if not rel:
        return ""
    root = Path(storage_root)
    for base in (root / "legal_ocr", root):
        try:
            candidate = (base / rel).resolve()
            if candidate.exists() and candidate.is_file() and candidate.is_relative_to(base.resolve()):
                return candidate.read_text(encoding="utf-8")
        except Exception:
            continue
    return ""


def _latest_legal_ocr_lex_text(storage_root: str | Path, tenant_id: str, document_id: str) -> str:
    try:
        from legal_ocr import LegalOcrEvidenceStore

        evidence = LegalOcrEvidenceStore(Path(storage_root) / "legal_ocr", tenant_id).find_latest_for_document(document_id)
    except Exception:
        evidence = None
    if not evidence:
        return ""
    lex_export = evidence.get("lex_export") or {}
    return _read_legal_ocr_text(storage_root, lex_export.get("path") or evidence.get("ocr_text_path"))


def _extract_native_document_text(data: bytes, filename: str, extension: str) -> tuple[str, int, str, list[str], list[str]]:
    try:
        from pct.document_intelligence.extraction import extract_text_from_document

        result = extract_text_from_document(data, filename, extension)
        page_count = len(result.pages) if getattr(result, "pages", None) else 1
        warnings = list(getattr(result, "warnings", []) or [])
        errors = [] if result.ok else [getattr(result, "error_message", "") or getattr(result, "error_code", "") or "Estrazione testo non completata."]
        return str(result.text or ""), page_count, str(result.extraction_engine or "document-ai-extractor"), warnings, errors
    except Exception as exc:
        return "", 0, "document-ai-extractor", [], [str(exc)]


def _extract_image_text(data: bytes, filename: str, language: str) -> tuple[str, str, list[str], list[str]]:
    try:
        from pct.ocr import estrai_testo

        text = estrai_testo(data, filename, lang=language)
        warnings = ["Immagine normalizzata con pipeline forense best-effort: deskew, denoise e binarizzazione registrati come preprocessing logico."]
        return str(text or ""), "pct-ocr-image", warnings, []
    except Exception as exc:
        return "", "pct-ocr-image", [], [str(exc)]


def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return bytes(data or b"").decode(encoding)
        except UnicodeDecodeError:
            continue
    return bytes(data or b"").decode("utf-8", errors="replace")


def _correct_ocr_text(text: str) -> str:
    clean = str(text or "").replace("\x00", " ")
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def _base_confidence(engine: str, text: str, errors: list[str]) -> float:
    if errors:
        return 0.35
    if not normalize_text(text):
        return 0.2
    if engine in {"native-text", "xml-parser"} or engine.startswith("pypdf") or engine.startswith("docx") or engine.startswith("pdf"):
        return 0.96
    if "image" in engine or "ocr" in engine:
        return 0.88
    return 0.82


def _build_tokens(text: str, threshold: float, *, base_confidence: float) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for line_number, line in enumerate(str(text or "").splitlines() or [str(text or "")], start=1):
        x = 32
        for match in re.finditer(r"\S+", line):
            token = match.group(0)
            penalty = 0.0
            if re.search(r"[\ufffd□]{1,}", token):
                penalty += 0.35
            if len(token) > 35:
                penalty += 0.07
            confidence = max(0.05, min(0.99, base_confidence - penalty))
            tokens.append(
                {
                    "page_number": 1,
                    "token_text": token,
                    "confidence": round(confidence, 3),
                    "bbox": {"x": x + match.start() * 7, "y": 42 + line_number * 18, "w": max(8, len(token) * 7), "h": 14},
                    "warning": "token_low_confidence" if confidence < threshold else "",
                }
            )
    return tokens


def _document_confidence(tokens: list[dict[str, Any]], text: str, errors: list[str]) -> float:
    if errors:
        return 0.35
    if not normalize_text(text):
        return 0.2
    if not tokens:
        return 0.2
    return round(sum(float(token.get("confidence") or 0.0) for token in tokens) / len(tokens), 3)


def _area_bonus(rule: ClassificationRule, text: str) -> float:
    bonus = 0.0
    clues = {
        "civile": (r"\btribunale\b", r"\bgiudice\b", r"\br\.?\s*g\.?\b"),
        "penale": (r"\bimputat", r"\bprocura della repubblica\b", r"\bgip\b", r"\bgup\b"),
        "amministrativo": (r"\btar\b", r"\bconsiglio di stato\b", r"\bpubblica amministrazione\b"),
        "tributario": (r"\bagenzia delle entrate\b", r"\bcgt\b", r"\btributaria\b"),
        "giudice di pace": (r"\bgiudice di pace\b",),
        "stragiudiziale": (r"\bdiffida\b", r"\bcontratto\b", r"\btransazione\b"),
    }
    for pattern in clues.get(rule.legal_area, ()):
        if re.search(pattern, text):
            bonus += 0.06
    return min(bonus, 0.18)


def _regex_entities(document_id: str, text: str) -> list[dict[str, Any]]:
    patterns: list[tuple[str, str, str, float]] = [
        ("NRG", r"\b(?:n\.?\s*)?(?:r\.?\s*g\.?|n\.?\s*r\.?\s*g\.?|ruolo generale)\s*(?:n\.?|numero)?\s*(\d{1,7})\s*/\s*((?:19|20)\d{2})\b", "regex", 0.94),
        ("PEC", r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]*pec\.[a-z]{2,}\b", "regex", 0.98),
        ("email", r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b", "regex", 0.92),
        ("codice_fiscale", r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", "regex", 0.94),
        ("partita_iva", r"\b\d{11}\b", "regex", 0.88),
        ("IBAN", r"\bIT\d{2}[A-Z]\d{10}[0-9A-Z]{12}\b", "regex", 0.94),
        ("data", r"\b(?:0?[1-9]|[12]\d|3[01])[\-/\.](?:0?[1-9]|1[0-2])[\-/\.]((?:19|20)\d{2})\b", "regex", 0.86),
        ("importo", r"(?:€|euro)\s*\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?", "regex", 0.9),
        ("numero_sentenza", r"\bsentenza\s*(?:n\.?|numero)?\s*(\d{1,7})\s*/?\s*((?:19|20)\d{2})?", "regex", 0.9),
        ("identificativo_deposito", r"\b(?:id|identificativo|numero)\s+deposito\s*[:#]?\s*([A-Z0-9._/-]{6,})", "regex", 0.84),
        ("riferimento_normativo", r"\bart\.?\s*\d+[^\n,;]{0,80}?(?:c\.p\.c\.|c\.p\.|c\.c\.|d\.lgs\.|legge|cost\.)", "regex", 0.86),
        ("riferimento_giurisprudenziale", r"\b(?:Cass\.|Consiglio di Stato|Corte cost\.|TAR)\s*[^\n]{0,120}?\b\d{1,6}/(?:19|20)\d{2}\b", "regex", 0.83),
    ]
    entities: list[dict[str, Any]] = []
    for entity_type, pattern, method, confidence in patterns:
        for match in re.finditer(pattern, str(text or ""), flags=re.IGNORECASE):
            value = match.group(0)
            if entity_type == "email" and ".pec." in value.lower():
                continue
            entities.append(_entity(document_id, entity_type, value, confidence, method, _validate_entity(entity_type, value)))
            if entity_type == "NRG":
                entities.append(_entity(document_id, "numero_ruolo", match.group(1), 0.94, method, "passed"))
                entities.append(_entity(document_id, "anno_ruolo", match.group(2), 0.94, method, "passed"))
    for date_match in re.finditer(r"\b(?:udienza|rinvio|rinviata|comparizione)[^\n]{0,80}?((?:0?[1-9]|[12]\d|3[01])[\-/\.](?:0?[1-9]|1[0-2])[\-/\.](?:19|20)\d{2})", str(text or ""), flags=re.IGNORECASE):
        entities.append(_entity(document_id, "data_udienza", date_match.group(1), 0.9, "regex", "passed"))
    for term_match in re.finditer(r"\btermine\s+(?:di|per)\s+(\d{1,3})\s+giorni\b", str(text or ""), flags=re.IGNORECASE):
        entities.append(_entity(document_id, "termine_processuale", f"{term_match.group(1)} giorni", 0.88, "regex", "passed"))
    return entities


def _context_entities(document_id: str, text: str) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for line in str(text or "").splitlines():
        clean = normalize_text(line)
        if not clean:
            continue
        for entity_type, pattern in (
            ("ufficio_giudiziario", r"\b(Tribunale|Corte d'Appello|Corte di Cassazione|TAR|Consiglio di Stato|Corte di Giustizia Tributaria|Giudice di Pace)[^,\n]{0,80}"),
            ("sezione", r"\bsezione\s+([A-Za-z0-9 .-]{1,40})"),
            ("giudice", r"\bgiudice\s+([A-Z][A-Za-zÀ-ÿ' .-]{2,80})"),
            ("relatore", r"\brelatore\s+([A-Z][A-Za-zÀ-ÿ' .-]{2,80})"),
            ("parte", r"\b(attore|convenuto|ricorrente|resistente|imputato|parte civile|controparte)\s*[:\-]\s*(.{2,120})"),
            ("contributo_unificato", r"\bcontributo unificato\s*(?:di|pari a|:)?\s*(€\s*\d[\d.,]*)"),
            ("valore_causa", r"\bvalore della causa\s*(?:di|pari a|:)?\s*(€\s*\d[\d.,]*)"),
            ("allegato", r"\ballegat[oi]\s*[:\-]\s*(.{2,120})"),
        ):
            match = re.search(pattern, clean, flags=re.IGNORECASE)
            if match:
                value = match.group(0 if entity_type == "ufficio_giudiziario" else min(1, len(match.groups())))
                if entity_type == "parte" and len(match.groups()) >= 2:
                    value = f"{match.group(1)}: {match.group(2)}"
                entities.append(_entity(document_id, entity_type, value, 0.78, "regex", "passed"))
    return entities


def _entity(document_id: str, entity_type: str, value: str, confidence: float, method: str, validation_status: str) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "value": normalize_text(value),
        "confidence": round(confidence, 3),
        "page": 1,
        "bbox": {},
        "source_document_id": document_id,
        "extraction_method": method,
        "validation_status": validation_status,
    }


def _validate_entity(entity_type: str, value: str) -> str:
    clean = re.sub(r"\s+", "", str(value or "")).upper()
    if entity_type == "codice_fiscale":
        return "passed" if _valid_cf(clean) else "failed"
    if entity_type == "partita_iva":
        return "passed" if _valid_piva(clean) else "failed"
    if entity_type in {"PEC", "email"}:
        return "passed" if re.fullmatch(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", clean, flags=re.IGNORECASE) else "failed"
    return "passed"


def _valid_cf(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]", value or ""))


def _valid_piva(value: str) -> bool:
    if not re.fullmatch(r"\d{11}", value or ""):
        return False
    digits = [int(char) for char in value]
    total = sum(digits[0:10:2])
    for digit in digits[1:10:2]:
        doubled = digit * 2
        total += doubled if doubled < 10 else doubled - 9
    return (10 - total % 10) % 10 == digits[-1]


def _invalid_labeled_values(text: str) -> list[str]:
    issues: list[str] = []
    for match in re.finditer(r"\b(?:codice fiscale|cf)\s*[:\-]?\s*([A-Z0-9]{8,20})", str(text or ""), flags=re.IGNORECASE):
        if not _valid_cf(match.group(1).upper()):
            issues.append("Codice fiscale indicato ma non valido.")
    for match in re.finditer(r"\b(?:partita iva|p\.?\s*iva)\s*[:\-]?\s*(\d{7,14})", str(text or ""), flags=re.IGNORECASE):
        if not _valid_piva(match.group(1)):
            issues.append("Partita IVA indicata ma non valida.")
    for match in re.finditer(r"\b(?:pec|email)\s*[:\-]?\s*([^\s,;]+@[^\s,;]+)", str(text or ""), flags=re.IGNORECASE):
        if not re.fullmatch(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", match.group(1), flags=re.IGNORECASE):
            issues.append("Indirizzo email o PEC indicato ma non valido.")
    return issues


def _entity_map(entities: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for entity in entities or []:
        out.setdefault(str(entity.get("entity_type") or ""), []).append(str(entity.get("value") or ""))
    return out


def _critical_fields_for(document_type: str) -> tuple[str, ...]:
    clean = str(document_type or "").lower()
    if clean in {"sentenza", "ordinanza", "decreto ingiuntivo", "verbale udienza", "ricevuta deposito", "esito controlli automatici"}:
        return ("ufficio_giudiziario",)
    if clean in {"ricevuta pec accettazione", "ricevuta pec consegna", "mancata consegna pec"}:
        return ("PEC",)
    if clean in {"ricorso tributario", "ricorso tar", "appello consiglio di stato", "appello cgt"}:
        return ("ufficio_giudiziario", "parte")
    if clean in {"avviso 415 bis", "nomina difensore", "costituzione parte civile"}:
        return ("parte",)
    return ()


def _future_document_date_issue(text: str) -> str:
    now = datetime.now(timezone.utc).date()
    for match in re.finditer(r"\bdata\s+atto\s*[:\-]?\s*((?:0?[1-9]|[12]\d|3[01])[\-/\.](?:0?[1-9]|1[0-2])[\-/\.](?:19|20)\d{2})", str(text or ""), flags=re.IGNORECASE):
        parsed = _parse_date(match.group(1))
        if parsed and parsed > now + timedelta(days=1):
            return "Data atto futura da verificare."
    return ""


def _parse_date(value: str) -> date | None:
    clean = str(value or "").replace(".", "/").replace("-", "/")
    try:
        return datetime.strptime(clean, "%d/%m/%Y").date()
    except ValueError:
        return None


def _extract_events(text: str) -> list[dict[str, Any]]:
    source = str(text or "")
    events: list[dict[str, Any]] = []
    for match in re.finditer(r"\budienza\s+(?:rinviata|differita|fissata)?\s*(?:al|per il)?\s*((?:0?[1-9]|[12]\d|3[01])[\-/\.](?:0?[1-9]|1[0-2])[\-/\.](?:19|20)\d{2})", source, flags=re.IGNORECASE):
        events.append(_event("udienza", "Udienza rilevata", match.group(1), match.group(0), 0.9))
    for match in re.finditer(r"\btermine\s+(?:di|per)\s+(\d{1,3})\s+giorni\b", source, flags=re.IGNORECASE):
        events.append(_event("scadenza", f"Termine di {match.group(1)} giorni", "", match.group(0), 0.86))
    simple_patterns = (
        ("deposito_accettato", "Deposito accettato", r"\bdeposito accettato\b", 0.92),
        ("deposito_verificato", "Esito controlli automatici positivo", r"\besito controlli automatici\s+positivo\b", 0.92),
        ("sentenza_pubblicata", "Sentenza pubblicata", r"\bsentenza pubblicata\b", 0.88),
        ("attivita_esecutiva", "Provvisoria esecutorietà concessa", r"\bprovvisoria esecutoriet[aà]\s+concessa\b", 0.86),
        ("notifica_perfezionata", "PEC consegnata", r"\bpec\s+consegnata\b|\bricevuta di avvenuta consegna\b", 0.92),
        ("alert_urgente", "Mancata consegna PEC", r"\bmancata consegna\b|\bavviso di mancata consegna\b", 0.95),
        ("deposito_rifiutato", "Deposito rifiutato", r"\bdeposito rifiutato\b|\besito negativo\b", 0.9),
    )
    for event_type, title, pattern, confidence in simple_patterns:
        simple_match = re.search(pattern, source, flags=re.IGNORECASE)
        if simple_match:
            events.append(_event(event_type, title, "", simple_match.group(0), confidence))
    return events


def _event(event_type: str, title: str, date_value: str, evidence: str, confidence: float) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "title": title,
        "date_value": date_value,
        "evidence_text": normalize_text(evidence),
        "confidence": round(confidence, 3),
        "status": "pending_review" if confidence < 0.93 else "proposed",
    }


def _fascicoli_candidates(repository: Any) -> list[dict[str, Any]]:
    if repository is None:
        return []
    if isinstance(repository, list):
        return [dict(item) for item in repository if isinstance(item, dict)]
    if isinstance(repository, dict):
        values = repository.values() if "id" not in repository else [repository]
        return [_object_to_case(item) for item in values]
    for method_name, kwargs in (("tutti", {"archiviati": True}), ("tutti", {}), ("list", {})):
        method = getattr(repository, method_name, None)
        if callable(method):
            try:
                return [_object_to_case(item) for item in method(**kwargs)]
            except TypeError:
                try:
                    return [_object_to_case(item) for item in method()]
                except Exception:
                    pass
            except Exception:
                pass
    return []


def _object_to_case(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    keys = (
        "id",
        "id_fascicolo",
        "numero",
        "numero_rg",
        "anno_rg",
        "ufficio",
        "ufficio_giudiziario",
        "oggetto",
        "nome_cliente",
        "cliente",
        "nome",
        "cognome",
        "id_cliente",
        "controparte",
        "parti",
        "pec",
        "codice_fiscale",
        "codice_fiscale_cliente",
        "partita_iva",
        "numero_sentenza",
    )
    return {key: getattr(item, key, "") for key in keys}


def _score_case(case: dict[str, Any], entity_values: dict[str, list[str]], haystack: str) -> tuple[float, list[str], list[str]]:
    score = 0.0
    signals: list[str] = []
    conflicts: list[str] = []
    rg_values = set(entity_values.get("NRG", []) + entity_values.get("numero_ruolo", []))
    case_rg = str(case.get("numero_rg") or case.get("rg") or case.get("numero") or "")
    if case_rg and any(case_rg.replace(" ", "") in value.replace(" ", "") for value in rg_values):
        score += 0.46
        signals.append("NRG")
    office = _searchable(str(case.get("ufficio") or case.get("ufficio_giudiziario") or ""))
    if office and office in haystack:
        score += 0.12
        signals.append("ufficio")
    case_cf = _normalize_identity_code(str(case.get("codice_fiscale_cliente") or case.get("codice_fiscale") or ""))
    text_cf_values = {_normalize_identity_code(value) for value in entity_values.get("codice_fiscale", []) if _normalize_identity_code(value)}
    if case_cf and case_cf in haystack.upper().replace(" ", ""):
        score += 0.38
        signals.append("codice fiscale cliente")
    elif case_cf and text_cf_values and case_cf not in text_cf_values:
        conflicts.append("Codice fiscale cliente non coincidente")
    client_names = _case_client_names(case)
    for name in client_names:
        searchable_name = _searchable(name)
        if searchable_name and searchable_name in haystack:
            score += 0.3 if "cliente" not in signals else 0.12
            signals.append("cliente")
            break
    mentioned_name = _client_identity_from_text(haystack)
    if client_names and mentioned_name and not any(_identity_tokens(name).issubset(_identity_tokens(mentioned_name)) or _identity_tokens(mentioned_name).issubset(_identity_tokens(name)) for name in client_names):
        conflicts.append("Nome cliente non coincidente")
    for case_field, signal in (("controparte", "controparte"), ("oggetto", "oggetto"), ("partita_iva", "partita IVA"), ("pec", "PEC"), ("numero_sentenza", "numero sentenza")):
        value = _searchable(str(case.get(case_field) or ""))
        if value and value in haystack:
            score += 0.12
            signals.append(signal)
    if case_rg and rg_values and not any(case_rg.replace(" ", "") in value.replace(" ", "") for value in rg_values):
        conflicts.append("NRG non coincidente")
    return min(score, 0.99), signals, conflicts


def _find_case_by_id(cases: Iterable[dict[str, Any]], case_id: str) -> dict[str, Any] | None:
    wanted = str(case_id or "").strip()
    if not wanted:
        return None
    for case in cases:
        if str(case.get("id") or case.get("id_fascicolo") or "").strip() == wanted:
            return dict(case)
    return None


def _has_client_identity_signal(signals: Iterable[str]) -> bool:
    normalized = {_searchable(signal) for signal in signals or []}
    return bool({"cliente", "codice fiscale cliente"} & normalized)


def _document_mentions_party(text: str) -> bool:
    return bool(re.search(r"\b(attore|convenuto|ricorrente|resistente|imputato|parte civile|cliente|assistit[oa])\b", str(text or ""), flags=re.IGNORECASE))


def _client_identity_from_text(haystack: str) -> str:
    for pattern in (
        r"\b(?:cliente|assistit[oa]|ricorrente|attore|imputato)\s*[:\-]\s*([a-zà-ÿ' .-]{4,80})",
        r"\b(?:sig\.?|signor[ae])\s+([a-zà-ÿ' .-]{4,80})",
    ):
        match = re.search(pattern, str(haystack or ""), flags=re.IGNORECASE)
        if match:
            return normalize_text(match.group(1))
    return ""


def _case_client_names(case: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("nome_cliente", "cliente"):
        value = normalize_text(str(case.get(key) or ""))
        if value:
            values.append(value)
    combined = normalize_text(f"{case.get('nome') or ''} {case.get('cognome') or ''}")
    if combined:
        values.append(combined)
    return list(dict.fromkeys(values))


def _identity_tokens(value: str) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9à-ÿ]+", _searchable(value)) if len(part) >= 3}


def _normalize_identity_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _require_direct_filename(filename: str) -> None:
    raw = str(filename or "").strip()
    folded = raw.replace("\\", "/")
    if not raw or "\x00" in raw:
        raise LegalDocumentIngestionError("Nome file non sicuro.")
    if folded.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", folded):
        raise LegalDocumentIngestionError("Nome file non sicuro.")
    if PureWindowsPath(raw).drive or str(PureWindowsPath(raw)).startswith("\\\\"):
        raise LegalDocumentIngestionError("Nome file non sicuro.")
    parts = [part for part in folded.split("/") if part]
    if len(parts) != 1 or any(part in {".", ".."} for part in parts):
        raise LegalDocumentIngestionError("Nome file non sicuro.")


def _chunk_for_lex(text: str) -> list[dict[str, Any]]:
    clean = str(text or "").strip()
    if not clean:
        return []
    paragraphs = [normalize_text(part) for part in re.split(r"\n\s*\n", clean) if normalize_text(part)]
    if not paragraphs:
        paragraphs = [normalize_text(clean)]
    chunks: list[dict[str, Any]] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        if len(paragraph) <= 1800:
            chunks.append({"page_number": 1, "text": paragraph, "metadata": {"chunk_kind": "paragrafo", "ordinal": index}})
            continue
        for offset in range(0, len(paragraph), 1500):
            chunks.append({"page_number": 1, "text": paragraph[offset : offset + 1500], "metadata": {"chunk_kind": "paragrafo", "ordinal": index}})
    return chunks


def _chunk_with_document_metadata(chunk: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    out = dict(chunk or {})
    metadata = dict(out.get("metadata") or {})
    metadata.update(
        {
            "document_id": document.get("id"),
            "fascicolo_id": document.get("fascicolo_id"),
            "filename": document.get("original_filename"),
            "source_type": document.get("source_type"),
        }
    )
    out["metadata"] = metadata
    return out


def _lex_metadata(document: dict[str, Any], classification: dict[str, Any], entities: list[dict[str, Any]], ocr: dict[str, Any]) -> dict[str, Any]:
    entity_values = _entity_map(entities)
    ocr_run = (ocr or {}).get("ocr_run") or {}
    return {
        "tenant_id": document.get("tenant_id"),
        "fascicolo_id": document.get("fascicolo_id"),
        "cliente_id": None,
        "procedimento": classification.get("procedimento"),
        "rito": classification.get("rito"),
        "fase": classification.get("fase"),
        "ufficio": (entity_values.get("ufficio_giudiziario") or [""])[0],
        "NRG": (entity_values.get("NRG") or [""])[0],
        "documento_tipo": classification.get("document_type"),
        "provenienza": document.get("source_type"),
        "livello_affidabilita_ocr": ocr_run.get("confidence_document"),
        "riferimenti_pagina": [1] if ocr_run else [],
        "riferimenti_bbox": True if (ocr or {}).get("tokens") else False,
        "warnings": ocr_run.get("warnings") or [],
    }
