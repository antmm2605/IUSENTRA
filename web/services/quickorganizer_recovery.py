"""Recupero degli originali senza relazione, con associazioni dimostrabili."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pct.document_crypto import decrypt_doc
from pct.document_intelligence.extraction import extract_text_from_document
from pct.document_intelligence import DocumentAIRepository
from pct.document_intelligence.audit import record_document_ai_event
from pct.fascicoli import TipoDocumento


def association_description(evidence):
    labels = {
        "codice_fiscale_cliente": "codice fiscale del cliente",
        "nome_completo_cliente": "nome completo del cliente",
        "numero_rg_e_anno": "numero e anno della pratica",
        "unico_fascicolo_cliente": "unico fascicolo corrispondente del cliente",
        "tribunale": "tribunale competente",
        "numero_rg_e_anno_esplicitamente_etichettati": "numero e anno di ruolo indicati nel documento",
    }
    return "; ".join(labels[item] for item in evidence if item in labels)


def resolve_original_case(text, cases, clienti):
    """Il nome da solo e i codici nell'oggetto email non identificano una pratica."""
    upper = text.upper()
    compact = re.sub(r"\s+", "", upper)
    matches = []
    candidates = []
    for case in cases:
        client = clienti.get(case.id_cliente)
        cf = re.sub(r"\s", "", getattr(client, "codice_fiscale", "") or "").upper()
        if len(cf) == 16 and cf in compact:
            candidates.append(case)
    for case in cases:
        rg = str(case.numero_rg or "").lstrip("0")
        year = str(case.anno_rg or "")
        role = r"\b0*" + re.escape(rg) + r"(?:\s*[/–-]\s*|\s+)" + re.escape(year) + r"\b"
        rg_match = bool(rg and year and re.search(role, upper))
        words = [w for w in re.findall(r"[A-ZÀ-Ù]+", case.nome_cliente.upper()) if len(w) > 2]
        name_match = bool(words) and all(re.search(r"\b" + re.escape(w) + r"\b", upper) for w in words)
        if case in candidates and name_match and (len(candidates) == 1 or rg_match):
            matches.append((case.id, ["codice_fiscale_cliente", "nome_completo_cliente", "numero_rg_e_anno" if rg_match else "unico_fascicolo_cliente"]))
            continue
        court = case.tribunale.upper()
        city = re.sub(r"^TRIBUNALE\s+(?:(?:CIVILE|ORDINARIO)\s+)?(?:DI\s+)?", "", court).strip()
        court_match = bool(city and court.startswith("TRIBUNALE") and re.search(r"TRIBUNALE\s+(?:(?:CIVILE|ORDINARIO)\s+)?(?:DI\s+)?" + re.escape(city).replace(r"\ ", r"\s+"), upper))
        label = r"(?:R\s*\.?\s*G\s*\.?|RUOLO\s+GENERALE)"
        labelled_role = bool(rg and year and (re.search(label + r"[^\n]{0,25}" + role, upper) or re.search(role + r"\s*" + label, upper)))
        if court_match and labelled_role:
            matches.append((case.id, ["tribunale", "numero_rg_e_anno_esplicitamente_etichettati"]))
    owners = {fid for fid, _ in matches}
    return matches[0] if len(owners) == 1 else None


def recover_unassigned_originals(package, *, fascicoli, clienti, assigned_files, read_file, actor):
    """Mantiene le versioni esistenti e rende esplicito ogni originale non associato."""
    def identity(file):
        return file.zip_member or str(file.source or file.name)

    assigned = {identity(file) for file in assigned_files if file is not None}
    cases = fascicoli.tutti(archiviati=True)
    result = {"recovered": 0, "alreadyPreserved": 0, "technicalLogs": 0, "pending": []}
    for file in package.files.values():
        if identity(file) in assigned:
            continue
        try:
            raw = read_file(file)
        except (OSError, ValueError):
            result["pending"].append({"name": file.name, "reason": "Originale non accessibile"})
            continue
        suffix = Path(file.name).suffix.lower()
        # Le righe MailBee sono registri SMTP, non originali documentali.
        # Restano nel pacchetto: possono contenere dati e non si cancellano qui.
        if suffix == ".txt" and re.match(rb"\s*\[\d{2}:\d{2}:\d{2}(?:\.\d+)?\]\s*\[(?:INFO|SEND|RECV|ERROR)\]", raw):
            result["technicalLogs"] += 1
            continue
        try:
            extraction = extract_text_from_document(raw, file.name, suffix.lstrip("."))
        except (OSError, ValueError):
            result["pending"].append({"name": file.name, "reason": "Contenuto non leggibile"})
            continue
        decision = resolve_original_case(extraction.text, cases, clienti) if extraction.ok else None
        if decision is None:
            result["pending"].append({"name": file.name, "reason": "Associazione non univoca" if extraction.ok else "Contenuto non leggibile"})
            continue
        fid, evidence = decision
        digest = hashlib.sha256(raw).hexdigest()
        case = fascicoli.get(fid)
        existing = next((d for d in case.documenti if digest in {d.hash_sha256, d.hash_contenuto_sha256}), None)
        existing_path = fascicoli.percorso_documento(fid, existing.id) if existing else None
        if existing_path and existing_path.is_file() and hashlib.sha256(decrypt_doc(existing_path.read_bytes())).hexdigest() == digest:
            result["alreadyPreserved"] += 1
            continue
        name = "Originale QuickOrganizer - " + file.name
        doc = fascicoli.aggiungi_documento(
            fid, name, TipoDocumento.COMUNICAZIONE if suffix == ".eml" else TipoDocumento.ALLEGATO, raw,
            note="Originale recuperato. Associazione verificata: " + association_description(evidence),
            tags=["import-pratiche", "originale-recuperato"], caricato_da=actor,
            fonte_documento="IMPORT_ESTERNO", nome_originale=file.name, nome_portale=name,
            classificazione_portale="Gestionale precedente",
            id_documento_portale="quickorganizer:unlinked-original:" + digest,
            nome_archivio="originale_" + digest[:16] + suffix,
        )
        if hashlib.sha256(decrypt_doc(fascicoli.percorso_documento(fid, doc.id).read_bytes())).hexdigest() != digest:
            raise OSError("L'originale recuperato non supera la verifica di integrità.")
        from web.services.document_intelligence_runtime import document_ai_tenant_id

        record_document_ai_event(
            DocumentAIRepository.from_fascicoli_db(fascicoli.db_path, structured_db=fascicoli._studio_db),
            "document_ai.original.recovered", tenant_id=document_ai_tenant_id(), fascicolo_id=fid,
            user_context={"user_id": actor}, document_id=doc.id, sha256=digest,
            filename=file.name, status="original_recovered",
            payload={"association_evidence": evidence, "preserved_existing_documents": True},
        )
        result["recovered"] += 1
    return result
