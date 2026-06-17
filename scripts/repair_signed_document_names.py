from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


SIGNED_SUFFIXES = (".p7m", ".sig", ".pkcs7")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _name(value: Any) -> str:
    text = _text(value).replace("\\", "/")
    return text.rsplit("/", 1)[-1].strip()


def _is_signed_name(value: Any) -> bool:
    return _name(value).lower().endswith(SIGNED_SUFFIXES)


def _legacy_signed_flag(document: dict[str, Any]) -> bool:
    for key in ("firmato", "firmato_digitalmente", "signed", "is_signed"):
        if document.get(key) is True:
            return True
        value = str(document.get(key) or "").strip().lower()
        if value in {"true", "1", "si", "sì", "signed", "firmato"}:
            return True
    return False


def _candidate_signed_name(document: dict[str, Any]) -> str:
    for key in (
        "nome_originale",
        "nome_portale",
        "nome_firmato",
        "signed_name",
        "percorso_firmato",
        "percorso",
        "nome",
    ):
        candidate = _name(document.get(key))
        if candidate and candidate.lower().endswith(SIGNED_SUFFIXES):
            return candidate
    for version in document.get("versioni") or []:
        if not isinstance(version, dict):
            continue
        for key in ("nome", "nome_originale", "percorso"):
            candidate = _name(version.get(key))
            if candidate and candidate.lower().endswith(SIGNED_SUFFIXES):
                return candidate
    return ""


def _normalised_target_name(current_name: str, signed_name: str) -> str:
    current = _name(current_name)
    signed = _name(signed_name)
    if not current:
        return signed
    if _is_signed_name(current):
        return current
    if signed and signed.lower().startswith(current.lower()):
        return signed
    return f"{current}.p7m"


def _iter_fascicoli(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("fascicoli", "items", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload and all(isinstance(value, dict) for value in payload.values()):
            return [item for item in payload.values() if isinstance(item, dict)]
    return []


def _document_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("documenti", "documents", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _candidate_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for candidate in (
        root / "fascicoli" / "fascicoli.json",
        root / "data" / "fascicoli" / "fascicoli.json",
    ):
        if candidate.exists():
            files.append(candidate)
    for candidate in root.glob("tenants/*/fascicoli/fascicoli.json"):
        if candidate.exists():
            files.append(candidate)
    data_root = root / "data"
    if data_root.exists():
        for candidate in data_root.glob("tenants/*/fascicoli/fascicoli.json"):
            if candidate.exists():
                files.append(candidate)
    return sorted({path.resolve() for path in files})


def _candidate_studio_dbs(root: Path) -> list[Path]:
    files: list[Path] = []
    for candidate in (
        root / "studio.db",
        root / "data" / "studio.db",
    ):
        if candidate.exists():
            files.append(candidate)
    for candidate in root.glob("tenants/*/studio.db"):
        if candidate.exists():
            files.append(candidate)
    data_root = root / "data"
    if data_root.exists():
        for candidate in data_root.glob("tenants/*/studio.db"):
            if candidate.exists():
                files.append(candidate)
    return sorted({path.resolve() for path in files})


def _new_report(path: Path, *, source_kind: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "source_kind": source_kind,
        "database_authoritative": source_kind in {"sqlite_core", "postgresql_core"},
        "json_source_of_truth": False,
        "checked": 0,
        "changed": 0,
        "signed_names_already_visible": 0,
        "signed_flag_plain_pdf": 0,
        "applied": False,
        "changes": [],
        "flag_only_examples": [],
    }


def _inspect_document(
    document: dict[str, Any],
    *,
    fascicolo_id: str,
    report: dict[str, Any],
    apply: bool,
) -> bool:
    report["checked"] += 1
    current_name = _name(document.get("nome"))
    if _is_signed_name(current_name):
        report["signed_names_already_visible"] += 1
        return False

    signed_name = _candidate_signed_name(document)
    if signed_name:
        target_name = _normalised_target_name(current_name, signed_name)
        if target_name and target_name != current_name:
            change = {
                "fascicolo_id": fascicolo_id,
                "documento_id": _text(document.get("id")),
                "nome_attuale": current_name,
                "nome_corretto": target_name,
                "prova_firma": signed_name,
            }
            report["changes"].append(change)
            if apply:
                document["nome"] = target_name
                if not _text(document.get("nome_originale")):
                    document["nome_originale"] = target_name
                return True
        return False

    if _legacy_signed_flag(document):
        report["signed_flag_plain_pdf"] += 1
        if len(report["flag_only_examples"]) < 10:
            report["flag_only_examples"].append(
                {
                    "fascicolo_id": fascicolo_id,
                    "documento_id": _text(document.get("id")),
                    "nome": current_name,
                    "nota": "Flag storico non usato come prova di firma digitale reale.",
                }
            )
    return False


def repair_file(path: Path, *, apply: bool) -> dict[str, Any]:
    report = _new_report(path, source_kind="json_mirror")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.update({"error": "file_non_trovato"})
        return report
    except json.JSONDecodeError as exc:
        report.update({"error": f"json_non_valido: {exc}"})
        return report

    changed = False
    for fascicolo in _iter_fascicoli(payload):
        fascicolo_id = _text(fascicolo.get("id"))
        for document in fascicolo.get("documenti") or []:
            if not isinstance(document, dict):
                continue
            changed = _inspect_document(
                document,
                fascicolo_id=fascicolo_id,
                report=report,
                apply=apply,
            ) or changed

    if apply and changed:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["changed"] = len(report["changes"])
    report["applied"] = bool(apply)
    return report


def repair_sqlite_db(path: Path, *, apply: bool) -> dict[str, Any]:
    report = _new_report(path, source_kind="sqlite_core")
    if not path.exists():
        report.update({"error": "studio_db_non_trovato"})
        return report

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
    except sqlite3.DatabaseError as exc:
        report.update({"error": f"sqlite_non_apribile: {exc}"})
        return report

    rows_to_update: list[tuple[str, str]] = []
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fascicoli'"
        ).fetchone()
        if not row:
            report.update({"error": "tabella_fascicoli_assente"})
            return report

        columns = {str(item[1]) for item in conn.execute("PRAGMA table_info(fascicoli)").fetchall()}
        if "documenti_json" not in columns:
            report.update({"error": "colonna_documenti_json_assente"})
            return report

        for row in conn.execute("SELECT id, documenti_json FROM fascicoli").fetchall():
            fascicolo_id = _text(row["id"])
            raw_json = _text(row["documenti_json"])
            if not raw_json:
                continue
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError:
                report.setdefault("json_errors", []).append(fascicolo_id)
                continue
            documents = _document_list(payload)
            changed = False
            for document in documents:
                changed = _inspect_document(
                    document,
                    fascicolo_id=fascicolo_id,
                    report=report,
                    apply=apply,
                ) or changed
            if changed:
                rows_to_update.append((json.dumps(payload, ensure_ascii=False), fascicolo_id))

        if apply and rows_to_update:
            conn.executemany(
                "UPDATE fascicoli SET documenti_json = ? WHERE id = ?",
                rows_to_update,
            )
            conn.commit()
    except sqlite3.DatabaseError as exc:
        report.update({"error": f"sqlite_errore: {exc}"})
    finally:
        conn.close()

    report["changed"] = len(report["changes"])
    report["applied"] = bool(apply)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Controlla i nomi visibili dei documenti firmati CAdES. "
            "Quando trova studio.db usa SQL come fonte autorevole e considera i JSON solo mirror."
        )
    )
    parser.add_argument("--root", default=".", help="Radice dati o repository da scandire.")
    parser.add_argument("--file", action="append", default=[], help="fascicoli.json specifico da controllare come mirror.")
    parser.add_argument("--studio-db", action="append", default=[], help="studio.db specifico da controllare come fonte SQL.")
    parser.add_argument("--include-json-mirrors", action="store_true", help="Controlla anche i fascicoli.json trovati, solo come mirror non autorevole.")
    parser.add_argument("--apply", action="store_true", help="Applica la riparazione; senza flag esegue solo dry-run.")
    parser.add_argument("--json", action="store_true", help="Stampa report JSON.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    dbs = [Path(value) for value in args.studio_db] if args.studio_db else _candidate_studio_dbs(root)
    json_files = [Path(value) for value in args.file] if args.file else _candidate_files(root)

    results: list[dict[str, Any]] = []
    for db_path in dbs:
        results.append(repair_sqlite_db(db_path, apply=args.apply))

    json_mirrors_skipped = 0
    if args.include_json_mirrors or not dbs or args.file:
        for json_path in json_files:
            results.append(repair_file(json_path, apply=args.apply))
    else:
        json_mirrors_skipped = len(json_files)

    total_changed = sum(int(result.get("changed") or 0) for result in results)
    report = {
        "ok": not any(result.get("error") for result in results),
        "apply": bool(args.apply),
        "authoritative_source": "sqlite_core" if dbs else "json_mirror",
        "json_source_of_truth": False if dbs else True,
        "sqlite_databases": len(dbs),
        "json_mirrors_checked": sum(1 for result in results if result.get("source_kind") == "json_mirror"),
        "json_mirrors_skipped": json_mirrors_skipped,
        "checked": sum(int(result.get("checked") or 0) for result in results),
        "changed": total_changed,
        "signed_flag_plain_pdf": sum(int(result.get("signed_flag_plain_pdf") or 0) for result in results),
        "results": results,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        action = "applicate" if args.apply else "da applicare"
        print(f"Fonte autorevole: {report['authoritative_source']}.")
        print(f"Documenti controllati: {report['checked']}; correzioni {action}: {total_changed}.")
        if json_mirrors_skipped:
            print(f"JSON mirror saltati perché esiste SQL autorevole: {json_mirrors_skipped}.")
        if report["signed_flag_plain_pdf"]:
            print(
                "Flag storici 'firmato' su PDF senza .p7m/metadati reali: "
                f"{report['signed_flag_plain_pdf']}."
            )
        for result in results:
            if result.get("changed"):
                print(f"- {result['path']}: {result['changed']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
