from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .models import DepositDocument, PreflightResult, PreflightStatus
from .office_rules import resolve_office_rule
from .policies import ChannelProfile


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._() -]+$")


class DocumentPreflightValidator:
    def validate(
        self,
        *,
        documents: list[DepositDocument],
        profile: ChannelProfile,
        office_name: str = "",
    ) -> list[PreflightResult]:
        results: list[PreflightResult] = []
        if profile.requires_main_act and not any(str(doc.role).upper() == "MAIN_ACT" for doc in documents):
            results.append(_error("MAIN_ACT_MISSING", "Atto principale assente.", "Seleziona un atto principale."))
        if profile.max_files and len(documents) > profile.max_files:
            results.append(
                _error(
                    "MAX_FILES_EXCEEDED",
                    f"Numero file superiore al limite del canale: massimo {profile.max_files}.",
                    "Riduci il numero di allegati o prepara un deposito distinto.",
                )
            )

        total_size = 0
        seen_hashes: set[str] = set()
        for doc in documents:
            results.extend(self._validate_one(doc, profile=profile, office_name=office_name))
            total_size += int(doc.size_bytes or 0)
            if doc.sha256:
                if doc.sha256 in seen_hashes:
                    results.append(
                        _warning(
                            "DUPLICATE_HASH",
                            f"Possibile duplicato: {doc.filename or Path(doc.path).name}.",
                            "Verifica se il file e' stato allegato due volte.",
                        )
                    )
                seen_hashes.add(doc.sha256)

        max_total = profile.max_total_size_mb * 1024 * 1024
        if total_size > max_total:
            results.append(
                _error(
                    "TOTAL_SIZE_EXCEEDED",
                    f"Dimensione totale superiore a {profile.max_total_size_mb} MB.",
                    "Riduci o separa gli allegati prima del deposito.",
                )
            )
        if not any(item.status == PreflightStatus.ERROR for item in results):
            results.append(PreflightResult(PreflightStatus.OK, "PREFLIGHT_COMPLETED", "Validazione completata."))
        return results

    def _validate_one(self, doc: DepositDocument, *, profile: ChannelProfile, office_name: str) -> list[PreflightResult]:
        path = Path(doc.path)
        filename = doc.filename or path.name
        results: list[PreflightResult] = []

        if ".." in path.parts or path.is_absolute() and ".." in str(path):
            results.append(_error("PATH_TRAVERSAL", "Percorso file non sicuro.", "Ricarica il documento dal fascicolo."))
            return results
        if not path.exists():
            results.append(_error("FILE_MISSING", f"File non trovato: {filename}.", "Ricarica il documento."))
            return results
        if not path.is_file():
            results.append(_error("NOT_A_FILE", f"Elemento non valido: {filename}.", "Seleziona un file."))
            return results
        size = path.stat().st_size
        doc.size_bytes = int(size)
        if size <= 0:
            results.append(_error("EMPTY_FILE", f"File vuoto: {filename}.", "Rigenera o ricarica il documento."))
        if size > profile.max_single_file_size_mb * 1024 * 1024:
            results.append(
                _error(
                    "SINGLE_SIZE_EXCEEDED",
                    f"{filename} supera {profile.max_single_file_size_mb} MB.",
                    "Comprimi il PDF o dividi gli allegati.",
                )
            )
        if len(filename) > profile.max_filename_length:
            results.append(
                _error(
                    "FILENAME_TOO_LONG",
                    f"Nome file troppo lungo per {filename}.",
                    f"Usa un nome file entro {profile.max_filename_length} caratteri.",
                )
            )
        if not _SAFE_NAME_RE.match(filename):
            results.append(
                _warning(
                    "UNSAFE_FILENAME",
                    f"Nome file da normalizzare: {filename}.",
                    "Usa solo lettere, numeri, spazi, trattini, punti e underscore.",
                    auto_fix=True,
                )
            )

        suffixes = [item.lower() for item in path.suffixes]
        is_pdf = suffixes[-1:] == [".pdf"]
        is_p7m = suffixes[-1:] == [".p7m"]
        if not (is_pdf or is_p7m):
            results.append(_error("FORMAT_NOT_ALLOWED", f"Formato non ammesso: {filename}.", "Usa PDF/PAdES o CAdES .p7m."))

        if is_pdf:
            results.extend(_validate_pdf(path, profile))
            if doc.signed or str(doc.signature_format).upper() == "PADES":
                results.append(PreflightResult(PreflightStatus.OK, "PADES_OK", "Firma PAdES/PDF rilevata o dichiarata."))
        if is_p7m:
            doc.signature_format = doc.signature_format or "CADES_BES"
            if profile.requires_pdfa and not bool(doc.metadata.get("pdfa_verified")):
                results.append(
                    _warning(
                        "PDFA_NOT_VERIFIABLE_MANUAL_REVIEW",
                        f"PDF/A non verificabile automaticamente nel file firmato {filename}.",
                        "Verifica il PDF/A prima della firma oppure acquisisci conferma manuale tracciata.",
                        manual_review=True,
                    )
                )
            rule = resolve_office_rule(office_name)
            if str(rule.get("pdp_signature_preference") or "") == "pades":
                results.append(
                    _warning(
                        "PALMI_PREFERS_PADES",
                        "Regola locale Palmi: preferire firma PAdES (.pdf).",
                        "Se possibile firma l'atto principale in PAdES. Il CAdES .p7m resta ammesso dalle specifiche PDP nazionali, ma puo' generare criticita operative locali.",
                    )
                )
            elif str(rule.get("cades_severity") or "info") in {"warning", "warning_strong"}:
                results.append(
                    _warning(
                        "CADES_LOCAL_WARNING",
                        "L'ufficio segnala una preferenza locale sulla firma.",
                        "Verifica la prassi locale prima del deposito.",
                    )
                )

        if (
            profile.signature_policy.required
            and str(profile.signature_policy.format).upper() != "NONE"
            and not (doc.signed or doc.signature_format)
        ):
            results.append(_error("SIGNATURE_REQUIRED", f"Firma digitale assente su {filename}.", "Firma l'atto prima del deposito."))

        if not doc.sha256:
            doc.sha256 = _sha256(path)
        results.append(PreflightResult(PreflightStatus.OK, "SHA256", f"Hash SHA-256 calcolato per {filename}.", detail=doc.sha256))
        return results


def _validate_pdf(path: Path, profile: ChannelProfile) -> list[PreflightResult]:
    results: list[PreflightResult] = []
    head = path.read_bytes()[:2048]
    if not head.startswith(b"%PDF-"):
        return [_error("PDF_INVALID_HEADER", f"PDF non leggibile: {path.name}.", "Rigenera il PDF.")]
    if b"/Encrypt" in head:
        results.append(_error("PDF_PASSWORD", f"PDF protetto da password: {path.name}.", "Rimuovi password/protezioni."))
    if b"/JavaScript" in head or b"/OpenAction" in head:
        results.append(_error("PDF_SCRIPT", f"PDF con azioni/script: {path.name}.", "Rigenera un PDF pulito."))
    if profile.requires_pdfa:
        pdfa = _pdfa_flavour(head)
        if not pdfa:
            results.append(_error("PDFA_REQUIRED", f"PDF/A obbligatorio per {path.name}.", "Converti o rigenera il documento in PDF/A."))
        elif profile.accepted_pdfa and pdfa not in profile.accepted_pdfa:
            results.append(
                _error(
                    "PDFA_VERSION_NOT_ALLOWED",
                    f"Formato {pdfa} non ammesso per {path.name}.",
                    f"Usa {' o '.join(profile.accepted_pdfa)}.",
                )
            )
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        if reader.is_encrypted:
            results.append(_error("PDF_PASSWORD", f"PDF protetto da password: {path.name}.", "Rimuovi password/protezioni."))
        page = reader.pages[0] if reader.pages else None
        if page:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            short, long = sorted((width, height))
            if not (560 <= short <= 610 and 780 <= long <= 860):
                results.append(_warning("PDF_NOT_A4", f"Formato pagina non A4 per {path.name}.", "Verifica il formato prima del deposito."))
            text = (page.extract_text() or "").strip()
            if len(text) < 20:
                results.append(
                    _warning(
                        "PDF_NATIVE_DIGITAL_NOT_VERIFIED",
                        f"Testo nativo non verificabile per {path.name}.",
                        "Evita scansioni: deposita atto nativo digitale quando richiesto.",
                    )
                )
    except Exception as exc:
        results.append(_warning("PDF_DEEP_CHECK_UNAVAILABLE", f"Controllo PDF avanzato non completato: {path.name}.", str(exc)))
    return results


def _pdfa_flavour(head: bytes) -> str:
    lowered = head.lower()
    if b"pdfaid:" not in lowered:
        return ""
    text_head = lowered.decode("latin-1", errors="ignore")
    part_match = re.search(r"pdfaid:part[^0-9]*([123])", text_head)
    conf_match = re.search(r"pdfaid:conformance[^a-z]*([ab])", text_head)
    part = part_match.group(1) if part_match else "1"
    conformance = (conf_match.group(1) if conf_match else "b").upper()
    return f"PDF/A-{part}{conformance}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _error(code: str, message: str, suggested_fix: str) -> PreflightResult:
    return PreflightResult(PreflightStatus.ERROR, code, message, suggested_fix=suggested_fix)


def _warning(code: str, message: str, suggested_fix: str, *, auto_fix: bool = False, manual_review: bool = False) -> PreflightResult:
    return PreflightResult(
        PreflightStatus.WARNING,
        code,
        message,
        suggested_fix=suggested_fix,
        auto_fix_available=auto_fix,
        manual_review_required=manual_review,
    )
