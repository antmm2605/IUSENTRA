from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pct.fascicolo_operational_presidio import build_fascicolo_operational_presidio
from web.services.react_fascicoli_bridge import _notification_relata


TO_NOTIFY_STATUSES = {"da_preparare", "da_firmare", "pronta_invio"}
RELATED_ACTION_STATUSES = {"da_acquisire", "ricevute_da_completare"}
ACTIONABLE_STATUSES = TO_NOTIFY_STATUSES | RELATED_ACTION_STATUSES


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _load_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    raw = _text(value)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _document_rows(value: Any) -> list[dict[str, Any]]:
    raw = _load_json(value, [])
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("documenti", "documents", "items", "rows", "data"):
            nested = raw.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raw = _text(value).casefold()
    return raw in {"1", "true", "vero", "si", "sì", "yes"}


def _doc_from_row(row: dict[str, Any], index: int) -> SimpleNamespace:
    name = _text(
        row.get("nome")
        or row.get("name")
        or row.get("filename")
        or row.get("safe_filename")
        or row.get("nome_originale")
        or row.get("original_filename")
        or f"Documento {index + 1}"
    )
    tags = row.get("tags") or row.get("etichette") or []
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        tags = []
    return SimpleNamespace(
        id=_text(row.get("id") or row.get("documento_id") or row.get("uuid") or f"doc-{index + 1}"),
        nome=name,
        nome_originale=_text(row.get("nome_originale") or row.get("original_filename") or row.get("filename") or name),
        nome_portale=_text(row.get("nome_portale") or row.get("portal_name") or row.get("nomePortale") or name),
        tipo=_text(row.get("tipo") or row.get("type") or row.get("tipo_documento") or row.get("tipoDocumento")),
        tipo_atto_portale=_text(row.get("tipo_atto_portale") or row.get("tipoAttoPortale")),
        classificazione_portale=_text(row.get("classificazione_portale") or row.get("classificazionePortale") or row.get("catalogRole")),
        note=_text(row.get("note") or row.get("notes") or row.get("descrizione") or row.get("description")),
        tags=tags,
        percorso=_text(row.get("percorso") or row.get("path") or row.get("storage_path") or row.get("file")),
        hash_sha256=_text(row.get("hash_sha256") or row.get("sha256") or row.get("hashSha256")),
        prova_notifica=_as_bool(row.get("prova_notifica") or row.get("provaNotifica")),
        data_documento=_text(row.get("data_documento") or row.get("dataDocumento") or row.get("date")),
        data_deposito_portale=_text(row.get("data_deposito_portale") or row.get("dataDepositoPortale") or row.get("data_deposito")),
        data_notifica=_text(row.get("data_notifica") or row.get("dataNotifica")),
        data_comunicazione_cancelleria=_text(row.get("data_comunicazione_cancelleria") or row.get("dataComunicazioneCancelleria")),
        signed_status=row.get("signed_status") or row.get("signedStatus"),
        signed_ui=row.get("signed_ui") or row.get("signedUi"),
        firma_status=row.get("firma_status") or row.get("firmaStatus"),
        firma_esito=row.get("firma_esito") or row.get("firmaEsito"),
        metadati_firma=row.get("metadati_firma") or row.get("metadatiFirma"),
        signature_metadata=row.get("signature_metadata") or row.get("signatureMetadata"),
        signature_status=row.get("signature_status") or row.get("signatureStatus"),
    )


def _available_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _select_fascicoli(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    columns = _available_columns(conn, "fascicoli")
    wanted = [
        "id",
        "codice",
        "titolo",
        "nome",
        "oggetto",
        "descrizione",
        "cliente",
        "nome_cliente",
        "parti",
        "controparte",
        "ufficio",
        "numero_rg",
        "anno_rg",
        "stato",
        "documenti_json",
    ]
    selected = [column for column in wanted if column in columns]
    if "id" not in selected:
        raise RuntimeError("La tabella fascicoli non espone la colonna id.")
    if "documenti_json" not in selected:
        raise RuntimeError("La tabella fascicoli non espone documenti_json: audit non eseguibile sulla fonte SQL.")
    order_columns = [column for column in ("titolo", "nome", "oggetto", "id") if column in columns]
    order_by = f"COALESCE({', '.join(order_columns)})" if len(order_columns) > 1 else order_columns[0]
    return list(conn.execute(f"SELECT {', '.join(selected)} FROM fascicoli ORDER BY {order_by}"))


def _row_value(row: sqlite3.Row, key: str) -> Any:
    try:
        return row[key]
    except Exception:
        return ""


def _fascicolo_from_row(row: sqlite3.Row) -> SimpleNamespace:
    docs = [_doc_from_row(item, index) for index, item in enumerate(_document_rows(_row_value(row, "documenti_json")))]
    title = _text(_row_value(row, "titolo") or _row_value(row, "nome") or _row_value(row, "oggetto") or _row_value(row, "id"))
    return SimpleNamespace(
        id=_text(_row_value(row, "id")),
        codice=_text(_row_value(row, "codice")),
        titolo=title,
        nome=title,
        oggetto=_text(_row_value(row, "oggetto") or _row_value(row, "descrizione") or title),
        nome_cliente=_text(_row_value(row, "nome_cliente") or _row_value(row, "cliente")),
        parti=_text(_row_value(row, "parti")),
        controparte=_text(_row_value(row, "controparte")),
        ufficio=_text(_row_value(row, "ufficio")),
        numero_rg=_text(_row_value(row, "numero_rg")),
        anno_rg=_text(_row_value(row, "anno_rg")),
        stato=_text(_row_value(row, "stato")),
        documenti=docs,
    )


def _fascicolo_label(fascicolo: SimpleNamespace) -> str:
    pieces = [
        _text(getattr(fascicolo, "titolo", "")),
        _text(getattr(fascicolo, "nome_cliente", "")),
        _text(getattr(fascicolo, "controparte", "")),
    ]
    return " — ".join(piece for piece in pieces if piece) or _text(getattr(fascicolo, "id", ""), "Fascicolo")


def _next_step(payload: dict[str, Any]) -> str:
    status = _text(payload.get("status"))
    return {
        "da_acquisire": "Acquisire il provvedimento indicato dalla PEC/portale prima di preparare la relata.",
        "da_preparare": "Preparare la relata di notifica con i dati del fascicolo e del documento da notificare.",
        "da_firmare": "Firmare digitalmente la relata già presente, poi procedere alla revisione/invio.",
        "pronta_invio": "Revisionare e inviare la notifica dal PC dell'avvocato tramite canale locale autorizzato.",
        "ricevute_da_completare": "Collegare RAC/RdAC o prova deposito: non è una nuova notifica da inviare.",
    }.get(status, "Nessuna azione di notifica residua.")


def _evaluate_fascicolo(fascicolo: SimpleNamespace) -> dict[str, Any]:
    start = time.perf_counter()
    payload = _notification_relata(fascicolo, [])
    presidio = build_fascicolo_operational_presidio(
        fascicolo=fascicolo,
        document_presidio={},
        notification_relata=payload,
        payment_summary={},
        deposits=[],
        duplicate_group=None,
        sentenze_economiche=None,
    )
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
    relata_sector = next((sector for sector in presidio.get("sectors", []) if sector.get("id") == "relata"), {})
    status = _text(payload.get("status"), "monitoraggio")
    return {
        "id": _text(getattr(fascicolo, "id", "")),
        "codice": _text(getattr(fascicolo, "codice", "")),
        "label": _fascicolo_label(fascicolo),
        "ufficio": _text(getattr(fascicolo, "ufficio", "")),
        "numeroRg": _text(getattr(fascicolo, "numero_rg", "")),
        "annoRg": _text(getattr(fascicolo, "anno_rg", "")),
        "stato": _text(getattr(fascicolo, "stato", "")),
        "status": status,
        "statusLabel": _text(payload.get("statusLabel")),
        "tone": _text(payload.get("tone")),
        "systemNotification": _text(payload.get("systemNotification")),
        "nextStep": _next_step(payload),
        "href": f"/fascicoli/{_text(getattr(fascicolo, 'id', ''))}#relata-notifica",
        "mustNotify": status in TO_NOTIFY_STATUSES,
        "relatedAction": status in RELATED_ACTION_STATUSES,
        "legacyAssumedHandled": bool(payload.get("legacyAssumedHandled")),
        "proofComplete": bool(payload.get("proofComplete")),
        "proofDeposited": bool(payload.get("proofDeposited")),
        "notificationAlreadySent": bool(payload.get("notificationAlreadySent")),
        "legacyNotificationSignals": int(payload.get("legacyNotificationSignals") or 0),
        "strictNotificationSignals": int(payload.get("strictNotificationSignals") or 0),
        "pendingPortalDocuments": int(payload.get("pendingPortalDocuments") or 0),
        "relataDocuments": int(payload.get("relataDocuments") or 0),
        "signedRelataDocuments": int(payload.get("signedRelataDocuments") or 0),
        "proofDocuments": int(payload.get("proofDocuments") or 0),
        "proofDepositDocuments": int(payload.get("proofDepositDocuments") or 0),
        "documentsCount": len(getattr(fascicolo, "documenti", []) or []),
        "steps": payload.get("steps") or [],
        "sectorActions": relata_sector.get("actions") or [],
        "elapsedMs": elapsed_ms,
    }


def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], *, empty: str) -> list[str]:
    if not rows:
        return [empty]
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        cells = []
        for _, key in columns:
            value = _text(row.get(key), "—").replace("|", "\\|").replace("\n", " ")
            cells.append(value)
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Audit presidio notifiche fascicoli",
        "",
        f"- Eseguito il: {payload['generatedAt']}",
        "- Fonte di verità: SQLite tenant `studio.db`.",
        "- Regola applicata: notifiche storiche fino al 19/07/2026 considerate già eseguite dallo studio; tracciamento stretto dal 20/07/2026.",
        f"- Fascicoli DB totali: {summary['totalDb']}",
        f"- Fascicoli analizzati: {summary['scanned']}",
        f"- Fascicoli archiviati saltati: {summary['archivedSkipped']}",
        f"- Tempo medio calcolo presidio: {summary['avgMs']} ms per fascicolo; massimo {summary['maxMs']} ms.",
        "",
        "## Cosa resta ancora da notificare",
        "",
    ]
    lines.extend(
        _markdown_table(
            payload["toNotify"],
            [
                ("Fascicolo", "id"),
                ("Oggetto/parti", "label"),
                ("Stato", "statusLabel"),
                ("Passaggio richiesto", "nextStep"),
                ("Apri", "href"),
            ],
            empty="Nessun fascicolo risulta con una nuova notifica da eseguire dopo il filtro storico.",
        )
    )
    lines.extend(["", "## Azioni correlate non equivalenti a nuova notifica", ""])
    lines.extend(
        _markdown_table(
            payload["relatedActions"],
            [
                ("Fascicolo", "id"),
                ("Oggetto/parti", "label"),
                ("Stato", "statusLabel"),
                ("Passaggio richiesto", "nextStep"),
                ("Apri", "href"),
            ],
            empty="Nessuna azione correlata residua.",
        )
    )
    lines.extend(["", "## Conteggi per stato", ""])
    for key, count in sorted(summary["statusCounts"].items()):
        lines.append(f"- `{key}`: {count}")
    lines.extend(["", "## Campione software 30 fascicoli", ""])
    lines.extend(
        _markdown_table(
            payload["sample30"],
            [
                ("Fascicolo", "id"),
                ("Oggetto/parti", "label"),
                ("Stato", "statusLabel"),
                ("Storico", "legacyLabel"),
                ("Prove", "proofLabel"),
                ("Passaggio", "nextStep"),
            ],
            empty="Campione non disponibile.",
        )
    )
    lines.extend(["", "## Falsi positivi dopo filtro storico", ""])
    lines.extend(
        _markdown_table(
            payload["falsePositives"],
            [
                ("Fascicolo", "id"),
                ("Oggetto/parti", "label"),
                ("Stato", "statusLabel"),
                ("Motivo", "systemNotification"),
            ],
            empty="Zero falsi positivi: nessun fascicolo storico/prova completa resta marcato come notifica da eseguire.",
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    tenant_root = Path(args.tenant_root)
    db_path = Path(args.db_path) if args.db_path else tenant_root / "studio.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Database non trovato: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = _select_fascicoli(conn)
    finally:
        conn.close()
    total_db = len(rows)
    archived = [
        row
        for row in rows
        if _text(_row_value(row, "stato")).casefold() in {"archiviato", "archiviata", "archived"}
    ]
    if args.visible_only:
        rows = [row for row in rows if row not in archived]
    results = [_evaluate_fascicolo(_fascicolo_from_row(row)) for row in rows]
    status_counts = dict(Counter(item["status"] for item in results))
    elapsed_values = [float(item["elapsedMs"]) for item in results]
    to_notify = [item for item in results if item["mustNotify"]]
    related_actions = [item for item in results if item["relatedAction"]]
    false_positives = [
        item
        for item in results
        if item["status"] in ACTIONABLE_STATUSES
        and (item["legacyAssumedHandled"] or item["proofComplete"] or item["proofDeposited"])
    ]
    sample_pool = sorted(
        results,
        key=lambda item: (
            0 if item["status"] in ACTIONABLE_STATUSES else 1,
            0 if item["legacyNotificationSignals"] or item["strictNotificationSignals"] or item["proofDocuments"] else 1,
            item["id"],
        ),
    )
    sample30 = sample_pool[: max(0, int(args.sample or 0))]
    for item in sample30:
        item["legacyLabel"] = "sì" if item["legacyAssumedHandled"] else "no"
        item["proofLabel"] = f"complete={item['proofComplete']}, deposited={item['proofDeposited']}, docs={item['proofDocuments']}"
    payload = {
        "generatedAt": time.strftime("%d/%m/%Y %H:%M:%S"),
        "tenantRoot": str(tenant_root),
        "dbPath": str(db_path),
        "sourceOfTruth": "sqlite",
        "summary": {
            "totalDb": total_db,
            "scanned": len(results),
            "archivedSkipped": len(archived) if args.visible_only else 0,
            "statusCounts": status_counts,
            "toNotifyCount": len(to_notify),
            "relatedActionCount": len(related_actions),
            "falsePositiveCount": len(false_positives),
            "avgMs": round(sum(elapsed_values) / len(elapsed_values), 3) if elapsed_values else 0,
            "maxMs": round(max(elapsed_values), 3) if elapsed_values else 0,
        },
        "toNotify": to_notify,
        "relatedActions": related_actions,
        "falsePositives": false_positives,
        "sample30": sample30,
        "results": results,
    }
    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md_output:
        _write_markdown(Path(args.md_output), payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit presidio notifiche sui fascicoli da studio.db.")
    parser.add_argument("--tenant-root", required=True, help="Root tenant, per esempio /data/tenants/studio-legale-giuseppe-montagnese")
    parser.add_argument("--db-path", default="", help="Percorso esplicito studio.db; se omesso usa tenant-root/studio.db")
    parser.add_argument("--visible-only", action="store_true", help="Salta fascicoli archiviati.")
    parser.add_argument("--sample", type=int, default=30, help="Numero fascicoli nel campione dettagliato.")
    parser.add_argument("--json-output", default="", help="File JSON di output.")
    parser.add_argument("--md-output", default="", help="File Markdown di output.")
    args = parser.parse_args()
    payload = run_audit(args)
    print(
        json.dumps(
            {
                "source_of_truth": payload["sourceOfTruth"],
                "scanned": payload["summary"]["scanned"],
                "to_notify": payload["summary"]["toNotifyCount"],
                "related_actions": payload["summary"]["relatedActionCount"],
                "false_positives": payload["summary"]["falsePositiveCount"],
                "avg_ms": payload["summary"]["avgMs"],
                "max_ms": payload["summary"]["maxMs"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
