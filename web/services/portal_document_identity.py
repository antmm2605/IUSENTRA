"""Riuso verificato dei file QuickOrganizer durante l'acquisizione PST.

Il nome non prova l'identità. Si confrontano SHA-256 in chiaro e byte reali,
senza fondere documenti con riferimenti ministeriali distinti.
"""
import hashlib
from copy import deepcopy

def trova_documento_importato_identico(gf, fasc, payload, item, decrypt):
    incoming_id = str(item.get("id_cat") or item.get("idCat") or item.get("id_documento_portale") or item.get("id_documento") or item.get("idDocumento") or item.get("idDoc") or item.get("id_repeatto") or item.get("msg_id") or "").strip()
    if not incoming_id:
        return None
    digest = hashlib.sha256(payload).hexdigest()
    matches = []
    for doc in fasc.documenti:
        if str(getattr(doc, "fonte_documento", "")).upper() != "IMPORT_ESTERNO":
            continue
        if not str(getattr(doc, "id_documento_portale", "")).startswith("quickorganizer:"):
            continue
        if any(str(getattr(doc, key, "") or "").strip() for key in ("id_cat_portale", "id_repeatto_portale", "msg_id_portale")):
            continue
        hashes = {str(getattr(doc, k, "") or "").lower() for k in ("hash_sha256", "hash_contenuto_sha256")}
        if digest not in hashes:
            continue
        try:
            stored = gf.percorso_documento(fasc.id, doc.id).read_bytes()
            if hashlib.sha256(stored).hexdigest() != doc.hash_sha256:
                continue
            plain = decrypt(stored)
            if plain != payload:
                continue
        except (OSError, ValueError):
            continue
        matches.append(doc)
    return matches[0] if len(matches) == 1 else None

def collega_identita_pst(gf, fasc, doc, item):
    # Conserva identificativo storico, file e note: il riferimento PST distinto
    # vive nel campo ministeriale già persistito su SQLite e PostgreSQL.
    previous = deepcopy(doc.__dict__)
    # I codici ministeriali non sono intercambiabili: salvare ogni namespace.
    doc.id_cat_portale = str(item.get("id_cat") or item.get("idCat") or "").strip()
    incoming = str(item.get("id_documento_portale") or item.get("id_documento") or item.get("idDocumento") or item.get("idDoc") or "").strip()
    if incoming:
        doc.id_documento_portale = incoming
    doc.id_repeatto_portale = str(item.get("id_repeatto") or item.get("idRepeatto") or item.get("idRepeatTo") or "").strip()
    doc.msg_id_portale = str(item.get("msg_id") or item.get("msgId") or item.get("msgid") or "").strip()
    try:
        gf.aggiorna_documento_metadati(fasc.id, doc.id)
    except Exception:
        doc.__dict__.clear()
        doc.__dict__.update(previous)
        raise
