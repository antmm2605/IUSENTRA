"""Verifica e recupero degli originali durante una reimportazione QuickOrganizer."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from pct.document_crypto import decrypt_doc
from pct.document_intelligence import DocumentAIRepository
from pct.document_intelligence.audit import record_document_ai_event


def unlinked_file_warning(package, linked_files):
    """Segnala file dell'archivio non descritti dalle relazioni dell'esportazione."""
    if not package.table("PRATICHE"):
        # Senza dati leggibili non è possibile diagnosticare le relazioni.
        return []

    def identity(file):
        return file.zip_member or str(file.source or file.name)

    linked = {identity(file) for file in linked_files if file is not None}
    available = {identity(file) for file in package.files.values()}
    count = len(available - linked)
    if not count:
        return []
    return [{
        "code": "file_senza_relazione_originale",
        "message": (
            f"File senza collegamento nelle tabelle dei documenti e delle email: {count}. "
            "Possono contenere allegati e documenti d'identità: conserva il pacchetto finché il recupero e l'associazione non sono verificati."
        ),
    }]


def package_file_coverage(package, resolve_file):
    """Conta tutti gli originali, anche le righe senza una pratica valida."""
    def identity(file):
        return file.zip_member or str(file.source or file.name)

    available = {identity(file) for file in package.files.values()}
    matters = {str(row.get("NUMEROPRATICA") or "").strip() for row in package.table("PRATICHE")}
    assigned = set()
    for section, table, field in (("ATTI", "TESTI", "NUMEROPRATICA"), ("EMAILS", "EMAILS", "NumeroPratica")):
        for row in package.table(table):
            number = str(row.get(field) or "").strip()
            if not number or number == "0" or number not in matters:
                continue
            file = resolve_file(row.get("NOME_DOS"), section)
            if file is not None:
                assigned.add(identity(file))
    return {"available": len(available), "assigned": len(assigned), "unassigned": len(available - assigned)}


def stored_original_is_readable(manager, matter_id, document):
    """L'audit conta byte verificati, mai la sola presenza del record SQL."""
    root = Path(manager.documents_dir).resolve()
    candidates = [document, *getattr(document, "versioni", [])]
    prefix = f"{document.id_documento_portale}:originale:"
    candidates.extend(d for d in manager.get(matter_id).documenti if d.id_documento_portale.startswith(prefix))
    for candidate in candidates:
        fields = candidate if isinstance(candidate, dict) else vars(candidate)
        path = root / str(fields.get("percorso", "")).replace("\\", "/")
        if not path.resolve().is_relative_to(root / matter_id) or path.is_symlink() or not path.is_file():
            continue
        raw = path.read_bytes()
        hashes = {hashlib.sha256(raw).hexdigest(), hashlib.sha256(decrypt_doc(raw)).hexdigest()}
        expected = {str(fields.get(k) or "").lower() for k in ("hash_sha256", "hash_contenuto_sha256")}
        if hashes & (expected - {""}):
            return True
    return False


def reconcile_existing_original(manager, matter_id, document, data, *, filename, actor):
    """Non confondere un record SQL esistente con un originale conservato.

    Ripristina il percorso solo quando l'impronta SQL certifica gli stessi byte.
    Le versioni differenti restano intatte; il recupero crea un documento distinto.
    """
    digest = hashlib.sha256(data).hexdigest()
    root = Path(manager.documents_dir).resolve()
    case_root = (root / matter_id).resolve()
    if not case_root.is_relative_to(root) or case_root == root:
        raise ValueError("Percorso del fascicolo non valido per il recupero.")

    def checked_path(relative):
        path = root / str(relative).replace("\\", "/")
        if not path.resolve().is_relative_to(case_root) or path.is_symlink():
            raise ValueError("Percorso del documento non valido per il recupero.")
        return path

    def identical(path):
        return path.is_file() and hashlib.sha256(decrypt_doc(path.read_bytes())).hexdigest() == digest

    variants = [document, *getattr(document, "versioni", [])]
    for variant in variants:
        relative = variant.get("percorso", "") if isinstance(variant, dict) else variant.percorso
        if relative and identical(checked_path(relative)):
            return "present"

    original_id = f"{document.id_documento_portale}:originale:{digest}"
    prior = next((d for d in manager.get(matter_id).documenti if d.id_documento_portale == original_id), None)
    target_doc = prior or document
    target = checked_path(target_doc.percorso)
    if not target.exists() and str(target_doc.hash_sha256).lower() == digest:
        # Pubblicazione atomica senza sovrascrittura, anche con import concorrenti.
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".originale-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o640)
            try:
                os.link(temporary, target)
            except FileExistsError:
                if not identical(target):
                    raise OSError("Il documento è cambiato durante il recupero dell'originale.")
        finally:
            Path(temporary).unlink(missing_ok=True)
        if not identical(target):
            raise OSError("L'originale recuperato non supera la verifica di integrità.")
        recovered = target_doc
        status = "restored"
    elif prior:
        if not identical(target):
            raise OSError("La copia originale già registrata non supera la verifica di integrità.")
        return "present"
    else:
        source_name = Path(filename)
        name = f"{Path(document.nome).stem} - originale QuickOrganizer{source_name.suffix}"
        recovered = manager.aggiungi_documento(
            matter_id, name, document.tipo, data,
            note="Originale QuickOrganizer recuperato. Conservata la versione già presente.",
            tags=["import-pratiche", "originale-recuperato"],
            data_documento=document.data_documento,
            caricato_da=actor, fonte_documento="IMPORT_ESTERNO",
            nome_originale=filename, nome_portale=name,
            classificazione_portale="Gestionale precedente",
            id_documento_portale=original_id,
            nome_archivio=f"originale_{digest[:16]}{source_name.suffix}",
        )
        if not identical(checked_path(recovered.percorso)):
            raise OSError("La nuova copia originale non supera la verifica di integrità.")
        status = "preserved_variant"

    from web.services.document_intelligence_runtime import document_ai_tenant_id

    repository = DocumentAIRepository.from_fascicoli_db(manager.db_path, structured_db=manager._studio_db)
    record_document_ai_event(
        repository, "document_ai.original.recovered",
        tenant_id=document_ai_tenant_id(), fascicolo_id=matter_id,
        user_context={"user_id": actor}, document_id=recovered.id,
        sha256=digest, filename=filename, status=status,
        payload={"source": "QuickOrganizer", "preserved_existing_documents": True},
    )
    return status
