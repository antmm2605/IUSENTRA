"""Ripristina gli stati positivi di un ciclo deposito gia' documentato.

Lo script non prepara buste e non invia PEC. Aggiorna soltanto la preparazione
salvata quando nel database esistono gia' la prova e il deposito reale attesi.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from pct.fascicoli import GestioneFascicoli
from pct.storage import StudioDB
from web.services.deposito_pec_runtime import (
    deposito_workflow_state,
    mark_deposito_workflow_stage,
    preserve_deposito_workflow,
)


def _standard_frontend_pec_body(document_names: list[str]) -> str:
    names = [str(name or "").strip() for name in document_names if str(name or "").strip()]
    files = ""
    if names:
        files = "\n\nIl pacchetto contiene i seguenti documenti:\n" + "\n".join(
            f"- {name}" for name in names
        )
    return (
        "Egregio sig. Cancelliere,\n\n"
        f"Allego alla presente il pacchetto di deposito telematico.{files}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-root", required=True)
    parser.add_argument("--fascicolo", required=True)
    parser.add_argument("--proof-id", required=True)
    parser.add_argument("--send-id", required=True)
    parser.add_argument("--proof-completed-at", required=True)
    parser.add_argument("--simulation-completed-at", required=True)
    parser.add_argument("--send-completed-at", required=True)
    parser.add_argument("--backup-path", default="")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(args.tenant_root).resolve()
    db_path = root / "studio.db"
    if not db_path.is_file():
        raise SystemExit(f"studio.db non trovato in {root}")

    studio_db = StudioDB.get(str(db_path))
    manager = GestioneFascicoli(
        str(root / "fascicoli" / "fascicoli.json"),
        documents_dir=str(root / "fascicoli" / "documenti"),
        archive_dir=str(root / "fascicoli" / "archivio"),
        studio_db=studio_db,
        carica_tutto=False,
    )
    fascicolo = manager.get(args.fascicolo)
    if fascicolo is None:
        raise SystemExit(f"Fascicolo {args.fascicolo} non trovato")

    profile = dict(fascicolo.profilo_deposito or {})
    preparation = dict(profile.get("preparazione_busta") or {})
    documents = preparation.get("documents") if isinstance(preparation.get("documents"), list) else []
    selected_rows = [
        row
        for row in documents
        if isinstance(row, dict) and row.get("selected") and row.get("role") != "fuori_busta"
    ]
    selected_ids = [str(row.get("documentId") or row.get("document_id") or "").strip() for row in selected_rows]
    selected_ids = [item for item in selected_ids if item]
    if not selected_ids:
        raise SystemExit("Preparazione priva di documenti selezionati")

    deposits = {str(item.id): item for item in fascicolo.depositi_pct or []}
    proof = deposits.get(args.proof_id)
    send = deposits.get(args.send_id)
    if proof is None or str(proof.stato) != "PROVA_SENZA_INVIO":
        raise SystemExit("La prova positiva attesa non risulta registrata")
    accepted_send_states = {
        "INVIATO",
        "ACCETTATO",
        "CONSEGNATO",
        "ACCETTATO_CANCELLERIA",
        "ESITO_POSITIVO",
    }
    if send is None or str(send.stato) not in accepted_send_states:
        raise SystemExit("Il deposito reale atteso non risulta inviato o consegnato")
    expected_documents = set(selected_ids)
    if set(proof.documenti_ids or []) != expected_documents:
        raise SystemExit("I documenti della prova non coincidono con la preparazione corrente")
    if set(send.documenti_ids or []) != expected_documents:
        raise SystemExit("I documenti del deposito reale non coincidono con la preparazione corrente")

    main_rows = [row for row in selected_rows if str(row.get("role") or "") == "atto_principale"]
    if len(main_rows) != 1:
        raise SystemExit("La preparazione non contiene un solo atto principale")

    document_by_id = {str(item.id): item for item in fascicolo.documenti or []}
    missing_ids = [item for item in selected_ids if item not in document_by_id]
    if missing_ids:
        raise SystemExit(f"Documenti non trovati nel fascicolo: {', '.join(missing_ids)}")
    payment_receipts = [
        row
        for row in selected_rows
        if str(row.get("studioDocumentType") or row.get("studio_document_type") or "")
        == "RicevutaPagamento"
    ]
    if not payment_receipts:
        raise SystemExit("Nessuna RT selezionata e indicizzata come RicevutaPagamento")

    next_preparation = dict(preparation)
    next_preparation["documents"] = [
        {**row, "additionalSignature": bool(row.get("additionalSignature") or row.get("additional_signature"))}
        if isinstance(row, dict)
        else row
        for row in documents
    ]
    next_preparation["corpo_pec"] = _standard_frontend_pec_body(
        [document_by_id[item].nome for item in selected_ids]
    )
    next_preparation = preserve_deposito_workflow(next_preparation, None, reset=True)
    next_profile = {**profile, "preparazione_busta": next_preparation}
    next_profile = mark_deposito_workflow_stage(
        next_profile,
        "proof",
        id_deposito=args.proof_id,
        completed_at=args.proof_completed_at,
    )
    next_profile = mark_deposito_workflow_stage(
        next_profile,
        "simulation",
        id_deposito=args.proof_id,
        completed_at=args.simulation_completed_at,
    )
    next_profile = mark_deposito_workflow_stage(
        next_profile,
        "send",
        id_deposito=args.send_id,
        completed_at=args.send_completed_at,
    )
    state = deposito_workflow_state(next_profile["preparazione_busta"])

    backup_path = ""
    if args.apply:
        if not str(args.backup_path or "").strip():
            raise SystemExit("--backup-path è obbligatorio con --apply")
        backup = Path(args.backup_path).resolve()
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.is_file() and backup.stat().st_size > 0:
            backup_connection = sqlite3.connect(
                f"file:{backup.as_posix()}?mode=ro",
                uri=True,
                timeout=10,
            )
            try:
                backup_row = backup_connection.execute(
                    "SELECT id FROM fascicoli WHERE id = ?",
                    (args.fascicolo,),
                ).fetchone()
                if not backup_row:
                    raise RuntimeError("Lo snapshot esistente non contiene il fascicolo atteso")
            finally:
                backup_connection.close()
        else:
            source_connection = sqlite3.connect(str(db_path))
            backup_connection = sqlite3.connect(str(backup))
            try:
                source_connection.backup(backup_connection)
                backup_connection.commit()
                backup_row = backup_connection.execute(
                    "SELECT id FROM fascicoli WHERE id = ?",
                    (args.fascicolo,),
                ).fetchone()
                if not backup_row:
                    raise RuntimeError("Lo snapshot SQLite non contiene il fascicolo atteso")
            finally:
                backup_connection.close()
                source_connection.close()
        backup_path = str(backup)
        # La fonte operativa e' SQLite. Per questa riparazione puntuale non
        # rigeneriamo l'intero mirror JSON del tenant: sarebbe una scansione
        # non necessaria e il runtime legge gia' la colonna SQL dedicata.
        connection = sqlite3.connect(str(db_path), timeout=15)
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT dati_json FROM fascicoli WHERE id = ?",
                (args.fascicolo,),
            ).fetchone()
            if current is None:
                raise RuntimeError("Il fascicolo non è più presente nella fonte SQL")
            data_payload = json.loads(current[0] or "{}")
            if not isinstance(data_payload, dict):
                data_payload = {}
            data_payload["profilo_deposito"] = next_profile
            modified_at = datetime.now().isoformat()
            cursor = connection.execute(
                """
                UPDATE fascicoli
                SET profilo_deposito_json = ?, dati_json = ?, modificato_il = ?
                WHERE id = ?
                """,
                (
                    json.dumps(next_profile, ensure_ascii=False),
                    json.dumps(data_payload, ensure_ascii=False),
                    modified_at,
                    args.fascicolo,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Aggiornamento SQL del fascicolo non eseguito")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    print(
        json.dumps(
            {
                "ok": True,
                "applied": bool(args.apply),
                "source_of_truth": "sqlite",
                "fascicolo": args.fascicolo,
                "fingerprint": state["fingerprint"],
                "proof": state["proof"]["ok"],
                "simulation": state["simulation"]["ok"],
                "send": state["send"]["ok"],
                "send_id": state["send"]["id_deposito"],
                "payment_receipts": len(payment_receipts),
                "backup_path": backup_path,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
