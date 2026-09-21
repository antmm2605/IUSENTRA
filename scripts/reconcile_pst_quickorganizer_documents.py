"""Riconcilia copie QuickOrganizer/PST dopo verifica del contenuto.
Default sola lettura; --apply conserva backup, versioni e cestino.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from pct.document_crypto import decrypt_doc, encrypt_doc
from pct.fascicoli import GestioneFascicoli
from pct.storage import StudioDB
from web.services.portal_document_identity import trova_documento_importato_identico, collega_identita_pst

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-root", required=True)
    parser.add_argument("--fascicolo", required=True)
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(args.tenant_root).resolve()
    if not (root / "studio.db").is_file():
        raise SystemExit("Database SQL dello studio non disponibile")
    gf = GestioneFascicoli(str(root / "fascicoli/fascicoli.json"),
                          studio_db=StudioDB(str(root / "studio.db")), carica_tutto=False)
    fasc = gf.get(args.fascicolo)
    if not fasc:
        raise SystemExit("Fascicolo non trovato")
    plan = []
    for doc in fasc.documenti:
        if doc.fonte_documento != "PORTALE_TELEMATICO" or doc.versioni:
            continue
        item = {"nome": doc.nome, "id_cat": doc.id_cat_portale, "id_documento": doc.id_documento_portale}
        payload = decrypt_doc(gf.percorso_documento(fasc.id, doc.id).read_bytes())
        existing = trova_documento_importato_identico(gf, fasc, payload, item, decrypt_doc)
        if existing:
            plan.append((existing, doc, item, payload))
    report = {"source_of_truth": "sqlite", "fascicolo": fasc.id, "prima": len(fasc.documenti),
              "applicato": args.apply, "coppie": [{"conservato": a.id, "cestino": b.id} for a,b,_,_ in plan]}
    if args.apply and plan:
        backup = Path(args.backup_dir).resolve()
        backup.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        before = backup / (fasc.id + "_" + stamp + ".json")
        # Serializzazione nativa: originale e riferimenti ripristinabili.
        from dataclasses import asdict
        before.write_text(json.dumps(asdict(fasc), default=str, ensure_ascii=False, indent=2), encoding="utf-8")
        for existing, duplicate, item, payload in plan:
            old = decrypt_doc(gf.percorso_documento(fasc.id, existing.id).read_bytes())
            if old != payload:
                gf.sostituisci_documento(fasc.id, existing.id, nome_file=existing.nome,
                    contenuto=encrypt_doc(payload), caricato_da="Riconciliazione duplicati autorizzata",
                    preserve_version_snapshot=True, hash_contenuto_sha256=hashlib.sha256(payload).hexdigest())
            collega_identita_pst(gf, fasc, existing, item)
            for dep in fasc.depositi_pct:
                dep.documenti_ids = list(dict.fromkeys(existing.id if did == duplicate.id else did for did in dep.documenti_ids))
            gf.rimuovi_documento(fasc.id, duplicate.id, eliminato_da="Riconciliazione con " + existing.id)
        gf.registra_onboarding(fasc.id, "Riconciliazione documenti identici QuickOrganizer/PST",
            note=json.dumps(report["coppie"], ensure_ascii=False) + ". File conservati nello storico e nel cestino.",
            avvocato="Intervento autorizzato dallo studio")
        report["dopo"] = len(fasc.documenti)
        report["backup"] = str(before)
        (backup / (fasc.id + "_" + stamp + "_esito.json")).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
if __name__ == "__main__":
    main()
