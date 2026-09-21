"""Riuso verificato dei file QuickOrganizer durante l'acquisizione PST.

Il nome non prova l'identità. Si confrontano SHA-256 in chiaro e byte reali,
senza fondere documenti con riferimenti ministeriali distinti.
"""
import hashlib
from copy import deepcopy

def trova_documento_importato_identico(gf, fasc, payload, item, decrypt):
    incoming_id = str(item.get("id_cat") or item.get("id_documento_portale") or item.get("id_documento") or "").strip()
    if not incoming_id:
        return None
    digest = hashlib.sha256(payload).hexdigest()
    matches = []
    for doc in fasc.documenti:
        if str(getattr(doc, "fonte_documento", "")).upper() != "IMPORT_ESTERNO":
            continue
        if not str(getattr(doc, "id_documento_portale", "")).startswith("quickorganizer:"):
            continue
        if str(getattr(doc, "id_cat_portale", "") or "").strip():
            continue
        hashes = {str(getattr(doc, k, "") or "").lower() for k in ("hash_sha256", "hash_contenuto_sha256")}
        possible_pdf = (str(getattr(doc, "nome", "")).lower().endswith(".pdf")
                        and _nome_pdf(doc.nome) == _nome_pdf(item.get("nome", ""))
                        and not getattr(doc, "firmato_digitalmente", False))
        if digest not in hashes and not possible_pdf:
            continue
        try:
            stored = gf.percorso_documento(fasc.id, doc.id).read_bytes()
            if hashlib.sha256(stored).hexdigest() != doc.hash_sha256:
                continue
            plain = decrypt(stored)
            if plain != payload and not (possible_pdf and pdf_equivalenti_privi_di_firma(plain, payload)):
                continue
        except (OSError, ValueError):
            continue
        matches.append(doc)
    return matches[0] if len(matches) == 1 else None

def collega_identita_pst(gf, fasc, doc, item):
    # Conserva identificativo storico, file e note: il riferimento PST distinto
    # vive nel campo ministeriale già persistito su SQLite e PostgreSQL.
    previous = deepcopy(doc.__dict__)
    doc.id_cat_portale = str(item.get("id_cat") or item.get("id_documento_portale") or item.get("id_documento") or "").strip()
    doc.nome_portale = str(item.get("nome") or "").strip()
    try:
        gf.aggiorna_documento_metadati(fasc.id, doc.id)
    except Exception:
        doc.__dict__.clear()
        doc.__dict__.update(previous)
        raise

def _nome_pdf(nome):
    import re
    import unicodedata
    from pathlib import Path
    value = unicodedata.normalize("NFKD", Path(str(nome)).stem).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", re.sub(r"_\d+$", "", value))

def pdf_equivalenti_privi_di_firma(left, right):
    """Confronto conservativo delle pagine; conserva comunque entrambi i file."""
    if not left.startswith(b"%PDF-") or not right.startswith(b"%PDF-"):
        return False
    if any(token in raw for raw in (left, right) for token in (b"/ByteRange", b"/JavaScript", b"/EmbeddedFile", b"/AcroForm")):
        return False
    import pymupdf
    try:
        with pymupdf.open(stream=left, filetype="pdf") as a, pymupdf.open(stream=right, filetype="pdf") as b:
            if a.needs_pass or b.needs_pass or len(a) != len(b) or not 0 < len(a) <= 100:
                return False
            for pa, pb in zip(a, b):
                if pa.rect != pb.rect or pa.rotation != pb.rotation or pa.rect.width * pa.rect.height > 1500000:
                    return False
                if list(pa.annots() or []) or list(pb.annots() or []) or pa.get_links() or pb.get_links():
                    return False
                if pa.get_text() != pb.get_text():
                    return False
                if pa.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).samples != pb.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).samples:
                    return False
            return True
    except (ValueError, RuntimeError):
        return False
