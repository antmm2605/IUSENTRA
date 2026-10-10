"""Bozza CTU e riferimento documentale nella transazione del comando.

I byte sono immutabili e indirizzati dal contenuto: un rollback SQL può
lasciare un file preparato, mai un documento dichiarato consegnato. Il retry
riscontra quei byte, senza sovrascriverli. Nessuna firma o invio.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from pct.ctu import IncaricoCtu
from pct.ctu_compensi.istanza import html_istanza
from pct.ctu_repository import CtuConflict
from pct.document_crypto import decrypt_doc, encrypt_doc
from pct.fascicoli import Documento, GestioneFascicoli, TipoDocumento


def deliver_liquidation_document(conn, record, *, tenant, actor, command_key, documents_dir, calculate):
    if not tenant or not actor:
        raise ValueError("Studio e operatore della bozza CTU obbligatori.")
    key = str(UUID(command_key))
    incarico = IncaricoCtu.from_dict(record)
    if incarico.ruolo_studio != "AUSILIARIO":
        raise ValueError("L’istanza di liquidazione appartiene al consulente d’ufficio.")
    columns = ("id", "documenti_json", "attivita_json", "scadenze_json", "profilo_deposito_json", "dati_json", "modificato_il")
    row = conn.execute(f"SELECT {','.join(columns)} FROM fascicoli WHERE id=?", (incarico.fascicolo_id,)).fetchone()
    if row is None:
        raise ValueError("Fascicolo della bozza CTU non presente nello studio.")
    raw = dict(row) if hasattr(row, "keys") else dict(zip(columns, row, strict=True))
    fascicolo = GestioneFascicoli._row_to_fascicolo(raw)
    if fascicolo is None or fascicolo.id != incarico.fascicolo_id:
        raise ValueError("Contenuto SQL del fascicolo discordante: bozza CTU non consegnata.")
    html = html_istanza(incarico=incarico, fascicolo=fascicolo, calcolo=calculate(incarico),
        operazioni=sorted(incarico.operazioni, key=lambda item: (item.get("data", ""), item.get("ora", ""))))
    content = html.encode("utf-8")
    plaintext_hash = hashlib.sha256(content).hexdigest()
    identifier = uuid5(NAMESPACE_URL, json.dumps(["ctu-document", tenant, incarico.id, key])).hex.upper()
    root = Path(documents_dir).resolve()
    directory = (root / incarico.fascicolo_id).resolve()
    if not directory.is_relative_to(root) or directory == root:
        raise ValueError("Percorso della bozza CTU non appartenente al fascicolo.")
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"istanza_liquidazione_ctu_{identifier}_{plaintext_hash[:16]}.html"
    destination = directory / filename
    if destination.exists():
        encrypted = destination.read_bytes()
        if hashlib.sha256(decrypt_doc(encrypted)).hexdigest() != plaintext_hash:
            raise RuntimeError("File preparato della bozza CTU discordante: nessuna sovrascrittura.")
    else:
        encrypted = encrypt_doc(content)
        try:
            with destination.open("xb") as stream:
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            encrypted = destination.read_bytes()
    if decrypt_doc(destination.read_bytes()) != content:
        raise RuntimeError("Integrità della bozza CTU non riscontrata.")
    encrypted_hash = hashlib.sha256(encrypted).hexdigest()
    today = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    documento = Documento(id=identifier, nome="istanza_liquidazione_ctu.html", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        percorso=str(destination.relative_to(root)), dimensione_bytes=len(encrypted),
        hash_sha256=encrypted_hash, hash_contenuto_sha256=plaintext_hash, data_documento=today,
        note="Bozza di istanza di liquidazione CTU: rileggere e firmare prima del deposito.",
        tags=["bozza-editor", "ctu", "istanza-liquidazione"], caricato_da=actor,
        fonte_documento="CTU_LIQUIDAZIONE", nome_originale="istanza_liquidazione_ctu.html")
    if any(item.id == identifier for item in fascicolo.documenti):
        raise ValueError("Documento CTU presente senza riscontro del comando: recupero necessario.")
    # Conserva integralmente metadata e collezioni precedenti; aggiorna solo
    # documento, presidio nativo e timestamp con confronto dello snapshot SQL.
    fascicolo.documenti.append(documento)
    GestioneFascicoli._segna_analisi_fascicolo_da_rieseguire(None, fascicolo,
        reason="nuovo_documento_fascicolo", document_id=documento.id)
    fascicolo.modificato_il = datetime.now(ZoneInfo("Europe/Rome")).isoformat()
    payload = fascicolo.to_dict()
    preserved = json.loads(raw["dati_json"])
    preserved.update(pagamenti=payload["pagamenti"], modificato_il=fascicolo.modificato_il)
    updated = conn.execute("UPDATE fascicoli SET documenti_json=?,dati_json=?,modificato_il=? WHERE id=? "
        "AND documenti_json IS NOT DISTINCT FROM ? AND dati_json IS NOT DISTINCT FROM ? "
        "AND modificato_il IS NOT DISTINCT FROM ? RETURNING id", (
        json.dumps(payload["documenti"], ensure_ascii=False),
        json.dumps(GestioneFascicoli._dati_json_snello(preserved), ensure_ascii=False), fascicolo.modificato_il,
        fascicolo.id, raw["documenti_json"], raw["dati_json"], raw["modificato_il"],
    )).fetchone()
    if updated is None:
        raise CtuConflict("Fascicolo aggiornato durante la produzione della bozza CTU: nessuna consegna confermata.")
    return {"kind": "liquidation_document", "document_id": documento.id,
        "url": f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/editor",
        "sha256": plaintext_hash, "encrypted_sha256": encrypted_hash, "path": documento.percorso}
