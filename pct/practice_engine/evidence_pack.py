"""Evidence pack deposito: riepilogo, audit, ricevute, timeline e hash."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import zipfile

from .models import EvidencePack, new_id
from .repository import PracticeEngineRepository


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_evidence_pack(
    repository: PracticeEngineRepository,
    *,
    fascicolo: Any,
    profile: Any,
    deposito_id: str,
) -> EvidencePack:
    session = repository.get_deposit_session(deposito_id)
    if not session:
        raise KeyError(f"Deposito '{deposito_id}' non trovato.")
    receipts = repository.list_receipts(deposito_id)
    timeline = repository.list_timeline(deposito_id)
    audit = repository.list_audit(str(getattr(fascicolo, "id", "")))
    target_dir = repository.evidence_dir / str(getattr(fascicolo, "id", "")) / deposito_id
    target_dir.mkdir(parents=True, exist_ok=True)
    pack_id = new_id("evp")
    target = target_dir / f"{pack_id}.zip"
    hashes: list[str] = []
    summary = {
        "fascicolo_id": getattr(fascicolo, "id", ""),
        "titolo": getattr(fascicolo, "titolo", ""),
        "deposito_id": deposito_id,
        "stato_finale": session.status,
        "profilo_pratica": profile.to_dict() if hasattr(profile, "to_dict") else profile,
        "messaggi": list(session.messages or []),
        "ricevute": [receipt.__dict__ for receipt in receipts],
        "timeline": [event.__dict__ for event in timeline],
    }
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("riepilogo_deposito.json", json.dumps(summary, ensure_ascii=False, indent=2))
        zf.writestr("audit_controlli.json", json.dumps([event.__dict__ for event in audit], ensure_ascii=False, indent=2))
        zf.writestr("profile.json", json.dumps(summary["profilo_pratica"], ensure_ascii=False, indent=2))
        zf.writestr("timeline_eventi.json", json.dumps([event.__dict__ for event in timeline], ensure_ascii=False, indent=2))
        for receipt in receipts:
            path = Path(receipt.original_path)
            if path.exists():
                archive_name = f"ricevute_originali/{receipt.id}_{receipt.original_name}"
                zf.write(path, archive_name)
                hashes.append(f"{receipt.original_hash_sha256}  {archive_name}")
        doc_rows = []
        for doc in getattr(fascicolo, "documenti", []) or []:
            doc_rows.append(
                {
                    "id": getattr(doc, "id", ""),
                    "nome": getattr(doc, "nome", ""),
                    "tipo": str(getattr(doc, "tipo", "")),
                    "hash_sha256": getattr(doc, "hash_sha256", ""),
                    "dimensione_bytes": getattr(doc, "dimensione_bytes", 0),
                }
            )
            if getattr(doc, "hash_sha256", ""):
                hashes.append(f"{getattr(doc, 'hash_sha256')}  documenti/{getattr(doc, 'nome', '')}")
        zf.writestr("documenti_depositati.json", json.dumps(doc_rows, ensure_ascii=False, indent=2))
        zf.writestr("hashes.sha256", "\n".join(hashes) + ("\n" if hashes else ""))
    pack = EvidencePack(pack_id, str(getattr(fascicolo, "id", "")), deposito_id, str(target), _sha256_file(target), available=True)
    repository.save_evidence_pack(pack)
    repository.audit(str(getattr(fascicolo, "id", "")), "EVIDENCE_PACK_CREATED", message="Evidence pack generato.", payload={"deposito_id": deposito_id, "path": str(target)})
    return pack
